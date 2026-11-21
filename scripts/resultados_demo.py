"""Arma los números de la vista Resultados de la demo (demo/resultados.json y su copia demo/resultados.js).

Son los mismos números de la tabla «Resultados» del README, leídos de los JSON de `results/`. La página no
calcula nada: solo dibuja lo que este script deja. Cada bloque dice de qué archivo salió (`fuente`) y con
qué comando se regenera ese archivo (`comando`).

Origen de cada número:
- `results/bench.json`: `grifter bench --json results/bench.json` (agente guionado, sin modelo ni red).
- `results/sonnet_jefe.json`: `python scripts/resumen_resultados.py logs/jefe --json results/sonnet_jefe.json`.
- `results/haiku_dueno.json`: `python scripts/resumen_resultados.py logs/dueno --idioma es --json results/haiku_dueno.json`.
- `results/clasificador.json`: `python scripts/validacion_cruzada_vivo.py --agrupar familia --json results/clasificador.json`.
- `results/falsas_alarmas.json`: `python scripts/falsas_alarmas_vivo.py --json results/falsas_alarmas.json` (las opciones
  para bajar las falsas alarmas del clasificador; bloque `falsas_alarmas`).
- `results/juez_gemini.json`: `python scripts/juez_vivo.py --modelo gemini-lite --banda 0.2,0.5 --barrido --pausa 7 --concurrencia 1
  --json results/juez_gemini.json` (el juez LLM de los casos dudosos, #131; bloque `juez`).
- `colados` (qué se cuela por capa y por familia): `por_escenario` de `results/bench.json` y `colados_por_familia` de
  `results/clasificador.json`.
- `results/atacante/*_curva.json`: `python scripts/resumen_curva_atacante.py <jsonl>... --salida <archivo>`, que une
  la corrida original con la que completó lo que cortó la cuota y trae Wilson por ronda; o
  `results/atacante/*_curvas.json`: `python scripts/graficar_atacante.py <jsonl>`. Con `--atacante` se elige
  el archivo; si no, el que tenga más rondas y estafas entre los que tienen a lo sumo un 10 % de muestras
  con error. No se usa la fecha del archivo, que cambia con cada clon.
- `results/duelo/{congelado,aprende}_s{0,1,2}.json`: `grifter duelo --generaciones 20 --semilla N [--sin-entrenar]
  --json <archivo>`, determinista: el atacante por mutaciones contra el clasificador congelado o que aprende.
- Pipelock (4 de 42): no hay archivo de origen en el repo; se corrió con `scripts/capa1_cobertura.py` y el
  binario real de Pipelock, que no está en este entorno. Va con su fuente escrita (`docs/pitch.md`).

Uso:
    python scripts/resultados_demo.py
    python scripts/resultados_demo.py --atacante results/atacante/<nombre>_curvas.json
"""
from __future__ import annotations

import argparse
import ast
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

from scamshield.attacker.resultados import SEP_ATACANTE  # noqa: E402
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
        "es_contra_en": _es_contra_en(b.get("es_contra_en") or {}),
        "fuente": _rel(ruta), "comando": "grifter bench --json results/bench.json",
    }


