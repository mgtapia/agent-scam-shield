"""Falsas alarmas del clasificador en vivo: de dónde salen y qué cuesta bajarlas (#131, seguimiento).

Mide sobre el mismo apartado por familia que scripts/validacion_cruzada_vivo.py (3 pliegues × semillas), sin mover el
reparto entrenamiento/apartado, cuatro reglas de decisión sobre la misma probabilidad del clasificador:

    fijo        el umbral de siempre, 0,5;
    calibrado   el umbral sale del presupuesto de falsas alarmas: el percentil 95 de la probabilidad que el modelo
                les daba a los correos legítimos del entrenamiento justo antes de aprenderlos (prequential: cada uno
                se puntúa antes de entrenar con él, así que es una estimación fuera de muestra), nunca bajo 0,5;
    remitente   0,5, pero un correo de un remitente que el dueño ya confirmó como legítimo, con SPF y DKIM en pass y
                sin cuenta nueva, no se marca (la bóveda guarda esa confirmación);
    ambas       las dos juntas.

La capa 2 no cambia: esto decide solo qué marca el clasificador (que únicamente sube la sospecha). Las reglas
«calibrado» y «remitente» viven solo aquí, para medir: el motor no las usa (ver el README, «Falsas alarmas»).
La tabla de umbrales incluye 0,45, que es desde donde la demo marca «sospechoso» y le pregunta al dueño.

Uso:
    python scripts/falsas_alarmas_vivo.py
    python scripts/falsas_alarmas_vivo.py --json results/falsas_alarmas.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scamshield.vivo.juez import metricas  # noqa: E402
from scamshield.vivo.flujo import CORREO  # noqa: E402
from scripts.validacion_cruzada_vivo import entrenar  # noqa: E402

REGLAS = ("fijo", "calibrado", "remitente", "ambas")
UMBRALES = (0.45, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.97, 0.99)
UMBRAL = 0.5
PERCENTIL = 0.95      # presupuesto de falsas alarmas del umbral calibrado: 5 % de los legítimos
MINIMO_CALIBRACION = 40
SENALES_DE_PEDIDO = ("cuenta_nueva", "servicio_legitimo_con_pago", "pide_codigo", "instruccion_oculta", "cambio_cuenta",
                     "dominio_parecido")


def autenticado(correo: Any) -> bool:
    """SPF y DKIM en pass, según lo que verificó el servidor de correo (`Correo.autenticacion`)."""
    a = getattr(correo, "autenticacion", None) or {}
    return str(a.get("spf", "")).lower() == "pass" and str(a.get("dkim", "")).lower() == "pass"


def umbral_calibrado(ps: list[float], percentil: float = PERCENTIL) -> float:
    """El percentil de la probabilidad de los legítimos del entrenamiento antes de aprenderlos, nunca bajo 0,5."""
    if len(ps) < MINIMO_CALIBRACION:
        return UMBRAL
    orden = sorted(ps)
    return max(UMBRAL, orden[min(len(orden) - 1, math.ceil(percentil * len(orden)) - 1)])


def remitente_confiable(correo: Any, senales: dict[str, float], confirmados: set[str]) -> bool:
    """Un remitente que el dueño ya confirmó como legítimo, autenticado otra vez, y sin nada que pida pagar o entregar."""
    return (correo.origen == CORREO and correo.de.lower() in confirmados and autenticado(correo)
            and not any(senales.get(k) for k in SENALES_DE_PEDIDO))


def correr(pliegue: int, semilla: int, episodios: int) -> dict[str, Any]:
    p_legitimos: list[float] = []
    confirmados: set[str] = set()

    def antes(motor: Any, c: Any, r: Any) -> None:
        # Prequential: la probabilidad que el modelo le da al legítimo antes de aprenderlo (fuera de muestra). Y lo que
        # el dueño confirma como legítimo con SPF y DKIM en pass: solo lo del entrenamiento, nunca lo apartado.
        if c.etiqueta == "legitimo":
            p_legitimos.append(motor.clasificador.probabilidad(r))
            if c.origen == CORREO and autenticado(c):
                confirmados.add(c.de.lower())

    motor, _ = entrenar(pliegue, semilla, episodios, "familia", antes)
    cl = motor.clasificador
    tau = umbral_calibrado(p_legitimos[-400:])
    filas = []
    for c, (r, y), m in zip(motor.evaluacion, cl.apartado, cl.meta):
        p = cl.probabilidad(r)
        confiable = remitente_confiable(c, r.senales, confirmados)
        filas.append({"y": y, "p": p, "escenario": m["escenario"], "familia": m["familia"], "canal": m["canal"],
                      "fijo": p > cl.UMBRAL, "calibrado": p > tau,
                      "remitente": p > cl.UMBRAL and not confiable, "ambas": p > tau and not confiable})
    falsas = sorted({f["escenario"] for f in filas if not f["y"] and f["fijo"]})
    return {"pliegue": pliegue, "semilla": semilla, "umbral_calibrado": round(tau, 3),
            "legitimos": sum(1 for f in filas if not f["y"]), "estafas": sum(f["y"] for f in filas),
            **{regla: metricas(filas, regla) for regla in REGLAS},
            "falsas_alarmas_fijo": falsas,
            "sin_marcar_por_remitente": sorted({f["escenario"] for f in filas if f["fijo"] and not f["remitente"]}),
            "remitentes_confirmados": len(confirmados),
            "p_falsas_alarmas": sorted(round(f["p"], 3) for f in filas if not f["y"] and f["fijo"]),
            "_ps": [(f["y"], f["p"]) for f in filas]}


def curva(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cuánto cuesta subir el umbral fijo: cobertura y falsas alarmas con la misma probabilidad."""
    salida = []
    for t in UMBRALES:
        rs = [metricas([{"y": y, "m": p > t} for y, p in f["_ps"]], "m") for f in filas]
        salida.append({"umbral": t, "recall": round(st.mean(r["recall"] for r in rs), 3),
                       "falsas_alarmas": round(st.mean(r["falsas_alarmas"] for r in rs), 3),
                       "falsas_alarmas_max": max(r["falsas_alarmas"] for r in rs)})
    return salida


