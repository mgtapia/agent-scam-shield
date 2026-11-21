"""Capa 1 real: Pipelock como firewall de agentes (https://github.com/pipelab-org/pipelock).

Pipelock es abierto (núcleo Apache-2.0). Aquí solo se usa su binario como un proceso aparte, sin copiar
su código. Los binarios oficiales traen además código bajo ELv2 (carpeta `enterprise/` del repo): nunca
se redistribuyen con este proyecto, cada persona se baja el suyo. Ver NOTICE.md.

Qué se le pregunta a Pipelock:
- El contenido no confiable que el agente leyó (correo, web, MCP), con `POST /api/v1/scan` y
  `kind=prompt_injection`: instrucciones que pisan al agente, falso mensaje de sistema, pedido de
  credenciales, fuga del prompt de sistema.
- Las descripciones de herramientas MCP, con `pipelock mcp scan`, que arma su detector de envenenamiento
  de herramientas («Instruction Tag», instrucciones escondidas). La API HTTP no lo cubre.
- La acción sensible que el agente quiere hacer, con `kind=tool_call`: secretos y credenciales que salen
  en los argumentos.

Pipelock no sabe de estafas: una boleta falsa o un «cambio de cuenta» no le dicen nada. Eso es lo que
mide la eval y lo que cubre la capa 2.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..env.world import MCP, NO_CONFIABLES, World

URL_POR_DEFECTO = "http://127.0.0.1:9090"
VERSION_PROBADA = "3.8.0"


# Lo que un proceso hijo necesita para arrancar. Las llaves de API no están, a propósito: Pipelock es un
# binario de terceros y no tiene por qué ver las de los proveedores que el ejecutor cargó desde `.env`.
_VARIABLES_BASE = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR",
                   "HOME", "USERPROFILE", "LANG", "LC_ALL")


def entorno_minimo(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """El entorno con el que se lanza Pipelock: lo básico del sistema, más lo que se pida."""
    entorno = {k: os.environ[k] for k in _VARIABLES_BASE if k in os.environ}
    entorno.update(extra or {})
    return entorno


class PipelockNoDisponible(RuntimeError):
    """El firewall no respondió. Nunca se cae en silencio a «sin defensa»: se corta con este error."""


@dataclass
class Veredicto:
    bloquea: bool
    reglas: list[str] = field(default_factory=list)

    def motivo(self) -> str:
        return ", ".join(self.reglas) or "sin detalle"


# Un escáner MCP recibe (nombre de la herramienta, descripción) y devuelve el veredicto.
EscanerMcp = Callable[[str, str], Veredicto]


class EscanerMcpCli:
    """`pipelock mcp scan`: arma un `tools/list` con la descripción y mira si hay envenenamiento."""

    def __init__(self, binario: str, timeout: float = 20.0):
        self.binario, self.timeout = binario, timeout

    def __call__(self, nombre: str, descripcion: str) -> Veredicto:
        pedido = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [
            {"name": nombre, "description": descripcion, "inputSchema": {"type": "object"}}]}}
        try:
            r = subprocess.run([self.binario, "mcp", "scan", "--json"], input=json.dumps(pedido),
                               capture_output=True, text=True, encoding="utf-8", timeout=self.timeout,
                               env=entorno_minimo())
        except (OSError, subprocess.TimeoutExpired) as e:
            raise PipelockNoDisponible(f"no se pudo correr {self.binario} mcp scan: {e}") from e
        return parsear_mcp_scan(r.stdout)


def parsear_mcp_scan(salida: str) -> Veredicto:
    """Lee la línea JSON de `pipelock mcp scan --json`: `clean: false` es un hallazgo."""
    for linea in salida.splitlines():
        linea = linea.strip()
        if not linea.startswith("{"):
            continue
        try:
            d = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if "clean" not in d:
            continue
        reglas = [f"MCP-{p}" for t in d.get("tool_findings", []) for p in t.get("tool_poison", [])]
        reglas += [f"MCP-{k}" for k in ("response_injection_findings", "response_dlp_findings") if d.get(k)]
        if not d["clean"] and not reglas:
            reglas = ["MCP-hallazgo"]
        return Veredicto(not d["clean"], reglas)
    raise PipelockNoDisponible("pipelock mcp scan no devolvió un veredicto: " + salida[:200])


class ClientePipelock:
    """Cliente de la API de escaneo (`POST /api/v1/scan`) con caché por contenido."""

    def __init__(self, url: str = URL_POR_DEFECTO, token: str = "", timeout: float = 10.0,
                 escaner_mcp: Optional[EscanerMcp] = None):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.escaner_mcp = escaner_mcp
        self._cache: dict[tuple[str, str], Veredicto] = {}
        self.llamadas = 0   # pedidos reales a Pipelock (sin contar los de la caché)

    def escanear(self, kind: str, entrada: dict) -> Veredicto:
        cuerpo = json.dumps({"kind": kind, "input": entrada}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}/api/v1/scan", data=cuerpo, method="POST",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        self.llamadas += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            raise PipelockNoDisponible(f"Pipelock respondió {e.code} a {kind}: {e.read()[:200]!r}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise PipelockNoDisponible(f"no se pudo hablar con Pipelock en {self.url}: {e}") from e
        if d.get("status") != "completed":
            raise PipelockNoDisponible(f"Pipelock no completó el escaneo ({kind}): {d.get('errors')}")
        # `warn` no bloquea: es auditoría. Solo `deny` corta, como el proxy en línea.
        return Veredicto(d.get("decision") == "deny", [f["rule_id"] for f in d.get("findings", [])])

    def contenido(self, origen: str, texto: str) -> Veredicto:
        """Veredicto sobre un texto no confiable que el agente leyó."""
        clave = (origen, hashlib.sha256(texto.encode("utf-8")).hexdigest())
        if clave not in self._cache:
            v = self.escanear("prompt_injection", {"content": texto})
            if origen == MCP and self.escaner_mcp is not None:
                m = self.escaner_mcp("herramienta_mcp", texto)
                v = Veredicto(v.bloquea or m.bloquea, v.reglas + m.reglas)
            self._cache[clave] = v
        return self._cache[clave]

    def accion(self, herramienta: str, args: dict) -> Veredicto:
        return self.escanear("tool_call", {"tool_name": herramienta, "arguments": args})


def firewall(cliente: ClientePipelock):
    """Defensa de scamshield (mundo, herramienta, args) → motivo | None, respaldada por Pipelock."""

    def defensa(world: World, herramienta: str, args: dict) -> Optional[str]:
        for origen, texto in world.leidos:
            if origen not in NO_CONFIABLES:
                continue
            v = cliente.contenido(origen, texto)
            if v.bloquea:
                return f"Pipelock bloqueó contenido de {origen} ({v.motivo()})."
        v = cliente.accion(herramienta, args)
        if v.bloquea:
            return f"Pipelock bloqueó la acción {herramienta} ({v.motivo()})."
        return None

    return defensa


# --- Servidor local ---

def buscar_binario() -> Optional[str]:
    """`PIPELOCK_BIN`, o `pipelock` en el PATH."""
    ruta = os.environ.get("PIPELOCK_BIN", "").strip()
    return ruta if ruta and Path(ruta).is_file() else shutil.which("pipelock")


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServidorPipelock:
    """Levanta `pipelock run` con la API de escaneo en un puerto libre y un token al azar.

    El token es solo de esta corrida y solo escucha en 127.0.0.1. Los límites de tasa se suben porque
    una eval hace cientos de escaneos seguidos y el valor por defecto (ráfaga de 50) los corta.
    """

    def __init__(self, binario: str):
        self.binario = binario
        self.token = secrets.token_urlsafe(16)
        self.puerto = _puerto_libre()
        self.puerto_proxy = _puerto_libre()   # el proxy en línea no se usa, pero no debe chocar con otro
        self._proc: Optional[subprocess.Popen] = None
        self._dir: Optional[str] = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}"

    def config(self) -> str:
        return (f"mode: balanced\nscan_api:\n  listen: \"127.0.0.1:{self.puerto}\"\n  auth:\n"
                f"    bearer_tokens:\n      - \"{self.token}\"\n  rate_limit:\n    requests_per_minute: 60000\n"
                f"    burst: 5000\n  connection_limit: 1000\n")

    def iniciar(self, espera: float = 30.0) -> "ServidorPipelock":
        self._dir = tempfile.mkdtemp(prefix="pipelock_")
        cfg = Path(self._dir) / "pipelock.yaml"
        cfg.write_text(self.config(), encoding="utf-8")
        self._proc = subprocess.Popen(
            [self.binario, "run", "--config", str(cfg)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=entorno_minimo({"PIPELOCK_HOME": self._dir}))
        limite = time.monotonic() + espera
        cliente = ClientePipelock(self.url, self.token, timeout=2.0)
        while time.monotonic() < limite:
            if self._proc.poll() is not None:
                raise PipelockNoDisponible(f"pipelock terminó al arrancar (código {self._proc.returncode}).")
            try:
                cliente.escanear("prompt_injection", {"content": "hola"})
                atexit.register(self.detener)
                return self
            except PipelockNoDisponible:
                time.sleep(0.3)
        self.detener()
        raise PipelockNoDisponible(f"pipelock no respondió en {espera:.0f} s.")

    def detener(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._dir:
            shutil.rmtree(self._dir, ignore_errors=True)
            self._dir = None

    def cliente(self) -> ClientePipelock:
        return ClientePipelock(self.url, self.token, escaner_mcp=EscanerMcpCli(self.binario))

    def __enter__(self) -> "ServidorPipelock":
        return self.iniciar()

    def __exit__(self, *exc) -> None:
        self.detener()


_CLIENTE: Optional[ClientePipelock] = None


def cliente_por_defecto() -> ClientePipelock:
    """El cliente de esta corrida, creado una vez.

    - `PIPELOCK_URL` (y `PIPELOCK_TOKEN`): usa un Pipelock que ya está corriendo.
    - `PIPELOCK_BIN` (o `pipelock` en el PATH): lo levanta solo, en un puerto libre, y lo apaga al salir.
    """
    global _CLIENTE
    if _CLIENTE is None:
        binario = buscar_binario()
        escaner = EscanerMcpCli(binario) if binario else None
        if os.environ.get("PIPELOCK_URL", "").strip():
            _CLIENTE = ClientePipelock(os.environ["PIPELOCK_URL"], os.environ.get("PIPELOCK_TOKEN", ""),
                                       escaner_mcp=escaner)
        elif binario:
            _CLIENTE = ServidorPipelock(binario).iniciar().cliente()
        else:
            raise PipelockNoDisponible("define PIPELOCK_URL o PIPELOCK_BIN (ver README, «Capa 1»).")
    return _CLIENTE


def reiniciar_cliente() -> None:
    """Olvida el cliente por defecto (para pruebas)."""
    global _CLIENTE
    _CLIENTE = None
