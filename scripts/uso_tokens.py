"""Cuántos tokens usamos en la hackathon: sesiones de Claude Code y corridas de Inspect.

Platanus pide mostrar el uso de tokens (su proxy lo cuenta desde que se configuró). Este script
reconstruye el uso **desde el comienzo** con lo que quedó guardado en la máquina:

- **Claude Code:** las transcripciones `~/.claude/projects/<carpeta>/<sesión>.jsonl` (y sus
  subagentes en `<sesión>/subagents/*.jsonl`) traen el `usage` de cada respuesta del modelo.
  Se cuenta una vez por respuesta (`message.id`), solo las que caen desde `--desde`.
- **Inspect:** los logs `.eval` de las corridas del benchmark, el atacante y la víctima traen
  `stats.model_usage` por modelo (Anthropic, Groq, Google...).

No lee ni imprime llaves: solo números de tokens, modelos y fechas. El costo es una **estimación a
precio de lista**: las sesiones de Claude Code con suscripción no se pagan por token.

    python scripts/uso_tokens.py                       # desde el inicio de la hackathon
    python scripts/uso_tokens.py --json results/uso_tokens.json
    python scripts/uso_tokens.py --transcripciones "C:/Users/.../projects/d--Repo/*.jsonl"
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# 22:30 del 20-nov-2026 en Chile (UTC-3): el comienzo de las 36 horas.
DESDE_POR_DEFECTO = "2026-11-21T01:30:00Z"

# US$ por millón de tokens: entrada, salida, lectura de caché. La escritura de caché se cobra a 1,25x la entrada.
PRECIOS = {
    "claude-fable-5-2": (8.0, 40.0, 0.20),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}


@dataclass
class Uso:
    entrada: int = 0
    escritura_cache: int = 0
    lectura_cache: int = 0
    salida: int = 0
    respuestas: int = 0

    def sumar(self, otro: "Uso") -> None:
        self.entrada += otro.entrada
        self.escritura_cache += otro.escritura_cache
        self.lectura_cache += otro.lectura_cache
        self.salida += otro.salida
        self.respuestas += otro.respuestas

    @property
    def total(self) -> int:
        return self.entrada + self.escritura_cache + self.lectura_cache + self.salida

    def costo(self, modelo: str) -> Optional[float]:
        clave = next((k for k in PRECIOS if modelo.endswith(k)), None)
        if clave is None:
            return None
        ent, sal, lec = PRECIOS[clave]
        return (self.entrada * ent + self.escritura_cache * ent * 1.25 + self.lectura_cache * lec
                + self.salida * sal) / 1_000_000


@dataclass
class Informe:
    desde: str
    por_fuente: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(Uso)))

    def agregar(self, fuente: str, modelo: str, uso: Uso) -> None:
        self.por_fuente[fuente][modelo].sumar(uso)


def _fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _uso_de(usage: dict) -> Uso:
    return Uso(entrada=int(usage.get("input_tokens") or 0),
               escritura_cache=int(usage.get("cache_creation_input_tokens") or 0),
               lectura_cache=int(usage.get("cache_read_input_tokens") or 0),
               salida=int(usage.get("output_tokens") or 0), respuestas=1)


def leer_transcripcion(ruta: Path, desde: datetime) -> Iterable[tuple[str, Uso]]:
    """(modelo, uso) por respuesta del modelo, una sola vez por message.id."""
    vistos: set[str] = set()
    with ruta.open(encoding="utf-8", errors="replace") as f:
        for linea in f:
            if '"usage"' not in linea:
                continue
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            msg = d.get("message") or {}
            usage = msg.get("usage")
            ts = d.get("timestamp")
            if not isinstance(usage, dict) or not ts or _fecha(ts) < desde:
                continue
            clave = msg.get("id") or d.get("requestId") or d.get("uuid")
            if clave in vistos:
                continue
            vistos.add(clave)
            modelo = msg.get("model") or "desconocido"
            if modelo == "<synthetic>":
                continue
            yield modelo, _uso_de(usage)


# La sesión que coordina a las demás se llama distinto en la máquina; en el informe va por su rol.
ALIAS = {"core-gerente": "coordinador"}


def nombre_de_sesion(ruta: Path) -> str:
    """El nombre que se le dio a la sesión (custom-title o agent-name), o el id."""
    with ruta.open(encoding="utf-8", errors="replace") as f:
        for _, linea in zip(range(50), f):
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            for k in ("customTitle", "agentName"):
                if d.get(k):
                    return ALIAS.get(str(d[k]), str(d[k]))
    return ruta.stem[:8]


def transcripciones(patrones: list[str]) -> list[tuple[str, Path]]:
    """(fuente, archivo): cada sesión con sus subagentes sumados a ella."""
    salida = []
    for patron in patrones:
        for archivo in sorted(glob.glob(patron)):
            ruta = Path(archivo)
            nombre = nombre_de_sesion(ruta)
            salida.append((f"Claude Code · {nombre}", ruta))
            for sub in sorted((ruta.parent / ruta.stem / "subagents").glob("*.jsonl")):
                salida.append((f"Claude Code · {nombre} (subagentes)", sub))
    return salida


def leer_inspect(carpetas: list[str], desde: datetime) -> Iterable[tuple[str, Uso]]:
    try:
        from inspect_ai.log import list_eval_logs, read_eval_log
    except ImportError:
        return
    for carpeta in carpetas:
        if not Path(carpeta).exists():
            continue
        for info in list_eval_logs(carpeta, recursive=True):
            try:
                log = read_eval_log(info, header_only=True)
            except Exception:
                continue
            creado = getattr(log.eval, "created", None)
            if creado and _fecha(str(creado)) < desde:
                continue
            for modelo, u in (log.stats.model_usage or {}).items():
                yield modelo, Uso(entrada=u.input_tokens or 0,
                                  escritura_cache=u.input_tokens_cache_write or 0,
                                  lectura_cache=u.input_tokens_cache_read or 0,
                                  salida=u.output_tokens or 0, respuestas=1)


def armar(desde: str, patrones: list[str], carpetas_inspect: list[str]) -> Informe:
    corte = _fecha(desde)
    informe = Informe(desde=desde)
    for fuente, ruta in transcripciones(patrones):
        for modelo, uso in leer_transcripcion(ruta, corte):
            informe.agregar(fuente, modelo, uso)
    for modelo, uso in leer_inspect(carpetas_inspect, corte):
        informe.agregar("Inspect (benchmark, atacante y víctima)", modelo, uso)
    return informe


def como_dict(informe: Informe) -> dict:
    filas, total, costo = [], Uso(), 0.0
    for fuente, modelos in sorted(informe.por_fuente.items()):
        for modelo, uso in sorted(modelos.items()):
            c = uso.costo(modelo)
            filas.append({"fuente": fuente, "modelo": modelo, "respuestas": uso.respuestas,
                          "entrada": uso.entrada, "escritura_cache": uso.escritura_cache,
                          "lectura_cache": uso.lectura_cache, "salida": uso.salida, "total": uso.total,
                          "costo_lista_usd": None if c is None else round(c, 2)})
            total.sumar(uso)
            costo += c or 0.0
    return {"desde": informe.desde, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "filas": filas, "total_tokens": total.total, "total_salida": total.salida,
            "costo_lista_usd": round(costo, 2),
            "nota": "Costo estimado a precio de lista; las sesiones de Claude Code con suscripción no se pagan por token."}


def _m(n: int) -> str:
    return f"{n / 1_000_000:,.1f} M" if n >= 100_000 else f"{n:,}"


def imprimir(d: dict) -> None:
    print(f"Uso de tokens desde {d['desde']}\n")
    print(f"{'Fuente':48} {'Modelo':28} {'Resp.':>6} {'Entrada+caché':>14} {'Salida':>10} {'US$ lista':>10}")
    for f in d["filas"]:
        entrada = f["entrada"] + f["escritura_cache"] + f["lectura_cache"]
        costo = "-" if f["costo_lista_usd"] is None else f"{f['costo_lista_usd']:,.2f}"
        print(f"{f['fuente'][:48]:48} {f['modelo'][:28]:28} {f['respuestas']:>6} {_m(entrada):>14} "
              f"{_m(f['salida']):>10} {costo:>10}")
    print(f"\nTotal: {_m(d['total_tokens'])} tokens ({_m(d['total_salida'])} de salida). "
          f"Costo a precio de lista: ~US${d['costo_lista_usd']:,.2f}.")
    print(d["nota"])


def main(argv: Optional[list[str]] = None) -> int:
    casa = Path.home() / ".claude" / "projects"
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--desde", default=DESDE_POR_DEFECTO, help="ISO 8601; por defecto, el inicio de la hackathon")
    p.add_argument("--transcripciones", nargs="*",
                   default=[str(casa / "*agent-scam-shield" / "*.jsonl")],
                   help="globs de transcripciones de Claude Code (.jsonl de la sesión)")
    p.add_argument("--inspect", nargs="*", default=["logs"], help="carpetas con logs .eval de Inspect")
    p.add_argument("--json", type=Path, help="guarda el resumen en este archivo")
    a = p.parse_args(argv)
    d = como_dict(armar(a.desde, a.transcripciones, a.inspect))
    imprimir(d)
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
