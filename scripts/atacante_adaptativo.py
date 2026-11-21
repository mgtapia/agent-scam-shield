"""Atacante adaptativo («grifter»): reescribe cada estafa ronda tras ronda contra una defensa.

Guarda una fila por (modelo, defensa, estafa, ronda) en un JSONL: {modelo, defensa, ronda, exito,
puntaje, ...}. El gráfico sale de `scripts/graficar_atacante.py`.

Las llaves se leen de `.env` solo para dejarlas en el entorno: nunca se imprimen.

Uso:
    python scripts/atacante_adaptativo.py --dry-run
    python scripts/atacante_adaptativo.py --victima google/gemini-3.5-flash --limit 2 --rondas 2
    python scripts/atacante_adaptativo.py --victima anthropic/claude-haiku-5-5 --rondas 3
    python scripts/atacante_adaptativo.py --atacante anthropic/claude-fable-5-2 --dry-run   # costo estimado
    python scripts/atacante_adaptativo.py --plan-b --defensas none,layer2 --limit 3 --rondas 3 --dry-run   # plan B, sin gastar
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
# Plan B (#131): modelos abiertos como atacantes, por si un Claude se niega. Qwen por Groq ya se usó en la curva de #87;
# DeepSeek y Kimi van por OpenRouter, que el proxy de Platanus sí cuenta (Groq no). Los ids de OpenRouter cambian de versión:
# si uno no existe, la corrida falla en la primera llamada y se pasa el bueno con --atacante.
PLAN_B = ("groq/qwen/qwen3.8-27b", "openrouter/deepseek/deepseek-chat", "openrouter/moonshotai/kimi-k2")
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


def _atacante_por_defecto(entorno: dict[str, str]) -> str:
    """Para --dry-run: el atacante que se usaría, o el primero de la lista si no hay ninguna llave."""
    try:
        return elegir_atacante(entorno)
    except SystemExit:
        return ATACANTES[0][1]


def elegir_atacante(entorno: dict[str, str]) -> str:
    for llave, modelo in ATACANTES:
        if (entorno.get(llave) or "").strip():
            return modelo
    raise SystemExit("No hay llave para el atacante: define GROQ_API_KEY o GOOGLE_API_KEY en .env.")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--victima", default=VICTIMA, help="Modelo víctima. Por defecto: %(default)s.")
    p.add_argument("--atacante", help="Modelo del atacante, crítico y juez; varios separados por coma (cada uno corre igual y "
                   "deja su JSONL). Por defecto, Groq o Gemini según la llave.")
    p.add_argument("--plan-b", action="store_true", help="Los atacantes abiertos del plan B (#131), si un Claude se niega: "
                   "Qwen por Groq, y DeepSeek y Kimi por OpenRouter. Los ids están en PLAN_B; confirma que existen en OpenRouter.")
    p.add_argument("--defensas", default=",".join(DEFENSAS), help="Por defecto: %(default)s.")
    p.add_argument("--idiomas", default="es", help="Por defecto: %(default)s.")
    p.add_argument("--rondas", type=int, default=3, help="Rondas de adaptación (la ronda 0 es la original). Por defecto %(default)s.")
    p.add_argument("--semillas", help="Ids de estafas separados por coma. Por defecto, todas las atacables.")
    p.add_argument("--limit", type=int, help="Máximo de estafas.")
    p.add_argument("--max-episodios", type=int, help="Tope de episodios de la víctima en toda la corrida.")
    p.add_argument("--realismo-min", type=int, default=5, help="Realismo mínimo (1 a 10). Por defecto %(default)s.")
    p.add_argument("--max-connections", type=int, default=2, help="Llamadas simultáneas. Por defecto %(default)s.")
    p.add_argument("--retry-on-error", type=int, help="Reintentos de un episodio de la víctima que falla (cuota, red).")
    p.add_argument("--tope-usd", type=float, help="Corta al llegar a este gasto del atacante, el crítico y el juez, "
                   "medido con el uso real de la API. Por defecto US$5 si el atacante cuesta; sin tope si es gratis.")
    p.add_argument("--precio-entrada", type=float, help="USD por millón de tokens de entrada del atacante (por defecto, "
                   "el de la tabla de scamshield/attacker/costo.py).")
    p.add_argument("--precio-salida", type=float, help="USD por millón de tokens de salida del atacante.")
    p.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"],
                   help="Esfuerzo de razonamiento de un atacante Claude 5.x. Por defecto %(default)s.")
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
    print(f"Plan: {len(estafas)} estafas × {len(defensas)} defensas × {args.rondas + 1} rondas "
          f"(víctima: {args.victima}).")
    print(f"  Episodios de la víctima: hasta {max_ep} (una estafa que cae deja de atacarse).")
    from scamshield.attacker.costo import TOPE_USD, estimar, llave_de, piensa_siempre, precio_de

    if args.plan_b and args.atacante:
        raise SystemExit("--plan-b y --atacante son excluyentes: --plan-b ya trae la lista de atacantes abiertos.")
    if args.plan_b:
        atacantes = list(PLAN_B)
    elif args.atacante:
        atacantes = [a.strip() for a in args.atacante.split(",") if a.strip()]
    else:
        atacantes = [elegir_atacante(os.environ) if not args.dry_run else _atacante_por_defecto(os.environ)]
    if len(atacantes) > 1 and args.salida:
        raise SystemExit("Con varios atacantes cada uno escribe su propio JSONL: no uses --salida.")

    planes = []   # (nombre, precio de entrada, de salida, tope, estimación)
    total_tipico = total_peor = 0.0
    for nombre_atacante in atacantes:
        p_ent, p_sal = precio_de(nombre_atacante)
        p_ent = p_ent if args.precio_entrada is None else args.precio_entrada
        p_sal = p_sal if args.precio_salida is None else args.precio_salida
        tope = args.tope_usd if args.tope_usd is not None else (TOPE_USD if p_sal > 0 else None)
        est = estimar(len(estafas), len(defensas), args.rondas, p_ent, p_sal)
        planes.append((nombre_atacante, p_ent, p_sal, tope, est))
        total_tipico += est["usd_tipico"]
        total_peor += est["usd_peor_caso"]
        print(f"  Atacante: {nombre_atacante}" + (" (piensa siempre: sin temperature, effort " + args.effort + ")"
                                                  if piensa_siempre(nombre_atacante) else ""))
        if p_sal > 0:
            print(f"    Costo estimado del atacante (US${p_ent:g} / US${p_sal:g} por millón de tokens): "
                  f"~US${est['usd_tipico']:.2f} típico, hasta US${est['usd_peor_caso']:.2f} en el peor caso "
                  f"({est['llamadas']} llamadas, ~{est['tokens_entrada'] / 1e3:.0f}k tokens de entrada).")
            print(f"    Tope: US${tope:.2f} " + ("(la corrida se corta sola al llegar)" if tope is not None else "") +
                  (". OJO: el peor caso pasa el tope." if tope is not None and est["usd_peor_caso"] > tope else ""))
        else:
            print(f"    Costo: US$0 (capa gratis; el tope de gasto no aplica). Hasta ~{est['llamadas']} llamadas.")
        llave = llave_de(nombre_atacante)
        if llave and not (os.environ.get(llave) or "").strip():
            print(f"    Falta la llave: define {llave} en .env (solo se mira que exista; nunca se imprime).")
    if len(planes) > 1:
        print(f"  Total de los {len(planes)} atacantes: ~US${total_tipico:.2f} típico, hasta US${total_peor:.2f} en el peor caso.")
    if args.dry_run:
        for e in estafas:
            print(f"  - {e['id']}__{e['idioma']}")
        return 0
    sin_llave = [(n, llave_de(n)) for n in atacantes if llave_de(n) and not (os.environ.get(llave_de(n)) or "").strip()]
    if sin_llave:
        raise SystemExit("No se corre nada: falta la llave de " + ", ".join(f"{n} ({v})" for n, v in sin_llave) + ".")

    from inspect_ai.model import GenerateConfig, get_model
    from scamshield.attacker.bucle import Config, correr_atacante
    from scamshield.attacker.costo import Gasto

    sello = f"{datetime.now():%Y%m%d_%H%M%S}"
    todas: list[dict] = []
    for nombre_atacante, p_ent, p_sal, tope, _ in planes:
        sufijo = "" if len(planes) == 1 else "_" + "".join(c if c.isalnum() else "-" for c in nombre_atacante)
        salida = Path(args.salida) if args.salida else RAIZ / "results" / "raw" / f"atacante_{sello}{sufijo}.jsonl"
        print(f"\n=== Atacante {nombre_atacante} ===")
        cfg = Config(
            victima=args.victima,
            atacante=get_model(nombre_atacante, config=GenerateConfig(max_connections=args.max_connections, max_retries=40)),
            defensas=defensas, rondas=args.rondas, realismo_min=args.realismo_min,
            max_episodios=args.max_episodios, cache=not args.sin_cache, retry_on_error=args.retry_on_error,
            log_dir=args.log_dir, salida=salida, nombre_victima=args.victima, nombre_atacante=nombre_atacante,
            gasto=Gasto(tope_usd=tope, precio_entrada=p_ent, precio_salida=p_sal), effort=args.effort,
            al_terminar_ronda=lambda r, filas: print(
                f"Ronda {r}: {len(filas)} episodios, {sum(f['exito'] for f in filas)} estafas cayeron, "
                f"{sum(f['intento'] and not f['exito'] for f in filas)} intentadas y frenadas."),
        )
        res = asyncio.run(correr_atacante(cfg, estafas))
        todas += res["filas"]
        print(f"\nFilas en {salida}")
        print(f"Episodios: {res['episodios']}. Tokens de la víctima: {res['tokens']}")
        g = res["gasto"]
        print(f"Atacante: {g['llamadas']} llamadas, {g['tokens_entrada']} tokens de entrada y {g['tokens_salida']} de salida, "
              f"gasto estimado US${g['gastado_usd']:.3f}" + (f" de un tope de US${g['tope_usd']:.2f}" if g["tope_usd"] else "")
              + f". El atacante se negó {g['rechazos']} veces.")
    print()
    print(tabla_markdown(curvas(todas)))   # con varios atacantes, un panel por «atacante → víctima»
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