def _es_contra_en(e: dict[str, Any]) -> dict[str, Any]:
    """Español contra inglés con el agente guionado: la tasa de cada idioma por configuración, cuántos pares
    (el mismo escenario en los dos idiomas) hay y cuáles dan distinto."""
    por = e.get("por_idioma") or {}
    return {
        "configuraciones": [{"clave": c, **{i: {m: _tasa(por[c][i][m]) for m in METRICAS} for i in ("es", "en")}}
                            for c in CONFIGURACIONES if c in por],
        "pares": int(e.get("pares") or 0),
        "difieren": list(e.get("difieren") or []),
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


def colados(bench_json: Path | None = None, clasif_json: Path | None = None) -> dict[str, Any]:
    """Qué se cuela, por capa y por familia de estafa (`anotaciones.familia`).

    Por capa sale de `por_escenario` de `results/bench.json`: una fila por escenario e idioma, como la tasa de
    estafas exitosas. `dueno_dicta` cuenta, por capa, las que se colaron porque el dueño ya cayó y dicta la
    cuenta. Para el clasificador, de `colados_por_familia` de `results/clasificador.json`:
    correos de estafa apartados que quedaron bajo el umbral, sumando las corridas. Son medidas distintas: el bench
    dice si el pago salió; el clasificador solo sube la sospecha.
    """
    bench_json = bench_json or RESULTS / "bench.json"
    clasif_json = clasif_json or RESULTS / "clasificador.json"
    filas = [e for e in _leer(bench_json)["por_escenario"] if e["tipo"] == "estafa"]
    configs = [c for c in CONFIGURACIONES if filas and c in filas[0]["resultados"]]
    familias: dict[str, dict[str, Any]] = {}
    totales = {c: 0 for c in configs}
    dicta = {c: 0 for c in configs}
    for e in filas:
        fam = e.get("familia") or e["escenario"].rsplit("__", 1)[0]
        f = familias.setdefault(fam, {"familia": fam, "estafas": 0, "dueno_dicta": {c: 0 for c in configs},
                                      "por_capa": {c: 0 for c in configs}, "escenarios": {c: set() for c in configs}})
        f["estafas"] += 1
        for c in configs:
            if e["resultados"][c]["cayo"]:
                f["por_capa"][c] += 1
                f["escenarios"][c].add(e["escenario"].rsplit("__", 1)[0])
                totales[c] += 1
                f["dueno_dicta"][c] += bool(e.get("dueno_dicta"))
                dicta[c] += bool(e.get("dueno_dicta"))
    cl = _leer(clasif_json) if clasif_json.exists() else {}
    por_familia = cl.get("colados_por_familia") or {}
    for fam, g in por_familia.items():
        f = familias.setdefault(fam, {"familia": fam, "estafas": 0, "dueno_dicta": {c: 0 for c in configs},
                                      "por_capa": {c: 0 for c in configs}, "escenarios": {c: set() for c in configs}})
        f["clasificador"] = {k: g[k] for k in ("colados", "correos", "corridas", "corridas_con_colados", "escenarios")}
    lista = []
    for f in familias.values():
        f["escenarios"] = {c: sorted(v) for c, v in f["escenarios"].items() if v}
        f.setdefault("clasificador", None)
        lista.append(f)
    # Primero lo que cruza el escudo completo, después la capa 2, después el clasificador.
    lista.sort(key=lambda f: (-f["por_capa"].get("layer23", 0), -f["por_capa"].get("layer2", 0),
                              -((f["clasificador"] or {}).get("colados", 0)), f["familia"]))
    clasif_total = {k: sum(g[k] for g in por_familia.values()) for k in ("colados", "correos")} if por_familia else None
    return {
        "configuraciones": configs, "familias": lista, "estafas": len(filas),
        "totales": totales, "dueno_dicta": dicta, "clasificador": clasif_total,
        "clasificador_por_canal": cl.get("colados_por_canal"),
        "unidad_capas": "escenario × idioma", "unidad_clasificador": "correos apartados, sumando las corridas",
        "corridas": cl.get("corridas"),
        "fuente": f"{_rel(bench_json) if bench_json.is_relative_to(RAIZ) else bench_json} · "
                  f"{_rel(clasif_json) if clasif_json.is_relative_to(RAIZ) else clasif_json}",
        "comando": "grifter bench --json results/bench.json && python scripts/validacion_cruzada_vivo.py --agrupar familia "
                   "--json results/clasificador.json",
    }


TESTS = RAIZ / "tests"


def limites_conocidos(carpeta: Path | None = None) -> list[dict[str, str]]:
    """Los ataques que sabemos que todavía nos rompen: las pruebas `xfail(strict=True)` del repo.

    Con `strict=True`, la CI falla si una de estas pruebas empieza a pasar, así que la lista no puede quedar
    vieja: si un arreglo cierra el hueco, hay que sacar la marca y la fila desaparece sola.
    """
    salida = []
    for ruta in sorted((carpeta or TESTS).glob("test_*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in nodo.decorator_list:
                if not (isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") == "xfail"):
                    continue
                kw = {k.arg: k.value for k in dec.keywords}
                if not (isinstance(kw.get("strict"), ast.Constant) and kw["strict"].value is True):
                    continue
                razon = kw.get("reason")
                texto = razon.value if isinstance(razon, ast.Constant) and isinstance(razon.value, str) else ""
                salida.append({"prueba": f"{_rel(ruta) if ruta.is_relative_to(RAIZ) else ruta.name}::{nodo.name}", "razon": " ".join(texto.split())})
    return salida


def cobertura(col: dict[str, Any] | None = None, duelo_: dict[str, Any] | None = None,
              tests: Path | None = None) -> dict[str, Any]:
    """Cobertura por tipo de ataque: lo que Grifter promete por diseño contra lo que se midió.

    - **Esperada (por diseño).** La capa 2 frena todo pago o envío cuyo destino salió de contenido externo
      (correo, web, WhatsApp, llamada, MCP). Si el dueño ya cayó y dicta él la cuenta, la capa 2 la deja pasar
      a propósito y la frena la capa 3 (beneficiario nuevo o que no calza con su RUT). Por eso el escudo completo
      promete el 100 % de cada familia, y la capa 2 sola, todas menos las que dicta el dueño.
    - **Real.** Lo que midió `grifter bench`, con un agente guionado que siempre intenta pagar: mide las
      defensas, no lo crédulo de un modelo. Una fila por escenario e idioma.
    - **Clasificador.** Aparte: solo sube la sospecha y no promete nada. Es la detección sobre correos
      apartados (validación cruzada por familia).
    - **Límites conocidos.** Las pruebas del equipo rojo que todavía fallan: esperada 0 %.
    """
    col = col or colados()
    duelo_ = duelo_ if duelo_ is not None else duelo()
    filas = []
    for f in col["familias"]:
        n = f["estafas"]
        if not n:
            continue
        dicta = f["dueno_dicta"].get("none", 0)
        capa = f["por_capa"]
        cl = f.get("clasificador")
        filas.append({
            "familia": f["familia"], "ataques": n, "dueno_dicta": dicta,
            "completo": {"esperada": n, "real": n - capa.get("layer23", 0)},
            "capa2": {"esperada": n - dicta, "real": n - capa.get("layer2", 0)},
            "clasificador": None if not cl or not cl["correos"] else
            {"detectados": cl["correos"] - cl["colados"], "correos": cl["correos"],
             "tasa": round(1 - cl["colados"] / cl["correos"], 3)},
            "cumple": n - capa.get("layer23", 0) >= n and n - capa.get("layer2", 0) >= n - dicta,
        })
    filas.sort(key=lambda r: (r["cumple"], -r["ataques"], r["familia"]))
    total = sum(r["ataques"] for r in filas)
    frenadas = sum(r["completo"]["real"] for r in filas)
    limites = limites_conocidos(tests)
    return {
        "familias": filas,
        "totales": {
            "familias": len(filas), "ataques_bench": total, "frenadas_bench": frenadas,
            "esperada": 1.0, "real": round(frenadas / total, 3) if total else None,
            "intentos_duelo": duelo_.get("candidatos"), "cruces_capa2_duelo": duelo_.get("exitosas_capa2"),
            "correos_clasificador": (col.get("clasificador") or {}).get("correos"),
            "limites_conocidos": len(limites),
        },
        "limites": limites,
        "unidad": "escenario × idioma (bench); intentos generados (Duelo); correos apartados (clasificador)",
        "fuente": f"{col['fuente']} · results/duelo · tests (xfail strict)",
        "comando": "grifter bench --json results/bench.json && python scripts/resultados_demo.py",
    }


FALSAS = RESULTS / "falsas_alarmas.json"
COMANDO_FALSAS = "python scripts/falsas_alarmas_vivo.py --json results/falsas_alarmas.json"


def falsas_alarmas(ruta: Path | None = None) -> dict[str, Any]:
    """Las opciones para bajar las falsas alarmas del clasificador: cobertura y falsas alarmas de cada regla de decisión
    y de cada umbral fijo, con la misma validación cruzada por familia. Ninguna regla cambia lo que marca la capa 2."""
    ruta = ruta or FALSAS
    if not ruta.exists():
        return {"estado": "sin_archivo", "fuente": None, "comando": COMANDO_FALSAS}
    d = _leer(ruta)
    return {
        "estado": "ok", "corridas": d["corridas"], "agrupar": d.get("agrupar"),
        "reglas": [{"clave": k, **{m: v[m] for m in ("recall", "precision", "falsas_alarmas")}} for k, v in d["total"].items()],
        "curva_umbral": d.get("curva_umbral", []),
        "umbral_calibrado": sorted({f["umbral_calibrado"] for f in d["filas"]}),
        "escenarios_con_falsa_alarma": sorted({e for f in d["filas"] for e in f.get("falsas_alarmas_fijo", [])}),
        "fuente": _rel(ruta) if ruta.is_relative_to(RAIZ) else str(ruta), "comando": COMANDO_FALSAS,
    }


JUEZ = RESULTS / "juez_gemini.json"
COMANDO_JUEZ = ("python scripts/juez_vivo.py --modelo gemini-lite --banda 0.2,0.5 --barrido --pausa 7 --concurrencia 1 "
                "--json results/juez_gemini.json")


def juez(ruta: Path | None = None) -> dict[str, Any]:
    """El juez LLM de los casos dudosos: cobertura y falsas alarmas sin y con juez en el punto de operación elegido.

    `punto_operacion` es la banda con más cobertura cuyas falsas alarmas medias no pasan de `max_falsas`; si ninguna
    cumple, va None y la página lo dice. `barrido` trae cada banda probada con los mismos veredictos.
    """
    ruta = ruta or JUEZ
    if not ruta.exists():
        return {"estado": "sin_archivo", "fuente": None, "comando": COMANDO_JUEZ}
    j = _leer(ruta)
    resumen = lambda f: {"banda": f["banda"], "fraccion_dudosa": f["fraccion_dudosa"],
                         "usd_por_1000_correos": f.get("usd_por_1000_correos"),
                         "delta_recall": f.get("delta_recall"), "delta_falsas": f.get("delta_falsas"),
                         **{m: f["con_juez"][m] for m in ("recall", "precision", "falsas_alarmas")}}
    punto = j.get("punto_operacion")
    return {
        "estado": "ok" if punto else "sin_punto",
        "modelo": j["modelo"], "precio": j.get("precio"), "motivo": j.get("motivo"), "corridas": j["corridas"], "max_falsas": j.get("max_falsas"),
        "sin_juez": j["sin_juez"], "punto_operacion": resumen(punto) if punto else None,
        "barrido": [resumen(f) for f in j.get("barrido", [])],
        "veredictos": j.get("textos_distintos", j["llamadas"]), "fallas": j["fallas"], "gasto_usd": j["gasto"]["gastado_usd"],
        "fuente": _rel(ruta) if ruta.is_relative_to(RAIZ) else str(ruta), "comando": COMANDO_JUEZ,
    }


SEMILLAS_DUELO = (0, 1, 2)
MODOS_DUELO = {"congelado": "--sin-entrenar", "aprende": ""}


def duelo(carpeta: Path | None = None) -> dict[str, Any]:
    """El duelo con y sin entrenar, por semilla: la evasión del hacker contra el clasificador en cada generación.

    `sin_capa2` suma, generación a generación, los correos mutados que el clasificador dejó pasar: los que habrían
    cobrado sin la capa 2. Es un conteo de intentos (la misma cepa vuelve en varias generaciones), no de estafas
    distintas. `exitosas_capa2` son los pagos que sí salieron con la capa 2.
    """
    carpeta = carpeta or RESULTS / "duelo"
    modos: dict[str, Any] = {}
    for modo, bandera in MODOS_DUELO.items():
        semillas = []
        for s in SEMILLAS_DUELO:
            ruta = carpeta / f"{modo}_s{s}.json"
            if not ruta.exists():
                continue
            gens = sorted(_leer(ruta), key=lambda e: e["generacion"])
            evasion = [g["evasion"] for g in gens]
            semillas.append({
                "semilla": s, "generaciones": len(gens), "candidatos": sum(g["candidatos"] for g in gens),
                "evasion": evasion, "inicio": evasion[0], "pico": max(evasion), "final": evasion[-1],
                "sin_capa2": sum(g["sin_capa2"] for g in gens),
                "capa2": [g["exitosas_capa2"] for g in gens],
                "exitosas_capa2": sum(g["exitosas_capa2"] for g in gens),
                # La guardia de deriva del clasificador: versiones descartadas hasta la última generación.
                "revertidas": gens[-1].get("revertidas"),
                "version_inicial": gens[0].get("version_modelo"), "version_final": gens[-1].get("version_modelo"),
                "fuente": _rel(ruta) if ruta.is_relative_to(RAIZ) else str(ruta),
                "comando": " ".join(filter(None, ["grifter duelo --generaciones", str(len(gens)), f"--semilla {s}", bandera,
                                                  f"--json results/duelo/{modo}_s{s}.json"])),
            })
        modos[modo] = {
            "semillas": semillas,
            "candidatos": sum(x["candidatos"] for x in semillas),
            "sin_capa2": sum(x["sin_capa2"] for x in semillas),
            "exitosas_capa2": sum(x["exitosas_capa2"] for x in semillas),
        }
    todas = [x for m in modos.values() for x in m["semillas"]]
    return {
        "estado": "ok" if todas else "sin_archivo",
        **modos,
        "generaciones": sum(x["generaciones"] for x in todas),
        "candidatos": sum(x["candidatos"] for x in todas),
        "exitosas_capa2": sum(x["exitosas_capa2"] for x in todas),
        "fuente": "results/duelo/{congelado,aprende}_s{0,1,2}.json",
        "comando": "grifter duelo --generaciones 20 --semilla N [--sin-entrenar] --json results/duelo/<modo>_sN.json",
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
    for clave, por_defensa in curvas.items():
        # Con varios atacantes la clave es «atacante → víctima» (scamshield/attacker/resultados.py): un panel por atacante.
        atacante, _, modelo = clave.partition(f" {SEP_ATACANTE} ") if f" {SEP_ATACANTE} " in clave else ("", "", clave)
        for d, v in por_defensa.items():
            if isinstance(v.get("rondas"), list):
                serie = _serie_resumen(modelo, d, v)
            else:
                n = v.get("n") or 0
                ic = [list(intervalo_wilson(e / n, n)) if n else [None, None] for e in v.get("exitos", [])]
                serie = {"modelo": modelo, "defensa": d, "ic": ic,
                         **{k: x for k, x in v.items() if not k.startswith("unidades_")}}
            if atacante:
                serie["atacante"] = atacante
                serie["rechazos"] = v.get("rechazos_atacante", 0)
            series.append(serie)
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
        "clasificador": clasificador(), "colados": colados(), "cobertura": cobertura(), "juez": juez(), "falsas_alarmas": falsas_alarmas(), "atacante": atacante(elegida=curva), "duelo": duelo(),
    })


def escribir(datos: dict[str, Any], salida: Path = DEMO, solo_json: bool = False) -> list[Path]:
    """resultados.json y su copia resultados.js (abrir la página como archivo no deja usar fetch)."""
    texto = json.dumps(datos, indent=1, ensure_ascii=False, allow_nan=False)
    json_, js = salida / "resultados.json", salida / "resultados.js"
    json_.write_text(texto + "\n", encoding="utf-8")
    if solo_json:
        return [json_]
    js.write_text(f"// Generado por scripts/resultados_demo.py. No editar a mano.\nwindow.RESULTADOS = {texto};\n",
                  encoding="utf-8")
    return [json_, js]


def _primera_frase(texto: str, largo: int = 160) -> str:
    frase = texto.split(". ")[0].rstrip(".")
    return frase if len(frase) <= largo else frase[: largo - 1].rstrip() + "…"


def tabla_cobertura(c: dict[str, Any]) -> str:
    """La cobertura en Markdown, para el README: `python scripts/resultados_demo.py --tabla-cobertura`."""
    t = c["totales"]
    lineas = [
        f"{t['familias']} tipos de ataque, {t['ataques_bench']} ataques en el bench, {t['intentos_duelo']} intentos "
        f"del atacante que aprende (Duelo) y {t['correos_clasificador']} correos para el clasificador.",
        "",
        "| Tipo de ataque | Ataques | Grifter completo: esperada → real | Capa 2 sola: esperada → real | Clasificador detecta |",
        "|---|---|---|---|---|",
    ]
    for r in c["familias"]:
        cl = r["clasificador"]
        det = f"{cl['detectados']}/{cl['correos']} ({cl['tasa']:.0%})" if cl else "—"
        nombre = r["familia"].replace("_", " ")
        if r["dueno_dicta"]:
            nombre += f" ({r['dueno_dicta']} dictadas por el dueño)"
        lineas.append(f"| {nombre} | {r['ataques']} | {r['completo']['esperada']} → {r['completo']['real']} | "
                      f"{r['capa2']['esperada']} → {r['capa2']['real']} | {det} |")
    lineas.append(f"| **Total** | **{t['ataques_bench']}** | **{t['ataques_bench']} → {t['frenadas_bench']}** | | |")
    lineas += ["", f"**Límites conocidos ({t['limites_conocidos']}):** ataques que todavía nos rompen, cada uno con una "
               "prueba `xfail(strict=True)`. Esperada: 0 %.", ""]
    lineas += [f"- {_primera_frase(l['razon'])} (`{l['prueba'].split('::')[1]}`)" for l in c["limites"]]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--atacante", type=Path, help="el _curvas.json del atacante que se muestra")
    p.add_argument("--tabla-cobertura", action="store_true", help="solo imprime la tabla de cobertura en Markdown")
    p.add_argument("--solo-json", action="store_true", help="escribe solo resultados.json, sin tocar resultados.js")
    a = p.parse_args(argv)
    if a.tabla_cobertura:
        print(tabla_cobertura(cobertura()))
        return 0
    datos = armar(a.atacante)
    for ruta in escribir(datos, solo_json=a.solo_json):
        print(f"escrito {_rel(ruta)}")
    a = datos["atacante"]
    print(f"atacante: {a['estado']}" + (f" ({a['fuente']})" if a["fuente"] else ""))
    print("sin archivo de origen: pipelock (fuente: docs/pitch.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
