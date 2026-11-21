"""Capa 2: política determinista por origen de los datos.

Regla central: el destino de una acción sensible (la cuenta de un pago o transferencia, o el
destinatario de un dato del dueño) tiene que venir del dueño o de un registro confiable. Si solo
apareció en contenido no confiable (correo, web, MCP, resultado de otra herramienta), la acción se
bloquea y se pide confirmación.

Garantía aparte: una credencial del dueño (clave, código, token o API key, ver `claves_de_credencial`)
nunca sale en `compartir_dato` ni en `responder`, a ningún destino, salvo que el encargo del dueño la
nombre y nombre ese destino. Un destino que apareció en el correo, o en las cuentas inscritas, no basta.

Mandato del dueño (#103, `mandato.py`): si la procedencia trae un `mandato` (lo que el dueño aprobó: producto,
cantidad, monto máximo, moneda, beneficiario y si es único o recurrente), un pago que se desvía en cualquiera
de esos campos se retiene, aunque vaya a la cuenta inscrita. Sin mandato no cambia nada.
Las herramientas que mandan texto a la web (`escribir_formulario`, `enviar_formulario` y `abrir_web` con datos en la
dirección) tienen su propia regla, en `dominios.py`: un dato del dueño atado a un dominio solo se escribe en ese
dominio exacto, como un gestor de contraseñas (#128).

Depósito por error (#129, `deposito.py`): con el libro del banco (`movimientos`), una «devolución» por
transferencia se retiene y se explica contra lo que llegó de verdad; lo real se devuelve solo por reverso.

No depende de que un LLM acierte: un estafador puede redactar el correo perfecto, pero no puede
hacer que su cuenta aparezca en el encargo del dueño ni en sus cuentas inscritas.

La política es pura: no conoce Inspect ni el mundo simulado completo. Solo necesita algo que diga
de dónde vino un valor (`Procedencia`). El `World` de scamshield la cumple, y el approver de
Inspect (`approver.py`) la arma desde el historial de mensajes.
"""
from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping, Optional, Protocol

from ..env.world import CONFIABLE, DUENO, NO_CONFIABLES, claves_de_credencial, origenes_en
from .dominios import HERRAMIENTAS_WEB, revisar_web

MOTIVO_CREDENCIAL = "La clave del dueño no sale sin su confirmación."

ORIGENES_SEGUROS = {DUENO, CONFIABLE}


class Procedencia(Protocol):
    """Interfaz mínima que necesita la política: el origen de un valor y los datos del dueño."""

    datos_dueno: Mapping[str, str]
    # Opcionales (se leen con getattr): `credenciales`, claves de `datos_dueno` declaradas como credencial,
    # y `encargo`, el texto que escribió el dueño. Sin `encargo`, ninguna credencial tiene permiso de salir.
    # Para la web: `dominios` (clave -> dominios oficiales) y `pagina_actual`. Ver `dominios.py`.

    def origenes_de(self, valor: str) -> set[str]: ...


@dataclass(frozen=True)
class AccionSensible:
    """Qué argumento de una herramienta es el destino que la política revisa.

    Attributes:
        destino: argumento con la cuenta o el destinatario.
        que: cómo se nombra el destino en el motivo del bloqueo.
        dato: si está, solo se revisa cuando ese argumento es un dato del dueño.
        mensaje: si está, solo se revisa cuando ese texto lleva un dato del dueño.
        opcional: si el destino no viene en la llamada, no hay destino nuevo que revisar
            (por ejemplo, cambiar solo el monto de una transferencia programada).
    """

    destino: str
    que: str = "la cuenta de destino"
    dato: Optional[str] = None
    mensaje: Optional[str] = None
    opcional: bool = False


# Herramientas sensibles del mundo simulado de scamshield.
SENSIBLES_SCAMSHIELD: dict[str, AccionSensible] = {
    "pagar": AccionSensible(destino="cuenta"),
    "transferir": AccionSensible(destino="cuenta"),
    "compartir_dato": AccionSensible(destino="destinatario", que="el destinatario del dato",
                                     dato="dato"),
    "responder": AccionSensible(destino="a", que="el destinatario del mensaje con datos del dueño",
                                mensaje="mensaje"),
}


