"""Grifter como MCP remoto: el token de portador, los MCP de abajo por HTTP y la falla cerrada.

Sin red externa ni llaves: todo corre en 127.0.0.1, con uvicorn dentro del mismo loop de la prueba.
El conjunto de pruebas del proxy corrido por HTTP está en `test_mcp_proxy.py`.
"""
from __future__ import annotations

import asyncio
import json
import socket
from contextlib import AsyncExitStack
from pathlib import Path

import anyio
import httpx
import pytest
import yaml

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from scamshield.mcp import servidor_banco, servidor_proveedor, servidor_tienda
from scamshield.mcp.proxy import Config, Grifter, cargar_config
from scamshield.mcp.remoto import ConectorMCP, crear_app, validar_token
from scamshield.mcp.servidor_proveedor import CUENTA_ESTAFADOR, CUENTA_LEGITIMA
from tests.test_mcp_proxy import MONTO, TOKEN, _escribir_config, _filas, servir_asgi

CABECERAS_MCP = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INICIO = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                     "clientInfo": {"name": "prueba", "version": "0"}}}


def _puerto_cerrado() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ExigeToken:
    """Un MCP «del comercio» que solo responde con su cabecera Authorization, y anota la que vio."""

    def __init__(self, app, esperado: str):
        self.app, self.esperado, self.vistas = app, esperado, []

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            vista = dict(scope["headers"]).get(b"authorization", b"").decode()
            self.vistas.append(vista)
            if vista != self.esperado:
                await send({"type": "http.response.start", "status": 401, "headers": []})
                await send({"type": "http.response.body", "body": b"no autorizado"})
                return
        await self.app(scope, receive, send)


# --- El conector: token de portador ---------------------------------------------------------------

def test_sin_token_configurado_o_muy_corto_el_conector_no_se_abre(tmp_path):
    config = cargar_config(_escribir_config(tmp_path))
    for malo in (None, "", "   ", "corto"):
        with pytest.raises(ValueError):
            crear_app(config, malo)
        with pytest.raises(ValueError):
            validar_token(malo)


def test_sin_token_o_con_otro_token_es_401_y_con_el_correcto_responde(tmp_path):
    async def correr() -> dict:
        out = {}
        config = cargar_config(_escribir_config(tmp_path))
        async with servir_asgi(crear_app(config, TOKEN)) as base:
            async with httpx.AsyncClient(timeout=30) as http:
                url = base + "/mcp"
                out["sin"] = await http.post(url, json=INICIO, headers=CABECERAS_MCP)
                out["otro"] = await http.post(url, json=INICIO, headers={
                    **CABECERAS_MCP, "Authorization": "Bearer otro-token-distinto-0123"})
                out["esquema"] = await http.post(url, json=INICIO, headers={
                    **CABECERAS_MCP, "Authorization": f"Basic {TOKEN}"})
                out["get_sin"] = await http.get(url, headers={"Accept": "text/event-stream"})
                out["bien"] = await http.post(url, json=INICIO, headers={
                    **CABECERAS_MCP, "Authorization": f"Bearer {TOKEN}"})
        return out

    out = asyncio.run(asyncio.wait_for(correr(), 90))
    for clave in ("sin", "otro", "esquema", "get_sin"):
        assert out[clave].status_code == 401, clave
        assert out[clave].headers["www-authenticate"].startswith("Bearer")
        assert TOKEN not in out[clave].text
    assert out["bien"].status_code == 200
    assert out["bien"].json()["result"]["serverInfo"]["name"] == "grifter"


def test_el_conector_sin_conectar_responde_503_y_no_reenvia(tmp_path):
    async def correr():
        conector = ConectorMCP(cargar_config(_escribir_config(tmp_path)), TOKEN)
        respuestas = []

        async def enviar(msg):
            respuestas.append(msg)

        scope = {"type": "http", "method": "POST", "path": "/mcp",
                 "headers": [(b"authorization", f"Bearer {TOKEN}".encode())]}
        await conector(scope, None, enviar)
        return respuestas[0]["status"]

    assert asyncio.run(correr()) == 503