def resumir(filas: list[dict[str, Any]]) -> dict[str, Any]:
    rango = lambda regla, m: {"media": round(st.mean(f[regla][m] for f in filas), 3),
                              "min": min(f[regla][m] for f in filas), "max": max(f[regla][m] for f in filas)}
    return {regla: {m: rango(regla, m) for m in ("recall", "precision", "falsas_alarmas")} for regla in REGLAS}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--episodios", type=int, default=300)
    p.add_argument("--semillas", default="1,2,3")
    p.add_argument("--json", type=Path)
    a = p.parse_args(argv)
    semillas = [int(s) for s in a.semillas.split(",")]
    filas = [correr(pl, s, a.episodios) for pl in (0, 1, 2) for s in semillas]
    total = resumir(filas)
    print("| Regla | Cobertura | Precisión | Falsas alarmas |\n|---|---|---|---|")
    for regla in REGLAS:
        t = total[regla]
        print(f"| {regla} | " + " | ".join(f"{t[m]['media']:.3f} [{t[m]['min']:.3f}-{t[m]['max']:.3f}]"
                                         for m in ("recall", "precision", "falsas_alarmas")) + " |")
    tabla = curva(filas)
    for f in filas:
        del f["_ps"]
    print("\nSubir el umbral fijo (la misma probabilidad):\n| Umbral | Cobertura | Falsas alarmas (media, máx) |\n|---|---|---|")
    for c in tabla:
        print(f"| {c['umbral']:.2f} | {c['recall']:.3f} | {c['falsas_alarmas']:.3f}, {c['falsas_alarmas_max']:.3f} |")
    print("\nProbabilidad de las falsas alarmas:", sorted({p for f in filas for p in f["p_falsas_alarmas"]}))
    print("Umbral calibrado por corrida:", [f["umbral_calibrado"] for f in filas])
    print("Legítimos con falsa alarma (umbral fijo):", sorted({e for f in filas for e in f["falsas_alarmas_fijo"]}))
    print("Que la regla del remitente deja sin marcar:", sorted({e for f in filas for e in f["sin_marcar_por_remitente"]}))
    if a.json:
        a.json.write_text(json.dumps({"agrupar": "familia", "episodios": a.episodios, "semillas": semillas,
                                      "corridas": len(filas), "total": total, "curva_umbral": tabla, "filas": filas},
                                     indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
