"""Gráfico y tabla de estafas exitosas acumuladas por ronda, con una línea por defensa y con intervalos.

Uso:
    python scripts/graficar_atacante.py results/raw/atacante_20261121_120000.jsonl [más archivos...]
Escribe junto al primer archivo: <nombre>.svg, <nombre>.md (tabla con intervalos) y <nombre>_curvas.json.

Los intervalos son los del resto del proyecto (`scripts/resumen_resultados.py`): remuestreo de estafas al 95 %,
ensanchado con Wilson en los extremos. Cada estafa es una unidad; con 5 estafas los intervalos son muy anchos.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scamshield.attacker.resultados import NOMBRES, curvas, leer, svg  # noqa: E402
from scripts.resumen_resultados import tasa_con_intervalo  # noqa: E402


def con_intervalos(c: dict) -> dict:
    """Suma a cada curva `ic_exitos` e `ic_intentos`: [tasa, bajo, alto] por ronda, en 0 a 1."""
    for por_def in c.values():
        for v in por_def.values():
            v["ic_exitos"] = [list(tasa_con_intervalo([float(x) for x in u])) for u in v["unidades_exitos"]]
            v["ic_intentos"] = [list(tasa_con_intervalo([float(x) for x in u])) for u in v["unidades_intentos"]]
    return c


def _pct(ic: list[float]) -> str:
    return f"{ic[0]:.0%} [{ic[1]:.0%}-{ic[2]:.0%}]"


def tabla(c: dict) -> str:
    lineas = ["| Modelo | Defensa | Estafas | Ronda | Cayó (acumulado) | El agente intentó (acumulado) |",
              "|---|---|---|---|---|---|"]
    for modelo, por_def in c.items():
        for d, v in por_def.items():
            for r in range(v["rondas"] + 1):
                lineas.append(f"| {modelo} | {NOMBRES.get(d, d)} | {v['n']} | {r} | "
                              f"{v['exitos'][r]}/{v['n']} = {_pct(v['ic_exitos'][r])} | "
                              f"{v['intentos'][r]}/{v['n']} = {_pct(v['ic_intentos'][r])} |")
    lineas += ["", "| Modelo | Defensa | Reescrituras que llegaron a la víctima | Reescrituras perdidas (cuota, validación) "
               "| El atacante se negó |", "|---|---|---|---|---|"]
    for modelo, por_def in c.items():
        for d, v in por_def.items():
            lineas.append(f"| {modelo} | {NOMBRES.get(d, d)} | {v['reescrituras_validas']} | {v['reescrituras_perdidas']} "
                          f"| {v.get('rechazos_atacante', 0)} |")
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    rutas = [Path(a) for a in argv]
    filas = [f for r in rutas for f in leer(r)]
    c = con_intervalos(curvas(filas))
    base = rutas[0].with_suffix("")
    base.with_suffix(".svg").write_text(svg(c), encoding="utf-8")
    base.with_suffix(".md").write_text(tabla(c) + "\n", encoding="utf-8")
    Path(f"{base}_curvas.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    print(tabla(c))
    print(f"Escrito: {base.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
