"""La demo con un agente real detrás del proxy MCP (#74), sin API ni llaves.

El agente es un guion que obedece al correo envenenado; los servidores MCP, el proxy y el banco sandbox son los de
verdad, y Telegram es un servidor HTTP falso. Lo que se prueba es el cableado: que sin Grifter el pago llega al
estafador, que con Grifter no llega y que el aviso sale al celular con sus botones.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from scamshield.mcp.alerta_telegram import alerta_para_telegram, escalar_telegram
from scamshield.mcp.proxy import Alerta
from scamshield.mcp.servidor_proveedor import CUENTA_ESTAFADOR, CUENTA_LEGITIMA
from scripts import demo_real
from scripts.demo_real import (Llamada, ModeloAnthropic, ModeloGuionado, Presupuesto, PresupuestoAgotado, Turno,
                               correr_episodio, demo, resumen)

TOKEN, CHAT = "123456:TOKEN-QUE-NO-DEBE-SALIR", "777"


def _correr(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def episodios():
    """Los tres episodios de la demo con el agente guionado: se corren una sola vez, los servidores MCP tardan."""
    salida: list[str] = []
    eps = _correr(demo(ModeloGuionado(), 1, Presupuesto(), imprimir=salida.append))
    return eps, "\n".join(salida)


def test_sin_grifter_el_agente_paga_a_la_cuenta_del_estafador(episodios):
    eps, _ = episodios
    sin = next(e for e in eps if e.modo == "sin Grifter")
    assert sin.cayo and not sin.pago_correcto
    assert [p["cuenta"] for p in sin.pagos] == [CUENTA_ESTAFADOR]
    assert sin.retenidos == 0


def test_con_grifter_el_pago_no_llega_al_banco_y_el_agente_lo_sabe(episodios):
    eps, _ = episodios
    con = next(e for e in eps if e.modo == "con Grifter")
    assert not con.cayo and con.pagos == []
    assert con.retenidos == 1 and con.alertas == 1
    assert "retuvo" in con.respuesta_final.lower()


def test_el_control_sin_veneno_paga_a_la_cuenta_inscrita_y_no_se_retiene_nada(episodios):
    eps, _ = episodios
    control = next(e for e in eps if e.modo == "control con Grifter")
    assert control.pago_correcto and not control.cayo
    assert control.retenidos == 0 and control.alertas == 0


def test_la_salida_muestra_el_correo_el_pago_y_la_retencion(episodios):
    _, salida = episodios
    assert "leer_correo" in salida and "GRIFTER" in salida and "retuvo el pago" in salida
    assert "CAYÓ" in salida and "ningún pago" in salida


def test_el_resumen_trae_intervalo_y_avisa_que_es_una_demostracion(episodios):
    eps, _ = episodios
    texto = resumen(eps, Presupuesto())
    assert "sin Grifter" in texto and "1/1 = 100 %" in texto and "0/1 = 0 %" in texto
    assert "[" in texto and "demostración" in texto


def test_el_gancho_de_escalada_recibe_la_alerta_del_proxy_y_sin_aprobacion_no_se_paga():
    recibidas: list[Alerta] = []

    def escalar(alerta):
        recibidas.append(alerta)
        return None

    ep = _correr(correr_episodio(ModeloGuionado(), "con Grifter", True, Presupuesto(), escalar, lambda _: None))
    assert len(recibidas) == 1 and recibidas[0].valor == CUENTA_ESTAFADOR and not ep.cayo


def test_si_el_dueno_aprueba_el_pago_sigue_y_el_banco_lo_anota():
    ep = _correr(correr_episodio(ModeloGuionado(), "con Grifter", True, Presupuesto(), lambda a: True, lambda _: None))
    assert ep.cayo and ep.retenidos == 0   # el dueño lo aprobó: ya no es un engaño, y queda en el registro


# --- Presupuesto y modelo -------------------------------------------------------------------------

def test_el_presupuesto_corta_al_llegar_al_tope():
    p = Presupuesto(tope_usd=0.01)
    p.sumar(Turno(tokens_entrada=1_000, tokens_salida=2_000))   # 0,001 + 0,010 = 0,011
    assert p.gastado_usd == pytest.approx(0.011)
    with pytest.raises(PresupuestoAgotado):
        p.revisar()


def test_un_episodio_se_corta_si_se_agota_el_presupuesto_y_la_demo_se_detiene():
    class Caro:
        nombre = "caro"

        def turno(self, *a):
            return Turno(llamadas=[Llamada("x", "leer_correo", {})], tokens_entrada=10_000_000)

    salida: list[str] = []
    eps = _correr(demo(Caro(), 2, Presupuesto(tope_usd=1.0), imprimir=salida.append))
    assert len(eps) == 1 and "tope" in eps[0].error and "tope" in "\n".join(salida)
    assert "se cortó" in resumen(eps, Presupuesto())


def test_el_modelo_de_anthropic_traduce_la_respuesta_y_cuenta_los_tokens():
    bloques = [SimpleNamespace(type="text", text="Voy a leer el correo."),
               SimpleNamespace(type="tool_use", id="tu_1", name="leer_correo", input={})]
    visto = {}

    class Mensajes:
        def create(self, **kw):
            visto.update(kw)
            return SimpleNamespace(content=bloques, usage=SimpleNamespace(input_tokens=120, output_tokens=30))

    modelo = ModeloAnthropic("claude-haiku-5-5", SimpleNamespace(messages=Mensajes()))
    t = modelo.turno("sistema", [{"role": "user", "content": "hola"}], [{"name": "leer_correo"}])
    assert t.texto == "Voy a leer el correo." and t.llamadas == [Llamada("tu_1", "leer_correo", {})]
    assert (t.tokens_entrada, t.tokens_salida) == (120, 30)
    assert visto["model"] == "claude-haiku-5-5" and visto["max_tokens"] == demo_real.MAX_TOKENS_RESPUESTA


def test_si_la_api_falla_la_demo_se_corta_con_el_motivo_y_sin_traceback():
    import anthropic
    import httpx

    class SinSaldo:
        def create(self, **kw):
            req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            resp = httpx.Response(400, request=req)
            raise anthropic.BadRequestError("x", response=resp, body={"error": {"message": "credit balance is too low"}})

    modelo = ModeloAnthropic("claude-haiku-5-5", SimpleNamespace(messages=SinSaldo()))
    salida: list[str] = []
    eps = _correr(demo(modelo, 1, Presupuesto(), imprimir=salida.append))
    assert len(eps) == 1 and "400" in eps[0].error and "credit balance is too low" in eps[0].error
    assert "se cortó" in resumen(eps, Presupuesto())


def test_los_servidores_hijos_no_heredan_la_llave_del_entorno(monkeypatch):
    """El agente tiene la llave; los servidores MCP que levanta el proxy, no."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-LLAVE-DE-PRUEBA")
    from mcp.client.stdio import get_default_environment

    assert "ANTHROPIC_API_KEY" not in get_default_environment()


