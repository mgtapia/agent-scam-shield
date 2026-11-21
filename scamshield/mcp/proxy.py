"""Grifter como proxy MCP: se pone entre el agente y uno o más servidores MCP.

Reexpone las herramientas de los servidores de abajo y guarda cada resultado como contenido no
confiable (origen `mcp`). Antes de reenviar una llamada sensible (pagar, transferir o compartir un
dato del dueño) aplica `politica_origen` de la capa 2: si el destino solo apareció en lo que
devolvieron los servidores, la llamada no se reenvía, el agente recibe un error de herramienta y el
evento queda en un JSONL.

Lo confiable sale de `grifter.yaml`, que escribe el dueño: sus cuentas inscritas, sus datos y, si
quiere, el texto del encargo. Los clientes MCP no exponen el mensaje del usuario al servidor, así
que sin `encargo` la regla es conservadora: solo vale como confiable lo inscrito. Lo que escribe el
agente en los argumentos nunca vuelve confiable un valor.

Uso: python -m scamshield.mcp.proxy --config grifter.yaml
Ejemplo de configuración: scamshield/mcp/grifter.ejemplo.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, Union

import mcp.types as types
import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from ..defenses.layer2 import SENSIBLES_SCAMSHIELD, AccionSensible, politica_origen
from ..env.world import CONFIABLE, DUENO, MCP, origenes_en

log = logging.getLogger("grifter")

RAIZ_PAQUETE = Path(__file__).resolve().parents[2]

# Herramientas sensibles por defecto: las del mundo simulado, con el destino nombrado como en el aviso.
SENSIBLES_POR_DEFECTO: dict[str, AccionSensible] = {
    **SENSIBLES_SCAMSHIELD,
    "pagar": AccionSensible(destino="cuenta", que="la cuenta"),
    "transferir": AccionSensible(destino="cuenta", que="la cuenta"),
}
ACCION_POR_DEFECTO = {
    "pagar": "el pago",
    "transferir": "la transferencia",
    "compartir_dato": "el envío del dato",
    "responder": "el mensaje",
}


# ---------------------------------------------------------------------------------------------
# Configuración del dueño
# ---------------------------------------------------------------------------------------------

@dataclass
class ServidorAbajo:
    nombre: str
    comando: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: Optional[Path] = None


@dataclass
class Config:
    servidores: list[ServidorAbajo] = field(default_factory=list)
    cuentas_inscritas: dict[str, str] = field(default_factory=dict)
    datos_dueno: dict[str, str] = field(default_factory=dict)
    encargo: str = ""
    sensibles: dict[str, AccionSensible] = field(default_factory=lambda: dict(SENSIBLES_POR_DEFECTO))
    acciones: dict[str, str] = field(default_factory=lambda: dict(ACCION_POR_DEFECTO))
    registro: Optional[Path] = None


def cargar_config(ruta: Union[str, Path]) -> Config:
    """Lee `grifter.yaml`. Las rutas relativas se resuelven contra la carpeta del archivo."""
    ruta = Path(ruta).resolve()
    base = ruta.parent
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

    servidores = []
    for nombre, s in (datos.get("servidores") or {}).items():
        cwd = Path(s["cwd"]) if s.get("cwd") else base
        servidores.append(ServidorAbajo(
            nombre=str(nombre),
            comando=str(s["comando"]),
            args=[str(a) for a in s.get("args", [])],
            env={str(k): str(v) for k, v in (s.get("env") or {}).items()},
            cwd=cwd if cwd.is_absolute() else base / cwd,
        ))

    config = Config(
        servidores=servidores,
        cuentas_inscritas={str(k): str(v) for k, v in (datos.get("cuentas_inscritas") or {}).items()},
        datos_dueno={str(k): str(v) for k, v in (datos.get("datos_dueno") or {}).items()},
        encargo=str(datos.get("encargo") or ""),
    )
    if datos.get("sensibles"):
        config.sensibles, config.acciones = {}, {}
        for herramienta, regla in datos["sensibles"].items():
            regla = dict(regla or {})
            accion = regla.pop("accion", None)
            config.sensibles[str(herramienta)] = AccionSensible(**regla)
            config.acciones[str(herramienta)] = accion or ACCION_POR_DEFECTO.get(
                str(herramienta), f"la llamada a {herramienta}")
    registro = datos.get("registro", "grifter_eventos.jsonl")
    if registro:
        registro = Path(registro)
        config.registro = registro if registro.is_absolute() else base / registro
    return config


# ---------------------------------------------------------------------------------------------
# La guardia: procedencia y decisión, sin MCP (se prueba en proceso)
# ---------------------------------------------------------------------------------------------

@dataclass
class Fuente:
    """Dónde se leyó un texto no confiable: qué servidor y qué herramienta lo devolvió."""

    servidor: str
    herramienta: str


@dataclass
class Alerta:
    """Lo que Grifter retuvo, listo para avisarle al dueño (por ejemplo, por Telegram, #20)."""

    herramienta: str
    servidor: str
    args: dict[str, Any]
    valor: str
    motivo: str
    mensaje: str
    fuentes: list[str]


Escalar = Callable[[Alerta], Union[Optional[bool], Awaitable[Optional[bool]]]]


def escalar_por_defecto(alerta: Alerta) -> Optional[bool]:
    """Gancho para avisar al dueño. Devuelve True si el dueño aprueba y la llamada debe seguir.

    Por defecto solo deja la alerta en el log de stderr y mantiene el bloqueo. El aviso al
    celular (Telegram, #20) se conecta pasando otra función a `Grifter(escalar=...)`.
    """
    log.warning("Alerta para el dueño: %s", alerta.mensaje)
    return None


class Guardia:
    """Procedencia de lo que pasó por el proxy, y la capa 2 sobre ella.

    Cumple la interfaz `Procedencia` de layer2: `datos_dueno` y `origenes_de(valor)`.
    """

    def __init__(self, config: Config):
        self.config = config
        self.datos_dueno: dict[str, str] = dict(config.datos_dueno)
        # Lista paralela: (origen, texto) para la política y la fuente para el aviso.
        self.leidos: list[tuple[str, str]] = []
        self.fuentes: list[Optional[Fuente]] = []
        if config.encargo:
            self._anotar(DUENO, config.encargo, None)
        for nombre, cuenta in config.cuentas_inscritas.items():
            self._anotar(CONFIABLE, f"{nombre}: {cuenta}", None)

    def _anotar(self, origen: str, texto: str, fuente: Optional[Fuente]) -> None:
        self.leidos.append((origen, texto))
        self.fuentes.append(fuente)

    def anotar_resultado(self, servidor: str, herramienta: str, texto: str) -> None:
        """Todo lo que devuelve un servidor de abajo es contenido no confiable (origen mcp)."""
        if texto:
            self._anotar(MCP, texto, Fuente(servidor, herramienta))

    def origenes_de(self, valor: str) -> set[str]:
        return origenes_en(self.leidos, valor)

    def revisar(self, herramienta: str, args: Mapping[str, Any], servidor: str = "") -> Optional[Alerta]:
        """None si la llamada puede seguir; si no, la alerta con el aviso para el agente."""
        motivo = politica_origen(self, herramienta, args, self.config.sensibles)
        if motivo is None:
            return None
        regla = self.config.sensibles[herramienta]
        valor = str(args.get(regla.destino, ""))
        fuentes = self._fuentes_de(valor)
        accion = self.config.acciones.get(herramienta, f"la llamada a {herramienta}")
        if fuentes:
            donde = ", ".join(fuentes)
            mensaje = (f"Grifter retuvo {accion}: {regla.que} {valor} apareció en {donde}, "
                       "no en tus cuentas inscritas.")
        else:
            mensaje = (f"Grifter retuvo {accion}: {regla.que} {valor} no aparece en tus cuentas "
                       "inscritas ni en el encargo.")
        mensaje += " Confírmala con el dueño por un canal conocido antes de reintentar."
        return Alerta(herramienta=herramienta, servidor=servidor, args=dict(args), valor=valor,
                      motivo=motivo, mensaje=mensaje, fuentes=fuentes)

    def _fuentes_de(self, valor: str) -> list[str]:
        vistas: list[str] = []
        for (origen, texto), fuente in zip(self.leidos, self.fuentes):
            if fuente is None or not origenes_en([(origen, texto)], valor):
                continue
            etiqueta = f"{fuente.herramienta} de {fuente.servidor}"
            if etiqueta not in vistas:
                vistas.append(etiqueta)
        return vistas


# ---------------------------------------------------------------------------------------------
# El proxy MCP
# ---------------------------------------------------------------------------------------------

def _texto_de(resultado: types.CallToolResult) -> str:
    partes = [c.text for c in resultado.content if isinstance(c, types.TextContent)]
    if resultado.structuredContent:
        partes.append(json.dumps(resultado.structuredContent, ensure_ascii=False))
    return "\n".join(partes)


def _error(mensaje: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=mensaje)], isError=True)


