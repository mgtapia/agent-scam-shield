"""Integridad del escudo (#102): que nadie de adentro pueda apagar o debilitar Grifter en silencio.

Sin red ni llaves: el servidor de abajo es una sesión falsa que anota lo que le llega, y Telegram es un servidor HTTP
falso. La prueba de que un pago no salió es que la sesión de abajo no recibió nada.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mcp.types as types
import pytest
import yaml

from scamshield.mcp import servidor_banco
from scamshield.mcp.alerta_telegram import ganchos_desde_entorno, texto_de_latido
from scamshield.mcp.integridad import Integridad, diferencias, huella, politica_canonica
from scamshield.mcp.proxy import Grifter, cargar_config

INSCRITA = "33-7741-0092"
ESTAFADOR = "90-1188-4417"
RUT = "15.482.331-7"
CLAVE_BANCO = "clave-del-banco-que-no-debe-salir"
BASE = {
    "servidores": {"banco": {"comando": "python", "args": ["-m", "x"], "env": {"BANCO_CLAVE": CLAVE_BANCO}}},
    "cuentas_inscritas": {"Silicio Austral": f"Banco Litoral {INSCRITA}"},
    "datos_dueno": {"rut_empresa": RUT},
    "registro": "eventos.jsonl",
}


class SesionFalsa:
    def __init__(self):
        self.llamadas: list[tuple[str, dict]] = []

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, args))
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")], isError=False)


class AprobadorFalso:
    """El dueño: `respuesta` es lo que contesta cuando se le pregunta (None = todavía no)."""

    def __init__(self, respuesta=None):
        self.respuesta, self.pedidos = respuesta, []

    def pedir(self, cambio):
        self.pedidos.append(cambio)

    def estado(self):
        return self.respuesta


def _escribir(ruta, **cambios):
    datos = {**BASE, **cambios}
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _montar(tmp_path, aprobador=None, latidos=None, clave=None, **cambios):
    """Un proxy con la política del archivo, vigilada. Devuelve (grifter, sesión de abajo, integridad, ruta)."""
    ruta = tmp_path / "grifter.yaml"
    _escribir(ruta, **cambios)
    integridad = Integridad(ruta, clave=clave)
    g = Grifter(cargar_config(ruta), escalar=lambda a: False, integridad=integridad, aprobador=aprobador,
                latido=(lambda evento, datos: latidos.append((evento, datos))) if latidos is not None else None)
    abajo = SesionFalsa()
    g.sesiones["abajo"] = abajo
    g.rutas["pagar"] = ("abajo", "pagar")
    return g, abajo, integridad, ruta


def _pagar(g, cuenta, monto=1000):
    return asyncio.run(g.llamar("pagar", {"cuenta": cuenta, "monto": monto}))


def _arrancar(g):
    return asyncio.run(g.arrancar())


def _eventos(tmp_path):
    ruta = tmp_path / "eventos.jsonl"
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines()] if ruta.exists() else []


# --- El primer arranque y la política que no cambia -----------------------------------------------

def test_el_primer_arranque_registra_la_politica_inicial_y_avisa(tmp_path):
    latidos = []
    g, _, integridad, _ = _montar(tmp_path, latidos=latidos)
    assert _arrancar(g) == "inicial"
    assert integridad.estado() is not None and integridad.estado().por == "primer arranque"
    evento, datos = latidos[0]
    assert evento == "arranque" and datos["politica"] == "inicial" and datos["capas"] == {"capa2": True}


def test_con_la_politica_aprobada_el_pago_a_la_cuenta_inscrita_pasa_y_a_otra_se_retiene(tmp_path):
    g, abajo, _, _ = _montar(tmp_path)
    _arrancar(g)
    assert not _pagar(g, INSCRITA).isError and len(abajo.llamadas) == 1
    assert _pagar(g, ESTAFADOR).isError and len(abajo.llamadas) == 1


def test_un_segundo_arranque_con_la_misma_politica_dice_igual(tmp_path):
    g, _, integridad, ruta = _montar(tmp_path)
    _arrancar(g)
    latidos = []
    g2 = Grifter(cargar_config(ruta), integridad=Integridad(ruta), latido=lambda e, d: latidos.append((e, d)))
    assert asyncio.run(g2.arrancar()) == "igual" and latidos[0][1]["politica"] == "igual"


# --- Reescribir grifter.yaml -----------------------------------------------------------------------

def test_si_el_agente_reescribe_grifter_yaml_el_siguiente_pago_se_retiene_y_llega_el_diff(tmp_path):
    aprobador = AprobadorFalso()
    g, abajo, _, ruta = _montar(tmp_path, aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})   # el ataque
    r = _pagar(g, ESTAFADOR)
    assert r.isError and abajo.llamadas == []
    assert "cambió" in r.content[0].text and "espera su aprobación" in r.content[0].text
    assert len(aprobador.pedidos) == 1
    assert (f"~ cuenta inscrita Silicio Austral: Banco Litoral {INSCRITA} → Banco Austral {ESTAFADOR}"
            in aprobador.pedidos[0].texto)


def test_mientras_la_politica_esta_sin_aprobar_se_retiene_todo_lo_sensible_hasta_a_la_cuenta_inscrita(tmp_path):
    g, abajo, _, ruta = _montar(tmp_path, AprobadorFalso())
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    assert _pagar(g, INSCRITA).isError and _pagar(g, ESTAFADOR).isError and abajo.llamadas == []
    assert [e["evento"] for e in _eventos(tmp_path)].count("retenido_por_politica") == 2


def test_el_dueno_no_recibe_el_mismo_cambio_dos_veces(tmp_path):
    aprobador = AprobadorFalso()
    g, _, _, ruta = _montar(tmp_path, aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    for _ in range(3):
        _pagar(g, ESTAFADOR)
    assert len(aprobador.pedidos) == 1


def test_si_el_dueno_aprueba_se_libera_y_el_proxy_pasa_a_la_politica_nueva(tmp_path):
    aprobador = AprobadorFalso()
    g, abajo, integridad, ruta = _montar(tmp_path, aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Litoral {INSCRITA}", "Nuevo": "Banco X 11-2222-3333"})
    assert _pagar(g, "11-2222-3333").isError
    aprobador.respuesta = True
    assert not _pagar(g, "11-2222-3333").isError and len(abajo.llamadas) == 1
    assert integridad.estado().por == "dueño" and integridad.cambio() is None
    assert "politica_aprobada" in [e["evento"] for e in _eventos(tmp_path)]


def test_si_el_dueno_rechaza_sigue_reteniendo_hasta_que_se_restaure_el_archivo(tmp_path):
    aprobador = AprobadorFalso(respuesta=False)
    g, abajo, _, ruta = _montar(tmp_path, aprobador)
    _arrancar(g)
    original = ruta.read_text(encoding="utf-8")
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    r = _pagar(g, ESTAFADOR)
    assert r.isError and "rechazó" in r.content[0].text
    assert _pagar(g, ESTAFADOR).isError and abajo.llamadas == []
    ruta.write_text(original, encoding="utf-8")   # se restaura lo que el dueño aprobó
    assert not _pagar(g, INSCRITA).isError


def test_apagar_la_capa_2_por_config_es_un_cambio_que_se_retiene_y_se_avisa_con_su_diff(tmp_path):
    aprobador = AprobadorFalso()
    g, abajo, _, ruta = _montar(tmp_path, aprobador)
    _arrancar(g)
    _escribir(ruta, capas={"capa2": False})
    assert _pagar(g, ESTAFADOR).isError and abajo.llamadas == []
    assert "~ capa2: encendida → APAGADA" in aprobador.pedidos[0].texto


def test_con_la_capa_2_apagada_y_aprobada_el_pago_pasa_y_queda_registrado(tmp_path):
    aprobador = AprobadorFalso(respuesta=True)
    g, abajo, _, ruta = _montar(tmp_path, aprobador)
    _arrancar(g)
    _escribir(ruta, capas={"capa2": False})
    assert not _pagar(g, ESTAFADOR).isError and len(abajo.llamadas) == 1
    assert "capa2_apagada" in [e["evento"] for e in _eventos(tmp_path)]


def test_un_grifter_yaml_ilegible_o_borrado_falla_cerrado(tmp_path):
    g, abajo, _, ruta = _montar(tmp_path, AprobadorFalso())
    _arrancar(g)
    ruta.write_text("cuentas_inscritas: [esto no es un mapa", encoding="utf-8")
    assert _pagar(g, INSCRITA).isError
    ruta.unlink()
    assert _pagar(g, INSCRITA).isError and abajo.llamadas == []


def test_al_arrancar_con_la_politica_cambiada_el_dueno_recibe_el_diff_desde_el_principio(tmp_path):
    g, _, _, ruta = _montar(tmp_path)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    aprobador, latidos = AprobadorFalso(), []
    g2 = Grifter(cargar_config(ruta), integridad=Integridad(ruta), aprobador=aprobador,
                 latido=lambda e, d: latidos.append((e, d)))
    assert asyncio.run(g2.arrancar()) == "cambio"
    assert len(aprobador.pedidos) == 1 and latidos[0][1]["politica"] == "cambio"


# --- El diff no filtra secretos --------------------------------------------------------------------

def test_el_diff_no_trae_los_datos_del_dueno_ni_las_credenciales_de_los_servidores(tmp_path):
    g, _, integridad, ruta = _montar(tmp_path)
    _arrancar(g)
    antes = integridad.estado().politica
    _escribir(ruta, datos_dueno={"rut_empresa": "99.999.999-9"},
              servidores={"banco": {"comando": "python", "args": ["-m", "x"], "env": {"BANCO_CLAVE": "otra-clave"}}})
    _, despues, _ = integridad.leer_actual()
    texto = "\n".join(diferencias(antes, despues))
    assert "~ dato del dueño rut_empresa cambió" in texto and "~ servidor banco: cambió credenciales" in texto
    for secreto in (RUT, "99.999.999-9", CLAVE_BANCO, "otra-clave"):
        assert secreto not in texto and secreto not in json.dumps(despues)


def test_la_huella_cambia_con_cada_cosa_que_decide_que_se_retiene():
    base = politica_canonica(_config(BASE))
    for cambio in ({"cuentas_inscritas": {}}, {"encargo": "otro"}, {"capas": {"capa2": False}},
                   {"sensibles": {"pagar": {"destino": "cuenta", "que": "la cuenta"}}}):
        assert huella(politica_canonica(_config({**BASE, **cambio}))) != huella(base), cambio
    assert huella(politica_canonica(_config(BASE))) == huella(base)


@pytest.mark.parametrize("campo,valor", [("dato", "dato"), ("mensaje", "texto"), ("opcional", True)])
def test_la_huella_incluye_las_condiciones_de_cada_regla_sensible(campo, valor):
    regla = {"destino": "cuenta", "que": "la cuenta"}
    antes = politica_canonica(_config({**BASE, "sensibles": {"pagar": regla}}))
    despues = politica_canonica(_config({**BASE, "sensibles": {"pagar": {**regla, campo: valor}}}))
    assert huella(antes) != huella(despues)
    assert diferencias(antes, despues) == ["~ cambió cómo se revisa pagar"]


@pytest.mark.parametrize("campo,valor", [("dato", "dato"), ("mensaje", "texto"), ("opcional", True)])
def test_cambiar_una_condicion_de_la_regla_retiene_el_pago_hasta_aprobar(tmp_path, campo, valor):
    regla = {"destino": "cuenta", "que": "la cuenta"}
    aprobador = AprobadorFalso()
    g, abajo, _, ruta = _montar(tmp_path, aprobador, sensibles={"pagar": regla})
    _arrancar(g)
    _escribir(ruta, sensibles={"pagar": {**regla, campo: valor}})
    assert _pagar(g, INSCRITA).isError and abajo.llamadas == []
    assert aprobador.pedidos[0].lineas == ["~ cambió cómo se revisa pagar"]


def test_cambiar_el_texto_de_aprobacion_cambia_la_huella_y_retiene_el_pago(tmp_path):
    regla = {"destino": "cuenta", "que": "la cuenta", "accion": "el pago"}
    aprobador = AprobadorFalso()
    g, abajo, integridad, ruta = _montar(tmp_path, aprobador, sensibles={"pagar": regla})
    _arrancar(g)
    antes = integridad.estado().politica
    _escribir(ruta, sensibles={"pagar": {**regla, "accion": "una consulta inofensiva"}})
    _, despues, error = integridad.leer_actual()
    assert error == "" and huella(antes) != huella(despues)
    assert diferencias(antes, despues) == ["~ cambió el texto de aprobación de pagar"]
    assert _pagar(g, INSCRITA).isError and abajo.llamadas == []
    assert "consulta inofensiva" not in aprobador.pedidos[0].texto


@pytest.mark.parametrize("nueva_ruta", ["privado/otras.json", None])
def test_cambiar_o_quitar_la_ruta_de_semillas_cambia_la_huella_y_retiene_el_pago(tmp_path, nueva_ruta):
    aprobador = AprobadorFalso()
    g, abajo, integridad, ruta = _montar(tmp_path, aprobador, semillas="privado/totp.json")
    _arrancar(g)
    antes = integridad.estado().politica
    _escribir(ruta, semillas=nueva_ruta)
    _, despues, error = integridad.leer_actual()
    assert error == "" and huella(antes) != huella(despues)
    assert diferencias(antes, despues) == ["~ cambió la ruta de las credenciales de aprobación"]
    assert _pagar(g, INSCRITA).isError and abajo.llamadas == []
    assert "privado" not in aprobador.pedidos[0].texto


def test_la_ruta_de_semillas_se_normaliza_sin_leerla_y_es_estable_al_mover_la_carpeta(tmp_path):
    politicas = []
    for carpeta in (tmp_path / "original", tmp_path / "movida"):
        carpeta.mkdir()
        ruta = carpeta / "grifter.yaml"
        # No existe el archivo de semillas: la integridad solo sigue la ruta configurada.
        _escribir(ruta, semillas="privado/../credenciales/totp.json")
        politicas.append(politica_canonica(cargar_config(ruta)))
    assert politicas[0]["semillas"] == "privado/../credenciales/totp.json"
    assert huella(politicas[0]) == huella(politicas[1])


def test_las_rutas_de_semillas_con_doble_punto_no_se_fusionan_con_la_ruta_directa():
    # `privado` podría ser un enlace: ambas rutas no necesariamente apuntan al mismo archivo.
    con_doble_punto = politica_canonica(_config({**BASE, "semillas": "privado/../credenciales/totp.json"}))
    directa = politica_canonica(_config({**BASE, "semillas": "credenciales/totp.json"}))
    assert huella(con_doble_punto) != huella(directa)
    assert diferencias(con_doble_punto, directa) == ["~ cambió la ruta de las credenciales de aprobación"]


@pytest.mark.parametrize("cambio,diff", [
    ({"url": "https://otro.example/mcp?token=otro-secreto"}, "URL"),
    ({"headers": {"Authorization": "Bearer otro-secreto"}}, "cabeceras HTTP"),
    ({"headers": {}}, "cabeceras HTTP"),
    ({"headers": {"X-API-Key": "Bearer secreto-header"}}, "cabeceras HTTP"),
])
def test_cambiar_el_endpoint_o_sus_cabeceras_cambia_la_huella_y_retiene_el_pago(tmp_path, cambio, diff):
    servidor = {"url": "https://tienda.example/mcp?token=secreto-url",
                "headers": {"Authorization": "Bearer secreto-header"}}
    aprobador = AprobadorFalso()
    g, abajo, integridad, ruta = _montar(tmp_path, aprobador, servidores={"banco": servidor})
    _arrancar(g)
    antes = integridad.estado().politica
    _escribir(ruta, servidores={"banco": {**servidor, **cambio}})
    _, despues, error = integridad.leer_actual()
    assert error == "" and huella(antes) != huella(despues)
    assert diferencias(antes, despues) == [f"~ servidor banco: cambió {diff}"]
    assert _pagar(g, INSCRITA).isError and abajo.llamadas == []
    texto = aprobador.pedidos[0].texto + json.dumps(antes) + json.dumps(despues)
    for secreto in ("secreto-url", "secreto-header", "otro-secreto"):
        assert secreto not in texto


def test_agregar_un_servidor_remoto_no_filtra_credenciales_de_su_url_o_cabeceras():
    antes = politica_canonica(_config({**BASE, "servidores": {}}))
    despues = politica_canonica(_config({**BASE, "servidores": {"tienda": {
        "url": "https://usuario:clave-url@tienda.example/clave-ruta?token=clave-query",
        "headers": {"Authorization": "Bearer clave-header"},
    }}}))
    texto = "\n".join(diferencias(antes, despues))
    assert texto == "+ servidor nuevo tienda: HTTP"
    for secreto in ("clave-url", "clave-ruta", "clave-query", "clave-header"):
        assert secreto not in texto and secreto not in json.dumps(despues)


def test_las_cabeceras_se_canonicalizan_sin_depender_del_orden():
    servidor = {"url": "https://tienda.example/mcp", "headers": {"X-Tenant": "uno", "Authorization": "token"}}
    antes = politica_canonica(_config({**BASE, "servidores": {"tienda": servidor}}))
    servidor["headers"] = dict(reversed(list(servidor["headers"].items())))
    despues = politica_canonica(_config({**BASE, "servidores": {"tienda": servidor}}))
    assert huella(antes) == huella(despues) and diferencias(antes, despues) == []


def test_el_diff_acepta_politicas_previas_sin_endpoint_ni_cabeceras():
    despues = politica_canonica(_config({**BASE, "servidores": {"banco": {
        "url": "https://tienda.example/mcp", "headers": {"Authorization": "token"},
    }}}))
    antes = json.loads(json.dumps(despues))
    for campo in ("url", "headers"):
        antes["servidores"]["banco"].pop(campo)
    assert diferencias(antes, despues) == ["~ servidor banco: cambió URL, cabeceras HTTP"]


def _config(datos):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "grifter.yaml"
        ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
        return cargar_config(ruta)


# --- El registro de lo aprobado --------------------------------------------------------------------

def test_con_clave_un_registro_reescrito_a_mano_se_nota(tmp_path):
    g, abajo, integridad, _ = _montar(tmp_path, clave="clave-del-proxy")
    _arrancar(g)
    ruta_estado = integridad.ruta_estado
    estado = json.loads(ruta_estado.read_text(encoding="utf-8"))
    estado["politica"]["cuentas_inscritas"]["Silicio Austral"] = f"Banco Austral {ESTAFADOR}"
    estado["huella"] = huella(estado["politica"])   # el atacante recalcula la huella, pero no tiene la clave
    ruta_estado.write_text(json.dumps(estado), encoding="utf-8")
    assert "firma" in integridad.cambio().ilegible
    assert _pagar(g, INSCRITA).isError and abajo.llamadas == []


def test_un_registro_dañado_no_se_acepta(tmp_path):
    g, _, integridad, _ = _montar(tmp_path)
    _arrancar(g)
    integridad.ruta_estado.write_text("{no es json", encoding="utf-8")
    assert integridad.cambio() is not None and _pagar(g, INSCRITA).isError


def test_sin_grifter_yaml_de_origen_no_hay_vigilancia_y_todo_sigue_como_antes():
    from scamshield.mcp.proxy import Config

    g = Grifter(Config(cuentas_inscritas={"Silicio Austral": f"Banco Litoral {INSCRITA}"}), escalar=lambda a: False)
    g.sesiones["abajo"] = SesionFalsa()
    g.rutas["pagar"] = ("abajo", "pagar")
    assert asyncio.run(g.arrancar()) == "sin_vigilancia"
    assert not _pagar(g, INSCRITA).isError and _pagar(g, ESTAFADOR).isError


# --- Latido ----------------------------------------------------------------------------------------

def test_el_latido_avisa_al_arrancar_y_al_detenerse_con_las_capas(tmp_path):
    latidos = []
    g, _, _, _ = _montar(tmp_path, latidos=latidos)
    _arrancar(g)
    asyncio.run(g.detener())
    assert [e for e, _ in latidos] == ["arranque", "parada"]
    assert latidos[1][1]["capas"] == {"capa2": True}
    assert [e["evento"] for e in _eventos(tmp_path)][-2:] == ["latido_arranque", "latido_parada"]


def test_si_el_latido_falla_el_proxy_sigue_funcionando(tmp_path):
    def roto(evento, datos):
        raise RuntimeError("sin red")

    g, abajo, _, _ = _montar(tmp_path)
    g.latido = roto
    assert _arrancar(g) == "inicial" and not _pagar(g, INSCRITA).isError


# --- Solo Grifter tiene la credencial del banco ----------------------------------------------------

def _pagar_en_el_banco(tmp_path, clave_env):
    servidor = servidor_banco.crear_servidor(tmp_path / "banco.jsonl", clave_env)
    asyncio.run(servidor.call_tool("pagar", {"destinatario": "Silicio Austral", "cuenta": ESTAFADOR, "monto": 1000}))
    ruta = tmp_path / "banco.jsonl"
    return ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []


def test_un_agente_que_va_directo_al_banco_sin_la_credencial_no_puede_pagar(tmp_path, monkeypatch):
    monkeypatch.delenv("BANCO_CLAVE", raising=False)
    assert _pagar_en_el_banco(tmp_path, "BANCO_CLAVE") == []


def test_el_banco_paga_cuando_la_credencial_viene_de_la_configuracion_del_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("BANCO_CLAVE", "lo-que-puso-el-proxy")
    assert len(_pagar_en_el_banco(tmp_path, "BANCO_CLAVE")) == 1


def test_la_credencial_del_banco_va_en_el_env_del_servidor_y_no_en_el_entorno_del_agente(tmp_path):
    config = _config(BASE)
    assert config.servidores[0].env == {"BANCO_CLAVE": CLAVE_BANCO}


# --- Telegram --------------------------------------------------------------------------------------

TOKEN, CHAT = "123456:TOKEN-QUE-NO-DEBE-SALIR", "777"


class TelegramFalso(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.llamadas: list[tuple[str, dict]] = []
        self.novedades: list[dict] = []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def de(self, metodo):
        return [d for m, d in self.llamadas if m == metodo]

    def apretar(self, accion):
        id_ = self.de("sendMessage")[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[0]
        n = len(self.novedades) + 1
        self.novedades.append({"update_id": n, "callback_query": {
            "id": f"cb{n}", "data": f"{id_}:{accion}", "message": {"message_id": 55, "chat": {"id": int(CHAT)}}}})


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        assert self.path.startswith(f"/bot{TOKEN}/")
        metodo = self.path.rsplit("/", 1)[1]
        self.server.llamadas.append((metodo, cuerpo))
        resultado = True
        if metodo == "getUpdates":
            resultado = [n for n in self.server.novedades if n["update_id"] >= cuerpo.get("offset", 0)]
        elif metodo == "sendMessage":
            resultado = {"message_id": 55}
        datos = json.dumps({"ok": True, "result": resultado}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(datos)


@pytest.fixture
def telegram():
    s = TelegramFalso()
    yield s
    s.shutdown()


def _entorno(telegram):
    return {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": CHAT, "TELEGRAM_API_BASE": telegram.url}


def test_el_cambio_de_politica_llega_a_telegram_con_el_diff_y_dos_botones(tmp_path, telegram):
    ganchos = ganchos_desde_entorno(_entorno(telegram))
    g, abajo, _, ruta = _montar(tmp_path, ganchos.aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    assert _pagar(g, ESTAFADOR).isError
    envio = telegram.de("sendMessage")[-1]
    assert envio["chat_id"] == CHAT and ESTAFADOR in envio["text"] and "retenidos hasta tu decisión" in envio["text"]
    assert [b["text"] for fila in envio["reply_markup"]["inline_keyboard"] for b in fila] == ["Aprobar el cambio", "Rechazar"]
    assert RUT not in envio["text"] and CLAVE_BANCO not in envio["text"]


def test_el_toque_de_aprobar_en_telegram_libera_el_pago(tmp_path, telegram):
    ganchos = ganchos_desde_entorno(_entorno(telegram))
    g, abajo, _, ruta = _montar(tmp_path, ganchos.aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Litoral {INSCRITA}", "Nuevo": "Banco X 11-2222-3333"})
    assert _pagar(g, "11-2222-3333").isError
    telegram.apretar("ap")
    assert not _pagar(g, "11-2222-3333").isError and len(abajo.llamadas) == 1
    assert telegram.de("editMessageText")   # el mensaje queda con lo que se eligió


def test_el_toque_de_rechazar_en_telegram_mantiene_la_retencion(tmp_path, telegram):
    ganchos = ganchos_desde_entorno(_entorno(telegram))
    g, abajo, _, ruta = _montar(tmp_path, ganchos.aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    _pagar(g, ESTAFADOR)
    telegram.apretar("re")
    r = _pagar(g, ESTAFADOR)
    assert r.isError and "rechazó" in r.content[0].text and abajo.llamadas == []


def test_un_boton_de_otro_chat_no_aprueba_el_cambio(tmp_path, telegram):
    ganchos = ganchos_desde_entorno(_entorno(telegram))
    g, abajo, _, ruta = _montar(tmp_path, ganchos.aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    _pagar(g, ESTAFADOR)
    telegram.apretar("ap")
    telegram.novedades[-1]["callback_query"]["message"]["chat"]["id"] = 999
    assert _pagar(g, ESTAFADOR).isError and abajo.llamadas == []


def test_si_telegram_esta_caido_no_se_aprueba_nada(tmp_path):
    ganchos = ganchos_desde_entorno({"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": CHAT,
                                     "TELEGRAM_API_BASE": "http://127.0.0.1:1"})
    g, abajo, _, ruta = _montar(tmp_path, ganchos.aprobador)
    _arrancar(g)
    _escribir(ruta, cuentas_inscritas={"Silicio Austral": f"Banco Austral {ESTAFADOR}"})
    assert _pagar(g, ESTAFADOR).isError and abajo.llamadas == []


def test_el_latido_llega_a_telegram_sin_el_token(tmp_path, telegram):
    ganchos = ganchos_desde_entorno(_entorno(telegram))
    g, _, _, _ = _montar(tmp_path)
    g.latido = ganchos.latido
    _arrancar(g)
    asyncio.run(g.detener())
    textos = [d["text"] for d in telegram.de("sendMessage")]
    assert textos[0].startswith("Grifter arrancó") and "capa2: activa" in textos[0]
    assert textos[1].startswith("Grifter se detuvo")
    assert all(TOKEN not in t for t in textos)


def test_el_texto_del_latido_dice_cuando_una_capa_esta_apagada():
    assert "capa2: APAGADA" in texto_de_latido("arranque", {"capas": {"capa2": False}, "politica": "igual"})
