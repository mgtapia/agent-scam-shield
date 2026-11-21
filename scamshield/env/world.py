"""El mundo simulado de un episodio: bandeja, web, banco, MCP y registro de acciones.

Todo es ficticio. El mundo guarda además el origen de cada texto que el agente puede leer,
para que la capa 2 sepa si un valor vino del dueño o de contenido no confiable.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# Orígenes posibles de un texto que entra al contexto del agente.
DUENO = "dueno"          # el encargo del dueño y sus datos guardados
CONFIABLE = "confiable"  # registros verificados (cuentas inscritas del dueño)
CORREO = "correo"
WEB = "web"
MCP = "mcp"
HERRAMIENTA = "herramienta"  # resultado de otra herramienta (por ejemplo, en una eval ajena como AgentDojo)
NO_CONFIABLES = {CORREO, WEB, MCP, HERRAMIENTA}


@dataclass
class Email:
    id: str
    de: str
    asunto: str
    cuerpo: str


@dataclass
class Accion:
    herramienta: str
    args: dict[str, Any]
    resultado: str
    bloqueada: bool = False
    motivo: str = ""


@dataclass
class World:
    encargo: str
    datos_dueno: dict[str, str] = field(default_factory=dict)       # RUT, dirección, código 2FA...
    cuentas_inscritas: dict[str, str] = field(default_factory=dict)  # nombre -> cuenta verificada
    correos: list[Email] = field(default_factory=list)
    paginas: dict[str, str] = field(default_factory=dict)            # url -> contenido
    mcp_herramientas: dict[str, str] = field(default_factory=dict)   # nombre -> descripción
    titulares: dict[str, dict[str, str]] = field(default_factory=dict)  # cuenta -> {nombre, rut}: lo que sabe el banco
    saldo: int = 1_000_000
    registro: list[Accion] = field(default_factory=list)
    # Textos que el agente ya leyó, con su origen: lista de (origen, texto).
    leidos: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.leidos.append((DUENO, self.encargo))
        for nombre, cuenta in self.cuentas_inscritas.items():
            self.leidos.append((CONFIABLE, f"{nombre}: {cuenta}"))

    def leer(self, origen: str, texto: str) -> str:
        self.leidos.append((origen, texto))
        return texto

    def origenes_de(self, valor: str) -> set[str]:
        """Dónde apareció un valor (cuenta, destinatario, monto) antes de usarse.

        Rastreo por coincidencia de valores: si el valor aparece completo en lo leído (no un pedazo de
        otro valor), se anota su origen.
        """
        return origenes_en(self.leidos, valor)

    def registrar(self, herramienta: str, args: dict[str, Any], resultado: str,
                  bloqueada: bool = False, motivo: str = "") -> None:
        self.registro.append(Accion(herramienta, args, resultado, bloqueada, motivo))

    def a_dict(self) -> dict[str, Any]:
        """Versión serializable, para guardar el mundo en el store de Inspect entre llamadas."""
        return asdict(self)

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> "World":
        w = World.__new__(World)  # sin __post_init__: los leídos ya vienen guardados
        w.encargo = d["encargo"]
        w.datos_dueno = dict(d["datos_dueno"])
        w.cuentas_inscritas = dict(d["cuentas_inscritas"])
        w.correos = [Email(**c) for c in d["correos"]]
        w.paginas = dict(d["paginas"])
        w.mcp_herramientas = dict(d["mcp_herramientas"])
        w.titulares = {k: dict(v) for k, v in d.get("titulares", {}).items()}
        w.saldo = int(d["saldo"])
        w.registro = [Accion(**a) for a in d["registro"]]
        w.leidos = [(o, t) for o, t in d["leidos"]]
        return w

    @staticmethod
    def desde_escenario(esc: dict[str, Any]) -> "World":
        return World(
            encargo=esc["encargo"],
            datos_dueno=dict(esc.get("datos_dueno", {})),
            cuentas_inscritas=dict(esc.get("cuentas_inscritas", {})),
            correos=[Email(**c) for c in esc.get("correos", [])],
            paginas=dict(esc.get("paginas", {})),
            mcp_herramientas=dict(esc.get("mcp_herramientas", {})),
            titulares={str(k): dict(v) for k, v in (esc.get("titulares") or {}).items()},
            saldo=int(esc.get("saldo", 1_000_000)),
        )


# Un trozo de texto: letras, dígitos y los signos que van dentro de una cuenta, un correo o un dominio.
_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ@._+\-]+")


def _tokens(texto: str) -> list[str]:
    """Trozos del texto separados por espacios o puntuación, normalizados (sin signos ni mayúsculas)."""
    return [t for t in (_normalizar(m) for m in _TOKEN.findall(str(texto))) if t]


def _aparece(valor_n: str, tokens: list[str]) -> bool:
    """El valor aparece completo: es la unión exacta de trozos seguidos, nunca un pedazo de uno.

    Así «17-2208» no cuenta como visto en «00-4417-2208», pero «00 4417 2208» sí cuenta como
    «00-4417-2208», y una URL o un correo leídos completos se reconocen como vistos.
    """
    for i in range(len(tokens)):
        acumulado = ""
        for t in tokens[i:]:
            acumulado += t
            if acumulado == valor_n:
                return True
            if not valor_n.startswith(acumulado):
                break
    return False


def origenes_en(leidos: Iterable[tuple[str, str]], valor: str) -> set[str]:
    """Orígenes de los textos leídos donde el valor aparece completo (sin mayúsculas ni signos)."""
    valor_n = _normalizar(valor)
    if not valor_n:
        return set()
    return {origen for origen, texto in leidos if _aparece(valor_n, _tokens(texto))}


def _normalizar(texto: str) -> str:
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())
