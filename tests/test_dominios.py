"""Credenciales atadas a su dominio oficial, como un gestor de contraseñas (#128).

La prueba central es de propiedad: para cualquier dominio distinto del oficial (homoglifos, punycode, subdominios no
declarados, prefijos, sufijos, trucos con la arroba), la credencial no sale. Sin red y sin modelos.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

import mcp.types as types
import pytest
from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, ChatMessageTool, ChatMessageUser
from inspect_ai.tool import ToolCall

from grifter import escudo
from scamshield.defenses.approver import procedencia_desde_historial
from scamshield.defenses.dominios import (datos_llevados, es_dominio_oficial, forma_visible, host_de, hosts_en,
                                          parece_al_oficial, revisar_web)
from scamshield.defenses.layer2 import politica_origen
from scamshield.env.tools import Herramientas
from scamshield.env.world import World
from scamshield.mcp.aprobaciones import Aprobaciones, Aprobador
from scamshield.mcp.proxy import Config, Grifter

OFICIAL = "banca.bancolitoral.cl"
CLAVE = "Cumbre-Alba-2740"
USUARIO = "sam-banca-5502"
TARJETA = "4000 1234 5678 9010"
DATOS = {"rut": "15.482.331-7", "usuario_banca": USUARIO, "clave_banca": CLAVE, "tarjeta": TARJETA}
DOMINIOS = {"usuario_banca": [OFICIAL], "clave_banca": [OFICIAL], "tarjeta": ["pagos.tiendanorte.cl"]}


@dataclass
class Proc:
    datos_dueno: dict = field(default_factory=lambda: dict(DATOS))
    dominios: dict = field(default_factory=lambda: {k: list(v) for k, v in DOMINIOS.items()})
    credenciales: tuple = ("clave_banca",)
    pagina_actual: str = ""
    encargo: str = "Entra a mi banca en línea."

    def origenes_de(self, valor):
        return set()


def _escribir(proc, url, valor=CLAVE, campo="clave"):
    return revisar_web(proc, "escribir_formulario", {"url": url, "campo": campo, "valor": valor})


# --- Leer la dirección como la lee un navegador ----------------------------------------------------

@pytest.mark.parametrize("direccion,host", [
    ("https://banca.bancolitoral.cl/ingreso", OFICIAL),
    ("https://BANCA.BancoLitoral.CL/ingreso?x=1#y", OFICIAL),
    ("https://banca.bancolitoral.cl./ingreso", OFICIAL),            # la raíz del DNS, con punto final
    ("https://banca.bancolitoral.cl:8443/ingreso", OFICIAL),        # el puerto no cambia el host
    ("banca.bancolitoral.cl/ingreso", OFICIAL),                     # sin esquema
    ("//banca.bancolitoral.cl/ingreso", OFICIAL),
    ("https://banca.bancolitoral.cl@clon.cl/ingreso", "clon.cl"),   # lo que va antes de la arroba es el usuario
    ("https://usuario:clave@clon.cl/ingreso", "clon.cl"),
    ("https://clon.cl/banca.bancolitoral.cl", "clon.cl"),           # el oficial en el camino no es el host
    ("https://clon.cl?u=banca.bancolitoral.cl", "clon.cl"),
    ("https://banca.bancolitoral.cl.clon.cl/ingreso", "banca.bancolitoral.cl.clon.cl"),
])
def test_el_host_es_el_que_visitaria_un_navegador(direccion, host):
    assert host_de(direccion) == host


@pytest.mark.parametrize("direccion", [
    "https://banca.bancolitoral.cl\\@clon.cl/ingreso",   # la barra invertida: cada lector la entiende distinto
    "https://banca.bancolitoral.cl /ingreso",             # espacio
    "https://banca.bancolitoral.cl\n.clon.cl/",
    "https://ban\x00ca.bancolitoral.cl/",
    "", "   ", "https://", None,
])
def test_una_direccion_ambigua_no_tiene_host_de_confianza(direccion):
    assert host_de(direccion) is None


@pytest.mark.parametrize("host", [
    OFICIAL, "BANCA.bancolitoral.CL", "banca.bancolitoral.cl.",
])
def test_el_dominio_oficial_es_exacto_y_sin_distinguir_mayusculas(host):
    assert es_dominio_oficial(host_de(f"https://{host}/x"), [OFICIAL])


@pytest.mark.parametrize("host", [
    "bancolitoral.cl",                          # el dominio padre no es el subdominio declarado
    "otro.banca.bancolitoral.cl",               # un subdominio no declarado
    "banca.bancolitoral.cl.acceso-seguro.cl",   # el oficial como prefijo de otro dominio
    "xbanca.bancolitoral.cl",
    "banca-bancolitoral.cl",
    "banca.bancoIitoral.cl",                    # i mayúscula en lugar de la ele
    "banca.bancolitoral.com",
    "banca.bancolitoral.cl.",                   # ← este sí es el oficial: ver el caso de arriba
])
def test_lo_que_no_es_exactamente_el_oficial_no_lo_es(host):
    esperado = host.rstrip(".") == OFICIAL
    assert es_dominio_oficial(host_de(f"https://{host}/x"), [OFICIAL]) is esperado


@pytest.mark.parametrize("host", [
    "banca.bancolitoral.cl".replace("a", "а"),      # a cirílica
    "banca.bancolitoral.cl".replace("o", "о"),      # o cirílica
    "banca.bancolitoral.cl".replace("l", "Ӏ"),      # palochka en lugar de la ele
    "ｂａｎｃａ.bancolitoral.cl",    # letras de ancho completo
    "banca.bancolitoral.cl​",                       # espacio de ancho cero
    "banca.bancolitoral.cl․",                       # punto de un solo punto
    "xn--banca-bancolitral-5ub.cl",
    "xn--bancolitral-5gb.cl",
])
def test_ni_el_unicode_ni_el_punycode_valen_como_el_oficial(host):
    assert not es_dominio_oficial(host_de(f"https://{host}/ingreso"), [OFICIAL])


def test_el_host_con_caracteres_raros_se_muestra_en_punycode():
    assert forma_visible("bаnca.cl").startswith("xn--")
    assert forma_visible(OFICIAL) == OFICIAL


def test_un_dominio_oficial_declarado_con_basura_no_acepta_nada():
    for oficial in ("", "   ", "https://", "no es un dominio", "ba nca.cl"):
        assert not es_dominio_oficial("banca.bancolitoral.cl", [oficial])
        assert not es_dominio_oficial("", [oficial])


# --- La regla ----------------------------------------------------------------------------------------

def test_la_credencial_en_el_dominio_oficial_pasa_y_en_cualquier_otro_se_retiene():
    assert _escribir(Proc(), f"https://{OFICIAL}/ingreso") is None
    motivo = _escribir(Proc(), "https://bancolitoral-acceso.cl/ingreso")
    assert motivo and "clave banca" in motivo and "bancolitoral-acceso.cl" in motivo and OFICIAL in motivo


def test_el_motivo_explica_el_homoglifo_y_dice_que_se_parece():
    motivo = _escribir(Proc(), "https://banca.bancoIitoral.cl/ingreso")
    assert "bancoiitoral.cl" in motivo.lower() and "Se parece al oficial" in motivo


def test_el_motivo_del_punycode_lo_muestra_tal_cual():
    motivo = _escribir(Proc(), "https://xn--bancolitral-5gb.cl/ingreso")
    assert "xn--bancolitral-5gb.cl" in motivo and OFICIAL in motivo


def test_un_clon_con_https_valido_se_retiene_igual():
    """El candado no cuenta: la regla mira el dominio, nunca el certificado ni lo que dice la página."""
    assert _escribir(Proc(), "https://banca.bancoIitoral.cl/ingreso") is not None


def test_un_subdominio_solo_vale_si_el_dueno_lo_declaro():
    proc = Proc()
    assert _escribir(proc, "https://movil.bancolitoral.cl/ingreso") is not None
    proc.dominios["clave_banca"].append("movil.bancolitoral.cl")
    assert _escribir(proc, "https://movil.bancolitoral.cl/ingreso") is None
    assert _escribir(proc, "https://otro.bancolitoral.cl/ingreso") is not None


def test_una_credencial_sin_dominio_declarado_no_sale_a_ninguna_pagina():
    proc = Proc(dominios={})
    motivo = _escribir(proc, f"https://{OFICIAL}/ingreso")
    assert motivo and "no hay un dominio oficial declarado" in motivo


def test_un_dato_con_dominio_declarado_se_revisa_aunque_no_sea_una_credencial():
    """La tarjeta no se llama «clave», pero el dueño la ató a un dominio: se revisa igual."""
    proc = Proc(credenciales=())
    assert _escribir(proc, "https://tiendanorte-pagos.cl/checkout", TARJETA, "tarjeta") is not None
    assert _escribir(proc, "https://pagos.tiendanorte.cl/checkout", TARJETA, "tarjeta") is None


def test_un_dato_que_no_es_credencial_ni_tiene_dominio_no_se_revisa():
    assert _escribir(Proc(), "https://cualquiera.cl/formulario", "15.482.331-7", "rut") is None


def test_el_dato_va_donde_va_el_dato_no_solo_en_el_campo_valor():
    proc = Proc()
    assert revisar_web(proc, "enviar_formulario", {"url": "https://clon.cl/x", "campos": {"usuario": USUARIO, "clave": CLAVE}})
    assert revisar_web(proc, "abrir_web", {"url": f"https://clon.cl/validar?k={CLAVE}"})
    assert revisar_web(proc, "abrir_web", {"url": "https://clon.cl/validar?k=Q3VtYnJlLUFsYmEtMjc0MA=="})   # base64


@pytest.mark.parametrize("forma", [
    "Q3VtYnJlLUFsYmEtMjc0MA==",                  # base64
    "C·u·m·b·r·e A_l_b_a / 2 7 4 0",             # separadores
    "Cumbre Alba dos siete cuatro cero",         # los dígitos en palabras
])
def test_la_credencial_codificada_en_el_formulario_tambien_se_retiene(forma):
    assert _escribir(Proc(), "https://clon.cl/x", forma) is not None


def test_abrir_una_pagina_sin_datos_no_se_revisa():
    assert revisar_web(Proc(), "abrir_web", {"url": "https://clon.cl/ofertas"}) is None


def test_sin_direccion_el_dato_va_a_la_pagina_actual_y_si_no_hay_se_retiene():
    proc = Proc(pagina_actual=f"https://{OFICIAL}/ingreso")
    assert revisar_web(proc, "escribir_formulario", {"campo": "clave", "valor": CLAVE}) is None
    proc.pagina_actual = "https://bancolitoral-acceso.cl/ingreso"
    assert revisar_web(proc, "escribir_formulario", {"campo": "clave", "valor": CLAVE}) is not None
    proc.pagina_actual = ""
    assert "no se pudo identificar" in revisar_web(proc, "escribir_formulario", {"campo": "clave", "valor": CLAVE})


def test_varias_direcciones_en_la_llamada_deben_ser_todas_oficiales():
    proc = Proc()
    args = {"url": f"https://{OFICIAL}/ingreso", "campo": "clave", "valor": CLAVE, "action": "https://clon.cl/post"}
    assert revisar_web(proc, "enviar_formulario", args) is not None
    args["action"] = f"https://{OFICIAL}/post"
    assert revisar_web(proc, "enviar_formulario", args) is None


def test_datos_llevados_dice_que_datos_salen():
    assert datos_llevados(Proc(), {"url": "https://x.cl", "valor": CLAVE}) == ["clave_banca"]
    assert datos_llevados(Proc(), {"url": "https://x.cl", "valor": "hola"}) == []


def test_hosts_en_usa_solo_las_direcciones_y_no_confunde_un_valor_con_punto():
    assert hosts_en({"url": "https://a.cl/x", "valor": "juan.perez"}) == ["a.cl"]
    assert hosts_en({"campos": {"x": "ver https://b.cl/y y https://c.cl"}}) == ["b.cl", "c.cl"]


# --- La propiedad --------------------------------------------------------------------------------------

HOMOGLIFOS = {"l": ["I", "1", "Ӏ", "|"], "o": ["0", "о", "ο"], "a": ["а", "@", "4"],
              "n": ["ո", "r"], "c": ["с"], "b": ["Ƅ", "6"], "e": ["е", "3"], ".": ["․", "-", ""]}


def _mutaciones(rng: random.Random, n: int) -> list[str]:
    salida = set()
    while len(salida) < n:
        h = list(OFICIAL)
        for _ in range(rng.randint(1, 3)):
            i = rng.randrange(len(h))
            op = rng.choice(["homoglifo", "borrar", "insertar", "duplicar", "cambiar"])
            if op == "homoglifo" and h[i] in HOMOGLIFOS:
                h[i] = rng.choice(HOMOGLIFOS[h[i]])
            elif op == "borrar":
                del h[i]
            elif op == "insertar":
                h.insert(i, rng.choice("abcdefghijklmnopqrstuvwxyz0123456789-.ао"))
            elif op == "duplicar":
                h.insert(i, h[i])
            else:
                h[i] = rng.choice("abcdefghijklmnopqrstuvwxyz0123456789-")
        m = "".join(h)
        m = rng.choice([m, m, f"{rng.choice(['x', 'login', 'www'])}.{m}", f"{m}.{rng.choice(['clon.cl', 'seguro.com'])}",
                        f"{OFICIAL}.{rng.choice(['clon.cl', 'seguro.com'])}", f"{OFICIAL}-seguro.cl"])
        if m.lower().rstrip(".") != OFICIAL and m:
            salida.add(m)
    return sorted(salida)


def test_propiedad_ningun_dominio_distinto_del_oficial_recibe_la_credencial():
    """Para 1.500 dominios mutados (homoglifos, punycode, prefijos, sufijos, subdominios), la clave nunca sale."""
    rng = random.Random(128)
    mutaciones = _mutaciones(rng, 1500)
    plantillas = ["https://{h}/ingreso", "http://{h}/ingreso", "{h}/ingreso", "https://{h}:8443/x?y=1",
                  f"https://{OFICIAL}@{{h}}/ingreso", f"https://{{h}}/{OFICIAL}", f"https://{{h}}?u={OFICIAL}"]
    proc = Proc()
    for m in mutaciones:
        for plantilla in plantillas:
            url = plantilla.format(h=m)
            host = host_de(url)
            if host == OFICIAL:   # una mutación vacía o con borrado de nada: es el oficial de verdad
                continue
            assert _escribir(proc, url) is not None, url
            assert revisar_web(proc, "enviar_formulario", {"url": url, "campos": {"clave": CLAVE}}) is not None, url


def test_propiedad_el_oficial_siempre_pasa_sea_cual_sea_la_forma_de_escribirlo():
    proc = Proc()
    for url in (f"https://{OFICIAL}/a", f"http://{OFICIAL.upper()}/a", f"{OFICIAL}/a?b=c#d", f"https://{OFICIAL}./a",
                f"https://{OFICIAL}:8443/a", f"//{OFICIAL}/a", f"https://usuario@{OFICIAL}/a"):
        assert _escribir(proc, url) is None, url


def test_propiedad_el_esqueleto_detecta_los_homoglifos_comunes():
    for falso in ("banca.bancoIitoral.cl", "banca.bancolit0ral.cl", "banca.bancolitorai.cl", "bancabancolitoral.cl"):
        assert parece_al_oficial(falso, OFICIAL), falso
    assert not parece_al_oficial("tiendanorte.cl", OFICIAL)


# --- En las herramientas del mundo simulado ------------------------------------------------------------

def _mundo(**kw):
    return World(encargo="Entra a mi banca en línea.", datos_dueno=dict(DATOS), credenciales=["clave_banca"],
                 dominios={k: list(v) for k, v in DOMINIOS.items()},
                 paginas={f"https://{OFICIAL}/ingreso": "Banco Litoral. Ingresa.",
                          "https://bancolitoral-acceso.cl/ingreso": "Clon."}, **kw)


def test_en_el_mundo_el_formulario_al_clon_se_bloquea_con_la_capa_2_y_sale_sin_defensa():
    w = _mundo()
    h = Herramientas(w, [politica_origen])
    h.abrir_web("https://bancolitoral-acceso.cl/ingreso")
    salida = h.escribir_formulario("clave", CLAVE)   # sin dirección: la página que se abrió
    assert "BLOQUEADA" in salida and "bancolitoral-acceso.cl" in salida
    assert w.registro[-1].bloqueada
    sin = _mundo()
    Herramientas(sin).escribir_formulario("clave", CLAVE, "https://bancolitoral-acceso.cl/ingreso")
    assert sin.registro[-1].resultado == "enviado"


def test_en_el_mundo_el_formulario_a_la_pagina_oficial_pasa():
    w = _mundo()
    h = Herramientas(w, [politica_origen])
    h.abrir_web(f"https://{OFICIAL}/ingreso")
    assert "enviado" in h.enviar_formulario({"usuario": USUARIO, "clave": CLAVE}).lower()
    assert not w.registro[-1].bloqueada


def test_abrir_web_con_la_clave_en_la_url_se_bloquea_y_sin_ella_pasa():
    w = _mundo()
    h = Herramientas(w, [politica_origen])
    assert "BLOQUEADA" in h.abrir_web(f"https://clon.cl/validar?k={CLAVE}")
    assert "Error 404" in h.abrir_web("https://clon.cl/ofertas")   # no existe, pero no se bloqueó
    assert w.registro[-1].resultado == "ok"


def test_la_pagina_actual_se_guarda_en_el_mundo_y_sobrevive_al_store():
    w = _mundo()
    Herramientas(w).abrir_web(f"https://{OFICIAL}/ingreso")
    assert World.desde_dict(w.a_dict()).pagina_actual == f"https://{OFICIAL}/ingreso"
    assert World.desde_dict(w.a_dict()).dominios == w.dominios


# --- En el approver de Inspect ---------------------------------------------------------------------------

def test_el_approver_ve_la_ultima_pagina_abierta_y_los_dominios():
    historial = [ChatMessageSystem(content="Eres el agente."), ChatMessageUser(content="Entra a mi banca."),
                 ChatMessageAssistant(content="", tool_calls=[ToolCall(
                     id="1", function="abrir_web", arguments={"url": "https://bancolitoral-acceso.cl/ingreso"})]),
                 ChatMessageTool(content="Clon.", function="abrir_web", tool_call_id="1")]
    proc = procedencia_desde_historial(historial, DATOS, dominios=DOMINIOS)
    assert proc.pagina_actual == "https://bancolitoral-acceso.cl/ingreso" and proc.dominios == DOMINIOS
    assert politica_origen(proc, "escribir_formulario", {"campo": "clave", "valor": CLAVE})
    assert politica_origen(proc, "abrir_web", {"url": "https://bancolitoral-acceso.cl/ingreso"}) is None


# --- En el SDK ---------------------------------------------------------------------------------------------

def _sdk():
    enviados: list[dict] = []

    def escribir_formulario(url: str, campo: str, valor: str) -> str:
        enviados.append({"url": url, "campo": campo, "valor": valor})
        return "enviado"

    def abrir_web(url: str) -> str:
        enviados.append({"url": url})
        return "ok"

    escribir, abrir = escudo([escribir_formulario, abrir_web], datos_dueno=DATOS, dominios=DOMINIOS,
                             encargo="Entra a mi banca en línea.")
    return enviados, escribir, abrir


def test_sdk_el_formulario_al_clon_se_retiene_y_al_oficial_sale():
    enviados, escribir, _ = _sdk()
    assert escribir(url="https://banca.bancoIitoral.cl/ingreso", campo="clave", valor=CLAVE).startswith("Grifter retuvo")
    assert enviados == []
    assert escribir(url=f"https://{OFICIAL}/ingreso", campo="clave", valor=CLAVE) == "enviado"
    assert len(enviados) == 1


def test_sdk_la_alerta_explica_el_dominio_y_no_trae_la_clave():
    enviados, escribir, _ = _sdk()
    texto = escribir(url="https://bancolitoral-acceso.cl/ingreso", campo="clave", valor=CLAVE)
    assert "clave banca" in texto and "bancolitoral-acceso.cl" in texto and OFICIAL in texto
    assert CLAVE not in texto


# --- En el proxy MCP -----------------------------------------------------------------------------------------

class SesionFalsa:
    def __init__(self):
        self.llamadas = []

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, args))
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")], isError=False)


def _proxy(tmp_path, escalar=lambda a: False):
    config = Config(datos_dueno=dict(DATOS), dominios={k: list(v) for k, v in DOMINIOS.items()},
                    encargo="Entra a mi banca.", registro=tmp_path / "eventos.jsonl")
    g = Grifter(config, escalar=escalar)
    abajo = SesionFalsa()
    g.sesiones["web"] = abajo
    for h in ("escribir_formulario", "navegar", "abrir_web"):
        g.rutas[h] = ("web", h)
    return g, abajo


def _llamar(g, nombre, args):
    return asyncio.run(g.llamar(nombre, args))


def test_proxy_retiene_el_formulario_al_clon_y_deja_pasar_al_oficial(tmp_path):
    g, abajo = _proxy(tmp_path)
    r = _llamar(g, "escribir_formulario", {"url": "https://banca.bancoIitoral.cl/ingreso", "campo": "clave", "valor": CLAVE})
    assert r.isError and "bancoiitoral.cl" in r.content[0].text.lower() and abajo.llamadas == []
    r = _llamar(g, "escribir_formulario", {"url": f"https://{OFICIAL}/ingreso", "campo": "clave", "valor": CLAVE})
    assert not r.isError and len(abajo.llamadas) == 1


def test_proxy_cubre_una_herramienta_con_otro_nombre_si_lleva_una_direccion(tmp_path):
    g, abajo = _proxy(tmp_path)
    r = _llamar(g, "navegar", {"destino": f"https://clon.cl/validar?k={CLAVE}"})
    assert r.isError and abajo.llamadas == []


def test_proxy_no_deja_la_clave_en_el_registro_ni_en_la_alerta(tmp_path):
    avisos = []
    g, _ = _proxy(tmp_path, escalar=lambda a: avisos.append(a) or False)
    _llamar(g, "escribir_formulario", {"url": "https://clon.cl/x", "campo": "clave", "valor": CLAVE})
    registro = (tmp_path / "eventos.jsonl").read_text(encoding="utf-8")
    assert CLAVE not in registro and "[dato del dueño]" in registro
    assert avisos and CLAVE not in avisos[0].mensaje and CLAVE not in str(avisos[0].args)


def test_proxy_abrir_paginas_sin_datos_no_molesta_ni_se_registra(tmp_path):
    g, abajo = _proxy(tmp_path)
    assert not _llamar(g, "abrir_web", {"url": "https://cualquiera.cl/ofertas"}).isError
    assert not (tmp_path / "eventos.jsonl").exists()


def test_proxy_los_dominios_oficiales_salen_del_yaml(tmp_path):
    from scamshield.mcp.proxy import cargar_config

    ruta = tmp_path / "grifter.yaml"
    ruta.write_text("datos_dueno: {clave_banca: x-clave-1234}\ndominios_oficiales:\n  clave_banca: [banca.bancolitoral.cl]\n"
                    "  tarjeta: pagos.tiendanorte.cl\n", encoding="utf-8")
    assert cargar_config(ruta).dominios == {"clave_banca": ["banca.bancolitoral.cl"], "tarjeta": ["pagos.tiendanorte.cl"]}


def test_cambiar_los_dominios_oficiales_es_un_cambio_de_politica_con_su_diff(tmp_path):
    from scamshield.mcp.integridad import diferencias, politica_canonica

    antes = Config(datos_dueno=dict(DATOS), dominios={"clave_banca": [OFICIAL]})
    despues = Config(datos_dueno=dict(DATOS), dominios={"clave_banca": [OFICIAL, "banca.clon.cl"]})
    diff = diferencias(politica_canonica(antes), politica_canonica(despues))
    assert any("dominios oficiales de clave_banca" in l and "banca.clon.cl" in l for l in diff)


# --- Las aprobaciones solo cuentan por los canales inscritos ------------------------------------------------

def test_una_pagina_que_imita_la_alerta_no_aprueba_nada():
    """El clon de la alerta de Grifter pide «aprueba aquí con tu código»: ningún voto entra por un link."""
    ap = Aprobaciones([Aprobador("Sam", "111"), Aprobador("Reed", "222")], 2, {})
    s = ap.abrir("pago", "Pago de $4.800.000", 4_800_000, "00-8842-1167")
    for quien in ("clon-web", "grifter-aprobar.cl", "Mallory"):
        r = ap.votar(s.id, quien, True, "481207", canal="web")
        assert not r.ok and "No eres aprobador" in r.mensaje
    assert ap.solicitudes[s.id].a_favor == 0
