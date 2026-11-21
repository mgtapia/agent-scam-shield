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

Integridad (#102): Grifter guarda la huella de la política que aprobó el dueño. Si `grifter.yaml` cambia, retiene
todo lo sensible y le manda el diff al dueño hasta que apruebe; y avisa (latido) al arrancar y al detenerse.
Ver `integridad.py`.

Con `mandato` en `grifter.yaml` (#103), un pago que se desvía de lo que aprobó el dueño (monto, producto,
cantidad, moneda, cuenta, recurrencia o cargos extra) se retiene, y una orden que devuelve el MCP con un
desvío no llega al agente. Con `herramientas_fijadas` (nombre -> SHA-256 de la descripción y el esquema),
una herramienta que cambió o que no se aprobó queda bloqueada; sin fijaciones, el log deja la huella de
cada herramienta al conectar, para copiarla.

Uso: python -m scamshield.mcp.proxy --config grifter.yaml            # stdio (Claude Desktop, Claude Code)
     GRIFTER_MCP_TOKEN=... python -m scamshield.mcp.proxy --http   # HTTP en /mcp, con token (ver docs/mcp.md)
Los MCP de abajo pueden ser procesos stdio (`comando`) o remotos por HTTP (`url`, `headers`).
Ejemplo de configuración: scamshield/mcp/grifter.ejemplo.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import re
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Optional, Protocol, Union

import mcp.types as types
import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from ..defenses.layer2 import MOTIVO_CREDENCIAL, SENSIBLES_SCAMSHIELD, AccionSensible, politica_origen, visible
from ..defenses.mandato import huella, motivo as motivo_mandato, parece_orden, revisar_fijacion
from ..env.world import CONFIABLE, DUENO, MCP, origenes_en
from .aprobaciones import (APROBADA, PENDIENTE, Aprobaciones, Aprobador, RegistroEncadenado, Solicitud,
                           aprobadores_de, cargar_semillas)
from .integridad import ENTORNO_CLAVE, Cambio, Integridad, corta
from .cliente_http import conectar_remoto

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
    """Un MCP de abajo: un proceso por stdio (`comando`) o uno remoto por HTTP (`url`)."""

    nombre: str
    comando: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: Optional[Path] = None
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    servidores: list[ServidorAbajo] = field(default_factory=list)
    cuentas_inscritas: dict[str, str] = field(default_factory=dict)
    datos_dueno: dict[str, str] = field(default_factory=dict)
    encargo: str = ""
    sensibles: dict[str, AccionSensible] = field(default_factory=lambda: dict(SENSIBLES_POR_DEFECTO))
    acciones: dict[str, str] = field(default_factory=lambda: dict(ACCION_POR_DEFECTO))
    registro: Optional[Path] = None
    capas: dict[str, bool] = field(default_factory=lambda: {"capa2": True})
    # Doble autorización (#102): quiénes aprueban, cuántos hacen falta y desde qué monto un pago los necesita.
    aprobadores: list[Aprobador] = field(default_factory=list)
    quorum: int = 1
    umbral_doble: int = 0            # 0 = los pagos no piden doble autorización
    semillas: Optional[Path] = None  # JSON {nombre: base32} fuera del repo; si no, GRIFTER_SEMILLAS
    registro_aprobaciones: Optional[Path] = None
    ruta: Optional[Path] = None      # el grifter.yaml del que salió, para vigilar que no cambie
    estado: Optional[Path] = None    # dónde se guarda la política aprobada (por defecto, junto al yaml)
    # Mandato del dueño (#103): lo que aprobó para el pago. Vacío, sin mandato.
    mandato: dict[str, Any] = field(default_factory=dict)
    # Fijación de herramientas (#103): nombre -> huella (SHA-256) de la descripción y el esquema aprobados.
    herramientas_fijadas: dict[str, str] = field(default_factory=dict)


def _con_entorno(valor: str, entorno: Mapping[str, str]) -> str:
    """Reemplaza `${VAR}` por la variable de entorno, para que el token del comercio no viva en el YAML.
    Si falta la variable, falla: no se conecta con credenciales a medias."""
    def sustituir(m: "re.Match[str]") -> str:
        if m.group(1) not in entorno:
            raise ValueError(f"grifter.yaml usa ${{{m.group(1)}}} y esa variable de entorno no está definida.")
        return entorno[m.group(1)]
    return re.sub(r"\$\{(\w+)\}", sustituir, valor)


def cargar_config(ruta: Union[str, Path]) -> Config:
    """Lee `grifter.yaml`. Las rutas relativas se resuelven contra la carpeta del archivo."""
    ruta = Path(ruta).resolve()
    base = ruta.parent
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

    servidores = []
    for nombre, s in (datos.get("servidores") or {}).items():
        if s.get("url"):   # un MCP remoto del comercio, por HTTP
            url = str(s["url"])
            if not url.startswith(("https://", "http://")):
                raise ValueError(f"El servidor {nombre} tiene una url que no es http(s): {url}")
            servidores.append(ServidorAbajo(
                nombre=str(nombre), url=url,
                headers={str(k): _con_entorno(str(v), os.environ) for k, v in (s.get("headers") or {}).items()}))
            continue
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
        ruta=ruta,
        mandato=dict(datos.get("mandato") or {}),
        herramientas_fijadas={str(k): str(v) for k, v in (datos.get("herramientas_fijadas") or {}).items()},
    )
    config.capas.update({str(k): bool(v) for k, v in (datos.get("capas") or {}).items()})
    if datos.get("estado"):
        estado = Path(str(datos["estado"]))
        config.estado = estado if estado.is_absolute() else base / estado
    config.aprobadores = [Aprobador(str(a["nombre"]), str(a.get("canal", ""))) for a in (datos.get("aprobadores") or [])]
    config.quorum = int(datos.get("quorum") or (2 if len(config.aprobadores) >= 2 else 1))
    config.umbral_doble = int(datos.get("umbral_doble") or 0)
    for campo, clave in (("semillas", "semillas"), ("registro_aprobaciones", "registro_aprobaciones")):
        if datos.get(clave):
            ruta_ = Path(str(datos[clave]))
            setattr(config, campo, ruta_ if ruta_.is_absolute() else base / ruta_)
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