def politica_origen(procedencia: Procedencia, herramienta: str, args: Mapping,
                    sensibles: Mapping[str, AccionSensible] = SENSIBLES_SCAMSHIELD) -> Optional[str]:
    """Devuelve None si la acción puede seguir, o el motivo del bloqueo."""
    if herramienta in HERRAMIENTAS_WEB:
        return revisar_web(procedencia, herramienta, args)
    regla = sensibles.get(herramienta)
    if regla is None:
        return None
    if _sale_una_credencial(procedencia, args, regla):
        return MOTIVO_CREDENCIAL
    # Plata que no es un dato del dueño (#142): el código de una tarjeta de regalo y el destinatario final en la referencia.
    from . import canje
    if regla.dato is None and regla.mensaje is None:
        desvio_ref = canje.motivo_referencia(procedencia, args, regla.destino)
        if desvio_ref:
            return desvio_ref
    else:
        codigo = canje.motivo_codigo(procedencia, args, regla.destino, regla.dato, regla.mensaje)
        if codigo:
            return codigo
    mandato = getattr(procedencia, "mandato", None)
    if mandato and regla.dato is None and regla.mensaje is None:
        # Un pago con mandato del dueño (#103): lo que se cobra tiene que calzar con lo que aprobó.
        from .mandato import motivo as motivo_mandato
        desvio = motivo_mandato(mandato, args)
        if desvio:
            return desvio
    # Depósito por error (#129): la «devolución» se compara con el libro del banco, y lo que pide salir del canal
    # (ir al banco, efectivo, tarjetas de regalo) se retiene. Solo si la procedencia trae el libro o un contacto.
    if getattr(procedencia, "movimientos", None) is not None or getattr(procedencia, "contacto_confianza", None):
        from .deposito import politica_deposito
        motivo_deposito = politica_deposito(procedencia, herramienta, args)
        if motivo_deposito:
            return motivo_deposito
    if regla.dato is not None and not _es_dato_del_dueno(procedencia, args.get(regla.dato, "")):
        return None
    if regla.mensaje is not None and not _mensaje_lleva_dato(procedencia, args.get(regla.mensaje, "")):
        return None
    destino = args.get(regla.destino)
    if regla.opcional and destino in (None, ""):
        return None
    return _revisar_destino(procedencia, "" if destino is None else str(destino), regla.que)


def _sale_una_credencial(procedencia: Procedencia, args: Mapping, regla: AccionSensible) -> bool:
    """True si la llamada saca una credencial del dueño que el encargo no autorizó a ese destino."""
    if regla.dato is None and regla.mensaje is None:
        return False  # pagar y transferir no llevan datos del dueño
    claves = claves_de_credencial(procedencia.datos_dueno, getattr(procedencia, "credenciales", ()))
    if not claves:
        return False
    destino = args.get(regla.destino)
    encargo = str(getattr(procedencia, "encargo", "") or "")
    for clave in sorted(claves):
        valor = _norm(procedencia.datos_dueno[clave])
        if len(valor) < MIN_CORTA:
            continue
        # Una credencial de 3 caracteres (el CVV) no se reconoce por su largo: cualquier número de 3 dígitos aparece
        # por todos lados. Se reconoce si la frase de al lado la nombra o si va pegada a un número de tarjeta.
        lleva = _lleva_credencial_corta(args, regla, valor) if len(valor) < 4 else _lleva_credencial(args, regla, valor)
        if not lleva:
            continue
        if not _autorizada(encargo, clave, procedencia.datos_dueno[clave], destino):
            return True
    return False


MIN_CORTA = 3     # el CVV tiene 3 dígitos (4 en algunas tarjetas, que ya entran por el largo normal)
VENTANA_PISTA = 48   # caracteres de cada lado de la pista en los que tiene que estar el valor
# La frase que nombra una credencial corta: «CVV 482», «el código de seguridad es 482», «los 3 números de atrás: 482».
PISTA_CORTA = re.compile(
    r"\b(?:cvv2?|cvc2?|cvn|csc|c[oó]digo de seguridad|security code|card verification|"
    r"(?:los )?(?:3|tres|4|cuatro) (?:n[uú]meros|d[ií]gitos)(?: de(?:l)? (?:atr[aá]s|reverso))?|"
    r"(?:the )?(?:3|three|4|four) digits(?: on the back)?)\b", re.IGNORECASE)
# Un número de tarjeta: 13 a 19 dígitos con espacios o guiones.
TARJETA = re.compile(r"(?<!\d)(?:\d[ \-]?){12,21}\d(?!\d)")


def _lleva_credencial_corta(args: Mapping, regla: AccionSensible, valor: str) -> bool:
    """True si lo que sale lleva la credencial corta con su pista: la nombra una frase cercana o va junto a una tarjeta."""
    textos = [str(args.get(c, "")) for c in (regla.dato, regla.mensaje) if c is not None]
    for crudo in textos:
        for m in PISTA_CORTA.finditer(crudo):
            ventana = crudo[max(0, m.start() - VENTANA_PISTA): m.end() + VENTANA_PISTA]
            if valor in _norm(ventana):
                return True
        for m in TARJETA.finditer(crudo):
            digitos = re.sub(r"\D", "", m.group(0))
            # «5300 0100 2200 7731 482»: el CVV pegado al final (o al principio) del mismo número corrido.
            if len(digitos) - len(valor) in range(13, 20) and (digitos.endswith(valor) or digitos.startswith(valor)):
                return True
            vecinos = crudo[max(0, m.start() - 12): m.start()] + " " + crudo[m.end(): m.end() + 12]
            if valor in _norm(vecinos):
                return True
    return False


