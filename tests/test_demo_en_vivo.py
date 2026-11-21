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
    entorno = {"GRIFTER_DEMO_CLAVE": "clave-de-prueba", "KAPSO_API_KEY": LLAVE}
    monkeypatch.setattr(server, "demo_en_vivo", en_vivo.EnVivo(entorno, reloj=lambda: reloj[0], canal=canal))
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
    assert "Marta quiere pagar $650.000 a J. Contreras V." in texto and "0 de 1 aprobaciones" in texto
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
    falla = en_vivo.EnVivo({"GRIFTER_DEMO_CLAVE": "clave-de-prueba", "KAPSO_API_KEY": LLAVE}, canal=CanalFalso(falla=True))
    monkeypatch.setattr(server, "demo_en_vivo", falla)
    with caplog.at_level(logging.DEBUG):
        r = c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"})
    assert r.status_code == 502
    assert LLAVE not in r.text and LLAVE not in caplog.text
    ok = c.post("/api/demo/alerta-en-vivo", json={"clave": "clave-de-prueba"})   # ya pasó por el tope: otra instancia
    assert LLAVE not in ok.text


def test_sin_llaves_de_kapso_lo_dice_sin_mostrar_nada(monkeypatch):
    monkeypatch.setenv(en_vivo.VARIABLE, "1")
    monkeypatch.setattr(server, "demo_en_vivo", en_vivo.EnVivo({"GRIFTER_DEMO_CLAVE": "c"}))
    r = TestClient(server.app).post("/api/demo/alerta-en-vivo", json={"clave": "c"})
    assert r.status_code == 503 and "KAPSO_API_KEY" in r.text


def test_sin_clave_en_env_usa_una_de_un_solo_uso_por_arranque():
    a, b = en_vivo.EnVivo({}), en_vivo.EnVivo({})
    assert a.clave() and a.clave() != b.clave()
    assert a.clave_valida(a.clave()) and not a.clave_valida(b.clave()) and not a.clave_valida("")


def test_demo_js_solo_llama_con_whatsapp_1():
    js = (Path(server.DEMO) / "demo.js").read_text(encoding="utf-8")
    assert "api/demo/alerta-en-vivo" in js
    # La única llamada está dentro de la función que sale de inmediato si la URL no trae ?whatsapp=1.
    funcion = re.search(r"function avisarEnVivo\(\) \{(.*?)\n  \}", js, re.S)
    assert funcion, "falta avisarEnVivo en demo.js"
    cuerpo = funcion.group(1)
    assert re.search(r'if \(params\.get\("whatsapp"\) !== "1"[^)]*\) return;', cuerpo)
    assert cuerpo.index("return;") < cuerpo.index("api/demo/alerta-en-vivo")
    assert js.count("api/demo/alerta-en-vivo") == 1
