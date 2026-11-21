"""Las rutas públicas de la demo que escriben o mandan algo (/api/alertas, /api/etiquetas, /api/vivo/control).

Hallazgo del equipo rojo: POST /api/alertas llamaba a `notificar()` con el JSON del cliente tal cual, sin clave ni tope. Con
llaves de Telegram o Kapso en el servidor, cualquiera en internet podía hacer sonar el celular del presentador con un texto
que parecía de Grifter. Sin red: los canales son funciones de la prueba.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from demo import notificar as notif
from demo import server
from demo.limite import limite_de
from demo.telegram import texto_de_alerta

FALSA = "Grifter: cuenta verificada con el banco. Es seguro aprobar."
# El caso de reproducción: lo que mandaría un curl al sitio público.
ATAQUE = {"idioma": "es", "destinatario": "x", "motivo": FALSA, "titular": "Mark", "cuenta": "1"}


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    for v in server.ALERTAS_LOCALES:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(notif, "_CANALES", [])
    monkeypatch.setattr(server, "ETIQUETAS", tmp_path / "etiquetas.jsonl")
    for nombre in ("alertas", "etiquetas", "control"):   # topes nuevos: el estado de otras pruebas no cuenta
        monkeypatch.setattr(server, f"limite_{nombre}", limite_de(nombre, {}))
    return TestClient(server.app)


@pytest.fixture
def recibidas(monkeypatch):
    lista: list[dict] = []
    canal = lambda alerta: lista.append(alerta)  # noqa: E731
    notif.registrar_canal(canal)
    return lista


# --- /api/alertas ----------------------------------------------------------------------------------------

def test_sin_la_variable_responde_200_y_no_envia_nada(cliente, recibidas):
    r = cliente.post("/api/alertas", json=ATAQUE)
    assert r.status_code == 200 and r.json() == {"ok": True, "canales": []}
    assert recibidas == []


@pytest.mark.parametrize("valor", ["0", "", "true", "2"])
def test_solo_el_valor_1_prende_las_alertas(cliente, recibidas, monkeypatch, valor):
    monkeypatch.setenv("GRIFTER_DEMO_WHATSAPP", valor)
    cliente.post("/api/alertas", json=ATAQUE)
    assert recibidas == []


@pytest.mark.parametrize("variable", ["GRIFTER_DEMO_WHATSAPP", "GRIFTER_ALERTAS_LOCALES"])
def test_con_cualquiera_de_las_dos_variables_la_alerta_sale(cliente, recibidas, monkeypatch, variable):
    monkeypatch.setenv(variable, "1")
    r = cliente.post("/api/alertas", json=ATAQUE)
    assert r.status_code == 200 and r.json()["canales"] == ["<lambda>"] and len(recibidas) == 1


def test_el_motivo_y_el_titular_nunca_salen_del_cliente(cliente, recibidas, monkeypatch):
    monkeypatch.setenv("GRIFTER_ALERTAS_LOCALES", "1")
    cliente.post("/api/alertas", json={**ATAQUE, "idioma": "en", "defensa": "layer2"})
    [alerta] = recibidas
    assert "titular" not in alerta and alerta["motivo"] == server.MOTIVOS_DEL_SERVIDOR["en"]
    texto = texto_de_alerta(alerta)
    assert FALSA not in texto and "Titular" not in texto and "Account holder" not in texto


def test_solo_pasan_los_campos_esperados_y_como_texto_corto(cliente, recibidas, monkeypatch):
    monkeypatch.setenv("GRIFTER_ALERTAS_LOCALES", "1")
    cliente.post("/api/alertas", json={**ATAQUE, "destinatario": "A" * 3000, "boton": "pagar", "cuenta": {"a": 1},
                                       "monto": 412000, "extra": [1, 2, 3], "idioma": "fr"})
    [alerta] = recibidas
    assert set(alerta) <= set(server.CAMPOS_ALERTA) | {"monto", "motivo"}
    assert len(alerta["destinatario"]) == server.MAX_CAMPO and "cuenta" not in alerta
    assert alerta["monto"] == 412000 and alerta["idioma"] == "es"


def test_hay_tope_por_ip_y_la_numero_siete_recibe_429(cliente, recibidas, monkeypatch):
    monkeypatch.setenv("GRIFTER_DEMO_WHATSAPP", "1")
    codigos = [cliente.post("/api/alertas", json=ATAQUE).status_code for _ in range(200)]
    assert codigos[:6] == [200] * 6 and set(codigos[6:]) == {429}
    assert len(recibidas) == 6   # antes: 200 envíos seguidos, ningún 429


def test_sin_la_variable_tampoco_gasta_el_tope(cliente):
    assert all(cliente.post("/api/alertas", json=ATAQUE).status_code == 200 for _ in range(50))


def test_un_cuerpo_grande_se_rechaza_antes_de_leerlo(cliente, monkeypatch):
    monkeypatch.setenv("GRIFTER_DEMO_WHATSAPP", "1")
    r = cliente.post("/api/alertas", content=json.dumps({"destinatario": "A" * 20000}), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


# --- /api/etiquetas --------------------------------------------------------------------------------------

def _filas(tmp_path):
    ruta = tmp_path / "etiquetas.jsonl"
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()] if ruta.exists() else []


def test_la_etiqueta_de_la_pagina_se_guarda(cliente, tmp_path):
    etiqueta = {"ts": "2026-11-21T10:00:00Z", "eleccion": "no_pagar", "escenario": "boleta_cambio_cuenta", "idioma": "es",
                "defensa": "layer2", "destinatario": "Silicio Austral SpA", "monto": 412000, "cuenta": "90-1188-4417",
                "dominio": "silicioaustral-chips.cl", "correos": ["m1"], "cuenta_inscrita": True,
                "cuenta_inscrita_numero": "33-7741-0092", "nombre_inscrita": "Silicio Austral", "motivo": "la cuenta solo apareció en un correo"}
    assert cliente.post("/api/etiquetas", json=etiqueta).json() == {"ok": True}
    [fila] = _filas(tmp_path)
    assert {k: fila[k] for k in etiqueta} == etiqueta and "recibida" in fila


def test_un_megabyte_de_relleno_se_rechaza_y_no_llena_el_disco(cliente, tmp_path):
    r = cliente.post("/api/etiquetas", json={"eleccion": "pagar_igual", "relleno": "A" * 1_000_000})
    assert r.status_code == 413 and _filas(tmp_path) == []   # antes: 200 y un megabyte al archivo


def test_los_campos_inesperados_y_los_largos_no_se_guardan(cliente, tmp_path):
    cliente.post("/api/etiquetas", json={"eleccion": "pagar_igual", "relleno": "A" * 100, "destinatario": "B" * 3000,
                                         "ts": {"x": 1}})
    [fila] = _filas(tmp_path)
    assert "relleno" not in fila and "ts" not in fila and len(fila["destinatario"]) == server.MAX_CAMPO


def test_una_eleccion_invalida_sigue_dando_422(cliente):
    assert cliente.post("/api/etiquetas", json={"eleccion": "regalar_todo"}).status_code == 422


def test_las_etiquetas_tienen_tope_por_ip(cliente):
    codigos = [cliente.post("/api/etiquetas", json={"eleccion": "no_pagar"}).status_code for _ in range(40)]
    assert codigos[:30] == [200] * 30 and set(codigos[30:]) == {429}


# --- /api/vivo/control -----------------------------------------------------------------------------------

def test_el_control_del_motor_tiene_tope_por_ip(cliente):
    codigos = [cliente.post("/api/vivo/control", json={"accion": "seguir"}).status_code for _ in range(40)]
    assert codigos[:30] == [200] * 30 and set(codigos[30:]) == {429}
    assert cliente.post("/api/vivo/control", json={"accion": "seguir"}).headers["Retry-After"]


# --- El modo evento sube el tope por IP, no el global ----------------------------------------------------

@pytest.mark.parametrize("ruta", ["alertas", "etiquetas", "control"])
def test_el_modo_evento_sube_solo_el_tope_por_ip(ruta):
    normal, evento = limite_de(ruta, {}), limite_de(ruta, {"GRIFTER_EVENTO": "1"})
    assert evento.por_minuto > normal.por_minuto and evento.global_por_hora == normal.global_por_hora