class AprobadorPolitica(Protocol):
    """Quien le pregunta al dueño por un cambio de la política (por ejemplo, por Telegram)."""

    def pedir(self, cambio: Cambio) -> Any: ...

    def estado(self) -> Any:
        """True si el dueño aprobó, False si rechazó, None si todavía no responde."""


# Latido: (evento, datos) con evento «arranque» o «parada».
Latido = Callable[[str, dict[str, Any]], Any]


class Quorum(Protocol):
    """Lo que el proxy necesita para pedir y contar aprobaciones de varias personas (por Telegram, por ejemplo)."""

    aprobaciones: Aprobaciones

    def notificar(self, solicitud: Solicitud) -> Any: ...

    def sondear(self) -> Any:
        """Recoge los votos que llegaron desde la última vez."""

    def reconfigurar(self, politica: Mapping[str, Any]) -> None:
        """Pasa a los aprobadores y el quórum de esa política (cuando el dueño aprobó un cambio)."""


def _es_pago(herramienta: str, args: Mapping[str, Any]) -> bool:
    claves = {str(k).lower() for k in args}
    return herramienta in ("pagar", "transferir") or any(m in claves for m in CLAVES_DINERO)


def _monto(args: Mapping[str, Any]) -> float:
    """El monto de la llamada en pesos. Si no se puede leer, infinito: ante la duda, pide quórum."""
    for k, v in args.items():
        if str(k).lower() in CLAVES_DINERO:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
            digitos = "".join(ch for ch in str(v) if ch.isdigit())
            return float(digitos) if digitos else float("inf")
    return float("inf")


