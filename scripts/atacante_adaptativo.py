"""Atacante adaptativo («grifter»): reescribe cada estafa ronda tras ronda contra una defensa.

Guarda una fila por (modelo, defensa, estafa, ronda) en un JSONL: {modelo, defensa, ronda, exito,
puntaje, ...}. El gráfico sale de `scripts/graficar_atacante.py`.

Las llaves se leen de `.env` solo para dejarlas en el entorno: nunca se imprimen.

Uso:
    python scripts/atacante_adaptativo.py --dry-run
    python scripts/atacante_adaptativo.py --victima google/gemini-3.5-flash --limit 2 --rondas 2
    python scripts/atacante_adaptativo.py --victima anthropic/claude-haiku-5-5 --rondas 3
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DEFENSAS = ("none", "layer1", "layer2")
VICTIMA = "anthropic/claude-haiku-5-5"
# El atacante es un modelo barato de capa gratis. Groq primero: la cuota de Gemini se agota y Inspect
# reintenta sin fin (verificado el 2026-11-21: Gemini daba ClientError, Groq y Claude respondían).
ATACANTES = (("GROQ_API_KEY", "groq/openai/gpt-oss-120b"), ("GOOGLE_API_KEY", "google/gemini-3.5-flash"))


def _cargar_env(ruta: str | None) -> None:
    """Deja las llaves de `.env` en el entorno, sin pisar lo ya definido y sin imprimirlas.

    Si el checkout es un worktree sin `.env`, busca el del checkout principal.
    """
    from dotenv import load_dotenv

    candidatos = [Path(ruta)] if ruta else [RAIZ / ".env"]
    if not ruta:
        try:
            comun = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                   cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
            candidatos.append(Path(comun).parent / ".env")
        except (OSError, subprocess.CalledProcessError):
            pass
    for c in candidatos:
        if c.is_file():
            load_dotenv(c, override=False)
            return


def elegir_atacante(entorno: dict[str, str]) -> str:
    for llave, modelo in ATACANTES:
        if (entorno.get(llave) or "").strip():
            return modelo
    raise SystemExit("No hay llave para el atacante: define GROQ_API_KEY o GOOGLE_API_KEY en .env.")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--victima", default=VICTIMA, help="Modelo víctima. Por defecto: %(default)s.")
    p.add_argument("--atacante", help="Modelo del atacante, crítico y juez. Por defecto, Groq o Gemini según la llave.")
    p.add_argument("--defensas", default=",".join(DEFENSAS), help="Por defecto: %(default)s.")
    p.add_argument("--idiomas", default="es", help="Por defecto: %(default)s.")
    p.add_argument("--rondas", type=int, default=3, help="Rondas de adaptación (la ronda 0 es la original). Por defecto %(default)s.")
    p.add_argument("--semillas", help="Ids de estafas separados por coma. Por defecto, todas las atacables.")
    p.add_argument("--limit", type=int, help="Máximo de estafas.")
    p.add_argument("--max-episodios", type=int, help="Tope de episodios de la víctima en toda la corrida.")
    p.add_argument("--realismo-min", type=int, default=5, help="Realismo mínimo (1 a 10). Por defecto %(default)s.")
    p.add_argument("--max-connections", type=int, default=2, help="Llamadas simultáneas. Por defecto %(default)s.")
    p.add_argument("--max-connections-victima", type=int, default=8,
                   help="Episodios simultáneos de la víctima. Por defecto %(default)s; 1 con la cuota gratis de Groq.")
    p.add_argument("--retry-on-error", type=int, help="Reintentos de un episodio de la víctima que falla (por ejemplo, por cuota).")
    p.add_argument("--sin-cache", action="store_true", help="No reusa respuestas guardadas en caché.")
    p.add_argument("--salida", help="JSONL de salida. Por defecto results/raw/atacante_<fecha>.jsonl.")
    p.add_argument("--log-dir", default=str(RAIZ / "logs" / "atacante"))
    p.add_argument("--env", help="Archivo .env con las llaves.")
    p.add_argument("--dry-run", action="store_true", help="Imprime el plan y el gasto máximo sin llamar a ningún modelo.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _cargar_env(args.env)
    os.environ.setdefault("INSPECT_DISPLAY", "none")
    from scamshield.attacker.escenario import semillas
    from scamshield.attacker.resultados import curvas, tabla_markdown
    from scamshield.evals.task import DEFENSAS as DEFENSAS_VALIDAS

    defensas = tuple(d.strip() for d in args.defensas.split(",") if d.strip())
    malas = [d for d in defensas if d not in DEFENSAS_VALIDAS]
    if malas:
        raise SystemExit(f"Defensas desconocidas: {', '.join(malas)}. Opciones: {', '.join(DEFENSAS_VALIDAS)}")
    ids = [i.strip() for i in args.semillas.split(",")] if args.semillas else None
    estafas = semillas(tuple(i.strip() for i in args.idiomas.split(",")), ids)
    if args.limit:
        estafas = estafas[:args.limit]
    if not estafas:
        raise SystemExit("No hay estafas atacables con esos filtros.")

    max_ep = len(estafas) * len(defensas) * (args.rondas + 1)
    llamadas = len(estafas) * len(defensas) * args.rondas * 3
    print(f"Plan: {len(estafas)} estafas × {len(defensas)} defensas × {args.rondas + 1} rondas "
          f"(víctima: {args.victima}).")
    print(f"  Episodios de la víctima: hasta {max_ep} (una estafa que cae deja de atacarse).")
    print(f"  Llamadas del atacante, crítico y juez: hasta ~{llamadas}.")
    if args.dry_run:
        for e in estafas:
            print(f"  - {e['id']}__{e['idioma']}")
        return 0

    from inspect_ai.model import GenerateConfig, get_model
    from scamshield.attacker.bucle import Config, correr_atacante

    nombre_atacante = args.atacante or elegir_atacante(os.environ)
    salida = Path(args.salida) if args.salida else RAIZ / "results" / "raw" / (
        f"atacante_{datetime.now():%Y%m%d_%H%M%S}.jsonl")
    cfg = Config(
        victima=args.victima,
        atacante=get_model(nombre_atacante, config=GenerateConfig(max_connections=args.max_connections, max_retries=40)),
        defensas=defensas, rondas=args.rondas, realismo_min=args.realismo_min,
        max_episodios=args.max_episodios, cache=not args.sin_cache, log_dir=args.log_dir, salida=salida,
        nombre_victima=args.victima, max_connections_victima=args.max_connections_victima,
        retry_on_error_victima=args.retry_on_error,
        al_terminar_ronda=lambda r, filas: print(
            f"Ronda {r}: {len(filas)} episodios, {sum(f['exito'] for f in filas)} estafas cayeron, "
            f"{sum(f['intento'] and not f['exito'] for f in filas)} intentadas y frenadas."),
    )
    res = asyncio.run(correr_atacante(cfg, estafas))
    print(f"\nFilas en {salida}")
    print(tabla_markdown(curvas(res["filas"])))
    print(f"Episodios: {res['episodios']}. Tokens de la víctima: {res['tokens']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
