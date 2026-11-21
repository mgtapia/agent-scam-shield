"""Gráfico de estafas exitosas acumuladas por ronda, con una línea por defensa, desde el JSONL del atacante.

Uso:
    python scripts/graficar_atacante.py results/raw/atacante_20261121_120000.jsonl [más archivos...]
Escribe junto al primer archivo: <nombre>.svg, <nombre>.md (tabla) y <nombre>_curvas.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scamshield.attacker.resultados import curvas, leer, svg, tabla_markdown  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    rutas = [Path(a) for a in argv]
    filas = [f for r in rutas for f in leer(r)]
    c = curvas(filas)
    base = rutas[0].with_suffix("")
    base.with_suffix(".svg").write_text(svg(c), encoding="utf-8")
    base.with_suffix(".md").write_text(tabla_markdown(c) + "\n", encoding="utf-8")
    Path(f"{base}_curvas.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    print(tabla_markdown(c))
    print(f"Escrito: {base.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
