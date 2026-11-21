"""/mcp de la demo en modo público (GRIFTER_MCP_PUBLICO=1): sin token, para ChatGPT en modo desarrollador.

Acotado: detrás solo la tienda ficticia (ni banco, ni Stripe, ni MCP remotos, ni credenciales), tope por IP y
cuerpo chico. Sin red externa: todo en 127.0.0.1.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import yaml
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import demo.server as servidor
from demo.limite import LimitePorIP
from scamshield.mcp.proxy import cargar_config
from scamshield.mcp.servidor_proveedor import CUENTA_ESTAFADOR, CUENTA_LEGITIMA
from tests.test_mcp_proxy import _filas, servir_asgi
from tests.test_mcp_remoto import CABECERAS_MCP, INICIO, _config_tienda

HERRAMIENTAS_TIENDA = {"buscar_productos", "crear_checkout", "pagar_checkout"}


@pytest.fixture
def publico(tmp_path, monkeypatch):
    monkeypatch.setenv("GRIFTER_MCP_PUBLICO", "1")
    monkeypatch.delenv("GRIFTER_MCP_TOKEN", raising=False)
    monkeypatch.setenv("GRIFTER_MCP_CONFIG", str(_config_tienda(tmp_path)))
    monkeypatch.setenv("STRIPE_TEST_KEY", "sk_test_no-se-usa-en-modo-publico")
    monkeypatch.setattr(servidor, "limite_mcp", LimitePorIP(por_minuto=1000, por_hora=10000, global_por_hora=10000))
    return tmp_path


def _yaml(carpeta: Path, servidores: dict) -> Path:
    ruta = carpeta / "otro.yaml"
    ruta.write_text(yaml.safe_dump({"servidores": servidores}), encoding="utf-8")
    return ruta


def test_el_modo_publico_solo_admite_la_tienda_ficticia(tmp_path):
    servidor.validar_config_publica(cargar_config(_config_tienda(tmp_path)))
    servidor.validar_config_publica(cargar_config(servidor.CONFIG_MCP_POR_DEFECTO))
    malos = [
        {"banco": {"comando": "python", "args": ["-m", "scamshield.mcp.servidor_banco"]}},
        {"tienda": {"url": "https://tienda.example/mcp"}},
        {"tienda": {"comando": "python", "args": ["-m", "scamshield.mcp.servidor_tienda"],
                    "env": {"STRIPE_TEST_KEY": "sk_test_x"}}},
        {"tienda": {"comando": "node", "args": ["-m", "scamshield.mcp.servidor_tienda"]}},
        {},
    ]
    for servidores in malos:
        with pytest.raises(ValueError):
            servidor.validar_config_publica(cargar_config(_yaml(tmp_path, servidores)))


def test_publico_con_otra_config_no_arranca(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GRIFTER_MCP_PUBLICO", "1")
    monkeypatch.setenv("GRIFTER_MCP_CONFIG", str(_yaml(tmp_path, {
        "banco": {"comando": "python", "args": ["-m", "scamshield.mcp.servidor_banco"]}})))
    with pytest.raises(ValueError, match="tienda ficticia"):
        with TestClient(servidor.app):
            pass


def test_publico_sin_token_sirve_solo_la_tienda_y_retiene_el_checkout_desviado(publico):
    async def correr() -> dict:
        out = {}
        async with servir_asgi(servidor.app) as base:
            async with httpx.AsyncClient(timeout=30) as cliente:   # sin Authorization
                async with streamable_http_client(base + "/mcp", http_client=cliente) as (read, write, _):
                    async with ClientSession(read, write) as sesion:
                        await sesion.initialize()
                        out["herramientas"] = {t.name for t in (await sesion.list_tools()).tools}
                        orden = (await sesion.call_tool("crear_checkout", {"sku": "SA-3NM", "cantidad": 10})).content[0].text
                        folio = orden.split()[1].rstrip(":")
                        out["desviado"] = await sesion.call_tool(
                            "pagar_checkout", {"orden": folio, "cuenta": CUENTA_ESTAFADOR, "monto": 412_000})
                        out["inscrito"] = await sesion.call_tool(
                            "pagar_checkout", {"orden": folio, "cuenta": CUENTA_LEGITIMA, "monto": 412_000})
        return out

    out = asyncio.run(asyncio.wait_for(correr(), 120))
    assert out["herramientas"] == HERRAMIENTAS_TIENDA   # nada más que la tienda: ni banco ni Stripe
    assert out["desviado"].isError and "Grifter" in out["desviado"].content[0].text
    assert not out["inscrito"].isError
    assert [p["cuenta"] for p in _filas(publico / "tienda.jsonl")] == [CUENTA_LEGITIMA]
    eventos = [e["evento"] for e in _filas(publico / "eventos.jsonl")]
    assert eventos[0] == "latido_arranque"   # la demo arma los ganchos de la CLI (#102)
    assert (publico / ".grifter_aprobada.json").exists()   # integridad: la política inicial quedó registrada


def test_publico_tope_de_cuerpo_y_por_ip(publico, monkeypatch):
    monkeypatch.setattr(servidor, "limite_mcp", LimitePorIP(por_minuto=2, por_hora=100, global_por_hora=100))
    monkeypatch.setenv("GRIFTER_PROXY_CONFIABLE", "1")

    async def correr() -> dict:
        out = {}
        async with servir_asgi(servidor.app) as base:
            async with httpx.AsyncClient(timeout=30) as http:
                url = base + "/mcp"
                grande = {**INICIO, "params": {**INICIO["params"], "relleno": "x" * (servidor.MAX_BYTES_MCP + 1)}}
                out["grande"] = (await http.post(url, json=grande, headers=CABECERAS_MCP)).status_code
                de_a = {**CABECERAS_MCP, "X-Forwarded-For": "203.0.113.7"}
                out["a"] = [(await http.post(url, json=INICIO, headers=de_a)).status_code for _ in range(3)]
                de_b = {**CABECERAS_MCP, "X-Forwarded-For": "203.0.113.8"}
                out["b"] = (await http.post(url, json=INICIO, headers=de_b)).status_code
        return out

    out = asyncio.run(asyncio.wait_for(correr(), 120))
    assert out["grande"] == 413
    assert out["a"] == [200, 200, 429]
    assert out["b"] == 200   # otra IP tiene su propio tope
