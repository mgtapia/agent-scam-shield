"""Los MCP remotos del comercio, por streamable HTTP: el lado de abajo de Grifter.

En `grifter.yaml` un servidor con `url` (y `headers`, que pueden traer `${VAR}` del entorno) se
conecta por HTTP en vez de levantarse como proceso stdio.

**Una tarea vigilante por servidor remoto.** El cliente HTTP del SDK corre cada petición como tarea
hija de su propio grupo; si el comercio responde 401, se cae o deja de contestar, ese grupo cancela a
la tarea que lo abrió. Si esa tarea fuera la de Grifter, un comercio caído tumbaría todo el proxy (o
todo el ciclo de vida de `/mcp`). Por eso cada conexión vive en su propia tarea, que abre y cierra
sus contextos ella misma y nunca deja escapar un error: lo anota y se termina.

**Falla cerrada:**
- si el comercio no responde al arrancar, sus herramientas no se exponen y nada se le reenvía;
- si cae después, la sesión se cierra y cada llamada pendiente o nueva termina en error
  (`Grifter.llamar` lo convierte en «no pudo llegar», sin inventar un resultado).
"""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

if TYPE_CHECKING:   # solo para los tipos: proxy.py importa este módulo
    from .proxy import Grifter, ServidorAbajo

log = logging.getLogger("grifter")

TIEMPO_CONEXION_S = 15   # conectar y saludar a un MCP remoto del comercio
TIEMPO_LLAMADA_S = 60    # esperar la respuesta de una herramienta remota


class ConexionCaida(ConnectionError):
    """El MCP remoto del comercio se cayó o cortó la conexión: la llamada no se completó."""


class SesionRemota:
    """La sesión con un MCP remoto, que sabe si su conexión sigue viva.

    El SDK no avisa a la llamada pendiente cuando la conexión se corta por cancelación (queda
    esperando hasta su tope de tiempo). Esta envoltura corre cada llamada contra el aviso de caída:
    si la conexión muere, la llamada termina enseguida en `ConexionCaida`, sin resultado inventado.
    """

    def __init__(self, nombre: str, sesion: ClientSession):
        self.nombre, self._sesion, self.caida = nombre, sesion, anyio.Event()

    def __getattr__(self, atributo: str) -> Any:   # list_tools y el resto, tal cual
        return getattr(self._sesion, atributo)

    async def call_tool(self, *args: Any, **kwargs: Any) -> Any:
        if self.caida.is_set():
            raise ConexionCaida(f"se cortó la conexión con {self.nombre}")
        salida: dict[str, Any] = {}
        async with anyio.create_task_group() as tg:
            async def llamar() -> None:
                try:
                    salida["resultado"] = await self._sesion.call_tool(*args, **kwargs)
                except Exception as e:   # se relanza afuera, sin envolverlo en un ExceptionGroup
                    salida["error"] = e
                tg.cancel_scope.cancel()

            async def esperar_caida() -> None:
                await self.caida.wait()
                tg.cancel_scope.cancel()

            tg.start_soon(llamar)
            tg.start_soon(esperar_caida)
        if "error" in salida:
            raise salida["error"]
        if "resultado" not in salida:
            raise ConexionCaida(f"se cortó la conexión con {self.nombre} durante la llamada")
        return salida["resultado"]


async def _grupo(grifter: "Grifter", pila: AsyncExitStack) -> anyio.abc.TaskGroup:
    """El grupo de tareas vigilantes de este Grifter, abierto en `pila` (se cancela al cerrarla)."""
    grupo = getattr(grifter, "_vigilantes", None)
    if grupo is None:
        grupo = await pila.enter_async_context(anyio.create_task_group())
        pila.callback(setattr, grifter, "_vigilantes", None)   # al cerrar, un conectar nuevo abre otro grupo
        pila.callback(grupo.cancel_scope.cancel)   # LIFO: cancela a las vigilantes antes de esperarlas
        grifter._vigilantes = grupo
    return grupo


async def conectar_remoto(grifter: "Grifter", pila: AsyncExitStack, s: "ServidorAbajo") -> bool:
    """Conecta un MCP remoto y expone sus herramientas. Devuelve False si quedó fuera (falla cerrada)."""
    grupo = await _grupo(grifter, pila)
    listo = anyio.Event()
    estado: dict[str, Any] = {"ok": False}
    grupo.start_soon(_vigilar, grifter, s, listo, estado, name=f"grifter-remoto-{s.nombre}")
    await listo.wait()
    return estado["ok"]


async def _vigilar(grifter: "Grifter", s: "ServidorAbajo", listo: anyio.Event, estado: dict) -> None:
    remota = None
    try:
        async with httpx.AsyncClient(headers=s.headers or None,
                                     timeout=httpx.Timeout(TIEMPO_LLAMADA_S, connect=TIEMPO_CONEXION_S)) as cliente, \
                streamable_http_client(s.url, http_client=cliente) as (read, write, _), \
                ClientSession(read, write, read_timeout_seconds=timedelta(seconds=TIEMPO_LLAMADA_S)) as sesion:
            remota = SesionRemota(s.nombre, sesion)
            with anyio.fail_after(TIEMPO_CONEXION_S):
                await sesion.initialize()
                await grifter._exponer(s.nombre, remota)
            estado["ok"] = True
            listo.set()
            await anyio.sleep_forever()   # hasta que Grifter se apague (cancelación) o el comercio caiga
    except Exception as e:   # incluye el ExceptionGroup del cliente HTTP; la cancelación sigue de largo
        if not estado["ok"]:
            grifter._olvidar(s.nombre)
            log.error("el MCP remoto %s no respondió (%s): sus herramientas no se exponen",
                      s.nombre, type(e).__name__)
            grifter._registrar("servidor_remoto_inalcanzable", servidor=s.nombre, error=type(e).__name__)
        else:
            log.error("se cortó la conexión con el MCP remoto %s (%s): sus llamadas fallan cerradas",
                      s.nombre, type(e).__name__)
            grifter._registrar("servidor_remoto_caido", servidor=s.nombre, error=type(e).__name__)
    finally:
        if remota is not None:
            remota.caida.set()
        listo.set()
