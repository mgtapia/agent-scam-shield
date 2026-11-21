"""Arma los números de la vista Resultados de la demo (demo/resultados.json y su copia demo/resultados.js).

Son los mismos números de la tabla «Resultados» del README, leídos de los JSON de `results/`. La página no
calcula nada: solo dibuja lo que este script deja. Cada bloque dice de qué archivo salió (`fuente`) y con
qué comando se regenera ese archivo (`comando`).

Origen de cada número:
- `results/bench.json`: `grifter bench --json results/bench.json` (agente guionado, sin modelo ni red).
- `results/sonnet_jefe.json`: `python scripts/resumen_resultados.py logs/jefe --json results/sonnet_jefe.json`.
- `results/haiku_dueno.json`: `python scripts/resumen_resultados.py logs/dueno --idioma es --json results/haiku_dueno.json`.
- `results/clasificador.json`: `python scripts/validacion_cruzada_vivo.py --agrupar familia --json results/clasificador.json`.
- `results/atacante/*_curva.json`: `python scripts/resumen_curva_atacante.py <jsonl>... --salida <archivo>`, que une
  la corrida original con la que completó lo que cortó la cuota y trae Wilson por ronda; o
  `results/atacante/*_curvas.json`: `python scripts/graficar_atacante.py <jsonl>`. Con `--atacante` se elige
  el archivo; si no, el que tenga más rondas y estafas entre los que tienen a lo sumo un 10 % de muestras
  con error. No se usa la fecha del archivo, que cambia con cada clon.
- Pipelock (4 de 42): no hay archivo de origen en el repo; se corrió con `scripts/capa1_cobertura.py` y el
  binario real de Pipelock, que no está en este entorno. Va con su fuente escrita (`docs/pitch.md`).

Uso:
    python scripts/resultados_demo.py
    python scripts/resultados_demo.py --atacante results/atacante/<nombre>_curvas.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
RESULTS = RAIZ / "results"
DEMO = RAIZ / "demo"

from scripts.resumen_resultados import intervalo_wilson  # noqa: E402

# Sin archivo de origen: el número y de dónde sale. Ver el docstring. El intervalo es el de Wilson sobre las
# 42 estafas, que aquí sí son independientes (una corrida por escenario).
_FRENADAS, _ESTAFAS = 4, 42
PIPELOCK = {
    "frenadas": _FRENADAS, "estafas": _ESTAFAS, "falsas_alarmas": 0,
    "tasa": _FRENADAS / _ESTAFAS, "bajo": intervalo_wilson(_FRENADAS / _ESTAFAS, _ESTAFAS)[0],
    "alto": intervalo_wilson(_FRENADAS / _ESTAFAS, _ESTAFAS)[1], "escenarios": _ESTAFAS,
    "que_frena": ["inyeccion_web", "mcp_envenenado"],
    "fuente": "docs/pitch.md (corrida de scripts/capa1_cobertura.py con el binario real de Pipelock)",
    "comando": "PIPELOCK_BIN=/ruta/a/pipelock python scripts/capa1_cobertura.py",
    "sin_archivo": True,
}
CONFIGURACIONES = ("none", "layer1", "layer2", "layer3", "layer23")
METRICAS = ("estafas_exitosas", "utilidad", "falsas_alarmas")


def _limpio(x: Any) -> Any:
    """NaN e infinitos a None: el JSON de la demo tiene que ser JSON válido."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _limpio(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_limpio(v) for v in x]
    return x


