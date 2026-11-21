"""Arma los números de la vista Resultados de la demo (demo/resultados.json y su copia demo/resultados.js).

Son los mismos números de la tabla «Resultados» del README, leídos de los JSON de `results/`. La página no
calcula nada: solo dibuja lo que este script deja. Cada bloque dice de qué archivo salió (`fuente`) y con
qué comando se regenera ese archivo (`comando`).

Origen de cada número:
- `results/bench.json`: `grifter bench --json results/bench.json` (agente guionado, sin modelo ni red).
- `results/sonnet_jefe.json`: `python scripts/resumen_resultados.py logs/jefe --json results/sonnet_jefe.json`.
- `results/haiku_dueno.json`: `python scripts/resumen_resultados.py logs/dueno --idioma es --json results/haiku_dueno.json`.
- `results/clasificador.json`: `python scripts/validacion_cruzada_vivo.py --json results/clasificador.json`.
- `results/atacante/*_curvas.json`: `python scripts/graficar_atacante.py <jsonl>`. Se usa el más reciente.
- Pipelock (4 de 42): no hay archivo de origen en el repo; se corrió con `scripts/capa1_cobertura.py` y el
  binario real de Pipelock, que no está en este entorno. Va con su fuente escrita (`docs/pitch.md`).

Uso:
    python scripts/resultados_demo.py
"""
from __future__ import annotations

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
        **c["total"], "corridas": c["corridas"], "pliegues": c["pliegues"], "semillas": c["semillas"],
        "episodios": c["episodios"],
        # Es el rango entre corridas (pliegues × semillas), no un intervalo de confianza.
        "tipo_intervalo": "rango",
        "fuente": _rel(ruta), "comando": "python scripts/validacion_cruzada_vivo.py --json results/clasificador.json",
    }


def atacante() -> dict[str, Any]:
    """La curva más reciente del atacante adaptativo, y en qué estado está para dibujarla."""
    archivos = sorted((RESULTS / "atacante").glob("*_curvas.json"), key=lambda p: p.stat().st_mtime)
    if not archivos:
        return {"estado": "sin_archivo", "curvas": None, "fuente": None}
    ruta = archivos[-1]
    curvas = _leer(ruta)
    series = [{"modelo": modelo, "defensa": d, **v} for modelo, porDefensa in curvas.items() for d, v in porDefensa.items()]
    if all(s.get("rondas", 0) < 1 for s in series):
        estado = "sin_rondas"
    elif all(not any(s.get("exitos") or []) for s in series):
        estado = "en_cero"
    else:
        estado = "ok"
    return {"estado": estado, "series": series, "fuente": _rel(ruta),
            "comando": f"python scripts/graficar_atacante.py <jsonl> && python scripts/resultados_demo.py"}


def armar() -> dict[str, Any]:
    return _limpio({
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "readme": "README.md#resultados",
        "bench": bench(), "pipelock": PIPELOCK, "sonnet": sonnet(), "haiku": haiku(),
        "clasificador": clasificador(), "atacante": atacante(),
    })


def escribir(datos: dict[str, Any], salida: Path = DEMO) -> list[Path]:
    """resultados.json y su copia resultados.js (abrir la página como archivo no deja usar fetch)."""
    texto = json.dumps(datos, indent=1, ensure_ascii=False, allow_nan=False)
    json_, js = salida / "resultados.json", salida / "resultados.js"
    json_.write_text(texto + "\n", encoding="utf-8")
    js.write_text(f"// Generado por scripts/resultados_demo.py. No editar a mano.\nwindow.RESULTADOS = {texto};\n",
                  encoding="utf-8")
    return [json_, js]


def main() -> int:
    datos = armar()
    for ruta in escribir(datos):
        print(f"escrito {_rel(ruta)}")
    a = datos["atacante"]
    print(f"atacante: {a['estado']}" + (f" ({a['fuente']})" if a["fuente"] else ""))
    print("sin archivo de origen: pipelock (fuente: docs/pitch.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