class Grifter:
    def __init__(self, config: Config, escalar: Escalar = escalar_por_defecto):
        self.config = config
        self.guardia = Guardia(config)
        self.escalar = escalar
        self.sesiones: dict[str, ClientSession] = {}
        # Nombre expuesto -> (servidor, nombre original de la herramienta).
        self.rutas: dict[str, tuple[str, str]] = {}
        self.herramientas: list[types.Tool] = []

    async def conectar(self, pila: AsyncExitStack, errlog=None) -> None:
        """Levanta cada servidor de abajo por stdio y junta sus herramientas."""
        for s in self.config.servidores:
            comando = sys.executable if s.comando in ("python", "python3") else s.comando
            env = {**s.env}
            env["PYTHONPATH"] = os.pathsep.join(
                p for p in (str(RAIZ_PAQUETE), os.environ.get("PYTHONPATH", ""), env.get("PYTHONPATH", "")) if p)
            parametros = StdioServerParameters(command=comando, args=s.args, env=env,
                                               cwd=str(s.cwd) if s.cwd else None)
            read, write = await pila.enter_async_context(
                stdio_client(parametros, errlog=errlog or sys.stderr))
            sesion = await pila.enter_async_context(ClientSession(read, write))
            await sesion.initialize()
            self.sesiones[s.nombre] = sesion
            for tool in (await sesion.list_tools()).tools:
                expuesto = tool.name if tool.name not in self.rutas else f"{s.nombre}_{tool.name}"
                self.rutas[expuesto] = (s.nombre, tool.name)
                self.herramientas.append(tool.model_copy(update={"name": expuesto}))
                # La descripción también es contenido del servidor de abajo.
                self.guardia.anotar_resultado(s.nombre, f"la descripción de {tool.name}",
                                              tool.description or "")

    async def llamar(self, nombre: str, args: dict[str, Any]) -> types.CallToolResult:
        if nombre not in self.rutas:
            return _error(f"Grifter no conoce la herramienta {nombre}.")
        servidor, original = self.rutas[nombre]
        if original in self.config.sensibles:
            alerta = self.guardia.revisar(original, args, servidor)
            if alerta is not None:
                aprobada = self.escalar(alerta)
                if inspect.isawaitable(aprobada):
                    aprobada = await aprobada
                self._registrar("aprobado_por_dueno" if aprobada else "retenido", alerta=alerta)
                if not aprobada:
                    return _error(alerta.mensaje)
            else:
                self._registrar("permitido", herramienta=original, servidor=servidor, args=args)
        resultado = await self.sesiones[servidor].call_tool(original, args)
        self.guardia.anotar_resultado(servidor, original, _texto_de(resultado))
        return resultado

    def _registrar(self, evento: str, alerta: Optional[Alerta] = None, **datos: Any) -> None:
        if self.config.registro is None:
            return
        fila = {"ts": datetime.now(timezone.utc).isoformat(), "evento": evento,
                **(asdict(alerta) if alerta else datos)}
        self.config.registro.parent.mkdir(parents=True, exist_ok=True)
        with self.config.registro.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    def servidor_mcp(self) -> Server:
        servidor = Server("grifter", instructions=(
            "Grifter revisa los pagos y el envío de datos antes de reenviarlos. Si retiene una "
            "llamada, no la reintentes con otra cuenta: pídele al dueño que la confirme."))

        @servidor.list_tools()
        async def listar() -> list[types.Tool]:
            return self.herramientas

        @servidor.call_tool(validate_input=False)
        async def llamar(nombre: str, args: dict[str, Any]) -> types.CallToolResult:
            return await self.llamar(nombre, args)

        return servidor


async def correr(config: Config, escalar: Escalar = escalar_por_defecto) -> None:
    grifter = Grifter(config, escalar)
    async with AsyncExitStack() as pila:
        await grifter.conectar(pila)
        servidor = grifter.servidor_mcp()
        async with stdio_server() as (read, write):
            await servidor.run(read, write, servidor.create_initialization_options())


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Grifter como proxy MCP con la capa 2.")
    parser.add_argument("--config", default="grifter.yaml", help="configuración del dueño")
    parser.add_argument("--encargo", default=None,
                        help="texto del encargo del dueño; se suma a lo confiable")
    args = parser.parse_args(argv)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="grifter: %(message)s")
    log.setLevel(logging.INFO)
    config = cargar_config(args.config)
    if args.encargo:
        config.encargo = args.encargo
    asyncio.run(correr(config))


if __name__ == "__main__":
    main()
