"""Validación cruzada del clasificador en línea del modo en vivo: recall en escenarios que nunca vio.

El motor aparta un tercio de los escenarios para evaluar y nunca entrena con ellos. Con un solo tercio
el número depende de cuál toque: puede salir mejor o peor que el promedio. Aquí se rotan los tres
pliegues y se reparten varias semillas (que solo reordenan el entrenamiento), y se reporta la media con
su rango. Cada pliegue evalúa 9 a 11 escenarios apartados (sus variaciones no son independientes).

No usa ningún modelo ni API: el clasificador es propio y el corpus son los escenarios del repo.

Además del recall, dice qué estafas se colaron: `colados_por_familia` y `colados_por_canal` cuentan, sobre todas las
corridas, cuántos correos de estafa apartados de cada familia (`anotaciones.familia`) y de cada canal (correo, llamada,
web, mcp) quedaron bajo el umbral, de cuántos se evaluaron, y en cuántas de las corridas en que estuvo apartada se coló
al menos uno. El conjunto apartado es en español, como el flujo por defecto.

Uso:
    python scripts/validacion_cruzada_vivo.py
    python scripts/validacion_cruzada_vivo.py --episodios 300 --semillas 1,2,3,4,5
    python scripts/validacion_cruzada_vivo.py --agrupar familia --json results/clasificador.json
"""
from __future__ import annotations

import argparse
import json
import itertools
import statistics as st
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any, Callable, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

METRICAS = ("recall", "precision", "falsas_alarmas")


def entrenar(pliegue: int, semilla: int, episodios: int, agrupar: str = "escenario",
             antes_de_aprender: Optional[Callable[[Any, Any, Any], None]] = None) -> tuple[Any, dict[str, Any]]:
    """El motor con el clasificador entrenado en los escenarios no apartados, y su evaluación antes de entrenar.

    Lo usan también scripts/juez_vivo.py y scripts/falsas_alarmas_vivo.py, que miden sobre el mismo apartado.
    `antes_de_aprender(motor, correo, rasgos)` corre antes de cada etiqueta (el modelo todavía no la vio).
    """
    from scamshield.vivo.flujo import Flujo
    from scamshield.vivo.motor import Motor

    reloj = itertools.count()
    flujo = Flujo(semilla=semilla, pliegue=pliegue, agrupar=agrupar)
    motor = Motor(semilla=semilla, reloj=lambda: float(next(reloj)), flujo=flujo)
    antes = motor.clasificador.evaluar()
    entrenados: set[str] = set()
    for _ in range(episodios):
        for c in flujo.episodio():
            if flujo.es_evaluacion(c):
                continue
            entrenados.add(c.unidad)
            r = motor._rasgos(c)
            if antes_de_aprender is not None:
                antes_de_aprender(motor, c, r)
            motor.clasificador.aprender(r, int(c.etiqueta == "estafa"))
    if not entrenados.isdisjoint(flujo.claves_evaluacion):
        raise RuntimeError("el entrenamiento tocó un escenario apartado")
    return motor, antes


def correr(pliegue: int, semilla: int, episodios: int, agrupar: str = "escenario") -> dict[str, Any]:
    """Entrena con los escenarios no apartados y evalúa en el pliegue apartado."""
    motor, antes = entrenar(pliegue, semilla, episodios, agrupar)
    flujo = motor.flujo
    cl = motor.clasificador
    apartadas: dict[tuple[str, str, str], int] = defaultdict(int)
    for m, (_, y) in zip(cl.meta or [], cl.apartado):
        if y:
            apartadas[(m["escenario"], m["familia"], m["canal"])] += 1
    return {**cl.evaluar(), "pliegue": pliegue, "semilla": semilla,
            "escenarios_apartados": len(flujo.claves_evaluacion), "recall_antes": antes["recall"],
            "apartadas": [{"escenario": e, "familia": f, "canal": c, "n": n} for (e, f, c), n in sorted(apartadas.items())]}