async def _resolver(valor: Any) -> Any:
    return await valor if inspect.isawaitable(valor) else valor


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

    def actualizar(self, config: Config) -> None:
        """Pasa a la política nueva que aprobó el dueño. Lo confiable viejo sale; lo leído de los servidores se queda."""
        pares = [(l, f) for l, f in zip(self.leidos, self.fuentes) if f is not None]
        self.leidos, self.fuentes = [l for l, _ in pares], [f for _, f in pares]
        self.config, self.datos_dueno, self.encargo = config, dict(config.datos_dueno), config.encargo
        self.mandato = dict(config.mandato)
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

    def revisar(self, herramienta: str, args: Mapping[str, Any], servidor: str = "",
                regla: Optional[AccionSensible] = None) -> Optional[Alerta]:
        """None si la llamada puede seguir; si no, la alerta con el aviso para el agente.

        `regla` es la de un pago anidado dentro de los argumentos (ver `subargumentos`); sin ella, la de `sensibles`.
        """
        regla = regla or self.config.sensibles.get(herramienta)
        if regla is None:
            return None
        desvio = self._fuera_del_mandato(regla, args)
        if desvio:
            accion = self.config.acciones.get(herramienta, f"la llamada a {herramienta}")
            return Alerta(herramienta=herramienta, servidor=servidor, args=dict(args),
                          valor=str(args.get(regla.destino, "")), motivo=desvio, fuentes=[],
                          mensaje=(f"Grifter retuvo {accion}. {desvio} Confírmalo con el dueño por un canal "
                                   "conocido antes de reintentar."))
        motivo = politica_origen(self, herramienta, args, {herramienta: regla})
        if motivo is None:
            return None
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

    def _fuera_del_mandato(self, regla: Optional[AccionSensible], args: Mapping[str, Any]) -> Optional[str]:
        """El desvío de un pago respecto del mandato del dueño (#103), o None. Solo en pagos, no en datos."""
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


def subargumentos(args: Any, profundidad: int = 6) -> list[Mapping[str, Any]]:
    """Los diccionarios anidados dentro de los argumentos (en valores y listas), sin contar los argumentos mismos.

    Un servidor puede recibir el pago como `{"pago": {"cuenta": ...}}` o `{"pagos": [{...}, {...}]}`: la cuenta
    escondida ahí no está en el primer nivel, y revisar solo el primer nivel la dejaba pasar.
    """
    salida: list[Mapping[str, Any]] = []
    if profundidad <= 0:
        return salida
    valores = args.values() if isinstance(args, Mapping) else args if isinstance(args, (list, tuple)) else ()
    for v in valores:
        if isinstance(v, Mapping):
            salida.append(v)
        salida.extend(subargumentos(v, profundidad - 1))
    return salida


def _error(mensaje: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=mensaje)], isError=True)


