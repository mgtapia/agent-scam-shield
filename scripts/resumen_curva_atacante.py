"""Resume la curva del atacante adaptativo con intervalos de Wilson al 95 %.

Lee uno o más JSONL de `scripts/atacante_adaptativo.py`. Si una estafa aparece en varios archivos para la
misma defensa, vale el último archivo (sirve para completar un flujo que la cuota cortó). Escribe un JSON
chico con, por defensa y por ronda, cuántas estafas cayeron (acumulado), cuántas el agente intentó aunque
la defensa las frenara, y cuántos flujos quedaron completos.

Uso:
    python scripts/resumen_curva_atacante.py results/atacante/grifter_20b_original.jsonl \
        results/atacante/grifter_20b_capa2_completada.jsonl --salida results/atacante/grifter_20b_curva.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from resumen_resultados import intervalo_wilson  # noqa: E402


def leer_filas(rutas: list[Path]) -> list[dict]:
    """Une los archivos: para cada (modelo, defensa, estafa), el último archivo que la trae reemplaza al resto."""
    por_flujo: dict[tuple, list[dict]] = {}
    for ruta in rutas:
        nuevo: dict[tuple, list[dict]] = {}
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                f = json.loads(linea)
                nuevo.setdefault((f["modelo"], f["defensa"], f["escenario"], f["idioma"]), []).append(f)
        por_flujo.update(nuevo)
    return [f for fs in por_flujo.values() for f in fs]


def resumir(filas: list[dict], rondas: int) -> dict:
    salida: dict = {}
    for modelo in sorted({f["modelo"] for f in filas}):
        for defensa in sorted({f["defensa"] for f in filas if f["modelo"] == modelo}):
            fs = [f for f in filas if f["modelo"] == modelo and f["defensa"] == defensa]
            estafas = sorted({f["escenario"] for f in fs})
            n = len(estafas)
            rondas_def = []
            for r in range(rondas + 1):
                cayeron = {f["escenario"] for f in fs if f["exito"] and f["ronda"] <= r}
                intentaron = {f["escenario"] for f in fs if (f["intento"] or f["exito"]) and f["ronda"] <= r}
                # Una estafa «sigue en juego» en la ronda r si cayó antes o si esa ronda tiene una fila válida.
                completas = {e for e in estafas if e in cayeron or any(
                    f["escenario"] == e and f["ronda"] == r and f["valida"] and not f["error"] for f in fs)}
                lo, hi = intervalo_wilson(len(cayeron) / n, n)
                rondas_def.append({
                    "ronda": r, "exitosas": len(cayeron), "n": n, "tasa": round(len(cayeron) / n, 3),
                    "wilson_95": [round(lo, 3), round(hi, 3)], "intentadas": len(intentaron),
                    "intentadas_en_la_ronda": len({f["escenario"] for f in fs if (f["intento"] or f["exito"]) and f["ronda"] == r}),
                    "estafas_con_ronda_valida": len(completas),
                })
            salida.setdefault(modelo, {})[defensa] = {"estafas": estafas, "rondas": rondas_def}
    return salida


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("jsonl", nargs="+", type=Path)
    p.add_argument("--salida", type=Path)
    args = p.parse_args(argv)
    filas = leer_filas(args.jsonl)
    rondas = max(f["ronda"] for f in filas)
    res = resumir(filas, rondas)
    if args.salida:
        args.salida.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for modelo, por_def in res.items():
        for defensa, v in por_def.items():
            celdas = " | ".join(
                f"r{c['ronda']}: {c['exitosas']}/{c['n']} [{round(c['wilson_95'][0] * 100)}-{round(c['wilson_95'][1] * 100)}]"
                f" (intentó acumulado {c['intentadas']}, en la ronda {c['intentadas_en_la_ronda']}, válidas {c['estafas_con_ronda_valida']})" for c in v["rondas"])
            print(f"{modelo} {defensa}: {celdas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
