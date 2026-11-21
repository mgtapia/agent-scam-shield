"""Línea de comandos de Grifter: `grifter bench` y `grifter duelo` (o `python -m scamshield <comando>`)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

MODELO_GUIONADO = ("mockllm", "guionado")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="grifter", description="Grifter: benchmark de estafas contra agentes que pagan.")
    sub = p.add_subparsers(dest="comando", required=True)
    b = sub.add_parser(
        "bench", help="corre el benchmark y escribe la tabla",
        description=("Corre el benchmark sin llaves de API. Por defecto usa un agente guionado e ingenuo: mide qué "
                     "frena cada defensa, no qué tan listo es un modelo. Con --modelo usa un modelo real."))
    b.add_argument("--modelo", default="mockllm",
                   help="mockllm (por defecto: agente guionado) o proveedor/modelo; Inspect lee las llaves de .env")
    b.add_argument("--json", type=Path, metavar="ARCHIVO", help="guarda además los números en este archivo")
    b.add_argument("--dry-run", action="store_true", help="describe lo que haría --modelo, sin correr nada")
    b.add_argument("--logs", default="logs/bench", help="carpeta de logs de Inspect (solo con --modelo)")
    d = sub.add_parser(
        "duelo", help="un hacker que aprende de cómo lo bloquean, contra un escudo que aprende de él",
        description=("Corre el duelo sin llaves de API: un atacante por mutaciones (Thompson sampling) contra el "
                     "clasificador y la bóveda reales, que se reentrenan con lo que el dueño simulado confirma. "
                     "La capa 2 no se entrena: `Pagos con capa 2` debe quedar en 0."))
    d.add_argument("--generaciones", type=int, default=20, help="generaciones a correr (por defecto 20)")
    d.add_argument("--semilla", type=int, default=0, help="semilla del flujo, el clasificador y el atacante")
    d.add_argument("--sin-entrenar", action="store_true",
                   help="congela el clasificador y la bóveda: el atacante aprende y el escudo no responde")
    d.add_argument("--json", type=Path, metavar="ARCHIVO", help="guarda además los eventos `duelo` en este archivo")
    return p


def _duelo(args: argparse.Namespace) -> int:
    from scamshield.vivo.duelo import Duelo, tabla
    from scamshield.vivo.flujo import Flujo
    from scamshield.vivo.motor import Motor

    inicio = time.perf_counter()
    motor = Motor(semilla=args.semilla, flujo=Flujo(semilla=args.semilla))
    motor.precalentar()
    duelo = Duelo(motor, semilla=args.semilla, entrenar=not args.sin_entrenar)
    eventos = [duelo.generacion()[0] for _ in range(args.generaciones)]
    sys.stdout.write(tabla(eventos) + "\n")
    pagos = sum(e["exitosas_capa2"] for e in eventos)
    sin_capa2 = sum(e["sin_capa2"] for e in eventos)
    sys.stdout.write(f"\nCon la capa 2: {pagos} pagos a una cuenta de estafador en {args.generaciones} "
                     f"generaciones. Sin ella habrían salido {sin_capa2}.\n")
    if args.json:
        args.json.write_text(json.dumps(eventos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Listo en {time.perf_counter() - inicio:.1f} s.", file=sys.stderr)
    return 0


def _utf8() -> None:
    """La tabla lleva tildes y debe salir igual en cualquier consola: UTF-8 y saltos de línea LF."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _utf8()
    if args.comando == "duelo":
        return _duelo(args)
    from scamshield import bench
    from scamshield.scenarios import cargar

    guionado = args.modelo in MODELO_GUIONADO
    if args.dry_run:
        sys.stdout.write(bench.describir_modelo(args.modelo, args.logs) if not guionado else
                         "Agente guionado: corre las 6 configuraciones sobre todos los escenarios, sin modelo "
                         "ni red, con la capa 1 de referencia.\n")
        return 0
    inicio = time.perf_counter()
    escenarios = cargar(bench.IDIOMAS)
    resultados = bench.correr_guionado(escenarios) if guionado else bench.ordenar(
        bench.correr_modelo(args.modelo, args.logs), escenarios)
    agente = "guionado" if guionado else args.modelo
    sys.stdout.write(bench.a_markdown(resultados, escenarios, agente))
    if args.json:
        args.json.write_text(json.dumps(bench.construir_resumen(resultados, escenarios, agente), indent=2,
                                        ensure_ascii=False), encoding="utf-8")
    print(f"Listo en {time.perf_counter() - inicio:.1f} s.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