class Grifter:
    def __init__(self, config: Config, escalar: Escalar = escalar_por_defecto,
                 integridad: Optional[Integridad] = None, aprobador: Optional[AprobadorPolitica] = None,
                 latido: Optional[Latido] = None, quorum: Optional[Quorum] = None):
        self.config = config
        self.guardia = Guardia(config)
        self.escalar = escalar
        self.integridad, self.aprobador, self.latido, self.quorum = integridad, aprobador, latido, quorum
        self._pagos: dict[tuple[str, str, float], str] = {}   # pago grande pendiente -> id de su solicitud
        self._pedido: Optional[str] = None      # la huella cuyo cambio ya se le mandó al dueño
        self._rechazado: Optional[str] = None   # la huella que el dueño rechazó
        self.sesiones: dict[str, ClientSession] = {}
        # Nombre expuesto -> (servidor, nombre original de la herramienta).
        self.rutas: dict[str, tuple[str, str]] = {}
        self.herramientas: list[types.Tool] = []
        self._alertas_recientes: list[float] = []
        # Herramientas que no calzan con su fijación (#103): nombre expuesto -> motivo. Quedan bloqueadas.
        self.bloqueadas: dict[str, str] = {}

    async def conectar(self, pila: AsyncExitStack, errlog=None) -> None:
        """Conecta cada servidor de abajo (stdio o HTTP) y junta sus herramientas.

        Un MCP remoto que no responde al arrancar queda fuera (falla cerrada: sus herramientas no se
        exponen y nada se le reenvía) y se anota en el registro. Un servidor stdio que no arranca sí
        detiene a Grifter: lo puso el dueño en su propia máquina."""
        for s in self.config.servidores:
            if s.url:
                await conectar_remoto(self, pila, s)
                continue
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
            await self._exponer(s.nombre, sesion)

    def _olvidar(self, servidor: str) -> None:
        self.rutas = {n: r for n, r in self.rutas.items() if r[0] != servidor}
        self.herramientas = [t for t in self.herramientas if t.name in self.rutas]
        self.sesiones.pop(servidor, None)

    async def _exponer(self, servidor: str, sesion: ClientSession) -> None:
        self.sesiones[servidor] = sesion
        for tool in (await sesion.list_tools()).tools:
            expuesto = tool.name if tool.name not in self.rutas else f"{servidor}_{tool.name}"
            self.rutas[expuesto] = (servidor, tool.name)
            self.herramientas.append(tool.model_copy(update={"name": expuesto}))
            # La descripción también es contenido del servidor de abajo.
            self.guardia.anotar_resultado(servidor, f"la descripción de {tool.name}", tool.description or "")
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
        # Pagos escondidos dentro de un argumento anidado: cada uno se revisa con su propia regla.
        anidados = [(sub, r) for sub in subargumentos(args)
                    for r in [self._regla_para(original, sub)] if r is not None]
        if original in self.config.sensibles or anidados:
            try:
                retenida = await self._politica_pendiente()
                if retenida:
                    self._registrar("retenido_por_politica", herramienta=original, servidor=servidor, args=args)
                    return _error(f"Grifter retuvo la llamada a {original}: {retenida}")
                alerta = None
                if self.config.capas.get("capa2", True):
                    if original in self.config.sensibles:
                        alerta = self.guardia.revisar(original, args, servidor)
                    for sub, regla in anidados:
                        if alerta is not None:
                            break
                        alerta = self.guardia.revisar(original, sub, servidor, regla)
                else:
                    self._registrar("capa2_apagada", herramienta=original, servidor=servidor, args=args)
                if self.quorum is not None and self.config.umbral_doble > 0 and _es_pago(original, args):
                    monto = _monto(args)
                    if monto > self.config.umbral_doble:
                        espera = await self._quorum_de_pago(original, servidor, args, alerta, monto)
                        if espera is not None:
                            return espera
                        alerta = None   # los aprobadores lo aprobaron: ya no depende del aviso al dueño
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
        try:
            resultado = await self.sesiones[servidor].call_tool(original, args)
        except Exception as e:   # el MCP de abajo cayó o no contestó: no se inventa un resultado
            log.error("el MCP %s falló al llamar a %s (%s)", servidor, original, type(e).__name__)
            self._registrar("servidor_inalcanzable", herramienta=original, servidor=servidor,
                            error=type(e).__name__)
            return _error(f"Grifter no pudo llegar a {servidor} para {original} ({type(e).__name__}). "
                          "La llamada no se completó; no la reintentes con otro destino.")
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

    def _regla_para(self, herramienta: str, args: Mapping[str, Any]) -> Optional[AccionSensible]:
        """La regla con la que revisar un diccionario anidado: la de la herramienta si trae su destino, o la que delatan sus claves."""
        declarada = self.config.sensibles.get(herramienta)
        if declarada is not None and declarada.destino in args:
            return declarada
        return regla_por_argumentos(args)

    # --- Doble autorización (#102) -------------------------------------------------------------------
    async def _quorum_de_pago(self, herramienta: str, servidor: str, args: dict[str, Any],
                              alerta: Optional[Alerta], monto: float) -> Optional[types.CallToolResult]:
        """None si los aprobadores ya aprobaron este pago (sale una sola vez); si no, el error con el avance."""
        regla = self.config.sensibles[herramienta]
        valor = str(args.get(regla.destino, ""))
        accion = self.config.acciones.get(herramienta, f"la llamada a {herramienta}")
        ap = self.quorum.aprobaciones
        clave = (herramienta, valor, monto)
        id_ = self._pagos.get(clave)
        if id_ is not None:
            await _resolver(self.quorum.sondear())
            estado = ap.estado(id_)
            if estado == APROBADA:
                ap.consumir(id_)
                del self._pagos[clave]
                self._registrar("aprobado_por_quorum", herramienta=herramienta, servidor=servidor, args=args)
                return None
            if estado == PENDIENTE:
                return _error(f"Grifter retuvo {accion}: es un pago sobre el umbral y espera la doble autorización "
                              f"({ap.progreso(id_)}). No lo reintentes con otra cuenta.")
            del self._pagos[clave]   # rechazada o vencida
            self._registrar("rechazado_por_quorum", herramienta=herramienta, servidor=servidor, args=args,
                            estado=estado)
            return _error(f"Grifter retuvo {accion}: los aprobadores no lo aprobaron ({estado}).")
        if self._inundado():
            self._registrar("retenido_sin_preguntar", herramienta=herramienta, servidor=servidor, args=args)
            return _error(f"Grifter retuvo {accion}: hay demasiadas solicitudes seguidas; retiene todo por unos minutos.")
        de_cuanto = f"${int(monto):,}".replace(",", ".") if monto != float("inf") else "un monto que no se pudo leer"
        detalle = f"{accion[0].upper() + accion[1:]} de {de_cuanto} a {regla.que} {valor}"
        if alerta is not None:
            detalle += f"\n{alerta.mensaje}"
        s = ap.abrir("pago", detalle, int(monto) if monto != float("inf") else "?", valor)
        self._pagos[clave] = s.id
        self._registrar("quorum_pedido", herramienta=herramienta, servidor=servidor, args=args, solicitud=s.id)
        await _resolver(self.quorum.notificar(s))
        return _error(f"Grifter retuvo {accion}: es un pago sobre el umbral y espera la doble autorización "
                      f"({ap.progreso(s.id)}).")

    # --- Integridad (#102) ---------------------------------------------------------------------------
    async def _politica_pendiente(self) -> str:
        """Vacío si la política es la que aprobó el dueño; si no, el motivo de la retención.

        La primera vez que ve un cambio le manda el diff al dueño; después solo pregunta si ya respondió. Si
        aprueba, Grifter pasa a la política nueva; si rechaza, sigue reteniendo hasta que se restaure el archivo.
        """
        if self.integridad is None:
            return ""
        cambio = self.integridad.cambio()
        if cambio is None:
            self._pedido = self._rechazado = None
            return ""
        clave = cambio.huella_nueva or f"ilegible:{cambio.ilegible}"
        if self._pedido != clave:
            self._pedido = clave
            self._registrar("politica_cambio", cambio=cambio.texto, huella=corta(cambio.huella_nueva))
            if self.aprobador is not None:
                await _resolver(self.aprobador.pedir(cambio))
        if self._rechazado == clave:
            return "el dueño rechazó el cambio de la política; restaura grifter.yaml."
        decision = await _resolver(self.aprobador.estado()) if self.aprobador is not None else None
        if decision is True and not cambio.ilegible:
            config, politica, _ = self.integridad.leer_actual()
            if config is not None and politica is not None:
                self.integridad.aprobar(politica, "dueño")
                self.config.cuentas_inscritas = dict(config.cuentas_inscritas)
                self.config.datos_dueno, self.config.encargo = dict(config.datos_dueno), config.encargo
                self.config.sensibles, self.config.acciones = dict(config.sensibles), dict(config.acciones)
                self.config.capas = dict(config.capas)
                self.config.aprobadores, self.config.quorum = list(config.aprobadores), config.quorum
                self.config.umbral_doble = config.umbral_doble
                # #103: un mandato o unas fijaciones nuevas valen desde que el dueño las aprueba. Las herramientas
                # bloqueadas se vuelven a revisar contra las fijaciones nuevas en la próxima llamada.
                self.config.mandato = dict(config.mandato)
                self.config.herramientas_fijadas = dict(config.herramientas_fijadas)
                self.bloqueadas.clear()
                self.guardia.actualizar(self.config)
                if self.quorum is not None:
                    self.quorum.reconfigurar(politica)
                self._pedido = None
                self._registrar("politica_aprobada", huella=corta(cambio.huella_nueva))
                return ""
        if decision is False:
            self._rechazado = clave
            self._registrar("politica_rechazada", huella=corta(cambio.huella_nueva))
            return "el dueño rechazó el cambio de la política; restaura grifter.yaml."
        return ("la política (grifter.yaml) cambió desde la última que aprobó el dueño y espera su aprobación. "
                "Hasta entonces no sale ningún pago ni envío de datos.")

    def _datos_latido(self) -> dict[str, Any]:
        aprobada = None
        if self.integridad is not None:
            try:
                estado = self.integridad.estado()
                aprobada = corta(estado.huella) if estado else None
            except Exception:
                aprobada = None
        return {"capas": dict(self.config.capas), "huella": aprobada,
                "servidores": [s.nombre for s in self.config.servidores]}

    async def arrancar(self) -> str:
        """Al arrancar: revisa la política, avisa al dueño del cambio si lo hay y manda el latido."""
        modo = "sin_vigilancia"
        if self.integridad is not None:
            try:
                modo = self.integridad.arrancar()
            except Exception:
                log.exception("no se pudo revisar la política al arrancar")
                modo = "cambio"
            if modo == "cambio":
                await self._politica_pendiente()   # le manda el diff al dueño desde el principio
        await self._avisar("arranque", {**self._datos_latido(), "politica": modo})
        return modo

    async def detener(self) -> None:
        await self._avisar("parada", self._datos_latido())

    async def _avisar(self, evento: str, datos: dict[str, Any]) -> None:
        self._registrar("latido_" + evento, **datos)
        if self.latido is None:
            return
        try:
            await _resolver(self.latido(evento, datos))
        except Exception:   # un aviso caído no detiene al proxy, pero queda dicho
            log.exception("no se pudo mandar el latido de %s", evento)

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


