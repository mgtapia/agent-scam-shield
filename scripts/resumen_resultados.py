"""Resumen de los logs de la eval: tasas con intervalo de confianza, por modelo y defensa.

Las repeticiones (epochs) de un mismo escenario no son muestras independientes. Por eso cada tasa
es el promedio de las fracciones por escenario, y el intervalo sale de remuestrear escenarios
(bootstrap percentil al 95 %, con semilla fija), no de contar todas las repeticiones como muestras.

Métricas, cada una solo donde aplica:
- estafas exitosas: sobre las estafas, la fracción de repeticiones en que el agente pagó al estafador;
- utilidad: sobre los escenarios con tarea legítima, la fracción en que la cumplió;
- falsas alarmas: sobre los controles, la fracción en que una defensa bloqueó algo.

Uso:
    python scripts/resumen_resultados.py logs/primera_tabla
    python scripts/resumen_resultados.py logs/dificiles --idioma es --json salida.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

REMUESTREOS = 2000
SEMILLA = 20261121


def tasa_con_intervalo(por_escenario: list[float], remuestreos: int = REMUESTREOS,
                       semilla: int = SEMILLA) -> tuple[float, float, float]:
    """(tasa, bajo, alto): promedio de las fracciones por escenario y su intervalo al 95 %."""
    n = len(por_escenario)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    media = sum(por_escenario) / n
    if n == 1:
        return media, media, media
    azar = random.Random(semilla)
    medias = sorted(sum(azar.choices(por_escenario, k=n)) / n for _ in range(remuestreos))
    return media, medias[int(0.025 * remuestreos)], medias[int(0.975 * remuestreos) - 1]


def _fracciones(repeticiones: Iterable[tuple[str, bool]]) -> list[float]:
    """Agrupa por escenario y devuelve, por cada uno, la fracción de repeticiones verdaderas."""
    por_id: dict[str, list[bool]] = defaultdict(list)
    for escenario, valor in repeticiones:
        por_id[escenario].append(valor)
    return [sum(v) / len(v) for v in por_id.values()]


def agregar(muestras: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Cada muestra: escenario, tipo, tiene_tarea, cayo, tarea_ok, falsa_alarma. Devuelve las 3 métricas."""
    estafas = [(m["escenario"], m["cayo"]) for m in muestras if m["tipo"] == "estafa"]
    tareas = [(m["escenario"], m["tarea_ok"]) for m in muestras if m["tiene_tarea"]]
    controles = [(m["escenario"], m["falsa_alarma"]) for m in muestras if m["tipo"] == "control"]
    salida = {}
    for nombre, reps in (("estafas_exitosas", estafas), ("utilidad", tareas), ("falsas_alarmas", controles)):
        fracciones = _fracciones(reps)
        tasa, bajo, alto = tasa_con_intervalo(fracciones)
        salida[nombre] = {"tasa": tasa, "bajo": bajo, "alto": alto, "escenarios": len(fracciones),
                          "repeticiones": len(reps)}
    return salida


def muestras_de_log(log) -> list[dict[str, Any]]:
    """Las muestras de un log de Inspect, con las métricas recalculadas desde la metadata del escenario."""
    resultado = []
    for s in log.samples or []:
        if not s.scores or "puntaje_estafa" not in s.scores:
            continue
        v = s.scores["puntaje_estafa"].value
        esc = s.metadata["escenario"]
        resultado.append({
            "escenario": s.id,
            "idioma": s.metadata["idioma"],
            "tipo": esc["tipo"],
            "tiene_tarea": esc["evaluacion"].get("tarea", "ninguna") != "ninguna",
            "cayo": v.get("seguridad") == "I",
            "tarea_ok": v.get("utilidad") == "C",
            "falsa_alarma": bool(v.get("falsa_alarma")),
        })
    return resultado


def resumir(carpeta: Path, idioma: str | None = None) -> list[dict[str, Any]]:
    from inspect_ai.log import read_eval_log

    grupos: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for ruta in sorted(carpeta.glob("*.eval")):
        log = read_eval_log(ruta)
        if log.status != "success":
            continue
        args = log.eval.task_args or {}
        clave = (log.eval.model, args.get("defense", "none"), bool(args.get("cuentas_visibles", True)))
        muestras = muestras_de_log(log)
        grupos[clave].extend(m for m in muestras if idioma is None or m["idioma"] == idioma)
    return [{"modelo": modelo, "defensa": defensa, "cuentas_visibles": visibles, **agregar(m)}
            for (modelo, defensa, visibles), m in sorted(grupos.items())]


def _celda(m: dict[str, Any]) -> str:
    if m["escenarios"] == 0:
        return "n/a"
    return f"{m['tasa'] * 100:.0f}% [{m['bajo'] * 100:.0f}-{m['alto'] * 100:.0f}] (n={m['escenarios']})"


def tabla(filas: list[dict[str, Any]]) -> str:
    cabecera = "| Modelo | Defensa | Lista de cuentas | Estafas exitosas | Utilidad | Falsas alarmas |"
    lineas = [cabecera, "|---|---|---|---|---|---|"]
    for f in filas:
        lineas.append(f"| {f['modelo']} | {f['defensa']} | {'sí' if f['cuentas_visibles'] else 'no'} | "
                      f"{_celda(f['estafas_exitosas'])} | {_celda(f['utilidad'])} | {_celda(f['falsas_alarmas'])} |")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("logs", type=Path, help="carpeta con archivos .eval")
    p.add_argument("--idioma", choices=["es", "en"], help="solo los escenarios de ese idioma")
    p.add_argument("--json", type=Path, help="guarda además los números en este archivo")
    args = p.parse_args(argv)
    filas = resumir(args.logs, args.idioma)
    if not filas:
        print(f"No hay logs terminados en {args.logs}", file=sys.stderr)
        return 2
    print(tabla(filas))
    if args.json:
        args.json.write_text(json.dumps(filas, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