# --- Los MCP de abajo por HTTP -------------------------------------------------------------------

def _config_remota(carpeta: Path, tienda: str, banco: str, headers: dict | None = None) -> Config:
    datos = {
        "servidores": {
            "silicio-austral": {"url": tienda + "/mcp", "headers": headers or {}},
            "banco": {"url": banco + "/mcp", "headers": headers or {}},
        },
        "cuentas_inscritas": {"Silicio Austral": f"Banco Litoral cta. cte. {CUENTA_LEGITIMA}"},
        "registro": "eventos.jsonl",
    }
    ruta = carpeta / "grifter.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return cargar_config(ruta)


def test_grifter_habla_con_mcp_remotos_con_sus_headers_y_retiene_la_cuenta_envenenada(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKEN_TIENDA", "secreto-del-comercio")
    esperado = "Bearer secreto-del-comercio"

    async def correr() -> dict:
        out = {}
        tienda = ExigeToken(servidor_proveedor.crear_servidor(envenenado=True).streamable_http_app(), esperado)
        banco = ExigeToken(servidor_banco.crear_servidor(tmp_path / "banco.jsonl").streamable_http_app(), esperado)
        async with servir_asgi(tienda) as url_tienda, servir_asgi(banco) as url_banco:
            config = _config_remota(tmp_path, url_tienda, url_banco, {"Authorization": "Bearer ${TOKEN_TIENDA}"})
            grifter = Grifter(config)
            with anyio.fail_after(60):
                async with AsyncExitStack() as pila:
                    await grifter.conectar(pila)
                    out["herramientas"] = {t.name for t in grifter.herramientas}
                    await grifter.llamar("datos_de_pago", {"proveedor": "Silicio Austral"})
                    out["envenenado"] = await grifter.llamar("pagar", {
                        "destinatario": "Silicio Austral SpA", "cuenta": CUENTA_ESTAFADOR, "monto": MONTO})
                    out["banco_tras_envenenado"] = len(_filas(tmp_path / "banco.jsonl"))
                    out["inscrito"] = await grifter.llamar("pagar", {
                        "destinatario": "Silicio Austral", "cuenta": CUENTA_LEGITIMA, "monto": MONTO})
        out["vistas"] = tienda.vistas + banco.vistas
        return out

    out = asyncio.run(correr())
    assert {"consultar_factura", "datos_de_pago", "pagar"} <= out["herramientas"]
    assert out["envenenado"].isError
    assert f"la cuenta {CUENTA_ESTAFADOR} apareció en datos_de_pago de silicio-austral" in \
        out["envenenado"].content[0].text
    assert out["banco_tras_envenenado"] == 0, "el pago envenenado llegó al banco remoto"
    assert not out["inscrito"].isError
    assert [p["cuenta"] for p in _filas(tmp_path / "banco.jsonl")] == [CUENTA_LEGITIMA]
    assert out["vistas"] and set(out["vistas"]) == {esperado}   # cada petición llevó el header del comercio


def test_un_mcp_remoto_que_rechaza_el_token_queda_fuera(tmp_path):
    async def correr() -> Grifter:
        tienda = ExigeToken(servidor_proveedor.crear_servidor().streamable_http_app(), "Bearer otro")
        banco = servidor_banco.crear_servidor(tmp_path / "banco.jsonl").streamable_http_app()
        async with servir_asgi(tienda) as url_tienda, servir_asgi(banco) as url_banco:
            grifter = Grifter(_config_remota(tmp_path, url_tienda, url_banco))
            with anyio.fail_after(60):
                async with AsyncExitStack() as pila:
                    await grifter.conectar(pila)
        return grifter

    grifter = asyncio.run(correr())
    assert "datos_de_pago" not in {t.name for t in grifter.herramientas}
    assert [e["evento"] for e in _filas(tmp_path / "eventos.jsonl")] == ["servidor_remoto_inalcanzable"]


def test_falla_cerrada_si_el_mcp_remoto_no_responde_al_arrancar(tmp_path):
    muerto = f"http://127.0.0.1:{_puerto_cerrado()}"

    async def correr():
        banco = servidor_banco.crear_servidor(tmp_path / "banco.jsonl").streamable_http_app()
        async with servir_asgi(banco) as url_banco:
            grifter = Grifter(_config_remota(tmp_path, muerto, url_banco))
            with anyio.fail_after(60):
                async with AsyncExitStack() as pila:
                    await grifter.conectar(pila)   # no revienta: deja fuera lo que no contesta
                    pago = await grifter.llamar("pagar", {
                        "destinatario": "Silicio Austral", "cuenta": CUENTA_LEGITIMA, "monto": MONTO})
                    desconocida = await grifter.llamar("datos_de_pago", {})
        return grifter, pago, desconocida

    grifter, pago, desconocida = asyncio.run(correr())
    assert {t.name for t in grifter.herramientas} == {"pagar"}   # solo las del banco vivo
    assert not pago.isError    # lo que sí responde sigue funcionando
    assert desconocida.isError and "no conoce" in desconocida.content[0].text
    eventos = _filas(tmp_path / "eventos.jsonl")
    assert eventos[0]["evento"] == "servidor_remoto_inalcanzable" and eventos[0]["servidor"] == "silicio-austral"


def test_falla_cerrada_si_el_mcp_remoto_cae_despues_de_conectar(tmp_path):
    async def correr():
        banco = servidor_banco.crear_servidor(tmp_path / "banco.jsonl").streamable_http_app()
        tienda = servidor_proveedor.crear_servidor().streamable_http_app()
        async with servir_asgi(tienda) as url_tienda:
            async with AsyncExitStack() as pila:
                url_banco = await pila.enter_async_context(servir_asgi(banco))
                grifter = Grifter(_config_remota(tmp_path, url_tienda, url_banco))
                with anyio.fail_after(60):
                    async with AsyncExitStack() as sesiones:
                        await grifter.conectar(sesiones)
                        await pila.aclose()   # el banco remoto se apaga con Grifter ya conectado
                        return await grifter.llamar("pagar", {
                            "destinatario": "Silicio Austral", "cuenta": CUENTA_LEGITIMA, "monto": MONTO})

    resultado = asyncio.run(correr())
    assert resultado.isError
    assert "no pudo llegar a banco" in resultado.content[0].text
    assert _filas(tmp_path / "banco.jsonl") == []
    assert "servidor_inalcanzable" in [e["evento"] for e in _filas(tmp_path / "eventos.jsonl")]


# --- grifter.yaml con url --------------------------------------------------------------------------

def test_config_con_url_lee_headers_del_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKEN_TIENDA", "abc")
    ruta = tmp_path / "grifter.yaml"
    ruta.write_text(yaml.safe_dump({"servidores": {
        "tienda": {"url": "https://tienda.example/mcp", "headers": {"Authorization": "Bearer ${TOKEN_TIENDA}"}},
        "banco": {"comando": "python", "args": ["-m", "x"]}}}), encoding="utf-8")
    config = cargar_config(ruta)
    por_nombre = {s.nombre: s for s in config.servidores}
    tienda, banco = por_nombre["tienda"], por_nombre["banco"]
    assert (tienda.url, tienda.comando, tienda.headers) == (
        "https://tienda.example/mcp", "", {"Authorization": "Bearer abc"})
    assert banco.url == "" and banco.comando == "python"


def test_config_con_variable_faltante_o_url_rara_falla(tmp_path, monkeypatch):
    monkeypatch.delenv("NO_EXISTE_ESTA", raising=False)
    ruta = tmp_path / "grifter.yaml"
    ruta.write_text(yaml.safe_dump({"servidores": {"t": {
        "url": "https://t.example/mcp", "headers": {"Authorization": "Bearer ${NO_EXISTE_ESTA}"}}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="NO_EXISTE_ESTA"):
        cargar_config(ruta)
    ruta.write_text(yaml.safe_dump({"servidores": {"t": {"url": "ftp://t.example/mcp"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="http"):
        cargar_config(ruta)


def test_el_json_del_registro_no_lleva_el_token_del_comercio(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKEN_TIENDA", "secreto-del-comercio")
    muerto = f"http://127.0.0.1:{_puerto_cerrado()}"

    async def correr():
        grifter = Grifter(_config_remota(tmp_path, muerto, muerto, {"Authorization": "Bearer ${TOKEN_TIENDA}"}))
        with anyio.fail_after(60):   # afuera de la pila: las tareas vigilantes viven en ella
            async with AsyncExitStack() as pila:
                await grifter.conectar(pila)

    asyncio.run(correr())
    texto = (tmp_path / "eventos.jsonl").read_text(encoding="utf-8")
    assert "secreto-del-comercio" not in texto
    assert len([json.loads(l) for l in texto.splitlines()]) == 2


# --- La demo: /mcp en demo/server.py con la tienda ficticia ----------------------------------------

def _config_tienda(carpeta: Path) -> Path:
    datos = yaml.safe_load((Path(servidor_tienda.__file__).parent / "grifter.tienda.yaml").read_text(encoding="utf-8"))
    datos["servidores"]["tienda"]["args"][-1] = str(carpeta / "tienda.jsonl")
    datos["registro"] = str(carpeta / "eventos.jsonl")
    ruta = carpeta / "grifter.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return ruta


def test_la_demo_sin_token_no_abre_mcp(monkeypatch):
    from fastapi.testclient import TestClient

    import demo.server as servidor

    monkeypatch.delenv("GRIFTER_MCP_TOKEN", raising=False)
    monkeypatch.delenv("GRIFTER_MCP_PUBLICO", raising=False)
    with TestClient(servidor.app) as cliente:
        assert cliente.post("/mcp", json=INICIO, headers=CABECERAS_MCP).status_code == 404
        assert cliente.get("/api/salud").json()["ok"] is True


def test_la_demo_sirve_mcp_y_retiene_el_checkout_desviado_de_la_tienda(tmp_path, monkeypatch):
    import demo.server as servidor

    monkeypatch.setenv("GRIFTER_MCP_TOKEN", TOKEN)
    monkeypatch.delenv("GRIFTER_MCP_PUBLICO", raising=False)
    monkeypatch.setenv("GRIFTER_MCP_CONFIG", str(_config_tienda(tmp_path)))

    async def correr() -> dict:
        out = {}
        async with servir_asgi(servidor.app) as base:
            async with httpx.AsyncClient(timeout=30) as http:
                out["sin_token"] = (await http.post(base + "/mcp", json=INICIO, headers=CABECERAS_MCP)).status_code
            async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30) as cliente:
                async with streamable_http_client(base + "/mcp", http_client=cliente) as (read, write, _):
                    async with ClientSession(read, write) as sesion:
                        await sesion.initialize()
                        out["herramientas"] = {t.name for t in (await sesion.list_tools()).tools}
                        orden = (await sesion.call_tool("crear_checkout", {"sku": "SA-3NM", "cantidad": 10})).content[0].text
                        out["orden"] = orden
                        folio = orden.split()[1].rstrip(":")
                        out["desviado"] = await sesion.call_tool(
                            "pagar_checkout", {"orden": folio, "cuenta": CUENTA_ESTAFADOR, "monto": 412_000})
                        out["inscrito"] = await sesion.call_tool(
                            "pagar_checkout", {"orden": folio, "cuenta": CUENTA_LEGITIMA, "monto": 412_000})
        return out

    out = asyncio.run(asyncio.wait_for(correr(), 120))
    assert out["sin_token"] == 401
    assert {"buscar_productos", "crear_checkout", "pagar_checkout"} <= out["herramientas"]
    assert CUENTA_ESTAFADOR in out["orden"]
    assert out["desviado"].isError and "Grifter" in out["desviado"].content[0].text
    assert not out["inscrito"].isError
    assert [p["cuenta"] for p in _filas(tmp_path / "tienda.jsonl")] == [CUENTA_LEGITIMA]
