"""Capa 2: política determinista por origen de los datos.

Regla central: el destino de una acción sensible (la cuenta de un pago o transferencia, o el
destinatario de un dato del dueño) tiene que venir del dueño o de un registro confiable. Si solo
apareció en contenido no confiable (correo, web, MCP, resultado de otra herramienta), la acción se
bloquea y se pide confirmación.

No depende de que un LLM acierte: un estafador puede redactar el correo perfecto, pero no puede
hacer que su cuenta aparezca en el encargo del dueño ni en sus cuentas inscritas.

La política es pura: no conoce Inspect ni el mundo simulado completo. Solo necesita algo que diga
de dónde vino un valor (`Procedencia`). El `World` de scamshield la cumple, y el approver de
Inspect (`approver.py`) la arma desde el historial de mensajes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol

from ..env.world import CONFIABLE, DUENO, NO_CONFIABLES

ORIGENES_SEGUROS = {DUENO, CONFIABLE}


class Procedencia(Protocol):
    """Interfaz mínima que necesita la política: el origen de un valor y los datos del dueño."""

    datos_dueno: Mapping[str, str]

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
    regla = sensibles.get(herramienta)
    if regla is None:
        return None
    if regla.dato is not None and not _es_dato_del_dueno(procedencia, args.get(regla.dato, "")):
        return None
    if regla.mensaje is not None and not _mensaje_lleva_dato(procedencia, args.get(regla.mensaje, "")):
        return None
    destino = args.get(regla.destino)
    if regla.opcional and destino in (None, ""):
        return None
    return _revisar_destino(procedencia, "" if destino is None else str(destino), regla.que)


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
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())
