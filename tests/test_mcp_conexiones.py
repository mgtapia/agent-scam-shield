"""Un intento fallido cierra sus contextos antes de volver a conectar los MCP."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from types import SimpleNamespace

import anyio
import mcp.types as types
import pytest
import yaml

from scamshield.mcp import proxy
from scamshield.mcp.integridad import Integridad


@pytest.mark.parametrize("fallo", ["initialize", "list_tools"])
def test_fallo_parcial_cierra_y_olvida_las_conexiones_antes_de_reintentar(tmp_path, monkeypatch, fallo):
    ruta = tmp_path / "grifter.yaml"
    ruta.write_text(yaml.safe_dump({"registro": None, "servidores": {
        "primero": {"comando": "primero"}, "segundo": {"comando": "segundo"},
    }}), encoding="utf-8")
    aperturas, cierres = [], []
    fallos = []

    @asynccontextmanager
    async def stdio(parametros, **kwargs):
        tarea = asyncio.current_task()
        aperturas.append(parametros.command)
        # AnyIO exige que el contexto se cierre en la tarea que lo abrió.
        async with anyio.create_task_group():
            try:
                yield parametros.command, None
            finally:
                assert asyncio.current_task() is tarea
                cierres.append(parametros.command)

    class Sesion:
        def __init__(self, nombre, write):
            self.nombre = nombre

        async def __aenter__(self):
            self.tarea = asyncio.current_task()
            return self

        async def __aexit__(self, *exc):
            assert asyncio.current_task() is self.tarea

        def _fallar(self, etapa):
            if self.nombre == "segundo" and etapa == fallo and not fallos:
                fallos.append(etapa)
                raise RuntimeError("fallo transitorio del segundo MCP")

        async def initialize(self):
            self._fallar("initialize")

        async def list_tools(self):
            self._fallar("list_tools")
            return SimpleNamespace(tools=[types.Tool(name="leer", description="Lectura", inputSchema={})])

    class Dueno:
        respuesta = None

        def pedir(self, cambio):
            pass

        def estado(self):
            return self.respuesta

    monkeypatch.setattr(proxy, "stdio_client", stdio)
    monkeypatch.setattr(proxy, "ClientSession", Sesion)
    dueno = Dueno()
    grifter = proxy.Grifter(proxy.cargar_config(ruta), integridad=Integridad(ruta), aprobador=dueno)
    listar = grifter.servidor_mcp().request_handlers[types.ListToolsRequest]

    async def correr():
        async with AsyncExitStack() as pila:
            await grifter.conectar(pila)
            assert aperturas == []
            dueno.respuesta = True
            with pytest.raises(Exception):
                await listar(types.ListToolsRequest(method="tools/list"))
            assert fallos == [fallo]
            assert aperturas == ["primero", "segundo"]
            assert cierres == ["segundo", "primero"]
            assert grifter.sesiones == {} and grifter.rutas == {} and grifter.herramientas == []
            assert not grifter._conexion_iniciada

            resultado = await listar(types.ListToolsRequest(method="tools/list"))
            assert [t.name for t in resultado.root.tools] == ["leer", "segundo_leer"]
            assert set(grifter.sesiones) == {"primero", "segundo"}
            assert aperturas == ["primero", "segundo", "primero", "segundo"]
            assert cierres == ["segundo", "primero"]

    asyncio.run(asyncio.wait_for(correr(), 10))
    assert cierres == ["segundo", "primero", "segundo", "primero"]
