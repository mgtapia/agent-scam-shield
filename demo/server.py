"""Servidor mínimo de la demo: la página, los episodios y las etiquetas del dueño.

Uso, desde la raíz del repo:
    python -m demo.server                 # http://127.0.0.1:8765
    python -m demo.server --puerto 9000
    uvicorn demo.server:app --port 8765

Rutas:
    GET  /                      la página de los tres carriles
    GET  /episodios/...         los JSON de episodios (indice.json, <id>.json, episodios.js)
    POST /api/etiquetas         guarda la respuesta del dueño en demo/etiquetas.jsonl (cuerpo chico, solo los campos de la alerta, tope por IP)
    POST /api/alertas           con GRIFTER_DEMO_WHATSAPP=1 o GRIFTER_ALERTAS_LOCALES=1 pasa la alerta a notificar() (Telegram,
                                WhatsApp), con tope por IP y sin `motivo` ni `titular` del cliente; sin la variable responde 200 y no envía
    GET  /api/salud             para comprobar que está arriba
    POST /api/probar            «Intenta estafarlo»: el correo del juez contra las tres capas (con tope por IP)
    GET  /api/vivo              Server-Sent Events del modo «Centro de operaciones» (scamshield/vivo)
    POST /api/vivo/control      {"accion": "pausa" | "seguir" | "velocidad" | "idioma", "valor": 1|2|4 | "es"|"en"|"ambos"} (tope por IP)
    GET  /api/vivo/estado       foto completa: bóveda, modelo, agentes y últimos 50 correos
    POST /mcp                   Grifter como conector MCP remoto (#105), con GRIFTER_MCP_TOKEN o, sin token,
                                con GRIFTER_MCP_PUBLICO=1 (solo la tienda ficticia, tope por IP y cuerpo chico)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from demo import telegram, whatsapp
from demo.limite import LimitePorIP, ip_cliente, limite_de, modo_evento
from demo.notificar import notificar

DEMO = Path(__file__).resolve().parent
ETIQUETAS = DEMO / "etiquetas.jsonl"
ELECCIONES = {"pagar_inscrita", "no_pagar", "pagar_igual"}
ACTIVOS_PUBLICOS = frozenset({
    "index.html", "estilos.css", "favicon.svg", "app.js", "graficos.js", "duelo.js",
    "operaciones.js", "vivo_simulado.js", "resultados.js", "resultados_vista.js",
    "resultados.json", "instalar.js", "demo.html", "demo.css", "demo.js",
    # El retrato del nieto que demo.js pone en la llamada del acto 1 (los mp3 van por el montaje /audio).
    "img/nieto.svg", "img/nieto.jpg", "img/abuela.jpg", "img/abuela.svg",
})


class _ActivosPublicos(StaticFiles):
    """Solo los activos de la página; el historial y el código de la demo son privados."""

    def lookup_path(self, path: str) -> tuple[str, os.stat_result | None]:
        archivo, estado = super().lookup_path(path)
        if estado is None:
            return archivo, estado
        # Un nombre público no hace público su destino si es un enlace a un archivo privado.
        relativo = Path(archivo).relative_to(Path(self.directory).resolve()).as_posix()
        if relativo != "." and relativo not in ACTIVOS_PUBLICOS:
            return "", None
        return archivo, estado

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        # Starlette arma la ruta con el separador del sistema: en Windows «img\nieto.svg». Se compara en posix.
        path = path.replace(os.sep, "/")
        if path != "." and path not in ACTIVOS_PUBLICOS:
            raise HTTPException(404, "Not Found")
        return await super().get_response(path, scope)

# Grifter como conector MCP remoto en /mcp (#105). Sin GRIFTER_MCP_TOKEN la ruta responde 404 y la demo
# sigue como siempre. La configuración por defecto pone detrás la tienda ficticia con el checkout desviado.
CONFIG_MCP_POR_DEFECTO = DEMO.parent / "scamshield" / "mcp" / "grifter.tienda.yaml"
# Modo público (GRIFTER_MCP_PUBLICO=1): /mcp sin token, para conectar ChatGPT en modo desarrollador, que solo
# ofrece OAuth o nada. Acotado: solo la tienda ficticia detrás, tope por IP y cuerpo chico.
MODULO_TIENDA = "scamshield.mcp.servidor_tienda"
MAX_BYTES_MCP = 16_384
limite_mcp = limite_de("mcp")   # con GRIFTER_EVENTO=1 sube el tope por IP, no el global


def mcp_publico(entorno=None) -> bool:
    return (os.environ if entorno is None else entorno).get("GRIFTER_MCP_PUBLICO", "").strip() == "1"


def validar_config_publica(config) -> None:
    """En modo público, detrás de Grifter solo puede ir la tienda ficticia: ni banco, ni Stripe, ni MCP remotos,
    ni credenciales. Lanza ValueError si la configuración trae otra cosa."""
    if not config.servidores:
        raise ValueError("el modo público necesita la tienda ficticia detrás de Grifter")
    for s in config.servidores:
        if s.url or s.headers or s.env:
            raise ValueError(f"modo público: {s.nombre} trae url, headers o env; solo se admite la tienda ficticia")
        if s.comando not in ("python", "python3") or s.args[:2] != ["-m", MODULO_TIENDA]:
            raise ValueError(f"modo público: {s.nombre} no es la tienda ficticia ({MODULO_TIENDA})")


async def _responder_json(scope, receive, send, estado: int, cuerpo: dict, cabeceras: dict | None = None) -> None:
    await JSONResponse(cuerpo, status_code=estado, headers=cabeceras)(scope, receive, send)


class _RutaMCP:
    """La ruta /mcp: delega en el conector de Grifter si está prendido; si no, 404.
    En modo público, antes de delegar aplica el tope por IP y el tamaño máximo del cuerpo."""

    def __init__(self) -> None:
        self.conector = None
        self.publico = False

    async def __call__(self, scope, receive, send) -> None:
        if self.conector is None:
            await _responder_json(scope, receive, send, 404, {"detail": "Grifter MCP no está activo en este servidor"})
            return
        if self.publico:
            encabezados = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
            if scope.get("method") == "POST":
                largo = encabezados.get("content-length", "")
                if not largo.isdigit() or int(largo) > MAX_BYTES_MCP:
                    await _responder_json(scope, receive, send, 413, {"detail": "el pedido es demasiado grande"})
                    return
            cliente = scope.get("client")
            ip = ip_cliente(SimpleNamespace(host=cliente[0] if cliente else None), encabezados)
            ok, espera = limite_mcp.permitir(ip)
            if not ok:
                await _responder_json(scope, receive, send, 429, {"detail": "demasiados pedidos seguidos: espera un momento"},
                                      {"Retry-After": str(espera)})
                return
        await self.conector(scope, receive, send)


ruta_mcp = _RutaMCP()


@asynccontextmanager
async def _conector_mcp():
    """Conecta a Grifter para /mcp: con GRIFTER_MCP_TOKEN (token de portador) o en modo público (sin token, solo
    la tienda). Arma los ganchos de la CLI que tienen sentido sin Telegram: la integridad de la política (#102)."""
    publico = mcp_publico()
    token = os.environ.get("GRIFTER_MCP_TOKEN", "").strip()
    if not token and not publico:
        yield
        return
    from scamshield.mcp.integridad import ENTORNO_CLAVE, Integridad
    from scamshield.mcp.proxy import Grifter, cargar_config
    from scamshield.mcp.remoto import ConectorMCP

    config = cargar_config(os.environ.get("GRIFTER_MCP_CONFIG") or CONFIG_MCP_POR_DEFECTO)
    if publico:
        validar_config_publica(config)
    integridad = None
    if config.ruta is not None:
        integridad = Integridad(config.ruta, config.estado, clave=os.environ.get(ENTORNO_CLAVE) or None)
    grifter = Grifter(config, integridad=integridad)
    async with ConectorMCP(config, token or None, grifter=grifter, publico=publico) as conector:
        ruta_mcp.conector, ruta_mcp.publico = conector, publico
        try:
            yield
        finally:
            ruta_mcp.conector, ruta_mcp.publico = None, False


@asynccontextmanager
async def _vida(_app: FastAPI):
    """Arranca el canal de Telegram si hay token y chat en el entorno (#20); si no, todo sigue como antes.
    Con GRIFTER_MCP_TOKEN o GRIFTER_MCP_PUBLICO=1, también conecta a Grifter con sus MCP de abajo para servir /mcp."""
    canal = telegram.iniciar_desde_entorno(registrar_etiqueta)
    _app.state.whatsapp = whatsapp.iniciar_desde_entorno(registrar_etiqueta)   # #116: el webhook de Kapso entra por /api/whatsapp/webhook
    try:
        async with _conector_mcp():
            yield
    finally:
        if canal:
            canal.detener()


app = FastAPI(title="agent-scam-shield demo", lifespan=_vida)
# La interfaz puede correr en otro puerto local (por ejemplo, en su propio worktree): solo localhost.
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
_candado = threading.Lock()


@app.get("/api/salud")
def salud() -> dict[str, Any]:
    episodios = sorted(p.name for p in (DEMO / "episodios").glob("*.json") if p.name != "indice.json")
    return {"ok": True, "episodios": len(episodios), "evento": modo_evento()}


def registrar_etiqueta(etiqueta: dict[str, Any]) -> None:
    """Una línea por respuesta del dueño, para entrenar el clasificador (#7). La usan la página y Telegram."""
    if etiqueta.get("eleccion") not in ELECCIONES:
        raise ValueError(f"eleccion debe ser una de {sorted(ELECCIONES)}")
    fila = {**etiqueta, "recibida": datetime.now(timezone.utc).isoformat()}
    with _candado, ETIQUETAS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


@app.post("/api/whatsapp/webhook")
async def webhook_whatsapp(request: Request) -> JSONResponse:
    """El webhook de Kapso: los botones que aprieta el dueño por WhatsApp. Falla cerrada: sin canal o con mala firma, no cuenta."""
    canal = getattr(request.app.state, "whatsapp", None)
    if canal is None:
        raise HTTPException(404, "WhatsApp no está configurado")
    estado, motivo = canal.atender_webhook(await request.body(), dict(request.headers))
    return JSONResponse({"ok": estado == 200, "motivo": motivo}, status_code=estado)


# Una alerta o una etiqueta que llega por HTTP la escribe quien sea: solo pasan los campos que la página manda, como texto
# corto. `motivo` y `titular` no: los arma el servidor (una línea de la alerta que dijera «cuenta verificada» sería de Grifter).
CAMPOS_ALERTA = ("escenario", "idioma", "defensa", "destinatario", "cuenta", "dominio", "cuenta_inscrita_numero", "nombre_inscrita")
CAMPOS_ETIQUETA = CAMPOS_ALERTA + ("ts", "eleccion", "motivo", "correos", "cuenta_inscrita", "monto")
MAX_CAMPO = 200
MAX_BYTES_ETIQUETA = 4096
MOTIVOS_DEL_SERVIDOR = {
    "es": "Grifter retuvo este pago: la cuenta de destino no viene del encargo ni de las cuentas inscritas del dueño.",
    "en": "Grifter held this payment: the destination account does not come from the owner's task or registered accounts.",
}
ALERTAS_LOCALES = ("GRIFTER_DEMO_WHATSAPP", "GRIFTER_ALERTAS_LOCALES")
limite_alertas = limite_de("alertas")
limite_etiquetas = limite_de("etiquetas")
limite_control = limite_de("control")


def alertas_habilitadas(entorno=None) -> bool:
    """Solo con GRIFTER_DEMO_WHATSAPP=1 o GRIFTER_ALERTAS_LOCALES=1: en el sitio público, quien llame no puede hacer sonar el celular."""
    e = os.environ if entorno is None else entorno
    return any(e.get(v, "").strip() == "1" for v in ALERTAS_LOCALES)


def _campos(datos: dict[str, Any], permitidos: tuple[str, ...]) -> dict[str, Any]:
    """Los campos permitidos de lo que mandó un cliente: texto corto, un número o un booleano; lo demás se descarta."""
    salida: dict[str, Any] = {}
    for k in permitidos:
        v = datos.get(k)
        if isinstance(v, bool) or v is None:
            if v is not None:
                salida[k] = v
        elif isinstance(v, (int, float)):
            salida[k] = v
        elif isinstance(v, str):
            salida[k] = v[:MAX_CAMPO]
        elif k == "correos" and isinstance(v, list):
            salida[k] = [x[:MAX_CAMPO] for x in v[:10] if isinstance(x, str)]
    return salida


def alerta_del_servidor(cliente: dict[str, Any]) -> dict[str, Any]:
    """La alerta que sale por Telegram o WhatsApp: lo del cliente que pasa el filtro y el motivo que pone el servidor."""
    alerta = _campos(cliente, CAMPOS_ALERTA)
    if isinstance(cliente.get("monto"), (int, float)) and not isinstance(cliente.get("monto"), bool):
        alerta["monto"] = cliente["monto"]
    if alerta.get("idioma") not in MOTIVOS_DEL_SERVIDOR:
        alerta["idioma"] = "es"
    alerta["motivo"] = MOTIVOS_DEL_SERVIDOR[alerta["idioma"]]
    return alerta


def _tope(limite: LimitePorIP, request: Request) -> None:
    ok, espera = limite.permitir(ip_cliente(request.client, request.headers))
    if not ok:
        raise HTTPException(429, "demasiados pedidos seguidos: espera un momento", headers={"Retry-After": str(espera)})


@app.post("/api/etiquetas")
def guardar_etiqueta(request: Request, etiqueta: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _tope(limite_etiquetas, request)
    try:
        registrar_etiqueta(_campos(etiqueta, CAMPOS_ETIQUETA))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"ok": True}


@app.post("/api/alertas")
def recibir_alerta(request: Request, alerta: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if not alertas_habilitadas():
        return {"ok": True, "canales": []}   # la página no se rompe y el carril del escudo dibuja su alerta igual
    _tope(limite_alertas, request)
    return {"ok": True, "canales": notificar(alerta_del_servidor(alerta))}


# --- Modo «Centro de operaciones» en vivo -------------------------------------------------------
# Agentes y correos simulados; capa 1, capa 2, bóveda y clasificador reales (scamshield/vivo).
@app.get("/api/vivo")
async def vivo(request: Request, idioma: str | None = None) -> StreamingResponse:
    from scamshield.vivo.motor import motor_global

    motor = motor_global()
    if idioma:
        try:
            motor.control("idioma", idioma)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    async def eventos():
        seq = motor.seq
        espera_ping = 0.0
        yield ": conectado\n\n"
        while not await request.is_disconnected():
            nuevos = motor.eventos_desde(seq)
            for s, ev in nuevos:
                seq = s
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if not nuevos:
                await asyncio.sleep(0.2)
                espera_ping += 0.2
                if espera_ping >= 15:
                    espera_ping = 0.0
                    yield ": ping\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/vivo/control")
def vivo_control(request: Request, orden: dict[str, Any] = Body(...)) -> dict[str, Any]:
    # Límite conocido: el motor es uno solo y global, así que la pausa, la velocidad o el idioma de un visitante los ven todos.
    # Hoy solo hay tope por IP; separar el estado por visitante es un cambio mayor que no entra con el software congelado.
    _tope(limite_control, request)
    from scamshield.vivo.motor import motor_global

    try:
        return {"ok": True, **motor_global().control(orden.get("accion", ""), orden.get("valor"))}
    except (TypeError, ValueError) as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/vivo/estado")
def vivo_estado() -> dict[str, Any]:
    from scamshield.vivo.motor import motor_global

    return motor_global().foto()


# --- «Intenta estafarlo» (#21) --------------------------------------------------------------------
# Un juez escribe su estafa y ve qué capa la frena. Sin API: el agente es guionado y las capas son las reales.
MAX_BYTES_PROBAR = 16_384
limite_probar = limite_de("probar")


class CorreoJuez(BaseModel):
    de: str = Field(default="", max_length=200)
    asunto: str = Field(default="", max_length=300)
    cuerpo: str = Field(max_length=4000)
    idioma: Literal["es", "en"] = "es"


@app.middleware("http")
async def _tope_de_cuerpo(request: Request, llamada_siguiente):
    """Rechaza el cuerpo enorme de /api/probar, /api/etiquetas y /api/alertas antes de leerlo."""
    tope = {"/api/probar": MAX_BYTES_PROBAR, "/api/etiquetas": MAX_BYTES_ETIQUETA, "/api/alertas": MAX_BYTES_ETIQUETA}.get(request.url.path)
    if tope is not None and request.method == "POST":
        largo = request.headers.get("content-length", "")
        if not largo.isdigit() or int(largo) > tope:
            return JSONResponse({"detail": "el pedido es demasiado grande"}, status_code=413)
    return await llamada_siguiente(request)


@app.post("/api/probar")
def probar_estafa(correo: CorreoJuez, request: Request) -> dict[str, Any]:
    """Evalúa el correo del juez con las tres capas. No entrena nada: solo se evalúa y se muestra en vivo."""
    ok, espera = limite_probar.permitir(ip_cliente(request.client, request.headers))
    if not ok:
        raise HTTPException(429, "demasiados intentos seguidos: espera un momento", headers={"Retry-After": str(espera)})
    from scamshield.vivo.motor import motor_global
    from scamshield.vivo.probar import probar

    try:
        return probar(correo.de, correo.asunto, correo.cuerpo, correo.idioma, motor_global())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


app.add_route("/mcp", ruta_mcp, methods=["GET", "POST", "DELETE"])

# Los episodios exportados son públicos y tienen su propia raíz para impedir salir de esa carpeta.
app.mount("/episodios", StaticFiles(directory=DEMO / "episodios"), name="episodios")
if (DEMO / "audio").is_dir():
    app.mount("/audio", StaticFiles(directory=DEMO / "audio"), name="audio")
# El montaje raíz va al final y solo permite los activos de la interfaz.
app.mount("/", _ActivosPublicos(directory=DEMO, html=True), name="demo")


def main() -> None:
    import uvicorn

    from dotenv import load_dotenv

    load_dotenv(DEMO.parent / ".env")   # el token de Telegram, si lo hay; el .env nunca entra al repo
    p = argparse.ArgumentParser(description="Servidor de la demo de agent-scam-shield")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8765)
    a = p.parse_args()
    print(f"Demo en http://{a.host}:{a.puerto}/")
    uvicorn.run(app, host=a.host, port=a.puerto)


if __name__ == "__main__":
    main()
