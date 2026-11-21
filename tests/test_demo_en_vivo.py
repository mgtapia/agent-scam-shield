"""Demo en vivo: el pedido de aprobación de Pablo por WhatsApp. Sin red: el canal es falso."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demo import en_vivo, server, whatsapp

LLAVE = "llave-secreta-de-kapso-NO-DEBE-SALIR"


class CanalFalso:
    """Guarda lo que se mandaría a Kapso. Con `falla`, responde como Kapso con error."""

    def __init__(self, falla: bool = False):
        self.dueno, self.enviados, self.falla, self._llave = "56912345678", [], falla, LLAVE

    def enviar(self, cuerpo):
        if self.falla:
            raise whatsapp.ErrorWhatsApp("enviar: Kapso respondió 401")
        self.enviados.append(cuerpo)
        return {"messages": [{"id": "wamid.x"}]}


@pytest.fixture
def cliente(monkeypatch):
    reloj = [1000.0]
    canal = CanalFalso()
    entorno = {"KAPSO_API_KEY": LLAVE}
    monkeypatch.setattr(server, "demo_en_vivo", en_vivo.EnVivo(entorno, reloj=lambda: reloj[0], canal=canal, clave="clave-de-prueba"))
    monkeypatch.setenv(en_vivo.VARIABLE, "1")
    return TestClient(server.app), canal, reloj


def test_sin_la_variable_la_ruta_no_existe(cliente, monkeypatch):
    c, canal, _ = cliente
    monkeypatch.delenv(en_vivo.VARIABLE)
    assert c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"}).status_code == 404
    assert canal.enviados == []


def test_sin_clave_o_con_otra_da_403(cliente):
    c, canal, _ = cliente
    assert c.post("/api/demo/alerta-en-vivo", json={}).status_code == 403
    assert c.post("/api/demo/alerta-en-vivo", json={"clave": "otra"}).status_code == 403
    assert canal.enviados == []


def test_manda_el_pedido_de_pablo_con_aprobar_y_rechazar(cliente):
    c, canal, _ = cliente
    r = c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba", "idioma": "es"})
    assert r.status_code == 200 and r.json()["ok"]
    [cuerpo] = canal.enviados
    assert cuerpo["to"] == canal.dueno
    texto = cuerpo["interactive"]["body"]["text"]
    assert texto.startswith("Grifter pide aprobación (demo-")
    assert "Marta quiere pagar $650.000 a J. Contreras V." in texto and "1 de 2 aprobaciones: Marta ya aprobó con su código" in texto
    assert [b["reply"]["title"] for b in cuerpo["interactive"]["action"]["buttons"]] == ["Aprobar", "Rechazar"]


def test_un_envio_cada_30_segundos(cliente):
    c, canal, reloj = cliente
    ok = {"clave": "clave-de-prueba"}
    assert c.post("/api/demo/alerta-en-vivo", json=ok).status_code == 200
    reloj[0] += 10
    r = c.post("/api/demo/alerta-en-vivo", json=ok)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) == 20
    reloj[0] += 21
    assert c.post("/api/demo/alerta-en-vivo", json=ok).status_code == 200
    assert len(canal.enviados) == 2


def test_la_llave_no_sale_en_la_respuesta_ni_en_los_registros(cliente, monkeypatch, caplog):
    c, _, _ = cliente
    falla = en_vivo.EnVivo({"KAPSO_API_KEY": LLAVE}, canal=CanalFalso(falla=True), clave="clave-de-prueba")
    monkeypatch.setattr(server, "demo_en_vivo", falla)
    with caplog.at_level(logging.DEBUG):
        r = c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"})
    assert r.status_code == 502
    assert LLAVE not in r.text and LLAVE not in caplog.text
    ok = c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"})   # el fallo devolvió el cupo
    assert LLAVE not in ok.text


def test_sin_llaves_de_kapso_lo_dice_sin_mostrar_nada(monkeypatch):
    monkeypatch.setenv(en_vivo.VARIABLE, "1")
    monkeypatch.setattr(server, "demo_en_vivo", en_vivo.EnVivo({}, clave="c"))
    r = TestClient(server.app).post("/api/demo/alerta-en-vivo", json={"clave": "c"})
    assert r.status_code == 503 and "KAPSO_API_KEY" in r.text


def test_la_clave_es_siempre_de_un_solo_uso_por_arranque():
    a, b = en_vivo.EnVivo({}), en_vivo.EnVivo({en_vivo.VARIABLE_CLAVE: "demo2026"})
    assert a.clave() and a.clave() != b.clave() and b.clave() != "demo2026"   # la de .env se ignora
    assert a.clave_valida(a.clave()) and not a.clave_valida(b.clave()) and not a.clave_valida("")
    avisos = []
    en_vivo.anunciar_clave(b, avisos.append)
    assert "se ignora" in avisos[0] and b.clave() in avisos[1] and "demo2026" not in "".join(avisos)


def test_si_kapso_falla_el_cupo_de_30_s_no_se_gasta(cliente, monkeypatch):
    c, _, _ = cliente
    falla = en_vivo.EnVivo({"KAPSO_API_KEY": LLAVE}, canal=CanalFalso(falla=True), clave="clave-de-prueba")
    monkeypatch.setattr(server, "demo_en_vivo", falla)
    assert c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"}).status_code == 502
    falla._canal = CanalFalso()   # Kapso vuelve: el reintento inmediato sale, sin 429
    assert c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"}).status_code == 200
    assert c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"}).status_code == 429   # el éxito sí cuenta


def test_despues_de_5_claves_malas_hay_que_esperar(cliente):
    c, canal, reloj = cliente
    for _ in range(en_vivo.MAX_FALLOS):
        assert c.post("/api/demo/alerta-en-vivo", json={"clave": "mala"}).status_code == 403
    r = c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"})   # ni la buena pasa durante la espera
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert c.get("/api/demo/alerta-en-vivo/estado?id=demo-0000", headers={"X-Grifter-Demo-Clave": "mala"}).status_code == 429
    reloj[0] += en_vivo.VENTANA_FALLOS_S
    assert c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"}).status_code == 200
    assert len(canal.enviados) == 1


def test_demo_js_solo_llama_con_whatsapp_1():
    js = (Path(server.DEMO) / "demo.js").read_text(encoding="utf-8")
    assert "api/demo/alerta-en-vivo" in js
    # La única llamada está dentro de la función que sale de inmediato si la URL no trae ?whatsapp=1.
    funcion = re.search(r"function avisarEnVivo\(\) \{(.*?)\n  \}", js, re.S)
    assert funcion, "falta avisarEnVivo en demo.js"
    cuerpo = funcion.group(1)
    assert re.search(r'if \(params\.get\("whatsapp"\) !== "1"[^)]*\) return;', cuerpo)
    assert cuerpo.index("return;") < cuerpo.index("api/demo/alerta-en-vivo")
    # Una sola llamada que manda, y la consulta del rechazo real solo se lanza desde ahí (sondear).
    assert js.count('fetch("api/demo/alerta-en-vivo"') == 1
    assert js.count("sondear(") == 2   # la definición y la única llamada, dentro de avisarEnVivo
    assert "sondear(clave)" in cuerpo


# --- El rechazo real de Pablo: el webhook firmado de Kapso vuelve al pedido ---------------------------------------
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402

SECRETO = "secreto-del-webhook"
PABLO = "56912345678"


def _entrega(numero: str, boton: str) -> tuple[bytes, dict[str, str]]:
    cuerpo = json.dumps({"message": {"from": numero, "type": "interactive",
                                     "interactive": {"type": "button_reply", "button_reply": {"id": boton}}}}).encode()
    firma = hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    return cuerpo, {"Content-Type": "application/json", "X-Webhook-Signature": firma, "X-Webhook-Event": "whatsapp.message.received"}


@pytest.fixture
def real(monkeypatch):
    """Un canal real (firma, manejadores) con el envío a Kapso falso, conectado como en el arranque del servidor."""
    reloj = [500.0]
    canal = whatsapp.CanalWhatsApp(LLAVE, "1", PABLO, lambda e: None, SECRETO)
    enviados = []
    monkeypatch.setattr(canal, "enviar", lambda cuerpo: enviados.append(cuerpo) or {"messages": [{}]})
    vivo = en_vivo.EnVivo({}, reloj=lambda: reloj[0], clave="c")
    vivo.usar_canal(canal)
    monkeypatch.setattr(server, "demo_en_vivo", vivo)
    monkeypatch.setenv(en_vivo.VARIABLE, "1")
    c = TestClient(server.app)
    c.app.state.whatsapp = canal   # lo que deja el arranque
    return c, reloj, enviados


def test_el_rechazo_firmado_de_pablo_llega_con_su_latencia(real):
    c, reloj, enviados = real
    id_ = c.post("/api/demo/alerta-en-vivo", json={"clave": "c"}).json()["id"]
    estado = lambda: c.get(f"/api/demo/alerta-en-vivo/estado?id={id_}", headers={"X-Grifter-Demo-Clave": "c"})  # noqa: E731
    assert estado().json() == {"id": id_, "estado": "esperando", "latencia_s": None}
    reloj[0] += 2.4
    cuerpo, cab = _entrega(PABLO, f"{id_}:re")
    assert c.post("/api/whatsapp/webhook", content=cuerpo, headers=cab).status_code == 200
    assert estado().json() == {"id": id_, "estado": "rechazado", "latencia_s": 2.4}
    assert enviados[-1]["text"]["body"].startswith("Rechazaste el pago")


def test_sin_firma_o_de_otro_numero_el_rechazo_no_cuenta(real):
    c, _, _ = real
    id_ = c.post("/api/demo/alerta-en-vivo", json={"clave": "c"}).json()["id"]
    cuerpo, cab = _entrega(PABLO, f"{id_}:re")
    assert c.post("/api/whatsapp/webhook", content=cuerpo, headers={**cab, "X-Webhook-Signature": "0" * 64}).status_code == 401
    cuerpo, cab = _entrega("56900000000", f"{id_}:re")   # otro número
    c.post("/api/whatsapp/webhook", content=cuerpo, headers=cab)
    r = c.get(f"/api/demo/alerta-en-vivo/estado?id={id_}", headers={"X-Grifter-Demo-Clave": "c"})
    assert r.json()["estado"] == "esperando"


def test_el_estado_pide_la_clave_y_no_existe_sin_la_variable(real, monkeypatch):
    c, _, _ = real
    id_ = c.post("/api/demo/alerta-en-vivo", json={"clave": "c"}).json()["id"]
    assert c.get(f"/api/demo/alerta-en-vivo/estado?id={id_}").status_code == 403
    assert c.get("/api/demo/alerta-en-vivo/estado?id=demo-0000", headers={"X-Grifter-Demo-Clave": "c"}).status_code == 404
    monkeypatch.delenv(en_vivo.VARIABLE)
    assert c.get(f"/api/demo/alerta-en-vivo/estado?id={id_}", headers={"X-Grifter-Demo-Clave": "c"}).status_code == 404
