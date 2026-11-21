"""El mundo simulado de un episodio: bandeja, web, banco, MCP y registro de acciones.

Todo es ficticio. El mundo guarda además el origen de cada texto que el agente puede leer,
para que la capa 2 sepa si un valor vino del dueño o de contenido no confiable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Orígenes posibles de un texto que entra al contexto del agente.
DUENO = "dueno"          # el encargo del dueño y sus datos guardados
CONFIABLE = "confiable"  # registros verificados (cuentas inscritas del dueño)
CORREO = "correo"
WEB = "web"
MCP = "mcp"
NO_CONFIABLES = {CORREO, WEB, MCP}


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

        Rastreo por coincidencia de valores: si el texto exacto aparece en lo leído, se anota su origen.
        """
        valor_n = _normalizar(valor)
        if not valor_n:
            return set()
        return {origen for origen, texto in self.leidos if valor_n in _normalizar(texto)}

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
            saldo=int(esc.get("saldo", 1_000_000)),
        )


def _normalizar(texto: str) -> str:
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())