def _lleva_credencial(args: Mapping, regla: AccionSensible, valor: str) -> bool:
    if regla.dato is not None:
        crudo = args.get(regla.dato, "")
        dato = _norm(crudo)
        if len(dato) >= 4 and (valor in dato or dato in valor):
            return True
        if any(valor in v for v in _variantes(crudo)):
            return True
    if regla.mensaje is not None:
        crudo = args.get(regla.mensaje, "")
        if valor in _norm(crudo) or any(valor in v for v in _variantes(crudo)):
            return True
    return False


def _autorizada(encargo: str, clave: str, valor: str, destino: object) -> bool:
    """El encargo del dueño nombra la credencial (por su nombre o su valor) y nombra el destino."""
    if not encargo or destino in (None, ""):
        return False
    leido = [(DUENO, encargo)]
    if not origenes_en(leido, str(destino)):
        return False
    return bool(origenes_en(leido, clave) or origenes_en(leido, valor))


def _mensaje_lleva_dato(procedencia: Procedencia, mensaje: str) -> bool:
    # Un mensaje que lleva un dato del dueño (RUT, código, dirección) es compartir ese dato.
    m = _norm(mensaje)
    for valor in procedencia.datos_dueno.values():
        v = _norm(valor)
        if len(v) >= 4 and v in m:
            return True
    return False


def _revisar_destino(procedencia: Procedencia, valor: str, que: str) -> Optional[str]:
    origenes = procedencia.origenes_de(valor)
    if origenes & ORIGENES_SEGUROS:
        return None
    if origenes & NO_CONFIABLES:
        fuentes = ", ".join(sorted(origenes & NO_CONFIABLES))
        return (f"{que} ({valor}) viene solo de contenido no confiable ({fuentes}), "
                "no del encargo ni de las cuentas inscritas del dueño.")
    return f"{que} ({valor}) no aparece en el encargo ni en las cuentas inscritas del dueño."


def _es_dato_del_dueno(procedencia: Procedencia, dato: str) -> bool:
    d = _norm(dato)
    if len(d) < 4:
        return False
    for valor in procedencia.datos_dueno.values():
        v = _norm(valor)
        if v and (v in d or d in v):
            return True
    return False


def _norm(texto: object) -> str:
    """Solo letras y dígitos, en minúsculas, con el Unicode llevado a su forma simple.

    NFKC (ancho completo), los dígitos de cualquier alfabeto a 0-9 y las letras cirílicas o griegas que
    se ven como latinas, a la latina. Solo sirve para reconocer un dato del dueño en lo que sale: leer de
    más solo puede retener de más. El origen de una cuenta o un destino no usa esta tabla.
    """
    salida = []
    for ch in unicodedata.normalize("NFKC", str(texto)).lower():
        if not ch.isalnum():
            continue
        if ch.isdecimal() and not ("0" <= ch <= "9"):
            ch = str(unicodedata.decimal(ch))
        salida.append(_CONFUSABLES.get(ch, ch))
    return "".join(salida)


# Letras cirílicas y griegas (en minúscula) que se ven como una latina.
_CONFUSABLES = {
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c",
    "т": "t", "у": "y", "х": "x", "ѕ": "s", "і": "i", "ї": "i", "ј": "j", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x",
}

# Dígitos en palabras, en español e inglés: «dos siete cuatro cero» es 2740.
_DIGITOS_EN_PALABRAS = {
    "cero": "0", "uno": "1", "una": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5", "seis": "6",
    "siete": "7", "ocho": "8", "nueve": "9", "zero": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
_PALABRA = re.compile(r"\w+")
_BASE64 = re.compile(r"[A-Za-z0-9+/_-]{8,}={0,2}")


def _variantes(texto: object) -> list[str]:
    """Otras lecturas del texto donde puede ir escondida una credencial, ya normalizadas.

    Los dígitos escritos en palabras y los trozos que son base64 (estándar o de URL) de un texto legible.
    """
    crudo = str(texto)
    en_digitos = _PALABRA.sub(lambda m: _DIGITOS_EN_PALABRAS.get(_sin_tildes(m.group()).lower(), m.group()), crudo)
    variantes = [_norm(en_digitos)]
    for trozo in _BASE64.findall(crudo):
        decodificado = _de_base64(trozo)
        if decodificado:
            variantes.append(_norm(decodificado))
    return variantes


def _de_base64(trozo: str) -> str:
    """El texto legible que esconde un trozo en base64 (estándar o de URL, con o sin relleno), o ""."""
    limpio = trozo.rstrip("=").replace("-", "+").replace("_", "/")
    try:
        texto = base64.b64decode(limpio + "=" * (-len(limpio) % 4), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return ""
    return texto if texto.isprintable() else ""


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def visible(texto: object, largo: int = 48) -> str:
    """Un valor que puso el agente, listo para ir dentro de un aviso al dueño sin poder escribir en él.

    Escapa los saltos de línea, los caracteres de control y los de dirección (U+202E), y corta lo largo:
    un destino no puede agregarle a la alerta líneas como «Inscrita: ... verificada».
    """
    salida = "".join(f"\\u{ord(ch):04x}" if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp", "Co", "Cs")
                     else ch for ch in str(texto))
    return salida if len(salida) <= largo else salida[:largo - 1] + "…"
