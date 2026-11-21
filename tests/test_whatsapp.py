"""WhatsApp con Kapso como canal del dueño (#116): alerta con botones y doble autorización con TOTP, sin red ni llaves.

Kapso es un servidor HTTP falso que anota lo que le mandan; los webhooks se firman con HMAC-SHA256 como dice la doc.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from demo import notificar as notificar_mod
from demo import whatsapp
from demo.whatsapp import CanalWhatsApp, desde_entorno, firma_valida, servir_webhook
from scamshield.mcp import alerta_whatsapp
from scamshield.mcp.alerta_whatsapp import QuorumWhatsApp
from scamshield.mcp.aprobaciones import (APROBADA, RECHAZADA, Aprobaciones, Aprobador, RegistroEncadenado, digipass,
                                         generar_semilla)
from scamshield.mcp.proxy import Alerta as AlertaProxy

LLAVE = "kapso-llave-que-no-debe-salir"
SECRETO = "secreto-del-webhook"
PID = "647015955153740"
DUENO = "56911112222"
ALERTA = {"escenario": "demo_microprocesadores", "idioma": "es", "defensa": "layer2",
          "destinatario": "Silicio Austral SpA", "monto": 412000000, "cuenta": "90-1188-4417",
          "dominio": "silicioaustral-chips.cl", "cuenta_inscrita_numero": "33-7741-0092",
          "motivo": "la cuenta solo apareció en un correo"}


class KapsoFalso(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.llamadas: list[tuple[str, str, dict]] = []   # (ruta, llave, cuerpo)
        self.falla = 0
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def a(self, numero):
        return [c for _, _, c in self.llamadas if c.get("to") == numero]


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        s = self.server
        s.llamadas.append((self.path, self.headers.get("X-API-Key", ""), cuerpo))
        if s.falla:
            self.send_response(s.falla)
            self.end_headers()
            return
        datos = json.dumps({"messaging_product": "whatsapp", "messages": [{"id": "wamid.X"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(datos)


@pytest.fixture
def kapso():
    s = KapsoFalso()
    yield s
    s.shutdown()


@pytest.fixture
def etiquetas():
    return []


@pytest.fixture
def canal(kapso, etiquetas):
    return CanalWhatsApp(LLAVE, PID, DUENO, etiquetas.append, SECRETO, api=kapso.url, timeout=3)


def _firmar(cuerpo: bytes, secreto=SECRETO) -> str:
    return hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def _boton(numero, id_):
    return {"message": {"id": "wamid.1", "type": "interactive", "from": numero, "interactive": {
        "type": "button_reply", "button_reply": {"id": id_, "title": "x"}}}, "phone_number_id": PID}


def _texto(numero, texto):
    return {"message": {"id": "wamid.2", "type": "text", "from": numero, "text": {"body": texto}},
            "phone_number_id": PID}


def _entregar(canal, datos, secreto=SECRETO, clave=None, evento="whatsapp.message.received", firma=True):
    cuerpo = json.dumps(datos).encode()
    cab = {"X-Webhook-Event": evento, "Content-Type": "application/json"}
    if firma:
        cab["X-Webhook-Signature"] = _firmar(cuerpo, secreto)
    if clave:
        cab["X-Idempotency-Key"] = clave
    return canal.atender_webhook(cuerpo, cab)


def _enviar(canal, kapso):
    canal(ALERTA)
    cuerpo = kapso.a(DUENO)[-1]
    id_ = cuerpo["interactive"]["action"]["buttons"][0]["reply"]["id"].split(":")[0]
    return cuerpo, id_


# --- Enviar ---------------------------------------------------------------------------------------

def test_manda_la_alerta_con_los_tres_botones_a_la_ruta_y_con_la_llave_de_kapso(canal, kapso):
    cuerpo, _ = _enviar(canal, kapso)
    ruta, llave, _ = kapso.llamadas[-1]
    assert ruta == f"/v24.0/{PID}/messages" and llave == LLAVE
    assert cuerpo["messaging_product"] == "whatsapp" and cuerpo["type"] == "interactive"
    assert cuerpo["interactive"]["type"] == "button"
    assert "$412.000.000" in cuerpo["interactive"]["body"]["text"] and "90-1188-4417" in cuerpo["interactive"]["body"]["text"]
    botones = cuerpo["interactive"]["action"]["buttons"]
    assert [b["type"] for b in botones] == ["reply"] * 3 and len(botones) == 3
    assert all(len(b["reply"]["title"]) <= 20 and len(b["reply"]["id"]) <= 256 for b in botones)


def test_los_botones_de_la_alerta_en_ingles_y_el_texto_largo_se_recortan(canal, kapso):
    canal({**ALERTA, "idioma": "en", "motivo": "x" * 2000})
    cuerpo = kapso.a(DUENO)[-1]
    assert len(cuerpo["interactive"]["body"]["text"]) <= 1024
    assert [b["reply"]["title"] for b in cuerpo["interactive"]["action"]["buttons"]] == [
        "Pay my registered", "Don't pay", "Pay anyway"]


# --- El webhook: botones --------------------------------------------------------------------------

@pytest.mark.parametrize("accion,eleccion", [("pi", "pagar_inscrita"), ("np", "no_pagar")])
def test_el_boton_deja_la_etiqueta_con_la_alerta_y_confirma_por_whatsapp(canal, kapso, etiquetas, accion, eleccion):
    _, id_ = _enviar(canal, kapso)
    assert _entregar(canal, _boton(DUENO, f"{id_}:{accion}")) == (200, "ok")
    assert len(etiquetas) == 1 and etiquetas[0]["eleccion"] == eleccion and etiquetas[0]["canal"] == "whatsapp"
    assert etiquetas[0]["cuenta"] == "90-1188-4417"
    assert "Elegiste" in kapso.a(DUENO)[-1]["text"]["body"]


def test_pagar_igual_pide_una_segunda_confirmacion_y_no_etiqueta_todavia(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    _entregar(canal, _boton(DUENO, f"{id_}:pg"))
    assert etiquetas == []
    pregunta = kapso.a(DUENO)[-1]
    assert [b["reply"]["id"] for b in pregunta["interactive"]["action"]["buttons"]] == [f"{id_}:pgc", f"{id_}:pgx"]
    _entregar(canal, _boton(DUENO, f"{id_}:pgc"))
    assert [e["eleccion"] for e in etiquetas] == ["pagar_igual"]


def test_cancelar_la_segunda_confirmacion_vuelve_a_los_tres_botones(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    _entregar(canal, _boton(DUENO, f"{id_}:pg"))
    _entregar(canal, _boton(DUENO, f"{id_}:pgx"))
    assert len(kapso.a(DUENO)[-1]["interactive"]["action"]["buttons"]) == 3 and etiquetas == []


def test_un_boton_apretado_dos_veces_no_registra_dos_etiquetas(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    _entregar(canal, _boton(DUENO, f"{id_}:np"))
    _entregar(canal, _boton(DUENO, f"{id_}:np"))
    assert len(etiquetas) == 1


def test_una_entrega_repetida_por_reintento_no_se_procesa_otra_vez(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    assert _entregar(canal, _boton(DUENO, f"{id_}:np"), clave="k1") == (200, "ok")
    assert _entregar(canal, _boton(DUENO, f"{id_}:np"), clave="k1") == (200, "repetida")
    assert len(etiquetas) == 1


def test_solo_cuenta_el_numero_del_dueno_aunque_traiga_mas_digitos_o_signos(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    _entregar(canal, _boton("56933334444", f"{id_}:pi"))
    assert etiquetas == []
    _entregar(canal, _boton("+56 9 1111 2222", f"{id_}:pi"))   # el mismo número escrito distinto
    assert len(etiquetas) == 1


def test_sin_respuesta_no_se_etiqueta_nada_y_una_alerta_desconocida_no_hace_nada(canal, kapso, etiquetas):
    _enviar(canal, kapso)
    _entregar(canal, _boton(DUENO, "desconocida:np"))
    assert etiquetas == []


def test_un_envio_en_lote_se_atiende_mensaje_por_mensaje(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    lote = {"type": "whatsapp.message.received", "batch": True, "batch_info": {"size": 2},
            "data": [_texto(DUENO, "hola"), _boton(DUENO, f"{id_}:np")]}
    assert _entregar(canal, lote) == (200, "ok") and len(etiquetas) == 1


def test_los_eventos_que_no_son_mensajes_recibidos_se_ignoran(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    assert _entregar(canal, _boton(DUENO, f"{id_}:np"), evento="whatsapp.message.sent") == (200, "ignorado")
    assert etiquetas == []


# --- Falla cerrada --------------------------------------------------------------------------------

def test_una_firma_mala_o_ausente_se_rechaza_y_no_cuenta_nada(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    assert _entregar(canal, _boton(DUENO, f"{id_}:pi"), secreto="otro-secreto")[0] == 401
    assert _entregar(canal, _boton(DUENO, f"{id_}:pi"), firma=False)[0] == 401
    assert etiquetas == []


def test_una_firma_valida_pero_de_otro_cuerpo_se_rechaza(canal, kapso, etiquetas):
    _, id_ = _enviar(canal, kapso)
    cuerpo = json.dumps(_boton(DUENO, f"{id_}:pi")).encode()
    firma = _firmar(json.dumps(_boton(DUENO, f"{id_}:np")).encode())
    assert canal.atender_webhook(cuerpo, {"X-Webhook-Signature": firma})[0] == 401 and etiquetas == []


def test_sin_secreto_configurado_el_webhook_esta_apagado(kapso, etiquetas):
    canal = CanalWhatsApp(LLAVE, PID, DUENO, etiquetas.append, "", api=kapso.url)
    _, id_ = _enviar(canal, kapso)
    assert _entregar(canal, _boton(DUENO, f"{id_}:pi"), secreto="")[0] == 503 and etiquetas == []


def test_un_cuerpo_que_no_es_json_con_buena_firma_da_400(canal):
    cuerpo = b"no es json"
    assert canal.atender_webhook(cuerpo, {"X-Webhook-Signature": _firmar(cuerpo)})[0] == 400


def test_si_kapso_falla_al_enviar_el_error_no_lleva_la_llave_ni_la_url(canal, kapso):
    kapso.falla = 500
    with pytest.raises(whatsapp.ErrorWhatsApp) as e:
        canal(ALERTA)
    assert LLAVE not in str(e.value) and "http" not in str(e.value) and "500" in str(e.value)


def test_el_log_de_notificar_no_imprime_la_llave(canal, caplog, monkeypatch):
    monkeypatch.setattr(notificar_mod, "_CANALES", [canal])
    caplog.set_level(logging.DEBUG)
    notificar_mod.notificar(ALERTA)
    assert LLAVE not in caplog.text and LLAVE not in repr(canal)


def test_firma_valida_acepta_mayusculas_y_rechaza_vacios():
    cuerpo = b"{}"
    assert firma_valida("s", cuerpo, _firmar(cuerpo, "s").upper())
    assert not firma_valida("", cuerpo, _firmar(cuerpo, "")) and not firma_valida("s", cuerpo, None)


# --- Configuración --------------------------------------------------------------------------------

def test_sin_llave_numero_o_dueno_no_hay_canal():
    base = {"KAPSO_API_KEY": LLAVE, "KAPSO_PHONE_NUMBER_ID": PID, "KAPSO_OWNER_NUMBER": DUENO}
    assert desde_entorno(lambda e: None, {}) is None
    for faltante in base:
        assert desde_entorno(lambda e: None, {k: v for k, v in base.items() if k != faltante}) is None
    assert desde_entorno(lambda e: None, base) is not None


def test_con_configuracion_se_registra_el_canal_en_notificar(kapso, etiquetas, monkeypatch):
    monkeypatch.setattr(notificar_mod, "_CANALES", [])
    entorno = {"KAPSO_API_KEY": LLAVE, "KAPSO_PHONE_NUMBER_ID": PID, "KAPSO_OWNER_NUMBER": DUENO,
               "KAPSO_WEBHOOK_SECRET": SECRETO, "KAPSO_API_BASE": kapso.url}
    assert whatsapp.iniciar_desde_entorno(etiquetas.append, entorno) is not None
    assert notificar_mod.notificar(ALERTA) == ["whatsapp"]
    assert kapso.a(DUENO)


def test_el_servidor_de_la_demo_atiende_el_webhook_y_rechaza_sin_firma(canal, kapso, etiquetas):
    from fastapi.testclient import TestClient

    from demo.server import app

    cliente = TestClient(app)
    app.state.whatsapp = canal
    try:
        _, id_ = _enviar(canal, kapso)
        cuerpo = json.dumps(_boton(DUENO, f"{id_}:np")).encode()
        mala = cliente.post("/api/whatsapp/webhook", content=cuerpo, headers={"X-Webhook-Signature": "00"})
        assert mala.status_code == 401 and etiquetas == []
        buena = cliente.post("/api/whatsapp/webhook", content=cuerpo, headers={
            "X-Webhook-Signature": _firmar(cuerpo), "X-Webhook-Event": "whatsapp.message.received"})
        assert buena.status_code == 200 and len(etiquetas) == 1
        app.state.whatsapp = None
        assert cliente.post("/api/whatsapp/webhook", content=cuerpo).status_code == 404
    finally:
        app.state.whatsapp = None


def test_el_servidor_minimo_del_webhook_para_el_proxy(canal, kapso, etiquetas):
    servidor = servir_webhook(canal, 0)
    try:
        _, id_ = _enviar(canal, kapso)
        cuerpo = json.dumps(_boton(DUENO, f"{id_}:pi")).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{servidor.server_address[1]}/webhook", data=cuerpo,
                                     headers={"X-Webhook-Signature": _firmar(cuerpo)}, method="POST")
        assert urllib.request.urlopen(req, timeout=3).status == 200 and len(etiquetas) == 1
    finally:
        servidor.shutdown()


# --- Proxy MCP: la alerta y el latido -------------------------------------------------------------

def _entorno(kapso):
    return {"KAPSO_API_KEY": LLAVE, "KAPSO_PHONE_NUMBER_ID": PID, "KAPSO_OWNER_NUMBER": DUENO,
            "KAPSO_WEBHOOK_SECRET": SECRETO, "KAPSO_API_BASE": kapso.url}


def _alerta_proxy():
    return AlertaProxy(herramienta="pagar", servidor="banco", args={"destinatario": "Silicio Austral SpA",
                       "cuenta": "90-1188-4417", "monto": 412_000_000}, valor="90-1188-4417", motivo="m",
                       mensaje="Grifter retuvo el pago.", fuentes=["leer_correo de silicio-austral"])


def test_la_alerta_del_proxy_llega_por_whatsapp_y_sin_respuesta_no_se_paga(kapso):
    ganchos = alerta_whatsapp.ganchos_desde_entorno(_entorno(kapso), cuenta_inscrita="33-7741-0092")
    assert ganchos.escalar(_alerta_proxy()) is None
    cuerpo = kapso.a(DUENO)[0]
    assert "90-1188-4417" in cuerpo["interactive"]["body"]["text"] and len(cuerpo["interactive"]["action"]["buttons"]) == 3


def test_con_espera_pagar_igual_confirmado_aprueba_y_no_pagar_no(kapso):
    ganchos = alerta_whatsapp.ganchos_desde_entorno(_entorno(kapso), esperar_s=5)

    def apretar(*acciones):
        id_ = kapso.a(DUENO)[-1]["interactive"]["action"]["buttons"][0]["reply"]["id"].split(":")[0]
        for a in acciones:
            _entregar(ganchos.canal, _boton(DUENO, f"{id_}:{a}"))

    threading.Timer(0.3, apretar, args=("np",)).start()
    assert ganchos.escalar(_alerta_proxy()) is None
    threading.Timer(0.3, apretar, args=("pg", "pgc")).start()
    assert ganchos.escalar(_alerta_proxy()) is True


def test_si_kapso_esta_caido_el_proxy_no_paga(kapso):
    kapso.falla = 500
    ganchos = alerta_whatsapp.ganchos_desde_entorno(_entorno(kapso))
    assert ganchos.escalar(_alerta_proxy()) is None


def test_sin_llaves_no_hay_ganchos_y_el_latido_llega_sin_la_llave(kapso):
    assert alerta_whatsapp.ganchos_desde_entorno({}) is None
    ganchos = alerta_whatsapp.ganchos_desde_entorno(_entorno(kapso))
    ganchos.latido("arranque", {"capas": {"capa2": True}, "politica": "inicial"})
    texto = kapso.a(DUENO)[-1]["text"]["body"]
    assert texto.startswith("Grifter arrancó") and LLAVE not in texto


# --- Doble autorización por WhatsApp --------------------------------------------------------------

T0 = 1_700_000_000.0
SEMILLAS = {"Sam": generar_semilla(), "Reed": generar_semilla()}
SAM, REED = "56955550001", "56955550002"


class Reloj:
    t = T0

    def __call__(self):
        return self.t


@pytest.fixture
def quorum(kapso, etiquetas, tmp_path):
    canal = CanalWhatsApp(LLAVE, PID, DUENO, etiquetas.append, SECRETO, api=kapso.url, timeout=3)
    ap = Aprobaciones([Aprobador("Sam", "+" + SAM), Aprobador("Reed", REED)], 2, SEMILLAS,
                      RegistroEncadenado(tmp_path / "a.jsonl"), Reloj())
    return QuorumWhatsApp(canal, ap), ap, canal


def _abrir(q, ap):
    s = ap.abrir("pago", "Pago de $8.000.000", 8_000_000, "90-1188-4417")
    q.notificar(s)
    return s


def test_la_solicitud_le_llega_a_cada_aprobador_por_whatsapp_con_el_desafio(quorum, kapso):
    q, ap, _ = quorum
    s = _abrir(q, ap)
    for numero in (SAM, REED):
        msg = kapso.a(numero)[0]
        assert s.desafio in msg["interactive"]["body"]["text"] and "0 de 2 aprobaciones" in msg["interactive"]["body"]["text"]
        assert [b["reply"]["title"] for b in msg["interactive"]["action"]["buttons"]] == ["Aprobar", "Rechazar"]
    assert kapso.a(DUENO) == []


def test_aprobar_pide_el_codigo_y_con_dos_codigos_buenos_se_aprueba(quorum, kapso):
    q, ap, canal = quorum
    s = _abrir(q, ap)
    _entregar(canal, _boton(SAM, f"{s.id}:ap"))
    _entregar(canal, _texto(SAM, digipass(SEMILLAS["Sam"], s.desafio, T0)))
    assert ap.progreso(s.id) == "1 de 2 aprobaciones" and "Registrado" in kapso.a(SAM)[-1]["text"]["body"]
    assert "Sam aprobó" in kapso.a(REED)[-1]["text"]["body"]
    _entregar(canal, _boton(REED, f"{s.id}:ap"))
    _entregar(canal, _texto(REED, digipass(SEMILLAS["Reed"], s.desafio, T0)))
    assert ap.estado(s.id) == APROBADA


def test_un_codigo_malo_no_vota_y_dice_cuantos_intentos_quedan(quorum, kapso):
    q, ap, canal = quorum
    s = _abrir(q, ap)
    _entregar(canal, _boton(SAM, f"{s.id}:ap"))
    _entregar(canal, _texto(SAM, "000000"))
    assert ap.solicitudes[s.id].a_favor == 0 and "Te quedan 2" in kapso.a(SAM)[-1]["text"]["body"]


def test_rechazar_rechaza_sin_pedir_codigo_y_avisa_al_otro(quorum, kapso):
    q, ap, canal = quorum
    s = _abrir(q, ap)
    _entregar(canal, _boton(REED, f"{s.id}:re"))
    assert ap.estado(s.id) == RECHAZADA and "Reed rechazó" in kapso.a(SAM)[-1]["text"]["body"]


def test_un_numero_que_no_es_aprobador_ni_dueno_no_vota(quorum):
    q, ap, canal = quorum
    s = _abrir(q, ap)
    _entregar(canal, _boton("56900000000", f"{s.id}:ap"))
    _entregar(canal, _texto("56900000000", digipass(SEMILLAS["Sam"], s.desafio, T0)))
    assert ap.solicitudes[s.id].a_favor == 0


def test_un_codigo_sin_haber_apretado_aprobar_no_cuenta(quorum):
    q, ap, canal = quorum
    s = _abrir(q, ap)
    _entregar(canal, _texto(SAM, digipass(SEMILLAS["Sam"], s.desafio, T0)))
    assert ap.solicitudes[s.id].a_favor == 0


def test_el_webhook_sin_firma_no_aprueba_aunque_traiga_el_codigo_bueno(quorum):
    q, ap, canal = quorum
    s = _abrir(q, ap)
    _entregar(canal, _boton(SAM, f"{s.id}:ap"), firma=False)
    _entregar(canal, _texto(SAM, digipass(SEMILLAS["Sam"], s.desafio, T0)), firma=False)
    assert ap.solicitudes[s.id].a_favor == 0


def test_el_boton_del_dueno_y_el_de_un_aprobador_no_se_pisan(quorum, kapso, etiquetas):
    q, ap, canal = quorum
    canal(ALERTA)
    id_alerta = kapso.a(DUENO)[-1]["interactive"]["action"]["buttons"][0]["reply"]["id"].split(":")[0]
    s = _abrir(q, ap)
    _entregar(canal, _boton(DUENO, f"{id_alerta}:np"))
    _entregar(canal, _boton(DUENO, f"{s.id}:ap"))   # el dueño no es aprobador: no vota
    assert len(etiquetas) == 1 and ap.solicitudes[s.id].a_favor == 0
