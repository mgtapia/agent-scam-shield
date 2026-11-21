"""Capa 1: firewall técnico.

El objetivo es integrar aquí un firewall abierto existente (Pipelock o mcp-watchdog) como primera
capa; ver el issue «Capa 1». Mientras tanto, `reglas_inyeccion` es una referencia mínima de lo que
esos firewalls buscan (instrucciones escondidas, envenenamiento de herramientas, fuga de secretos).
En los resultados se reporta como «capa 1 de referencia» hasta que esté la integración real.
"""
from __future__ import annotations

import re
from typing import Optional

from ..env.world import NO_CONFIABLES, World

PATRONES_INYECCION = [
    r"ignor[ae] (todas )?(tus|las) instrucciones",
    r"ignore (all )?(previous|prior|your) instructions",
    r"system prompt",
    r"<\s*(important|system|instructions?)\s*>",
    r"no (se lo )?(menciones|digas) al usuario",
    r"do not (tell|mention|inform) the user",
    r"\.env\b|id_rsa|api[_ -]?key|secret[_ -]?key",
]


def reglas_inyeccion(world: World, herramienta: str, args: dict) -> Optional[str]:
    """Bloquea la acción si algún contenido no confiable leído trae patrones de inyección técnica."""
    for origen, texto in world.leidos:
        if origen not in NO_CONFIABLES:
            continue
        for patron in PATRONES_INYECCION:
            if re.search(patron, texto, flags=re.IGNORECASE):
                return f"contenido de {origen} con patrón de inyección técnica ({patron})."
    return None
