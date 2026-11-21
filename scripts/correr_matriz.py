"""Corre la matriz de la eval: configuraciones de defensa × modelos × idiomas.

Los modelos salen de las llaves que haya en el entorno (o en `.env`): solo se mira si cada
variable está definida y no vacía, y su valor no se imprime nunca.

Uso:
    python scripts/correr_matriz.py --dry-run
    python scripts/correr_matriz.py --defensas none,layer2 --idiomas es --limit 5
    python scripts/correr_matriz.py --modelos google/gemini-3.8-flash,groq/openai/gpt-oss-120b
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Al correr `python scripts/correr_matriz.py`, sys.path parte en scripts/: así se usa el
# scamshield de este checkout y no otro que esté instalado en el venv.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Llave de API → modelos que se corren si la llave está. Edítalo a gusto.
# Los nombres siguen la notación de Inspect (proveedor/modelo). Todos deben aceptar
# llamadas a herramientas. Revisa en cada proveedor que el modelo siga disponible
# (y en la capa gratis, si es el caso): los catálogos cambian seguido.
MODELOS_POR_LLAVE: dict[str, list[str]] = {
    "GOOGLE_API_KEY": ["google/gemini-3.8-flash"],
    "GROQ_API_KEY": ["groq/openai/gpt-oss-120b"],
    "HF_TOKEN": ["hf-inference-providers/meta-llama/Llama-3.3-70B-Instruct"],
    "ANTHROPIC_API_KEY": ["anthropic/claude-sonnet-5-5"],
    "OPENAI_API_KEY": ["openai/gpt-6.2-sol"],
}

# Las mismas claves que scamshield.evals.task.DEFENSAS (lo verifica una prueba). Se repiten
# aquí para que --dry-run no tenga que importar Inspect.
DEFENSAS: tuple[str, ...] = ("none", "layer1", "layer2", "both")
IDIOMAS: tuple[str, ...] = ("es", "en")


def llaves_presentes(entorno: Mapping[str, str]) -> list[str]:
    """Nombres de las llaves conocidas que están definidas y no vacías. Nunca devuelve valores."""
    return [llave for llave in MODELOS_POR_LLAVE if (entorno.get(llave) or "").strip()]


def modelos_disponibles(entorno: Mapping[str, str]) -> list[str]:
    """Los modelos por defecto de cada proveedor que tiene llave, sin repetir."""
    modelos: list[str] = []
    for llave in llaves_presentes(entorno):
        for modelo in MODELOS_POR_LLAVE[llave]:
            if modelo not in modelos:
                modelos.append(modelo)
    return modelos


def armar_matriz(
    modelos: Sequence[str], defensas: Sequence[str], idiomas: Sequence[str]
) -> list[tuple[str, str, str]]:
    """Todas las celdas (defensa, modelo, idioma). Cada celda tiene un solo idioma."""
    return list(product(defensas, modelos, idiomas))


def _lista(texto: str) -> list[str]:
    return [x.strip() for x in texto.split(",") if x.strip()]


def _validar(valores: list[str], permitidos: Sequence[str], nombre: str) -> None:
    malos = [v for v in valores if v not in permitidos]
    if malos:
        raise ValueError(f"{nombre} desconocidos: {', '.join(malos)}. Opciones: {', '.join(permitidos)}")


def cargar_dotenv(ruta: Path) -> None:
    """Carga `.env` en el entorno sin pisar lo que ya esté definido. No imprime nada."""
    from dotenv import load_dotenv  # viene con inspect_ai

    if ruta.is_file():
        load_dotenv(ruta, override=False)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Corre la eval de scamshield sobre defensas × modelos × idiomas."
    )
    p.add_argument("--modelos", help="Modelos separados por coma. Si no se pasa, salen de las llaves.")
    p.add_argument("--defensas", default=",".join(DEFENSAS), help="Por defecto: %(default)s.")
    p.add_argument("--idiomas", default=",".join(IDIOMAS), help="Por defecto: %(default)s.")
    p.add_argument("--dry-run", action="store_true", help="Imprime la matriz sin correr nada.")
    p.add_argument("--limit", type=int, help="Máximo de muestras por celda.")
    p.add_argument(
        "--max-connections", type=int, default=2,
        help="Llamadas simultáneas por modelo (por defecto %(default)s, por los límites de las capas gratis).",
    )
    p.add_argument("--log-dir", default=str(RAIZ / "logs"), help="Dónde quedan los logs de Inspect.")
    p.add_argument("--env", default=str(RAIZ / ".env"), help="Archivo .env con las llaves.")
    p.add_argument("--display", help="Display de Inspect (full, rich, plain, none...).")
    return p


def _imprimir_matriz(celdas: list[tuple[str, str, str]]) -> None:
    print(f"Matriz: {len(celdas)} celdas (defensa × modelo × idioma)")
    for defensa, modelo, idioma in celdas:
        print(f"  {defensa:<7} {modelo:<60} {idioma}")


def _resumen(log) -> str:
    args = log.eval.task_args or {}
    partes = [f"{args.get('defense', '?'):<7}", f"{log.eval.model:<60}", f"{args.get('idiomas', '?'):<3}", log.status]
    if log.results:
        for puntaje in log.results.scores:
            for metrica in puntaje.metrics.values():
                partes.append(f"{puntaje.name}.{metrica.name}={metrica.value:.2f}")
    return " ".join(partes)


def correr(
    celdas: list[tuple[str, str, str]],
    log_dir: str,
    limit: int | None = None,
    max_connections: int | None = None,
    display: str | None = None,
) -> bool:
    """Corre cada celda con inspect_ai.eval. Devuelve True si todas terminaron bien."""
    from inspect_ai import eval as inspect_eval

    from scamshield.evals.task import scamshield

    todo_ok = True
    for defensa, modelo, idioma in celdas:
        logs = inspect_eval(
            scamshield(defense=defensa, idiomas=idioma),
            model=modelo,
            log_dir=log_dir,
            limit=limit,
            max_connections=max_connections,
            display=display,
        )
        for log in logs:
            print(_resumen(log))
            todo_ok = todo_ok and log.status == "success"
    return todo_ok


def main(argv: Sequence[str] | None = None) -> int:
    import os

    args = _parser().parse_args(argv)
    try:
        defensas = _lista(args.defensas)
        idiomas = _lista(args.idiomas)
        _validar(defensas, DEFENSAS, "Defensas")
        _validar(idiomas, IDIOMAS, "Idiomas")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Se carga siempre: con --modelos, Inspect igual necesita las llaves en el entorno.
    cargar_dotenv(Path(args.env))
    if args.modelos:
        modelos = _lista(args.modelos)
    else:
        presentes = llaves_presentes(os.environ)
        if not presentes:
            print(
                "Error: no hay ningún proveedor con llave. Define al menos una de estas variables en "
                f"{args.env} (o en el entorno): {', '.join(MODELOS_POR_LLAVE)}. "
                "También puedes pasar --modelos, por ejemplo --modelos mockllm/model.",
                file=sys.stderr,
            )
            return 2
        print(f"Llaves presentes: {', '.join(presentes)}")
        modelos = modelos_disponibles(os.environ)

    celdas = armar_matriz(modelos, defensas, idiomas)
    _imprimir_matriz(celdas)
    if args.dry_run:
        return 0

    ok = correr(celdas, args.log_dir, args.limit, args.max_connections, args.display)
    return 0 if ok else 1


if __name__ == "__main__":
    # Que una consola sin UTF-8 (Windows) no se caiga con las tildes.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
