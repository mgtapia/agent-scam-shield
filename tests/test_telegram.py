"""El canal de Telegram (#20) contra un servidor falso: sin red real, sin token y sin API."""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from demo import notificar as notificar_mod
from demo import telegram
from demo.telegram import CanalTelegram, ErrorTelegram, desde_entorno, texto_de_alerta

TOKEN = "123456:TOKEN-QUE-NO-DEBE-SALIR"
CHAT = "777"
ALERTA = {"escenario": "demo_microprocesadores", "idioma": "es", "defensa": "layer2",
          "destinatario": "Silicio Austral SpA", "monto": 412000000, "cuenta": "90-1188-4417",
          "dominio": "silicioaustral-chips.cl", "cuenta_inscrita_numero": "33-7741-0092",
          "motivo": "la cuenta solo apareció en un correo"}


class TelegramFalso(ThreadingHTTPServer):
    """Imita lo mínimo de la API de bots: registra cada llamada y entrega las novedades en cola."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.llamadas: list[tuple[str, dict]] = []
        self.novedades: list[dict] = []
        self.falla: dict[str, int] = {}
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def apretar(self, id_, accion, chat=CHAT, update_id=None):
        n = len(self.novedades) + 1
        self.novedades.append({"update_id": update_id or n, "callback_query": {
            "id": f"cb{n}", "data": f"{id_}:{accion}",
            "message": {"message_id": 55, "chat": {"id": int(chat)}}}})

    def de(self, metodo):
        return [d for m, d in self.llamadas if m == metodo]


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencio
        pass

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        assert self.path.startswith(f"/bot{TOKEN}/"), "el token tiene que ir en la ruta"
        metodo = self.path.rsplit("/", 1)[1]
        s = self.server
        s.llamadas.append((metodo, cuerpo))
        if s.falla.get(metodo):
            self.send_response(s.falla[metodo])
            self.end_headers()
            return
        resultado = True
        if metodo == "getUpdates":
            resultado = [n for n in s.novedades if n["update_id"] >= cuerpo.get("offset", 0)]
        elif metodo == "sendMessage":
            resultado = {"message_id": 55}
        datos = json.dumps({"ok": True, "result": resultado}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(datos)


@pytest.fixture
def servidor():
    s = TelegramFalso()
    yield s
    s.shutdown()


@pytest.fixture
def etiquetas():
    return []


@pytest.fixture
def canal(servidor, etiquetas):
    return CanalTelegram(TOKEN, CHAT, etiquetas.append, api=servidor.url, timeout=3)


def _enviar(canal, servidor):
    canal(ALERTA)
    mensaje = servidor.de("sendMessage")[-1]
    id_ = mensaje["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[0]
    return mensaje, id_


def test_manda_la_alerta_al_chat_con_los_tres_botones(canal, servidor):
    mensaje, _ = _enviar(canal, servidor)
    assert mensaje["chat_id"] == CHAT
    assert "$412.000.000" in mensaje["text"] and "90-1188-4417" in mensaje["text"]
    assert "33-7741-0092" in mensaje["text"] and "silicioaustral-chips.cl" in mensaje["text"]
    botones = [b["text"] for fila in mensaje["reply_markup"]["inline_keyboard"] for b in fila]
    assert botones == ["Pagar a mi cuenta inscrita", "No pagar", "Pagar igual"]
    assert all(len(b["callback_data"].encode()) <= 64
               for fila in mensaje["reply_markup"]["inline_keyboard"] for b in fila)


def test_la_alerta_sale_en_ingles_si_el_escenario_es_en_ingles(canal, servidor):
    canal({**ALERTA, "idioma": "en"})
    m = servidor.de("sendMessage")[-1]
    assert m["text"].startswith("Grifter held a payment")
    assert [b["text"] for f in m["reply_markup"]["inline_keyboard"] for b in f] == [
        "Pay my registered account", "Don't pay", "Pay anyway"]


@pytest.mark.parametrize("accion, eleccion", [("pi", "pagar_inscrita"), ("np", "no_pagar")])
def test_el_boton_deja_la_etiqueta_con_la_alerta_y_confirma_en_el_chat(canal, servidor, etiquetas, accion, eleccion):
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, accion)
    assert canal.sondear_una_vez() == 1
    [e] = etiquetas
    assert e["eleccion"] == eleccion and e["canal"] == "telegram"
    assert e["cuenta"] == "90-1188-4417" and e["escenario"] == "demo_microprocesadores" and e["ts"]
    editado = servidor.de("editMessageText")[-1]
    assert editado["reply_markup"] == {"inline_keyboard": []}  # los botones desaparecen
    assert servidor.de("answerCallbackQuery")


def test_pagar_igual_pide_una_segunda_confirmacion_y_no_etiqueta_todavia(canal, servidor, etiquetas):
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, "pg")
    canal.sondear_una_vez()
    assert etiquetas == []
    pregunta = servidor.de("editMessageText")[-1]
    assert "no está inscrita" in pregunta["text"]
    textos = [b["text"] for f in pregunta["reply_markup"]["inline_keyboard"] for b in f]
    assert textos == ["Pagar igual a la cuenta nueva", "Cancelar"]
    servidor.apretar(id_, "pgc")
    canal.sondear_una_vez()
    assert [e["eleccion"] for e in etiquetas] == ["pagar_igual"]


def test_cancelar_la_segunda_confirmacion_vuelve_a_los_tres_botones(canal, servidor, etiquetas):
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, "pg")
    servidor.apretar(id_, "pgx")
    canal.sondear_una_vez()
    assert etiquetas == []
    assert len(servidor.de("editMessageText")[-1]["reply_markup"]["inline_keyboard"]) == 2


def test_un_boton_apretado_dos_veces_no_registra_dos_etiquetas(canal, servidor, etiquetas):
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, "np")
    servidor.apretar(id_, "np")
    canal.sondear_una_vez()
    assert len(etiquetas) == 1
    assert "Ya respondiste" in servidor.de("answerCallbackQuery")[-1]["text"]


def test_solo_cuentan_los_botones_del_chat_configurado(canal, servidor, etiquetas):
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, "pi", chat="999")  # otro chat
    canal.sondear_una_vez()
    assert etiquetas == [] and not servidor.de("editMessageText")


def test_sin_respuesta_no_se_etiqueta_nada(canal, servidor, etiquetas):
    _enviar(canal, servidor)
    assert canal.sondear_una_vez() == 0 and etiquetas == []


def test_una_alerta_desconocida_no_hace_nada(canal, servidor, etiquetas):
    servidor.apretar("deadbeef", "pi")
    canal.sondear_una_vez()
    assert etiquetas == []


def test_no_relee_las_novedades_ya_atendidas(canal, servidor, etiquetas):
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, "np")
    canal.sondear_una_vez()
    canal.sondear_una_vez()
    assert len(etiquetas) == 1 and servidor.de("getUpdates")[-1]["offset"] == 2


def test_si_telegram_falla_el_error_no_lleva_el_token(canal, servidor):
    servidor.falla["sendMessage"] = 401
    with pytest.raises(ErrorTelegram) as e:
        canal(ALERTA)
    assert "401" in str(e.value) and TOKEN not in str(e.value) and "123456" not in str(e.value)


def test_el_log_de_notificar_no_imprime_el_token(canal, servidor, caplog, monkeypatch):
    servidor.falla["sendMessage"] = 500
    monkeypatch.setattr(notificar_mod, "_CANALES", [canal])
    with caplog.at_level(logging.DEBUG):
        entregados = notificar_mod.notificar(ALERTA)
    assert entregados == []  # un canal caído no detiene nada
    assert TOKEN not in caplog.text and "123456:" not in caplog.text and repr(canal) == "<CanalTelegram chat=777>"


def test_sin_token_o_sin_chat_no_hay_canal():
    assert desde_entorno(print, {}) is None
    assert desde_entorno(print, {"TELEGRAM_BOT_TOKEN": TOKEN}) is None
    assert desde_entorno(print, {"TELEGRAM_CHAT_ID": CHAT}) is None
    assert desde_entorno(print, {"TELEGRAM_BOT_TOKEN": " ", "TELEGRAM_CHAT_ID": CHAT}) is None
    assert telegram.iniciar_desde_entorno(print, {}) is None


def test_con_token_y_chat_se_registra_el_canal_y_arranca(servidor, etiquetas, monkeypatch):
    monkeypatch.setattr(notificar_mod, "_CANALES", [])
    canal = telegram.iniciar_desde_entorno(etiquetas.append, {
        "TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": CHAT, "TELEGRAM_API_BASE": servidor.url})
    try:
        assert canal in notificar_mod._CANALES
        assert notificar_mod.notificar(ALERTA) == ["telegram"]
    finally:
        canal.detener()


def test_el_texto_no_revienta_con_una_alerta_incompleta():
    texto = texto_de_alerta({"idioma": "es"})
    assert texto.startswith("Grifter retuvo un pago") and "Cuenta:" in texto
    assert "$" not in texto_de_alerta({"monto": None}).splitlines()[1]  # sin monto no inventa uno
    assert "$1.500" in texto_de_alerta({"monto": 1500})


def test_la_etiqueta_de_telegram_queda_en_el_archivo_del_servidor(canal, servidor, tmp_path, monkeypatch):
    """Telegram y la página comparten la misma función de etiquetas: una línea por respuesta."""
    import demo.server as server

    monkeypatch.setattr(server, "ETIQUETAS", tmp_path / "etiquetas.jsonl")
    canal.al_elegir = server.registrar_etiqueta
    _, id_ = _enviar(canal, servidor)
    servidor.apretar(id_, "pi")
    canal.sondear_una_vez()
    [fila] = [json.loads(x) for x in (tmp_path / "etiquetas.jsonl").read_text(encoding="utf-8").splitlines()]
    assert fila["eleccion"] == "pagar_inscrita" and fila["canal"] == "telegram" and fila["recibida"]
    with pytest.raises(ValueError):
        server.registrar_etiqueta({"eleccion": "robar"})
