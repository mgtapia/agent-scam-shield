"""Qué bloquea la capa 1 en cada escenario, sin ningún modelo: lee todo el contenido y pide la acción de la estafa.

Sirve para documentar qué detecta cada firewall. No mide a un agente: asume que cayó y mira si la capa 1
lo habría frenado. En los controles mide las falsas alarmas.

Uso:
    PIPELOCK_BIN=/ruta/a/pipelock python scripts/capa1_cobertura.py            # Pipelock real
    SCAMSHIELD_CAPA1=referencia python scripts/capa1_cobertura.py              # reglas de referencia
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scamshield.defenses.layer1 import backend_capa1, reglas_inyeccion  # noqa: E402
from scamshield.env.tools import Herramientas  # noqa: E402
from scamshield.env.world import World  # noqa: E402
from scamshield.scenarios import cargar  # noqa: E402


def bloquea(esc: dict) -> str | None:
    """El motivo si la capa 1 frena la acción de la estafa (o la legítima, en un control)."""
    w = World.desde_escenario(esc)
    h = Herramientas(w)
    if w.correos:
        h.leer_correos()
    for url in w.paginas:
        h.abrir_web(url)
    for nombre in w.mcp_herramientas:
        h.usar_mcp(nombre)
    ev = esc["evaluacion"]
    a = ev.get("accion_estafa") or ev.get("accion_legitima") or {"herramienta": "pagar", "args": {}}
    return reglas_inyeccion(w, a["herramienta"], a["args"])


def main() -> int:
    idiomas = tuple(sys.argv[1].split(",")) if len(sys.argv) > 1 else ("es", "en")
    print(f"Capa 1: {backend_capa1()}\n")
    print("| Escenario | Idioma | Tipo | Familia | Capa 1 | Motivo |\n|---|---|---|---|---|---|")
    total = {"estafa": [0, 0], "control": [0, 0]}
    for esc in cargar(idiomas):
        motivo = bloquea(esc)
        tipo = esc.get("tipo", "estafa")
        total[tipo][0] += bool(motivo)
        total[tipo][1] += 1
        familia = esc.get("anotaciones", {}).get("familia", "")
        print(f"| {esc['id']} | {esc['idioma']} | {tipo} | {familia} | {'bloquea' if motivo else 'deja pasar'} | "
              f"{(motivo or '')[:90]} |")
    print(f"\nEstafas bloqueadas: {total['estafa'][0]}/{total['estafa'][1]}. "
          f"Falsas alarmas en controles: {total['control'][0]}/{total['control'][1]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
