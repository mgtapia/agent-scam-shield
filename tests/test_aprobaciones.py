"""Doble autorización con digipass (#102, parte 2): quórum, TOTP atado a la operación y registro encadenado.

Sin red ni llaves: el reloj es de mentira, el servidor de abajo es una sesión falsa y Telegram es un servidor HTTP falso.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mcp.types as types
import pytest
import yaml

from scamshield.mcp.alerta_telegram import QuorumTelegram, ganchos_desde_entorno
from scamshield.mcp.aprobaciones import (APROBADA, PENDIENTE, RECHAZADA, VENCIDA, Aprobaciones, Aprobador,
                                         AprobadorQuorum, RegistroEncadenado, cargar_semillas, contador_valido, desafio, digipass,
                                         generar_semilla, hotp, main as main_digipass, totp)
from scamshield.mcp.integridad import Integridad, politica_canonica
from scamshield.mcp.proxy import Grifter, cargar_config

T0 = 1_700_000_000.0
INSCRITA, ESTAFADOR = "33-7741-0092", "90-1188-4417"
SEMILLAS = {"Sam": generar_semilla(), "Reed": generar_semilla(), "Mallory": generar_semilla()}
APROBADORES = [Aprobador("Sam", "111"), Aprobador("Reed", "222")]


class Reloj:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _aprobaciones(reloj=None, ruta=None, quorum=2, aprobadores=None):
    return Aprobaciones(aprobadores or APROBADORES, quorum, SEMILLAS, RegistroEncadenado(ruta), reloj or Reloj())


def _codigo(nombre, s, reloj):
    return digipass(SEMILLAS[nombre], s.desafio, reloj())


# --- TOTP (RFC 6238) -------------------------------------------------------------------------------

def test_hotp_calza_con_los_vectores_de_rfc_4226():
    clave = b"12345678901234567890"
    assert [hotp(clave, n) for n in range(3)] == ["755224", "287082", "359152"]


@pytest.mark.parametrize("t,esperado", [(59, "94287082"), (1111111109, "07081804"), (20000000000, "65353130")])
def test_totp_calza_con_los_vectores_de_rfc_6238(t, esperado):
    assert totp(b"12345678901234567890", t, digitos=8) == esperado


def test_el_codigo_cambia_cada_30_segundos_y_con_la_operacion():
    semilla = SEMILLAS["Sam"]
    d1, d2 = desafio("aaaa", 8_000_000, ESTAFADOR), desafio("aaaa", 9_000_000, ESTAFADOR)
    assert digipass(semilla, d1, T0) == digipass(semilla, d1, T0 + 5)
    assert digipass(semilla, d1, T0) != digipass(semilla, d1, T0 + 30)
    assert digipass(semilla, d1, T0) != digipass(semilla, d2, T0)                    # otro monto
    assert digipass(semilla, d1, T0) != digipass(semilla, desafio("aaaa", 8_000_000, INSCRITA), T0)   # otra cuenta
    assert digipass(semilla, d1, T0) != digipass(SEMILLAS["Reed"], d1, T0)           # otra persona


# --- El quórum --------------------------------------------------------------------------------------

def _abrir(ap, **k):
    return ap.abrir("pago", "Pago de $8.000.000", 8_000_000, ESTAFADOR, **k)


def test_dos_aprobadores_distintos_completan_el_quorum():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    r1 = ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj))
    assert r1.ok and ap.estado(s.id) == PENDIENTE and ap.progreso(s.id) == "1 de 2 aprobaciones"
    r2 = ap.votar(s.id, "Reed", True, _codigo("Reed", s, reloj))
    assert r2.ok and ap.estado(s.id) == APROBADA


def test_el_mismo_aprobador_dos_veces_no_completa_el_quorum():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    codigo = _codigo("Sam", s, reloj)
    assert ap.votar(s.id, "Sam", True, codigo).ok
    segundo = ap.votar(s.id, "Sam", True, codigo)
    assert not segundo.ok and "Ya votaste" in segundo.mensaje
    assert ap.estado(s.id) == PENDIENTE and ap.solicitudes[s.id].a_favor == 1


def test_quien_inicio_no_cuenta_como_aprobador():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap, iniciador="Sam")
    r = ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj))
    assert not r.ok and "otra persona" in r.mensaje and ap.solicitudes[s.id].a_favor == 0


def test_un_solo_no_rechaza_aunque_el_otro_ya_haya_aprobado_y_no_pide_codigo():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj))
    r = ap.votar(s.id, "Reed", False)   # sin código
    assert r.ok and ap.estado(s.id) == RECHAZADA
    assert not ap.votar(s.id, "Reed", True, _codigo("Reed", s, reloj)).ok


def test_si_vence_sin_quorum_queda_rechazada_y_ya_no_acepta_votos():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap, plazo_s=1800)
    ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj))
    reloj.t += 1801
    assert ap.estado(s.id) == VENCIDA
    assert not ap.votar(s.id, "Reed", True, digipass(SEMILLAS["Reed"], s.desafio, reloj.t)).ok


def test_el_plazo_de_la_politica_es_mas_largo_que_el_de_un_pago():
    ap = _aprobaciones()
    pago = ap.abrir("pago", "x")
    politica = ap.abrir("politica", "x")
    assert (politica.vence - politica.creada) == 24 * 3600 and (pago.vence - pago.creada) == 30 * 60


def test_tres_codigos_malos_bloquean_a_ese_aprobador_para_esa_operacion_pero_no_a_otro():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    for _ in range(3):
        assert not ap.votar(s.id, "Sam", True, "000000").ok
    bueno = ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj))
    assert not bueno.ok and "bloqueado" in bueno.mensaje   # ni con el código bueno
    otra = _abrir(ap)   # en otra operación, Sam sigue pudiendo
    assert ap.votar(otra.id, "Sam", True, _codigo("Sam", otra, reloj)).ok
    assert ap.votar(s.id, "Reed", True, _codigo("Reed", s, reloj)).ok   # y Reed sigue pudiendo en esta


def test_un_codigo_de_otra_operacion_otra_persona_o_vencido_no_sirve():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s, otra, tercera = _abrir(ap), _abrir(ap), _abrir(ap)
    assert not ap.votar(s.id, "Sam", True, _codigo("Sam", otra, reloj)).ok       # de otra solicitud
    assert not ap.votar(s.id, "Sam", True, _codigo("Reed", s, reloj)).ok          # de otra persona
    viejo = digipass(SEMILLAS["Sam"], tercera.desafio, T0)
    reloj.t += 120
    assert not ap.votar(tercera.id, "Sam", True, viejo).ok                        # de hace cuatro pasos
    assert ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj)).ok               # el de ahora sí (le quedaba un intento)


def test_se_tolera_un_paso_de_diferencia_de_reloj():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    assert ap.votar(s.id, "Sam", True, digipass(SEMILLAS["Sam"], s.desafio, T0 - 30)).ok


def test_quien_no_es_aprobador_no_vota_aunque_tenga_semilla():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    r = ap.votar(s.id, "Mallory", True, digipass(SEMILLAS["Mallory"], s.desafio, reloj.t))
    assert not r.ok and ap.solicitudes[s.id].a_favor == 0


def test_un_pago_aprobado_se_consume_una_sola_vez():
    reloj = Reloj()
    ap = _aprobaciones(reloj)
    s = _abrir(ap)
    for n in ("Sam", "Reed"):
        ap.votar(s.id, n, True, _codigo(n, s, reloj))
    assert ap.consumir(s.id) and not ap.consumir(s.id)


def test_el_quorum_no_puede_ser_mayor_que_los_aprobadores():
    with pytest.raises(ValueError):
        Aprobaciones(APROBADORES, 3, SEMILLAS)
    with pytest.raises(ValueError):
        Aprobaciones([Aprobador("Sam"), Aprobador("Sam")], 1, SEMILLAS)


# --- Registro encadenado -----------------------------------------------------------------------------

def _con_registro(tmp_path):
    reloj = Reloj()
    ap = _aprobaciones(reloj, tmp_path / "aprobaciones.jsonl")
    s = _abrir(ap)
    ap.votar(s.id, "Sam", True, _codigo("Sam", s, reloj))
    ap.votar(s.id, "Reed", True, _codigo("Reed", s, reloj))
    return ap, tmp_path / "aprobaciones.jsonl"


def test_el_registro_dice_quien_cuando_y_por_que_canal_y_no_guarda_el_codigo(tmp_path):
    ap, ruta = _con_registro(tmp_path)
    lineas = ap.registro.lineas()
    assert [l["evento"] for l in lineas] == ["abierta", "aprobacion", "aprobacion"]
    assert lineas[1]["quien"] == "Sam" and lineas[1]["ts"] and "canal" in lineas[1]
    assert ap.registro.verificar() is None
    s = next(iter(ap.solicitudes.values()))
    assert _codigo("Sam", s, Reloj()) not in ruta.read_text(encoding="utf-8")


def test_cambiar_una_linea_del_registro_rompe_la_cadena(tmp_path):
    ap, ruta = _con_registro(tmp_path)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    cambiada = json.loads(lineas[1])
    cambiada["quien"] = "Mallory"
    lineas[1] = json.dumps(cambiada, ensure_ascii=False)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    assert ap.registro.verificar() == 2


def test_borrar_una_linea_del_medio_se_nota(tmp_path):
    ap, ruta = _con_registro(tmp_path)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text("\n".join([lineas[0], lineas[2]]) + "\n", encoding="utf-8")
    assert ap.registro.verificar() == 2


def test_borrar_la_ultima_linea_deja_una_cadena_valida_pero_mas_corta(tmp_path):
    """Límite honesto: quitar el final no rompe la cadena. Por eso cada voto además le llega al otro aprobador."""
    ap, ruta = _con_registro(tmp_path)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text("\n".join(lineas[:-1]) + "\n", encoding="utf-8")
    assert ap.registro.verificar() is None and len(ap.registro.lineas()) == 2


# --- Semillas y digipass simulado --------------------------------------------------------------------

def test_las_semillas_se_cargan_de_un_archivo_fuera_del_repo(tmp_path):
    ruta = tmp_path / "semillas.json"
    ruta.write_text(json.dumps({"Sam": "JBSWY3DPEHPK3PXP"}), encoding="utf-8")
    assert cargar_semillas(str(ruta)) == {"Sam": "JBSWY3DPEHPK3PXP"}
    assert cargar_semillas(None, {"GRIFTER_SEMILLAS": str(ruta)}) == {"Sam": "JBSWY3DPEHPK3PXP"}
    assert cargar_semillas(None, {}) == {}


def test_el_digipass_simulado_crea_semillas_y_da_el_codigo_que_el_quorum_acepta(tmp_path, capsys):
    ruta = tmp_path / "semillas.json"
    assert main_digipass(["semillas", "Sam", "Reed", "--salida", str(ruta)]) == 0
    assert main_digipass(["semillas", "Sam", "--salida", str(ruta)]) == 2   # no pisa las que ya hay
    semillas = cargar_semillas(str(ruta))
    capsys.readouterr()
    main_digipass(["codigo", "--nombre", "Sam", "--id", "ab12", "--monto", "8000000", "--cuenta", ESTAFADOR,
                   "--semillas", str(ruta)])
    codigo = capsys.readouterr().out.strip()
    assert len(codigo) == 6 and codigo.isdigit()
    assert contador_valido(semillas["Sam"], desafio("ab12", "8000000", ESTAFADOR), codigo, time.time()) is not None


# --- En el proxy: pagos grandes ----------------------------------------------------------------------

class SesionFalsa:
    def __init__(self):
        self.llamadas = []

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, args))
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")], isError=False)


class QuorumFalso:
    """Lo que el proxy usa del quórum, con los votos de los aprobadores en una cola que se vacía al sondear."""

    def __init__(self, ap, reloj):
        self.aprobaciones, self.reloj, self.notificadas, self.cola, self.reconfigurado = ap, reloj, [], [], []

    def notificar(self, s):
        self.notificadas.append(s)

    def sondear(self):
        cola, self.cola = self.cola, []
        for nombre, aprobar in cola:
            s = self.notificadas[-1]
            codigo = digipass(SEMILLAS[nombre], s.desafio, self.reloj()) if aprobar else ""
            self.aprobaciones.votar(s.id, nombre, aprobar, codigo, canal="prueba")

    def reconfigurar(self, politica):
        self.reconfigurado.append(politica)

    def votar(self, *nombres, aprobar=True):
        self.cola += [(n, aprobar) for n in nombres]


def _proxy(tmp_path, umbral=5_000_000, **extra):
    ruta = tmp_path / "grifter.yaml"
    datos = {"cuentas_inscritas": {"Silicio Austral": f"Banco Litoral {INSCRITA}"}, "registro": "eventos.jsonl",
             "aprobadores": [{"nombre": "Sam", "canal": "111"}, {"nombre": "Reed", "canal": "222"}], "quorum": 2,
             "umbral_doble": umbral, **extra}
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    reloj = Reloj()
    quorum = QuorumFalso(_aprobaciones(reloj), reloj)
    config = cargar_config(ruta)
    integridad = Integridad(ruta)
    integridad.aprobar(politica_canonica(config), "dueño")
    g = Grifter(config, escalar=lambda a: False, integridad=integridad, aprobador=AprobadorQuorum(quorum), quorum=quorum)
    abajo = SesionFalsa()
    g.sesiones["abajo"] = abajo
    g.rutas["pagar"] = ("abajo", "pagar")
    asyncio.run(g.arrancar())
    return g, abajo, quorum, ruta, integridad


def _pagar(g, cuenta, monto):
    return asyncio.run(g.llamar("pagar", {"cuenta": cuenta, "monto": monto}))


def test_un_pago_bajo_el_umbral_a_la_cuenta_inscrita_pasa_sin_quorum(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    assert not _pagar(g, INSCRITA, 4_000_000).isError and len(abajo.llamadas) == 1 and quorum.notificadas == []


def test_un_pago_sobre_el_umbral_a_la_cuenta_inscrita_espera_la_doble_autorizacion(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    r = _pagar(g, INSCRITA, 8_000_000)
    assert r.isError and "0 de 2 aprobaciones" in r.content[0].text and abajo.llamadas == []
    assert len(quorum.notificadas) == 1 and "$8.000.000" in quorum.notificadas[0].detalle


def test_con_una_sola_aprobacion_el_pago_sigue_retenido_y_con_dos_sale_una_sola_vez(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    _pagar(g, INSCRITA, 8_000_000)
    quorum.votar("Sam")
    r = _pagar(g, INSCRITA, 8_000_000)
    assert r.isError and "1 de 2 aprobaciones" in r.content[0].text and abajo.llamadas == []
    quorum.votar("Reed")
    assert not _pagar(g, INSCRITA, 8_000_000).isError and len(abajo.llamadas) == 1
    # El mismo pago otra vez abre otra solicitud: lo aprobado se usó.
    assert _pagar(g, INSCRITA, 8_000_000).isError and len(quorum.notificadas) == 2


def test_cambiar_el_monto_o_la_cuenta_no_reaprovecha_la_aprobacion(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    _pagar(g, INSCRITA, 8_000_000)
    quorum.votar("Sam", "Reed")
    assert _pagar(g, INSCRITA, 9_000_000).isError   # otro monto: solicitud nueva
    assert abajo.llamadas == [] and len(quorum.notificadas) == 2


def test_un_pago_grande_a_una_cuenta_que_la_capa_2_retiene_tambien_pasa_con_el_quorum(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    _pagar(g, ESTAFADOR, 8_000_000)
    assert "doble autorización" in _pagar(g, ESTAFADOR, 8_000_000).content[0].text
    quorum.votar("Sam", "Reed")
    assert not _pagar(g, ESTAFADOR, 8_000_000).isError and len(abajo.llamadas) == 1   # lo decidieron dos personas


def test_un_rechazo_de_un_aprobador_deja_el_pago_rechazado(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    _pagar(g, INSCRITA, 8_000_000)
    quorum.votar("Reed", aprobar=False)
    r = _pagar(g, INSCRITA, 8_000_000)
    assert r.isError and "no lo aprobaron" in r.content[0].text and abajo.llamadas == []


def test_un_monto_que_no_se_puede_leer_pide_quorum(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    assert asyncio.run(g.llamar("pagar", {"cuenta": INSCRITA, "monto": "muchísimo"})).isError and quorum.notificadas


def test_un_monto_con_puntos_de_miles_se_lee_bien(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path)
    assert asyncio.run(g.llamar("pagar", {"cuenta": INSCRITA, "monto": "8.000.000"})).isError
    assert not asyncio.run(g.llamar("pagar", {"cuenta": INSCRITA, "monto": "4.000.000"})).isError


def test_sin_umbral_los_pagos_no_piden_doble_autorizacion(tmp_path):
    g, abajo, quorum, *_ = _proxy(tmp_path, umbral=0)
    assert not _pagar(g, INSCRITA, 900_000_000).isError and quorum.notificadas == []


# --- En el proxy: cambios de política ------------------------------------------------------------------

def test_una_cuenta_inscrita_nueva_necesita_los_dos_aprobadores(tmp_path):
    g, abajo, quorum, ruta, integridad = _proxy(tmp_path)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    datos["cuentas_inscritas"]["Nuevo"] = "Banco X 11-2222-3333"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert _pagar(g, "11-2222-3333", 1000).isError          # pide quórum y retiene
    quorum.votar("Sam")
    assert _pagar(g, "11-2222-3333", 1000).isError          # con uno no alcanza
    quorum.votar("Reed")
    assert not _pagar(g, "11-2222-3333", 1000).isError      # con dos, se aprueba la política y sale el pago
    assert integridad.cambio() is None and len(abajo.llamadas) == 1


def test_agregar_un_aprobador_con_una_sola_firma_no_pasa(tmp_path):
    """Cambiar la lista de aprobadores se aprueba con la lista anterior: el nuevo no vota su propia entrada."""
    g, abajo, quorum, ruta, integridad = _proxy(tmp_path)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    datos["aprobadores"].append({"nombre": "Mallory", "canal": "333"})
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert _pagar(g, INSCRITA, 1000).isError
    assert "+ aprobador nuevo Mallory" in quorum.notificadas[-1].detalle
    quorum.votar("Sam", "Mallory")   # Sam y Mallory: solo Sam está en la lista anterior
    assert _pagar(g, INSCRITA, 1000).isError and integridad.cambio() is not None
    quorum.votar("Reed")
    assert not _pagar(g, INSCRITA, 1000).isError and integridad.cambio() is None
    assert quorum.reconfigurado    # y desde ahora el quórum usa la lista nueva


def test_bajar_el_quorum_o_el_umbral_tambien_pide_quorum_y_sale_en_el_diff(tmp_path):
    g, abajo, quorum, ruta, _ = _proxy(tmp_path)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    datos.update(quorum=1, umbral_doble=50_000_000)
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert _pagar(g, INSCRITA, 1000).isError
    diff = quorum.notificadas[-1].detalle
    assert "~ quórum: 2 → 1" in diff and "~ umbral de doble autorización: 5000000 → 50000000" in diff


def test_si_un_aprobador_rechaza_el_cambio_de_politica_se_mantiene_la_retencion(tmp_path):
    g, abajo, quorum, ruta, _ = _proxy(tmp_path)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    datos["cuentas_inscritas"]["Nuevo"] = "Banco X 11-2222-3333"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _pagar(g, INSCRITA, 1000)
    quorum.votar("Reed", aprobar=False)
    r = _pagar(g, INSCRITA, 1000)
    assert r.isError and "rechazó" in r.content[0].text and abajo.llamadas == []


# --- Telegram ----------------------------------------------------------------------------------------

TOKEN = "123456:TOKEN-QUE-NO-DEBE-SALIR"


class TelegramFalso(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.llamadas: list[tuple[str, dict]] = []
        self.novedades: list[dict] = []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def a(self, chat):
        return [d for m, d in self.llamadas if m == "sendMessage" and str(d["chat_id"]) == chat]

    def apretar(self, chat, id_, accion):
        n = len(self.novedades) + 1
        self.novedades.append({"update_id": n, "callback_query": {
            "id": f"cb{n}", "data": f"{id_}:{accion}", "message": {"message_id": 55, "chat": {"id": int(chat)}}}})

    def escribir(self, chat, texto):
        n = len(self.novedades) + 1
        self.novedades.append({"update_id": n, "message": {"chat": {"id": int(chat)}, "text": texto}})


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
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


def _quorum_telegram(telegram, reloj, tmp_path):
    ganchos = ganchos_desde_entorno({"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "111",
                                     "TELEGRAM_API_BASE": telegram.url})
    ap = _aprobaciones(reloj, tmp_path / "aprobaciones.jsonl")
    return QuorumTelegram(ganchos.canal, ap), ap


def test_la_solicitud_le_llega_a_cada_aprobador_con_el_desafio_y_dos_botones(telegram, tmp_path):
    q, ap = _quorum_telegram(telegram, Reloj(), tmp_path)
    s = _abrir(ap)
    q.notificar(s)
    for chat in ("111", "222"):
        msg = telegram.a(chat)[0]
        assert s.desafio in msg["text"] and "0 de 2 aprobaciones" in msg["text"]
        assert [b["text"] for fila in msg["reply_markup"]["inline_keyboard"] for b in fila] == ["Aprobar", "Rechazar"]
        assert TOKEN not in msg["text"]


def test_aprobar_por_telegram_pide_el_codigo_y_con_dos_codigos_buenos_se_aprueba(telegram, tmp_path):
    reloj = Reloj()
    q, ap = _quorum_telegram(telegram, reloj, tmp_path)
    s = _abrir(ap)
    q.notificar(s)
    telegram.apretar("111", s.id, "ap")
    telegram.escribir("111", digipass(SEMILLAS["Sam"], s.desafio, reloj()))
    q.sondear()
    assert ap.progreso(s.id) == "1 de 2 aprobaciones" and "Registrado" in telegram.a("111")[-1]["text"]
    assert "Sam aprobó" in telegram.a("222")[-1]["text"]   # el otro aprobador se entera
    telegram.apretar("222", s.id, "ap")
    telegram.escribir("222", digipass(SEMILLAS["Reed"], s.desafio, reloj()))
    q.sondear()
    assert ap.estado(s.id) == APROBADA


def test_un_codigo_malo_por_telegram_no_vota_y_dice_cuantos_intentos_quedan(telegram, tmp_path):
    q, ap = _quorum_telegram(telegram, Reloj(), tmp_path)
    s = _abrir(ap)
    q.notificar(s)
    telegram.apretar("111", s.id, "ap")
    telegram.escribir("111", "000000")
    q.sondear()
    assert ap.solicitudes[s.id].a_favor == 0 and "Te quedan 2" in telegram.a("111")[-1]["text"]


def test_rechazar_por_telegram_rechaza_la_solicitud_sin_pedir_codigo(telegram, tmp_path):
    q, ap = _quorum_telegram(telegram, Reloj(), tmp_path)
    s = _abrir(ap)
    q.notificar(s)
    telegram.apretar("222", s.id, "re")
    q.sondear()
    assert ap.estado(s.id) == RECHAZADA and "Reed rechazó" in telegram.a("111")[-1]["text"]


def test_un_chat_que_no_es_de_un_aprobador_no_vota(telegram, tmp_path):
    q, ap = _quorum_telegram(telegram, Reloj(), tmp_path)
    s = _abrir(ap)
    q.notificar(s)
    telegram.apretar("999", s.id, "ap")
    telegram.escribir("999", digipass(SEMILLAS["Sam"], s.desafio, T0))
    q.sondear()
    assert ap.solicitudes[s.id].a_favor == 0


def test_un_codigo_escrito_sin_haber_apretado_aprobar_no_cuenta(telegram, tmp_path):
    reloj = Reloj()
    q, ap = _quorum_telegram(telegram, reloj, tmp_path)
    s = _abrir(ap)
    q.notificar(s)
    telegram.escribir("111", digipass(SEMILLAS["Sam"], s.desafio, reloj()))
    q.sondear()
    assert ap.solicitudes[s.id].a_favor == 0