def resumir(filas: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {k: {"media": st.mean(f[k] for f in filas), "min": min(f[k] for f in filas),
                "max": max(f[k] for f in filas)} for k in METRICAS}


def colados_por(filas: list[dict[str, Any]], campo: str) -> dict[str, dict[str, Any]]:
    """Por familia o por canal: correos de estafa apartados que se colaron, de cuántos, y en cuántas corridas.

    `corridas` es en cuántas corridas estuvo apartada (con `--agrupar familia` cada familia cae en un solo pliegue,
    así que son tantas como semillas); `corridas_con_colados`, en cuántas de ellas se coló al menos un correo.
    """
    salida: dict[str, dict[str, Any]] = {}
    for f in filas:
        vistos: set[str] = set()
        for a in f.get("apartadas", []):
            g = salida.setdefault(a[campo], {"colados": 0, "correos": 0, "corridas": 0, "corridas_con_colados": 0,
                                             "escenarios": set()})
            g["correos"] += a["n"]
            if a[campo] not in vistos:
                vistos.add(a[campo])
                g["corridas"] += 1
        con: set[str] = set()
        for c in f.get("colados", []):
            g = salida[c[campo]]
            g["colados"] += c["n"]
            g["escenarios"].add(c["escenario"])
            con.add(c[campo])
        for k in con:
            salida[k]["corridas_con_colados"] += 1
    for g in salida.values():
        g["tasa"] = round(g["colados"] / g["correos"], 3) if g["correos"] else 0.0
        g["escenarios"] = sorted(g["escenarios"])
    return dict(sorted(salida.items(), key=lambda kv: (-kv[1]["tasa"], -kv[1]["colados"], kv[0])))


def validar(episodios: int, semillas: list[int],
            agrupar: str = "escenario") -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    filas = [correr(p, s, episodios, agrupar) for p in (0, 1, 2) for s in semillas]
    return filas, resumir(filas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--episodios", type=int, default=300, help="episodios de entrenamiento por corrida")
    p.add_argument("--semillas", default="1,2,3", help="semillas separadas por coma")
    p.add_argument("--json", type=Path, help="guarda además los números en este archivo")
    p.add_argument("--agrupar", choices=["escenario", "familia"], default="escenario",
                   help="«familia» aparta juntas las variantes de una misma historia: es la medición más honesta")
    a = p.parse_args(argv)
    filas, total = validar(a.episodios, [int(s) for s in a.semillas.split(",")], a.agrupar)
    print(f"| Pliegue | Escenarios apartados | Correos | Recall | Precisión | Falsas alarmas |\n|---|---|---|---|---|---|")
    for pl in (0, 1, 2):
        fs = [f for f in filas if f["pliegue"] == pl]
        print(f"| {pl} | {fs[0]['escenarios_apartados']} | {fs[0]['evaluado_en']} | "
              + " | ".join(f"{st.mean(f[k] for f in fs):.2f}" for k in METRICAS) + " |")
    print(f"\nApartando por {a.agrupar}. Total, {len(filas)} corridas ({len(filas) // 3} semillas x 3 pliegues, {a.episodios} episodios):")
    for k, v in total.items():
        print(f"  {k:15} media {v['media']:.2f}  rango [{v['min']:.2f} - {v['max']:.2f}]")
    print(f"  recall antes de entrenar: {sorted({f['recall_antes'] for f in filas})}")
    por_familia, por_canal = colados_por(filas, "familia"), colados_por(filas, "canal")
    print("\n| Familia | Correos colados | Corridas con colados | Escenarios |\n|---|---|---|---|")
    for k, g in por_familia.items():
        if g["colados"]:
            print(f"| {k} | {g['colados']}/{g['correos']} | {g['corridas_con_colados']}/{g['corridas']} | {', '.join(g['escenarios'])} |")
    print("\nPor canal: " + " · ".join(f"{k} {g['colados']}/{g['correos']}" for k, g in por_canal.items()))
    if a.json:
        texto = json.dumps({"agrupar": a.agrupar, "episodios": a.episodios, "semillas": [int(s) for s in a.semillas.split(",")],
                            "pliegues": 3, "corridas": len(filas), "total": total,
                            "colados_por_familia": por_familia, "colados_por_canal": por_canal, "filas": filas},
                           indent=2, ensure_ascii=False)
        a.json.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
