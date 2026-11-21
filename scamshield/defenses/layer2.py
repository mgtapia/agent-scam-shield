"""Capa 2: política determinista por origen de los datos.

Regla central: el destino de una acción sensible (la cuenta de un pago o transferencia, o el
destinatario de un dato del dueño) tiene que venir del dueño o de un registro confiable. Si solo
apareció en contenido no confiable (correo, web, MCP), la acción se bloquea y se pide confirmación.

No depende de que un LLM acierte: un estafador puede redactar el correo perfecto, pero no puede
hacer que su cuenta aparezca en el encargo del dueño ni en sus cuentas inscritas.
"""
from __future__ import annotations

from typing import Optional

from ..env.world import CONFIABLE, DUENO, NO_CONFIABLES, World

ORIGENES_SEGUROS = {DUENO, CONFIABLE}


def politica_origen(world: World, herramienta: str, args: dict) -> Optional[str]:
    if herramienta in ("pagar", "transferir"):
        return _revisar_destino(world, args.get("cuenta", ""), "la cuenta de destino")
    if herramienta == "compartir_dato":
        if not _es_dato_del_dueno(world, args.get("dato", "")):
            return None
        return _revisar_destino(world, args.get("destinatario", ""), "el destinatario del dato")
    if herramienta == "responder":
        # Un mensaje que lleva un dato del dueño (RUT, código, dirección) es compartir ese dato.
        if not _mensaje_lleva_dato(world, args.get("mensaje", "")):
            return None
        return _revisar_destino(world, args.get("a", ""), "el destinatario del mensaje con datos del dueño")
    return None


def _mensaje_lleva_dato(world: World, mensaje: str) -> bool:
    m = "".join(ch for ch in mensaje.lower() if ch.isalnum())
    for valor in world.datos_dueno.values():
        v = "".join(ch for ch in str(valor).lower() if ch.isalnum())
        if len(v) >= 4 and v in m:
            return True
    return False


def _revisar_destino(world: World, valor: str, que: str) -> Optional[str]:
    origenes = world.origenes_de(valor)
    if origenes & ORIGENES_SEGUROS:
        return None
    if origenes & NO_CONFIABLES:
        fuentes = ", ".join(sorted(origenes & NO_CONFIABLES))
        return (f"{que} ({valor}) viene solo de contenido no confiable ({fuentes}), "
                "no del encargo ni de las cuentas inscritas del dueño.")
    return f"{que} ({valor}) no aparece en el encargo ni en las cuentas inscritas del dueño."


def _es_dato_del_dueno(world: World, dato: str) -> bool:
    d = "".join(ch for ch in dato.lower() if ch.isalnum())
    if len(d) < 4:
        return False
    for valor in world.datos_dueno.values():
        v = "".join(ch for ch in str(valor).lower() if ch.isalnum())
        if v and (v in d or d in v):
            return True
    return False