def _leer(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _rel(ruta: Path) -> str:
    return ruta.relative_to(RAIZ).as_posix()


def _tasa(m: dict[str, Any]) -> dict[str, Any]:
    """La métrica con lo que dibuja la página: tasa, intervalo y n."""
    return {k: m.get(k) for k in ("tasa", "bajo", "alto", "escenarios", "repeticiones") if k in m}


def bench() -> dict[str, Any]:
    ruta = RESULTS / "bench.json"
    b = _leer(ruta)
    por = b["por_configuracion"]
    return {
        "agente": b.get("agente"), "aviso": b.get("aviso"), "escenarios": b.get("escenarios"),
        "configuraciones": [{"clave": c, **{m: _tasa(por[c][m]) for m in METRICAS}} for c in CONFIGURACIONES if c in por],
        "fuente": _rel(ruta), "comando": "grifter bench --json results/bench.json",
    }


def sonnet() -> dict[str, Any]:
    ruta = RESULTS / "sonnet_jefe.json"
    fila = next(f for f in _leer(ruta) if f["defensa"] == "none")
    m = fila["estafas_exitosas"]
    return {
        "modelo": fila["modelo"], "defensa": fila["defensa"], "estafas_exitosas": _tasa(m),
        # La tasa es el promedio por escenario; con el mismo número de repeticiones en cada uno, esto es el conteo.
        "pagos": round(m["tasa"] * m["repeticiones"]), "repeticiones": m["repeticiones"],
        "fuente": _rel(ruta), "comando": "python scripts/resumen_resultados.py logs/jefe --json results/sonnet_jefe.json",
    }


def haiku() -> dict[str, Any]:
    ruta = RESULTS / "haiku_dueno.json"
    fila = next(f for f in _leer(ruta) if f.get("dueno_simulado"))
    return {
        "modelo": fila["modelo"], "defensa": fila["defensa"],
        "estafas_exitosas": _tasa(fila["estafas_exitosas"]), "utilidad": _tasa(fila["utilidad"]),
        # Ya viene por cada 100 acciones sensibles.
        "toques_por_100": {k: fila["toques_por_100"].get(k) for k in ("tasa", "bajo", "alto", "escenarios", "intentos")},
        "fuente": _rel(ruta),
        "comando": "python scripts/resumen_resultados.py logs/dueno --idioma es --json results/haiku_dueno.json",
    }


def clasificador() -> dict[str, Any]:
    ruta = RESULTS / "clasificador.json"
    c = _leer(ruta)
    return {
        **c["total"], "agrupar": c.get("agrupar", "escenario"), "corridas": c["corridas"], "pliegues": c["pliegues"], "semillas": c["semillas"],
        "episodios": c["episodios"],
        # Es el rango entre corridas (pliegues × semillas), no un intervalo de confianza.
        "tipo_intervalo": "rango",
        "fuente": _rel(ruta), "comando": "python scripts/validacion_cruzada_vivo.py --agrupar familia --json results/clasificador.json",
    }


MAX_ERRORES = 0.10   # una curva con más muestras con error que esto no se presenta como la curva del atacante


def _serie_resumen(modelo: str, defensa: str, v: dict[str, Any]) -> dict[str, Any]:
    """Una serie desde el formato de resumen_curva_atacante.py: una entrada por ronda, con su Wilson y cuántas
    estafas tienen un episodio puntuado en esa ronda (si es menos que n, la ronda quedó incompleta)."""
    rs = sorted(v["rondas"], key=lambda r: r["ronda"])
    n = max((r["n"] for r in rs), default=0)
    return {"modelo": modelo, "defensa": defensa, "n": n, "rondas": max((r["ronda"] for r in rs), default=0),
            "exitos": [r["exitosas"] for r in rs], "intentos": [r.get("intentadas") for r in rs],
            "ic": [list(r["wilson_95"]) for r in rs], "errores": 0,
            "incompletas": [{"ronda": r["ronda"], "validas": r["estafas_con_ronda_valida"], "n": r["n"]}
                            for r in rs if r.get("estafas_con_ronda_valida", r["n"]) < r["n"]]}


def _series(curvas: dict[str, Any]) -> list[dict[str, Any]]:
    """Una serie por modelo y defensa, sin las unidades crudas y con el intervalo de Wilson por ronda.

    Cada estafa cuenta una vez por ronda (cayó o no hasta esa ronda), así que son unidades independientes.
    """
    series = []
    for modelo, por_defensa in curvas.items():
        for d, v in por_defensa.items():
            if isinstance(v.get("rondas"), list):
                series.append(_serie_resumen(modelo, d, v))
                continue
            n = v.get("n") or 0
            ic = [list(intervalo_wilson(e / n, n)) if n else [None, None] for e in v.get("exitos", [])]
            series.append({"modelo": modelo, "defensa": d, "ic": ic,
                           **{k: x for k, x in v.items() if not k.startswith("unidades_")}})
    return series


def _puntaje(series: list[dict[str, Any]]) -> tuple[int, int, int]:
    """(válida, rondas, estafas): la curva más completa entre las que tienen pocos errores."""
    rondas = max((s.get("rondas", 0) for s in series), default=0)
    n = max((s.get("n", 0) for s in series), default=0)
    muestras = sum((s.get("n", 0) or 0) * ((s.get("rondas", 0) or 0) + 1) for s in series)
    errores = sum(s.get("errores", 0) or 0 for s in series)
    return int(muestras > 0 and errores / muestras <= MAX_ERRORES), rondas, n


def atacante(carpeta: Path | None = None, elegida: Path | None = None) -> dict[str, Any]:
    """La curva del atacante adaptativo y en qué estado está para dibujarla."""
    carpeta = carpeta or RESULTS / "atacante"
    archivos = [elegida] if elegida else sorted([*carpeta.glob("*_curvas.json"), *carpeta.glob("*_curva.json")])
    if not archivos:
        return {"estado": "sin_archivo", "series": None, "fuente": None,
                "comando": "python scripts/graficar_atacante.py <jsonl> && python scripts/resultados_demo.py"}
    ruta, series = max(((r, _series(_leer(r))) for r in archivos), key=lambda x: _puntaje(x[1]))
    if all(s.get("rondas", 0) < 1 for s in series):
        estado = "sin_rondas"
    elif not _puntaje(series)[0]:
        estado = "con_errores"
    elif all(not any(s.get("exitos") or []) for s in series):
        estado = "en_cero"
    else:
        estado = "ok"
    return {"estado": estado, "series": series, "fuente": _rel(ruta) if ruta.is_relative_to(RAIZ) else str(ruta),
            "comando": "python scripts/resumen_curva_atacante.py <jsonl>... --salida <archivo> && python scripts/resultados_demo.py"}


def armar(curva: Path | None = None) -> dict[str, Any]:
    return _limpio({
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "readme": "README.md#resultados",
        "bench": bench(), "pipelock": PIPELOCK, "sonnet": sonnet(), "haiku": haiku(),
        "clasificador": clasificador(), "atacante": atacante(elegida=curva),
    })


def escribir(datos: dict[str, Any], salida: Path = DEMO) -> list[Path]:
    """resultados.json y su copia resultados.js (abrir la página como archivo no deja usar fetch)."""
    texto = json.dumps(datos, indent=1, ensure_ascii=False, allow_nan=False)
    json_, js = salida / "resultados.json", salida / "resultados.js"
    json_.write_text(texto + "\n", encoding="utf-8")
    js.write_text(f"// Generado por scripts/resultados_demo.py. No editar a mano.\nwindow.RESULTADOS = {texto};\n",
                  encoding="utf-8")
    return [json_, js]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--atacante", type=Path, help="el _curvas.json del atacante que se muestra")
    a = p.parse_args(argv)
    datos = armar(a.atacante)
    for ruta in escribir(datos):
        print(f"escrito {_rel(ruta)}")
    a = datos["atacante"]
    print(f"atacante: {a['estado']}" + (f" ({a['fuente']})" if a["fuente"] else ""))
    print("sin archivo de origen: pipelock (fuente: docs/pitch.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
