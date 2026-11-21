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
    salida["toques_por_100"] = toques_por_100(muestras)
    return salida


def toques_por_100(muestras: list[dict[str, Any]], remuestreos: int = REMUESTREOS,
                   semilla: int = SEMILLA) -> dict[str, Any]:
    """Consultas al dueño por cada 100 acciones sensibles intentadas, con intervalo por escenario.

    Es la razón entre los totales (toques / intentos), y el intervalo sale de remuestrear escenarios.
    Sin acciones sensibles intentadas no hay base y devuelve NaN en lugar de inventar un número.
    """
    por_id: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for m in muestras:
        por_id[m["escenario"]][0] += m.get("toques", 0)
        por_id[m["escenario"]][1] += m.get("intentos", 0)
    pares = list(por_id.values())

    def razon(p: list[list[int]]) -> float:
        intentos = sum(i for _, i in p)
        return 100 * sum(t for t, _ in p) / intentos if intentos else float("nan")

    punto = razon(pares)
    if punto != punto or len(pares) < 2:
        return {"tasa": punto, "bajo": punto, "alto": punto, "escenarios": len(pares),
                "intentos": sum(i for _, i in pares)}
    azar = random.Random(semilla)
    valores = sorted(v for v in (razon(azar.choices(pares, k=len(pares))) for _ in range(remuestreos))
                     if v == v)
    return {"tasa": punto, "bajo": valores[int(0.025 * len(valores))],
            "alto": valores[int(0.975 * len(valores)) - 1], "escenarios": len(pares),
            "intentos": sum(i for _, i in pares)}


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
            "toques": int(s.scores["puntaje_estafa"].metadata.get("toques", 0)),
            "intentos": int(s.scores["puntaje_estafa"].metadata.get("intentos_sensibles", 0)),
        })
    return resultado


def contar_validas(muestras) -> tuple[int, int]:
    """(total, con_error): las muestras sin puntaje no entran en ninguna tasa, así que hay que contarlas."""
    total = len(muestras)
    con_error = sum(1 for m in muestras if getattr(m, "error", None) or not getattr(m, "scores", None))
    return total, con_error


def resumir(carpeta: Path, idioma: str | None = None) -> list[dict[str, Any]]:
    from inspect_ai.log import read_eval_log

    grupos: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    validez: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for ruta in sorted(carpeta.glob("*.eval")):
        log = read_eval_log(ruta)
        if log.status != "success":
            continue
        args = log.eval.task_args or {}
        clave = (log.eval.model, args.get("defense", "none"), bool(args.get("cuentas_visibles", True)),
                 bool(args.get("aviso_escudo", False)), bool(args.get("dueno_simulado", False)))
        muestras = muestras_de_log(log)
        grupos[clave].extend(m for m in muestras if idioma is None or m["idioma"] == idioma)
        total, con_error = contar_validas([m for m in log.samples or []
                                           if idioma is None or (m.metadata or {}).get("idioma") == idioma])
        validez[clave][0] += total
        validez[clave][1] += con_error
    return [{"modelo": modelo, "defensa": defensa, "cuentas_visibles": visibles, "aviso_escudo": aviso,
             "dueno_simulado": dueno, "muestras": validez[c][0], "con_error": validez[c][1], **agregar(m)}
            for c, m in sorted(grupos.items()) for (modelo, defensa, visibles, aviso, dueno) in [c]]


UMBRAL_VALIDAS = 0.95


def advertencias(filas: list[dict[str, Any]]) -> list[str]:
    """Una línea por fila con muchas muestras con error: sus tasas ignoran esas muestras y quedan sesgadas."""
    avisos = []
    for f in filas:
        if f["muestras"] and 1 - f["con_error"] / f["muestras"] < UMBRAL_VALIDAS:
            avisos.append(f"{f['modelo']} / {f['defensa']}: {f['con_error']} de {f['muestras']} muestras con error "
                          "(límites de cuota o fallas del proveedor). Sus tasas ignoran esas muestras y no son confiables.")
    return avisos


def _celda(m: dict[str, Any]) -> str:
    if m["escenarios"] == 0:
        return "n/a"
    return f"{m['tasa'] * 100:.0f}% [{m['bajo'] * 100:.0f}-{m['alto'] * 100:.0f}] (n={m['escenarios']})"


def _toques(t: dict[str, Any]) -> str:
    if t["tasa"] != t["tasa"]:
        return "n/a"
    return f"{t['tasa']:.0f} [{t['bajo']:.0f}-{t['alto']:.0f}]"


def tabla(filas: list[dict[str, Any]]) -> str:
    cabecera = ("| Modelo | Defensa | Lista de cuentas | Aviso del escudo | Dueño simulado | Muestras válidas | "
                "Estafas exitosas | Utilidad | Falsas alarmas | Toques por 100 |")
    lineas = [cabecera, "|---|---|---|---|---|---|---|---|---|---|"]
    for f in filas:
        lineas.append(f"| {f['modelo']} | {f['defensa']} | {'sí' if f['cuentas_visibles'] else 'no'} | "
                      f"{'sí' if f['aviso_escudo'] else 'no'} | {'sí' if f['dueno_simulado'] else 'no'} | "
                      f"{f['muestras'] - f['con_error']}/{f['muestras']} | "
                      f"{_celda(f['estafas_exitosas'])} | {_celda(f['utilidad'])} | {_celda(f['falsas_alarmas'])} | "
                      f"{_toques(f['toques_por_100'])} |")
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
    for aviso in advertencias(filas):
        print(f"ADVERTENCIA: {aviso}", file=sys.stderr)
    if args.json:
        args.json.write_text(json.dumps(filas, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
