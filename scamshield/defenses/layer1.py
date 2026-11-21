"""Capa 1: firewall técnico.

`reglas_inyeccion` es la defensa que usa la eval (`defense=layer1`) y el motor en vivo. Tiene dos
respaldos, y se elige con `SCAMSHIELD_CAPA1`:

- `pipelock`: el firewall abierto real (ver `pipelock.py`). Es el valor por defecto en cuanto hay
  `PIPELOCK_URL` o `PIPELOCK_BIN`.
- `referencia`: unas reglas mínimas propias (`reglas_referencia`) de lo que esos firewalls buscan
  (instrucciones escondidas, envenenamiento de herramientas, fuga de secretos). Es lo que corre sin
  Pipelock, por ejemplo en CI. En los resultados se reporta como «capa 1 de referencia».

Con `SCAMSHIELD_CAPA1=pipelock` y sin Pipelock disponible se corta con un error: nunca se mide «capa 1»
con una defensa que en realidad no corrió.
"""
from __future__ import annotations

import os
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


def backend_capa1() -> str:
    """«pipelock» o «referencia», según `SCAMSHIELD_CAPA1` (auto: pipelock si hay URL o binario)."""
    modo = os.environ.get("SCAMSHIELD_CAPA1", "auto").strip().lower() or "auto"
    if modo not in ("auto", "pipelock", "referencia"):
        raise ValueError("SCAMSHIELD_CAPA1 debe ser auto, pipelock o referencia.")
    if modo == "auto":
        # En auto solo cuentan las variables: un `pipelock` suelto en el PATH no activa nada.
        hay = os.environ.get("PIPELOCK_URL", "").strip() or os.environ.get("PIPELOCK_BIN", "").strip()
        modo = "pipelock" if hay else "referencia"
    return modo


def reglas_inyeccion(world: World, herramienta: str, args: dict) -> Optional[str]:
    """La defensa de la capa 1: Pipelock si está configurado, y si no las reglas de referencia."""
    if backend_capa1() == "pipelock":
        from .pipelock import cliente_por_defecto, firewall
        return firewall(cliente_por_defecto())(world, herramienta, args)
    return reglas_referencia(world, herramienta, args)


def reglas_referencia(world: World, herramienta: str, args: dict) -> Optional[str]:
    """Bloquea la acción si algún contenido no confiable leído trae patrones de inyección técnica."""
    for origen, texto in world.leidos:
        if origen not in NO_CONFIABLES:
            continue
        for patron in PATRONES_INYECCION:
            if re.search(patron, texto, flags=re.IGNORECASE):
                return f"contenido de {origen} con patrón de inyección técnica ({patron})."
    return None
