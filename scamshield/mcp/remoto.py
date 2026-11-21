"""Grifter como conector MCP remoto: streamable HTTP en `/mcp`, con token de portador.

Un agente remoto se conecta a la URL de Grifter (`https://tu-host/mcp`) en vez de la del comercio. Grifter recibe
las llamadas, aplica las mismas capas que por stdio y recién entonces las reenvía a los MCP de
abajo (por stdio o por HTTP, ver `grifter.yaml`).

- **Autenticación del conector:** un token de portador (`Authorization: Bearer <token>`), el de
  `GRIFTER_MCP_TOKEN`. Es lo mínimo para una demo y sirve a los clientes que dejan poner una cabecera
  (Claude Code, las APIs, el MCP Inspector). ChatGPT (modo desarrollador) y Claude.ai solo ofrecen OAuth
  o nada: para ellos, y en producción, corresponde OAuth 2.1 (pendiente, ver docs/mcp.md). Sin token configurado, el endpoint no
  arranca, y sin el token correcto responde 401 antes de tocar nada.
- **Las credenciales del comercio y del banco** viven en Grifter (los `headers` de `grifter.yaml`,
  que pueden venir de variables de entorno con `${VAR}`), no en ChatGPT ni en Claude.ai.
- **Sin estado por sesión:** cada petición es independiente (`stateless`), así Render o cualquier
  balanceador sirve. La guardia (qué se leyó y de dónde), el tope de alertas y el registro son los
  de todo el proceso: pensado para un dueño, no para varios clientes a la vez.

Uso: GRIFTER_MCP_TOKEN=... python -m scamshield.mcp.proxy --config grifter.yaml --http --puerto 8766
Para montarlo en otro servidor ASGI (como `demo/server.py`): `ConectorMCP`, ver más abajo.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Optional

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from .proxy import Config, Escalar, Grifter, escalar_por_defecto

log = logging.getLogger("grifter")

RUTA = "/mcp"
VARIABLE_TOKEN = "GRIFTER_MCP_TOKEN"
LARGO_MINIMO_TOKEN = 16


def validar_token(token: Optional[str]) -> str:
    """El token de portador, o ValueError. Falta o es corto: el endpoint no se abre."""
    token = (token or "").strip()
    if not token:
        raise ValueError(f"Falta {VARIABLE_TOKEN}: Grifter no abre /mcp sin un token de portador.")
    if len(token) < LARGO_MINIMO_TOKEN:
        raise ValueError(f"{VARIABLE_TOKEN} es muy corto: usa al menos {LARGO_MINIMO_TOKEN} caracteres.")
    return token


def _token_del_pedido(scope: Scope) -> str:
    for nombre, valor in scope.get("headers", []):
        if nombre == b"authorization":
            esquema, _, resto = valor.decode("latin-1").partition(" ")
            return resto.strip() if esquema.lower() == "bearer" else ""
    return ""


async def _responder(send: Send, estado: int, cuerpo: dict[str, Any], extra: Optional[list] = None) -> None:
    datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    cabeceras = [(b"content-type", b"application/json; charset=utf-8"),
                 (b"content-length", str(len(datos)).encode()), *(extra or [])]
    await send({"type": "http.response.start", "status": estado, "headers": cabeceras})
    await send({"type": "http.response.body", "body": datos})


class ConectorMCP:
    """Grifter detrás de HTTP: una app ASGI para `/mcp` y el ciclo de vida de lo que lleva abajo.

    Se usa como `async with conector:` (conecta los MCP de abajo y arranca el gestor de sesiones) y se
    monta como ASGI en la ruta `/mcp`. Falla cerrada: sin el token correcto, 401; si todavía no está
    conectado, 503; si algo revienta, nada se reenvía.
    """

    def __init__(self, config: Config, token: Optional[str], escalar: Escalar = escalar_por_defecto,
                 grifter: Optional[Grifter] = None, publico: bool = False):
        # `publico`: sin token, para ChatGPT en modo desarrollador (OAuth o nada). Quien lo prende responde por lo
        # que va detrás: la demo lo permite solo con la tienda ficticia, con tope por IP y cuerpo chico.
        self.publico = publico
        self._token = b"" if publico else validar_token(token).encode("utf-8")
        self.grifter = grifter if grifter is not None else Grifter(config, escalar)
        self._gestor: Optional[StreamableHTTPSessionManager] = None
        self._pila: Optional[AsyncExitStack] = None

    async def __aenter__(self) -> "ConectorMCP":
        pila = AsyncExitStack()
        try:
            await self.grifter.conectar(pila)
            await self.grifter.arrancar()   # revisa la política aprobada y manda el latido (#102)
            pila.push_async_callback(self.grifter.detener)
            gestor = StreamableHTTPSessionManager(
                app=self.grifter.servidor_mcp(), json_response=True, stateless=True)
            await pila.enter_async_context(gestor.run())
        except BaseException:
            await pila.aclose()
            raise
        self._pila, self._gestor = pila, gestor
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pila, self._pila, self._gestor = self._pila, None, None
        if pila is not None:
            await pila.aclose()

    def _autorizado(self, scope: Scope) -> bool:
        if self.publico:
            return True
        return hmac.compare_digest(_token_del_pedido(scope).encode("utf-8"), self._token)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return
        if not self._autorizado(scope):
            await _responder(send, 401, {"error": "falta el token de portador o no es válido"},
                             [(b"www-authenticate", b'Bearer realm="grifter"')])
            return
        gestor = self._gestor
        if gestor is None:
            await _responder(send, 503, {"error": "Grifter todavía no está conectado a sus servidores"})
            return
        try:
            await gestor.handle_request(scope, receive, send)
        except Exception:
            log.exception("error en /mcp")
            raise


def crear_app(config: Config, token: Optional[str], escalar: Escalar = escalar_por_defecto,
              grifter: Optional[Grifter] = None) -> Starlette:
    """Una app Starlette con solo `/mcp`. Lanza ValueError si el token falta o es corto."""
    conector = ConectorMCP(config, token, escalar, grifter)

    @asynccontextmanager
    async def vida(_app: Starlette):
        async with conector:
            yield

    app = Starlette(routes=[Route(RUTA, conector, methods=["GET", "POST", "DELETE"]),
                            Route(RUTA + "/", conector, methods=["GET", "POST", "DELETE"])], lifespan=vida)
    app.state.conector = conector
    return app


def servir(config: Config, host: str = "127.0.0.1", puerto: int = 8766,
           token: Optional[str] = None, escalar: Escalar = escalar_por_defecto,
           grifter: Optional[Grifter] = None) -> None:
    import uvicorn

    app = crear_app(config, token if token is not None else os.environ.get(VARIABLE_TOKEN), escalar, grifter)
    log.info("Grifter en http://%s:%s%s (token de portador en %s)", host, puerto, RUTA, VARIABLE_TOKEN)
    uvicorn.run(app, host=host, port=puerto, log_level="warning")
