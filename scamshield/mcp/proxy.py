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

Con `mandato` en `grifter.yaml` (#103), un pago que se desvía de lo que aprobó el dueño (monto, producto,
cantidad, moneda, cuenta, recurrencia o cargos extra) se retiene, y una orden que devuelve el MCP con un
desvío no llega al agente. Con `herramientas_fijadas` (nombre -> SHA-256 de la descripción y el esquema),
una herramienta que cambió o que no se aprobó queda bloqueada; sin fijaciones, el log deja la huella de
cada herramienta al conectar, para copiarla.

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
import time
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

from ..defenses.layer2 import MOTIVO_CREDENCIAL, SENSIBLES_SCAMSHIELD, AccionSensible, politica_origen, visible
from ..defenses.mandato import huella, motivo as motivo_mandato, parece_orden, revisar_fijacion
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
    # Mandato del dueño (#103): lo que aprobó para el pago. Vacío, sin mandato.
    mandato: dict[str, Any] = field(default_factory=dict)
    # Fijación de herramientas (#103): nombre -> huella (SHA-256) de la descripción y el esquema aprobados.
    herramientas_fijadas: dict[str, str] = field(default_factory=dict)


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
        mandato=dict(datos.get("mandato") or {}),
        herramientas_fijadas={str(k): str(v) for k, v in (datos.get("herramientas_fijadas") or {}).items()},
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
        self.encargo: str = config.encargo
        self.mandato: dict[str, Any] = dict(config.mandato)
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
        desvio = self._fuera_del_mandato(herramienta, args)
        if desvio:
            regla = self.config.sensibles[herramienta]
            accion = self.config.acciones.get(herramienta, f"la llamada a {herramienta}")
            return Alerta(herramienta=herramienta, servidor=servidor, args=dict(args),
                          valor=str(args.get(regla.destino, "")), motivo=desvio, fuentes=[],
                          mensaje=(f"Grifter retuvo {accion}. {desvio} Confírmalo con el dueño por un canal "
                                   "conocido antes de reintentar."))
        motivo = politica_origen(self, herramienta, args, self.config.sensibles)
        if motivo is None:
            return None
        regla = self.config.sensibles[herramienta]
        valor = str(args.get(regla.destino, ""))
        credencial = motivo == MOTIVO_CREDENCIAL
        fuentes = [] if credencial else self._fuentes_de(valor)
        accion = self.config.acciones.get(herramienta, f"la llamada a {herramienta}")
        dicho = visible(valor)   # lo escribió el agente: no puede agregarle líneas al aviso del dueño
        if credencial:
            mensaje = f"Grifter retuvo {accion}: {MOTIVO_CREDENCIAL[:-1].lower()}."
        elif fuentes:
            donde = ", ".join(fuentes)
            mensaje = (f"Grifter retuvo {accion}: {regla.que} {dicho} apareció en {donde}, "
                       "no en tus cuentas inscritas.")
        else:
            mensaje = (f"Grifter retuvo {accion}: {regla.que} {dicho} no aparece en tus cuentas "
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

    def _fuera_del_mandato(self, herramienta: str, args: Mapping[str, Any]) -> Optional[str]:
        """El desvío de un pago respecto del mandato del dueño (#103), o None. Solo en pagos, no en datos."""
        regla = self.config.sensibles.get(herramienta)
        if not self.mandato or regla is None or regla.dato is not None or regla.mensaje is not None:
            return None
        return motivo_mandato(self.mandato, args, quien="el MCP")

    def revisar_orden(self, resultado: types.CallToolResult) -> Optional[str]:
        """Si el MCP devolvió una orden (#103) y se desvía del mandato, el motivo; si no, None."""
        if not self.mandato:
            return None
        orden = _orden_de(resultado)
        return motivo_mandato(self.mandato, orden, quien="el MCP") if orden is not None else None


# ---------------------------------------------------------------------------------------------
# El proxy MCP
# ---------------------------------------------------------------------------------------------

def _orden_de(resultado: types.CallToolResult) -> Optional[dict[str, Any]]:
    """La orden que devolvió el MCP (contenido estructurado o un JSON en el texto), o None si no hay."""
    candidatos: list[Any] = [resultado.structuredContent]
    for c in resultado.content:
        if isinstance(c, types.TextContent):
            try:
                candidatos.append(json.loads(c.text))
            except (ValueError, TypeError):
                continue
    for c in candidatos:
        if isinstance(c, dict) and isinstance(c.get("orden"), dict):
            c = c["orden"]
        if parece_orden(c):
            return dict(c)
    return None


def _texto_de(resultado: types.CallToolResult) -> str:
    partes = [c.text for c in resultado.content if isinstance(c, types.TextContent)]
    if resultado.structuredContent:
        partes.append(json.dumps(resultado.structuredContent, ensure_ascii=False))
    return "\n".join(partes)


# Argumentos que delatan una herramienta de dinero aunque no esté declarada en `sensibles`.
# Un servidor que expone el pago como `send_money` o `pagar_factura` no se salta la revisión.
CLAVES_CUENTA = ("cuenta", "cuenta_destino", "numero_cuenta", "account", "account_number", "iban")
CLAVES_DESTINO = ("destinatario", "beneficiario", "recipient", "destino", "to")
CLAVES_DINERO = ("monto", "amount", "importe", "valor", "total")

# Tope de alertas: si un atacante inunda al agente de pagos retenidos para cansar al dueño, Grifter
# deja de preguntar y retiene todo lo sensible en silencio hasta que pase la ventana.
TOPE_ALERTAS = 5
VENTANA_ALERTAS_S = 600


def regla_por_argumentos(args: Mapping[str, Any]) -> Optional[AccionSensible]:
    """Si los argumentos parecen un pago, la regla con la que revisarlo; si no, None."""
    claves = {str(k).lower(): str(k) for k in args}
    for c in CLAVES_CUENTA:
        if c in claves:
            return AccionSensible(destino=claves[c], que="el destino")
    if any(m in claves for m in CLAVES_DINERO):
        for c in CLAVES_DESTINO:
            if c in claves:
                return AccionSensible(destino=claves[c], que="el destino")
    return None


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
        self._alertas_recientes: list[float] = []
        # Herramientas que no calzan con su fijación (#103): nombre expuesto -> motivo. Quedan bloqueadas.
        self.bloqueadas: dict[str, str] = {}

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
                self._fijar(expuesto, tool)

    async def llamar(self, nombre: str, args: dict[str, Any]) -> types.CallToolResult:
        if nombre not in self.rutas:
            return _error(f"Grifter no conoce la herramienta {nombre}.")
        servidor, original = self.rutas[nombre]
        bloqueo = await self._herramienta_bloqueada(nombre, servidor, original)   # fijación (#103)
        if bloqueo is not None:
            return bloqueo
        if original not in self.config.sensibles:
            regla = regla_por_argumentos(args)
            if regla is not None:
                log.warning("%s no estaba declarada como sensible; se revisa como pago", original)
                self.config.sensibles[original] = regla
        if original in self.config.sensibles:
            try:
                alerta = self.guardia.revisar(original, args, servidor)
                if alerta is not None:
                    if self._inundado():
                        self._registrar("retenido_sin_preguntar", alerta=alerta)
                        return _error(alerta.mensaje + " Hay demasiadas alertas seguidas: Grifter "
                                      "retiene todo sin preguntar por unos minutos.")
                    aprobada = self.escalar(alerta)
                    if inspect.isawaitable(aprobada):
                        aprobada = await aprobada
                    aprobada = aprobada is True   # solo True es el toque del dueño; «no» o 1 no aprueban
                    self._registrar("aprobado_por_dueno" if aprobada else "retenido", alerta=alerta)
                    if not aprobada:
                        return _error(alerta.mensaje)
                else:
                    self._registrar("permitido", herramienta=original, servidor=servidor, args=args)
            except Exception as e:  # falla cerrada: si Grifter no pudo revisar, no se reenvía
                log.exception("error al revisar %s", original)
                try:
                    self._registrar("error_de_revision", herramienta=original, servidor=servidor,
                                    error=type(e).__name__)
                except Exception:
                    pass
                return _error(f"Grifter retuvo la llamada a {original}: no pudo revisarla "
                              f"({type(e).__name__}). Por seguridad no se reenvía.")
        resultado = await self.sesiones[servidor].call_tool(original, args)
        self.guardia.anotar_resultado(servidor, original, _texto_de(resultado))
        return self._orden_retenida(servidor, original, resultado) or resultado   # mandato (#103)

    # --- Mandato y fijación de herramientas (#103) ---------------------------------------------

    def _fijar(self, expuesto: str, tool: types.Tool) -> None:
        """Compara la herramienta con su fijación. Sin fijaciones, deja su huella en el log para copiarla."""
        if not self.config.herramientas_fijadas:
            log.info("huella de %s: %s", tool.name, huella(tool.description, tool.inputSchema))
            return
        motivo = revisar_fijacion(self.config.herramientas_fijadas, tool.name, tool.description, tool.inputSchema)
        if motivo:
            log.warning("Grifter bloqueó %s: %s", tool.name, motivo)
            self.bloqueadas[expuesto] = motivo

    async def _herramienta_bloqueada(self, nombre: str, servidor: str,
                                     original: str) -> Optional[types.CallToolResult]:
        """Error si la herramienta no calza con su fijación, ahora o al conectar; None si puede seguir.

        Con fijaciones, antes de cada llamada se vuelve a listar la herramienta: un servidor que la cambia a
        mitad de la sesión (rug pull) no se salta la revisión. Si no se puede listar, falla cerrada.
        """
        if not self.config.herramientas_fijadas:
            return None
        motivo = self.bloqueadas.get(nombre)
        if motivo is None:
            try:
                vigentes = (await self.sesiones[servidor].list_tools()).tools
                tool = next((t for t in vigentes if t.name == original), None)
                motivo = (f"la herramienta {visible(original, 40)} ya no está en el servidor." if tool is None
                          else revisar_fijacion(self.config.herramientas_fijadas, original, tool.description,
                                                tool.inputSchema))
            except Exception as e:
                motivo = f"no pudo revisar la herramienta {visible(original, 40)} ({type(e).__name__})."
            if motivo:
                self.bloqueadas[nombre] = motivo
        if not motivo:
            return None
        self._registrar("herramienta_bloqueada", herramienta=original, servidor=servidor, motivo=motivo)
        return _error(f"Grifter bloqueó la llamada a {original}: {motivo} Pídele al dueño que la revise.")

    def _orden_retenida(self, servidor: str, original: str,
                        resultado: types.CallToolResult) -> Optional[types.CallToolResult]:
        """Si la orden que devolvió el MCP se desvía del mandato, el error que la reemplaza; si no, None."""
        try:
            motivo = self.guardia.revisar_orden(resultado)
        except Exception as e:  # falla cerrada: una orden que no se pudo comparar no llega al agente
            motivo = f"Grifter no pudo comparar la orden con el mandato ({type(e).__name__})."
        if not motivo:
            return None
        log.warning("Alerta para el dueño: %s", motivo)
        self._registrar("orden_retenida", herramienta=original, servidor=servidor, motivo=motivo)
        return _error(f"Grifter retuvo la orden de {original}. {motivo} No la pagues: confírmala con el dueño.")

    def _inundado(self) -> bool:
        """Cuenta esta alerta y dice si ya se pasó el tope de la ventana (contra el cansancio)."""
        ahora = time.monotonic()
        self._alertas_recientes = [t for t in self._alertas_recientes if ahora - t < VENTANA_ALERTAS_S]
        self._alertas_recientes.append(ahora)
        return len(self._alertas_recientes) > TOPE_ALERTAS

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