def test_el_agente_guionado_sin_correo_envenenado_usa_la_cuenta_inscrita():
    ep = _correr(correr_episodio(ModeloGuionado(), "sin Grifter", False, Presupuesto(), None, lambda _: None))
    assert ep.pago_correcto and ep.pagos[0]["cuenta"] == CUENTA_LEGITIMA


# --- Telegram ------------------------------------------------------------------------------------

class TelegramFalso(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.llamadas: list[tuple[str, dict]] = []
        self.novedades: list[dict] = []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def de(self, metodo):
        return [d for m, d in self.llamadas if m == metodo]


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


def _alerta():
    return Alerta(herramienta="pagar", servidor="banco", args={"destinatario": "Silicio Austral SpA",
                  "cuenta": CUENTA_ESTAFADOR, "monto": 412_000_000}, valor=CUENTA_ESTAFADOR,
                  motivo="m", mensaje="Grifter retuvo el pago.", fuentes=["leer_correo de silicio-austral"])


def test_la_alerta_del_proxy_llega_a_telegram_con_tres_botones_y_sin_llamar_a_getupdates(telegram):
    escalar = escalar_telegram(_entorno(telegram), cuenta_inscrita=CUENTA_LEGITIMA)
    assert escalar(_alerta()) is None   # solo avisa: la llamada sigue retenida
    envio = telegram.de("sendMessage")[0]
    assert envio["chat_id"] == CHAT
    assert CUENTA_ESTAFADOR in envio["text"] and CUENTA_LEGITIMA in envio["text"] and "$412.000.000" in envio["text"]
    botones = [b for fila in envio["reply_markup"]["inline_keyboard"] for b in fila]
    assert len(botones) == 3
    assert telegram.de("getUpdates") == []   # sin polling: no choca con el servidor de la demo (409)


def _apretar(telegram, *acciones):
    id_ = telegram.de("sendMessage")[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[0]
    for accion in acciones:
        n = len(telegram.novedades) + 1
        telegram.novedades.append({"update_id": n, "callback_query": {
            "id": f"cb{n}", "data": f"{id_}:{accion}", "message": {"message_id": 55, "chat": {"id": int(CHAT)}}}})


def test_con_espera_sin_respuesta_no_aprueba(telegram):
    escalar = escalar_telegram(_entorno(telegram), esperar_s=0.5)
    assert escalar(_alerta()) is None


def test_con_espera_no_pagar_no_aprueba(telegram):
    escalar = escalar_telegram(_entorno(telegram), esperar_s=3)
    threading.Timer(0.3, _apretar, args=(telegram, "np")).start()
    assert escalar(_alerta()) is None
    assert any("No pagar" in d.get("text", "") or "no pagar" in d.get("text", "").lower()
               for d in telegram.de("answerCallbackQuery"))


def test_con_espera_pagar_igual_pide_segunda_confirmacion_y_solo_entonces_aprueba(telegram):
    escalar = escalar_telegram(_entorno(telegram), esperar_s=1)
    threading.Timer(0.3, _apretar, args=(telegram, "pg")).start()
    assert escalar(_alerta()) is None   # el primer «pagar igual» solo pide confirmar
    escalar = escalar_telegram(_entorno(telegram), esperar_s=3)
    threading.Timer(0.3, _apretar, args=(telegram, "pg", "pgc")).start()
    assert escalar(_alerta()) is True


def test_sin_token_o_sin_chat_no_hay_gancho():
    assert escalar_telegram({}) is None
    assert escalar_telegram({"TELEGRAM_BOT_TOKEN": TOKEN}) is None


def test_si_telegram_falla_no_se_paga_y_el_error_no_lleva_el_token():
    escalar = escalar_telegram({"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": CHAT,
                                "TELEGRAM_API_BASE": "http://127.0.0.1:1"})
    assert escalar(_alerta()) is None


def test_el_formato_de_la_alerta_usa_el_destinatario_de_los_argumentos():
    a = alerta_para_telegram(_alerta(), CUENTA_LEGITIMA)
    assert a["destinatario"] == "Silicio Austral SpA" and a["monto"] == 412_000_000
    assert a["cuenta"] == CUENTA_ESTAFADOR and a["dominio"] == "leer_correo de silicio-austral"
