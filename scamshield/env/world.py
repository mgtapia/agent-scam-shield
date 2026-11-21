"""El mundo simulado de un episodio: bandeja, web, banco, MCP y registro de acciones.

Todo es ficticio. El mundo guarda además el origen de cada texto que el agente puede leer,
para que la capa 2 sepa si un valor vino del dueño o de contenido no confiable.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Optional

# Orígenes posibles de un texto que entra al contexto del agente.
DUENO = "dueno"          # el encargo del dueño y sus datos guardados
CONFIABLE = "confiable"  # registros verificados (cuentas inscritas del dueño)
CORREO = "correo"
WEB = "web"
MCP = "mcp"
LLAMADA = "llamada"  # transcripción de una llamada: el número que se muestra se puede falsificar
WHATSAPP = "whatsapp"  # mensaje de chat con sus notas de voz y adjuntos como texto: el remitente puede ser cualquiera
HERRAMIENTA = "herramienta"  # resultado de otra herramienta (por ejemplo, en una eval ajena como AgentDojo)
NO_CONFIABLES = {CORREO, WEB, MCP, HERRAMIENTA, LLAMADA, WHATSAPP}


@dataclass
class Email:
    id: str
    de: str
    asunto: str
    cuerpo: str
    # Lo que el servidor de correo verificó del remitente: {"spf": "pass", "dkim": "pass", "dmarc": "pass"}. Un correo
    # que sale de una cuenta legítima (un replay de DKIM, un cobro real con la nota del estafador) pasa los tres. Es
    # informativo: ninguna defensa de Grifter decide por esto, porque la retención no depende de quién manda.
    autenticacion: dict[str, str] = field(default_factory=dict)


@dataclass
class Llamada:
    """Una llamada que llega como transcripción. `de` es el número que se muestra (falsificable)."""

    id: str
    de: str
    quien_dice_ser: str
    transcripcion: str


@dataclass
class MensajeChat:
    """Un mensaje de chat (WhatsApp). `de` es el número que lo manda, que puede ser nuevo o robado.

    Los adjuntos llegan como texto: una nota de voz como su transcripción y un documento como el texto que se lee en
    él. Son contenido no confiable igual que el cuerpo. Cada adjunto: `tipo` (nota_de_voz, documento, imagen) y `texto`.
    """

    id: str
    de: str
    quien_dice_ser: str
    texto: str
    adjuntos: list[dict[str, Any]] = field(default_factory=list)

    def completo(self) -> str:
        """El mensaje como lo lee el agente: el encabezado, el texto y, debajo, cada adjunto con su tipo."""
        partes = [f"[{self.id}] Chat de: {self.de} (dice ser: {self.quien_dice_ser})", self.texto]
        for a in self.adjuntos:
            etiqueta = {"nota_de_voz": "Nota de voz (transcripción)", "documento": "Documento (texto)",
                        "imagen": "Imagen (texto)"}.get(str(a.get("tipo")), "Adjunto")
            nombre = f" {a['nombre']}" if a.get("nombre") else ""
            partes.append(f"[{etiqueta}{nombre}] {a.get('texto', '')}")
        return "\n".join(partes)


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
    llamadas: list[Llamada] = field(default_factory=list)
    chat: list[MensajeChat] = field(default_factory=list)
    paginas: dict[str, str] = field(default_factory=dict)            # url -> contenido
    mcp_herramientas: dict[str, str] = field(default_factory=dict)   # nombre -> descripción
    titulares: dict[str, dict[str, str]] = field(default_factory=dict)  # cuenta -> {nombre, rut}: lo que sabe el banco
    saldo: int = 1_000_000
    # Claves de `datos_dueno` que son credenciales (clave, código, token, API key), además de las que
    # `claves_de_credencial` reconoce por el nombre.
    credenciales: list[str] = field(default_factory=list)
    # Lo que el dueño aprobó para un pago (producto, cantidad, monto máximo, moneda, beneficiario, recurrencia):
    # el mandato de `defenses/mandato.py`. Vacío: sin mandato.
    mandato: dict[str, Any] = field(default_factory=dict)
    # El libro de movimientos del banco (#129): [{id, monto, origen, glosa}], abonos con monto positivo. Es la verdad
    # sobre qué plata llegó, no el comprobante. None: el banco no entrega el libro (distinto de un libro vacío).
    movimientos: Optional[list[dict[str, Any]]] = None
    # Un familiar inscrito que recibe el aviso cuando alguien pide sacar la plata del canal (#129): {nombre, canal}.
    contacto_confianza: dict[str, str] = field(default_factory=dict)
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

    def avisar(self, a: str, mensaje: str, por: str = "agente") -> bool:
        """Deja un aviso al dueño (`a="dueno"`) o al contacto de confianza (`a="contacto"`). False si no hay contacto."""
        if a == "contacto" and not self.contacto_confianza:
            return False
        destino = "dueño" if a == "dueno" else self.contacto_confianza.get("nombre", "contacto")
        self.registrar("avisar_dueno" if a == "dueno" else "avisar_contacto",
                       {"a": destino, "mensaje": mensaje, "por": por}, "enviado")
        return True

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
        w.llamadas = [Llamada(**c) for c in d.get("llamadas", [])]
        w.chat = [MensajeChat(**c) for c in d.get("chat", [])]
        w.paginas = dict(d["paginas"])
        w.mcp_herramientas = dict(d["mcp_herramientas"])
        w.titulares = {k: dict(v) for k, v in d.get("titulares", {}).items()}
        w.saldo = int(d["saldo"])
        w.credenciales = list(d.get("credenciales", []))
        w.mandato = dict(d.get("mandato") or {})
        movimientos = d.get("movimientos")
        w.movimientos = None if movimientos is None else [dict(m) for m in movimientos]
        w.contacto_confianza = dict(d.get("contacto_confianza") or {})
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
            llamadas=[Llamada(**c) for c in esc.get("llamadas", [])],
            chat=[MensajeChat(**c) for c in esc.get("chat", [])],
            paginas=dict(esc.get("paginas", {})),
            mcp_herramientas=dict(esc.get("mcp_herramientas", {})),
            titulares={str(k): dict(v) for k, v in (esc.get("titulares") or {}).items()},
            saldo=int(esc.get("saldo", 1_000_000)),
            credenciales=[str(k) for k in (esc.get("credenciales") or [])],
            mandato=dict(esc.get("mandato") or {}),
            movimientos=(None if esc.get("movimientos") is None else [dict(m) for m in esc["movimientos"]]),
            contacto_confianza={str(k): str(v) for k, v in (esc.get("contacto_confianza") or {}).items()},
        )


# Un trozo de texto: letras, dígitos y los signos que van dentro de una cuenta, un correo o un dominio.
_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ@._+\-]+")


def _tokens(texto: str) -> list[str]:
    """Trozos del texto separados por espacios o puntuación, normalizados (sin signos ni mayúsculas).

    Lo leído pasa antes por `_simple` (ancho completo y dígitos de otros alfabetos a 0-9) para que una
    cuenta escrita así se reconozca donde apareció. El valor que se usa no pasa por ahí: una cuenta o un
    destino con caracteres raros no calza con lo confiable y se retiene.
    """
    return [t for t in (_normalizar(m) for m in _TOKEN.findall(_simple(str(texto)))) if t]


def _simple(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto)
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() and not "0" <= ch <= "9" else ch
                   for ch in texto)


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


# Palabras que, dentro del nombre de una clave de `datos_dueno`, la marcan como credencial.
_PALABRAS_CREDENCIAL = {
    "clave", "claves", "contrasena", "contrasenas", "password", "passwd", "passphrase", "codigo",
    "codigos", "code", "token", "secret", "secreto", "pin", "otp", "apikey",
}
_NO_CREDENCIAL = {"postal", "zip", "region", "comuna", "area"}  # «codigo_postal» no es una clave


def es_clave_de_credencial(nombre: str) -> bool:
    """El nombre de un dato del dueño dice que es una credencial («clave_banca», «verification_code»)."""
    palabras = re.findall(r"[a-z0-9]+", _sin_tildes(str(nombre)).lower())
    if _NO_CREDENCIAL & set(palabras):
        return False
    return bool(_PALABRAS_CREDENCIAL & set(palabras)) or "apikey" in "".join(palabras)


def claves_de_credencial(datos_dueno: Mapping[str, str], declaradas: Iterable[str] = ()) -> set[str]:
    """Claves de `datos_dueno` que son credenciales: las declaradas y las que el nombre delata."""
    declaradas = set(declaradas)
    return {k for k in datos_dueno if k in declaradas or es_clave_de_credencial(k)}


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def origenes_en(leidos: Iterable[tuple[str, str]], valor: str) -> set[str]:
    """Orígenes de los textos leídos donde el valor aparece completo (sin mayúsculas ni signos)."""
    valor_n = _normalizar(valor)
    if not valor_n:
        return set()
    return {origen for origen, texto in leidos if _aparece(valor_n, _tokens(texto))}


def _normalizar(texto: str) -> str:
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())