async def correr(config: Config, escalar: Escalar = escalar_por_defecto,
                 integridad: Optional[Integridad] = None, aprobador: Optional[AprobadorPolitica] = None,
                 latido: Optional[Latido] = None, quorum: Optional[Quorum] = None) -> None:
    grifter = Grifter(config, escalar, integridad, aprobador, latido, quorum)
    async with AsyncExitStack() as pila:
        await grifter.conectar(pila)
        await grifter.arrancar()
        try:
            servidor = grifter.servidor_mcp()
            async with stdio_server() as (read, write):
                await servidor.run(read, write, servidor.create_initialization_options())
        finally:
            await grifter.detener()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Grifter como proxy MCP con la capa 2.")
    parser.add_argument("--config", default="grifter.yaml", help="configuración del dueño")
    parser.add_argument("--encargo", default=None,
                        help="texto del encargo del dueño; se suma a lo confiable")
    parser.add_argument("--http", action="store_true",
                        help="expone streamable HTTP en /mcp en vez de stdio (clientes que mandan cabecera, como Claude Code; "
                             "ChatGPT y Claude.ai piden OAuth, ver docs/mcp.md); "
                             "pide GRIFTER_MCP_TOKEN en el entorno")
    parser.add_argument("--host", default="127.0.0.1", help="con --http: dirección donde escucha")
    parser.add_argument("--puerto", type=int, default=8766, help="con --http: puerto")
    args = parser.parse_args(argv)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="grifter: %(message)s")
    log.setLevel(logging.INFO)
    config = cargar_config(args.config)
    if args.encargo:
        config.encargo = args.encargo
    integridad = None
    if config.ruta is not None:
        integridad = Integridad(config.ruta, config.estado, clave=os.environ.get(ENTORNO_CLAVE) or None)
    escalar, aprobador, latido = escalar_por_defecto, None, None
    from .alerta_telegram import ganchos_desde_entorno   # import tardío: el proxy no depende de la demo

    telegram = ganchos_desde_entorno(os.environ)
    quorum = None
    if telegram is not None:
        escalar, aprobador, latido = telegram.escalar, telegram.aprobador, telegram.latido
        if config.aprobadores:   # con aprobadores, los cambios de política y los pagos grandes piden quórum
            from .alerta_telegram import quorum_desde_entorno

            quorum = quorum_desde_entorno(config, integridad, telegram.canal, os.environ)
            aprobador = quorum.aprobador_de_politica()
    if args.http:   # el mismo Grifter, con sus ganchos, detrás de /mcp (#105)
        from .remoto import servir
        servir(config, host=args.host, puerto=args.puerto,
               grifter=Grifter(config, escalar, integridad, aprobador, latido, quorum))
        return
    asyncio.run(correr(config, escalar, integridad, aprobador, latido, quorum))


if __name__ == "__main__":
    main()
