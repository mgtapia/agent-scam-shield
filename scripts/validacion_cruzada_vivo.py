"""Validación cruzada del clasificador en línea del modo en vivo: recall en escenarios que nunca vio.

El motor aparta un tercio de los escenarios para evaluar y nunca entrena con ellos. Con un solo tercio
el número depende de cuál toque: puede salir mejor o peor que el promedio. Aquí se rotan los tres
pliegues y se reparten varias semillas (que solo reordenan el entrenamiento), y se reporta la media con
su rango. Cada pliegue evalúa 9 a 11 escenarios apartados (sus variaciones no son independientes).

No usa ningún modelo ni API: el clasificador es propio y el corpus son los escenarios del repo.

Uso:
    python scripts/validacion_cruzada_vivo.py
    python scripts/validacion_cruzada_vivo.py --episodios 300 --semillas 1,2,3,4,5
"""
from __future__ import annotations

import argparse
import itertools
import statistics as st
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

METRICAS = ("recall", "precision", "falsas_alarmas")


def correr(pliegue: int, semilla: int, episodios: int) -> dict[str, Any]:
    """Entrena con los escenarios no apartados y evalúa en el pliegue apartado."""
    from scamshield.vivo.flujo import Flujo
    from scamshield.vivo.motor import Motor

    reloj = itertools.count()
    flujo = Flujo(semilla=semilla, pliegue=pliegue)
    motor = Motor(semilla=semilla, reloj=lambda: float(next(reloj)), flujo=flujo)
    antes = motor.clasificador.evaluar()
    entrenados: set[str] = set()
    for _ in range(episodios):
        for c in flujo.episodio():
            if flujo.es_evaluacion(c):
                continue
            entrenados.add(c.unidad)
            motor.clasificador.aprender(motor._rasgos(c), int(c.etiqueta == "estafa"))
    if not entrenados.isdisjoint(flujo.claves_evaluacion):
        raise RuntimeError("el entrenamiento tocó un escenario apartado")
    return {**motor.clasificador.evaluar(), "pliegue": pliegue, "semilla": semilla,
            "escenarios_apartados": len(flujo.claves_evaluacion), "recall_antes": antes["recall"]}


def resumir(filas: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {k: {"media": st.mean(f[k] for f in filas), "min": min(f[k] for f in filas),
                "max": max(f[k] for f in filas)} for k in METRICAS}


def validar(episodios: int, semillas: list[int]) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    filas = [correr(p, s, episodios) for p in (0, 1, 2) for s in semillas]
    return filas, resumir(filas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--episodios", type=int, default=300, help="episodios de entrenamiento por corrida")
    p.add_argument("--semillas", default="1,2,3", help="semillas separadas por coma")
    a = p.parse_args(argv)
    filas, total = validar(a.episodios, [int(s) for s in a.semillas.split(",")])
    print(f"| Pliegue | Escenarios apartados | Correos | Recall | Precisión | Falsas alarmas |\n|---|---|---|---|---|---|")
    for pl in (0, 1, 2):
        fs = [f for f in filas if f["pliegue"] == pl]
        print(f"| {pl} | {fs[0]['escenarios_apartados']} | {fs[0]['evaluado_en']} | "
              + " | ".join(f"{st.mean(f[k] for f in fs):.2f}" for k in METRICAS) + " |")
    print(f"\nTotal, {len(filas)} corridas ({len(filas) // 3} semillas x 3 pliegues, {a.episodios} episodios):")
    for k, v in total.items():
        print(f"  {k:15} media {v['media']:.2f}  rango [{v['min']:.2f} - {v['max']:.2f}]")
    print(f"  recall antes de entrenar: {sorted({f['recall_antes'] for f in filas})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
