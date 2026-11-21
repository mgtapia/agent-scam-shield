"""Juez LLM para los casos dudosos del clasificador: cobertura y falsas alarmas con y sin juez, y su costo (#131).

Mide sobre el mismo conjunto apartado que la validación cruzada por familia (scripts/validacion_cruzada_vivo.py):
3 pliegues × las semillas, con el clasificador entrenado sin ver lo apartado. En cada corrida, los correos
apartados cuya probabilidad cae en la banda dudosa (por defecto 0,2 a 0,5) van al juez; el juez solo puede subir
la sospecha. Si se cae, se niega o no se le entiende, el caso queda marcado (no hay «seguro» por defecto), y se
cuenta como falla.

El mismo texto se juzga una sola vez: el apartado es igual entre semillas, así que el gasto real es el de los
textos distintos. El costo por 1.000 correos es la fracción de correos que va al juez por el costo medio de una
llamada.

Sin --modelo corre con mockllm (sin red ni llaves: su respuesta no se entiende, así que todo dudoso queda
marcado; sirve para probar el circuito, no como medición). Con un modelo real, las llaves se leen de .env sin
imprimirlas y la corrida se corta al llegar a --tope-usd.

Uso:
    python scripts/juez_vivo.py --dry-run                                # costo estimado con Haiku, Sonnet, Fable y Gemini
    python scripts/juez_vivo.py --modelo haiku --dry-run
    python scripts/juez_vivo.py --modelo haiku --tope-usd 2 --json results/juez_haiku.json
    python scripts/juez_vivo.py --modelo anthropic/claude-sonnet-5-5 --banda 0,0.5
    python scripts/juez_vivo.py --modelo gemini --banda 0,0.5 --barrido --pausa 7 --concurrencia 1 \
        --cache results/juez_gemini_cache.json --json results/juez_gemini.json

Con --barrido, después de juzgar la banda pedida se recalculan bandas más angostas (desde 0; 0,05; 0,1... hasta el
mismo tope) con los veredictos ya obtenidos, sin llamar de nuevo, y se elige el punto de operación: la banda con más
cobertura cuyas falsas alarmas medias no pasan de --max-falsas (por defecto 8 %). --cache guarda en disco los
veredictos (por huella del texto, sin los correos), así una corrida cortada por la cuota sigue donde quedó.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scamshield.attacker.costo import Gasto, PresupuestoAgotado, config_para, piensa_siempre, precio_de  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402

from scamshield.vivo.juez import (BANDA, MAX_TOKENS, SISTEMA, CuotaAgotada, Juez, Veredicto, combinar,  # noqa: E402
                                  mensaje, metricas)
from scripts.validacion_cruzada_vivo import colados_por, entrenar  # noqa: E402

MODELOS = {
    "haiku": "anthropic/claude-haiku-5-5",
    "sonnet": "anthropic/claude-sonnet-5-5",
    "fable": "anthropic/claude-fable-5-2",
    "gemini": "google/gemini-3.5-flash",
    "gemini-lite": "google/gemini-3.5-flash-lite",
}
TOPE_USD = 2.0
CHARS_POR_TOKEN = 3.5            # para estimar la entrada sin llamar a nada
SALIDA_TIPICA, SALIDA_PENSANDO = 60, 400   # tokens de salida típicos: una línea, o una línea más el pensamiento
DESDE_BARRIDO = (0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4)
MAX_FALSAS = 0.08
GRATIS = "gratis (plan gratuito)"


def precio_texto(modelo: str) -> str:
    """El precio que se informa. Sin precio verificado no se inventa: Gemini va en el plan gratuito."""
    pe, ps = precio_de(modelo)
    if (pe, ps) != (0.0, 0.0):
        return f"US${pe:g} / US${ps:g} por millón de tokens (entrada / salida)"
    return GRATIS if modelo.startswith("google/") else "sin precio conocido"


def resolver(modelo: str | None) -> str:
    return MODELOS.get((modelo or "").lower(), modelo or "mockllm/model")


def casos(pliegue: int, semilla: int, episodios: int, agrupar: str = "familia") -> list[dict[str, Any]]:
    """Los correos apartados de una corrida, con la probabilidad que les da el clasificador ya entrenado."""
    motor, _ = entrenar(pliegue, semilla, episodios, agrupar)
    cl = motor.clasificador
    return [{"texto": c.texto, "canal": m["canal"], "y": y, "p": cl.probabilidad(r), "familia": m["familia"],
             "escenario": m["escenario"]}
            for c, (r, y), m in zip(motor.evaluacion, cl.apartado, cl.meta)]


def corridas(semillas: list[int], episodios: int, agrupar: str = "familia") -> list[dict[str, Any]]:
    return [{"pliegue": p, "semilla": s, "casos": casos(p, s, episodios, agrupar)} for p in (0, 1, 2) for s in semillas]


def _colados(filas: list[dict[str, Any]], campo: str) -> dict[str, Any]:
    """Las estafas que quedaron sin marcar, en el formato de validacion_cruzada_vivo.colados_por."""
    apartadas: dict[tuple[str, str, str], int] = defaultdict(int)
    colados: dict[tuple[str, str, str], int] = defaultdict(int)
    for f in filas:
        if f["y"]:
            k = (f["escenario"], f["familia"], f["canal"])
            apartadas[k] += 1
            colados[k] += 0 if f[campo] else 1
    return {"apartadas": [{"escenario": e, "familia": fa, "canal": c, "n": n} for (e, fa, c), n in apartadas.items()],
            "colados": [{"escenario": e, "familia": fa, "canal": c, "n": n} for (e, fa, c), n in colados.items() if n]}


async def medir(juez: Juez, runs: list[dict[str, Any]], concurrencia: int = 4) -> dict[str, Any]:
    """Juzga los dudosos de cada corrida y compara clasificador solo contra clasificador + juez."""
    sem = asyncio.Semaphore(concurrencia)

    async def uno(c: dict[str, Any]):
        async with sem:
            return await juez.juzgar(c["texto"], c["canal"])

    filas_run, cortado = [], None
    for run in runs:
        dudosos = [c for c in run["casos"] if juez.dudoso(c["p"])]
        try:
            veredictos = await asyncio.gather(*(uno(c) for c in dudosos))
        except (PresupuestoAgotado, CuotaAgotada) as e:
            cortado = str(e)
            break
        por_id = {id(c): v for c, v in zip(dudosos, veredictos)}
        filas = []
        for c in run["casos"]:
            v = por_id.get(id(c))
            filas.append({**{k: c[k] for k in ("y", "p", "familia", "escenario", "canal")},
                          "sin": c["p"] > 0.5, "con": combinar(c["p"], 0.5, v), "dudoso": v is not None,
                          "falla": bool(v is not None and v.estafa is None)})
        filas_run.append({"pliegue": run["pliegue"], "semilla": run["semilla"], "correos": len(filas),
                          "dudosos": sum(f["dudoso"] for f in filas), "fallas": sum(f["falla"] for f in filas),
                          "sin_juez": metricas(filas, "sin"), "con_juez": metricas(filas, "con"),
                          "colados_sin": _colados(filas, "sin"), "colados_con": _colados(filas, "con")})
    return {"filas": filas_run, "cortado": cortado}


def resumir(medido: dict[str, Any], juez: Juez) -> dict[str, Any]:
    filas = medido["filas"]
    rango = lambda clave, m: {"media": round(st.mean(f[clave][m] for f in filas), 3),
                              "min": min(f[clave][m] for f in filas), "max": max(f[clave][m] for f in filas)}
    correos = sum(f["correos"] for f in filas)
    dudosos = sum(f["dudosos"] for f in filas)
    g = juez.gasto
    por_llamada = g.gastado_usd / g.llamadas if g.llamadas else 0.0
    return {
        "modelo": juez.nombre, "banda": list(juez.banda), "corridas": len(filas), "cortado": medido["cortado"],
        "sin_juez": {m: rango("sin_juez", m) for m in ("recall", "precision", "falsas_alarmas")} if filas else None,
        "con_juez": {m: rango("con_juez", m) for m in ("recall", "precision", "falsas_alarmas")} if filas else None,
        "correos": correos, "dudosos": dudosos, "fraccion_dudosa": round(dudosos / correos, 4) if correos else 0.0,
        "llamadas": juez.llamadas, "fallas": juez.fallas, "textos_distintos": len(juez.cache),
        "gasto": g.resumen(), "usd_por_llamada": round(por_llamada, 6),
        "usd_por_1000_correos": round(1000 * (dudosos / correos if correos else 0.0) * por_llamada, 4),
        "colados_por_familia_sin": colados_por([f["colados_sin"] for f in filas], "familia"),
        "colados_por_familia_con": colados_por([f["colados_con"] for f in filas], "familia"),
        "filas": [{k: v for k, v in f.items() if not k.startswith("colados_")} for f in filas],
    }


async def _sin_llamar(*_a, **_k) -> str:
    raise RuntimeError("el barrido no llama al modelo: el texto no estaba juzgado")


def barrer(juez: Juez, runs: list[dict[str, Any]], desde: tuple[float, ...] = DESDE_BARRIDO) -> list[dict[str, Any]]:
    """Las bandas más angostas que la juzgada, con los mismos veredictos (de la caché del juez, sin llamar)."""
    g = juez.gasto
    por_llamada = g.gastado_usd / g.llamadas if g.llamadas else 0.0
    filas = []
    for lo in sorted({juez.banda[0], *(d for d in desde if juez.banda[0] <= d <= juez.banda[1])}):
        j = Juez(juez._modelo, banda=(lo, juez.banda[1]), cache=juez.cache, pedir=_sin_llamar)
        r = resumir(asyncio.run(medir(j, runs, 8)), j)
        delta = lambda m: round(r["con_juez"][m]["media"] - r["sin_juez"][m]["media"], 3)
        filas.append({"banda": [lo, juez.banda[1]], "sin_juez": r["sin_juez"], "con_juez": r["con_juez"],
                      "delta_recall": delta("recall"), "delta_falsas": delta("falsas_alarmas"),
                      "fraccion_dudosa": r["fraccion_dudosa"], "fallas": r["fallas"],
                      "usd_por_1000_correos": round(1000 * r["fraccion_dudosa"] * por_llamada, 4)})
    return filas


def elegir(barrido: list[dict[str, Any]], max_falsas: float = MAX_FALSAS) -> dict[str, Any] | None:
    """El punto de operación: más cobertura con falsas alarmas medias hasta `max_falsas`; a igual cobertura, menos
    correos al juez. None si ninguna banda cumple."""
    validas = [f for f in barrido if f["con_juez"] and f["con_juez"]["falsas_alarmas"]["media"] <= max_falsas]
    if not validas:
        return None
    return max(validas, key=lambda f: (f["con_juez"]["recall"]["media"], -f["fraccion_dudosa"]))


def cargar_cache(ruta: Path | None, modelo: str) -> dict[str, Veredicto]:
    if not ruta or not ruta.exists():
        return {}
    d = json.loads(ruta.read_text(encoding="utf-8"))
    if d.get("modelo") != modelo:
        return {}
    return {h: Veredicto(v["estafa"], v.get("porque", "")) for h, v in d.get("veredictos", {}).items()}


def guardar_cache(ruta: Path | None, juez: Juez) -> None:
    """Solo los veredictos: una falla no se guarda, así la próxima corrida la vuelve a intentar."""
    if not ruta:
        return
    veredictos = {h: {"estafa": v.estafa, "porque": v.porque} for h, v in sorted(juez.cache.items()) if v.estafa is not None}
    ruta.write_text(json.dumps({"modelo": juez.nombre, "veredictos": veredictos}, indent=1, ensure_ascii=False),
                    encoding="utf-8")


def estimar(runs: list[dict[str, Any]], modelo: str, banda: tuple[float, float]) -> dict[str, Any]:
    """Costo estimado sin llamar a nada: textos distintos en la banda, tokens por llamada y precio de lista."""
    juez_banda = lambda p: banda[0] <= p <= min(banda[1], 0.5)
    textos = {mensaje(c["texto"], c["canal"]) for r in runs for c in r["casos"] if juez_banda(c["p"])}
    entrada = sum(int((len(SISTEMA) + len(t)) / CHARS_POR_TOKEN) for t in textos)
    pe, ps = precio_de(modelo)
    tope = config_para(modelo, 0.0, MAX_TOKENS, False).max_tokens or MAX_TOKENS
    salida = SALIDA_PENSANDO if piensa_siempre(modelo) else SALIDA_TIPICA
    correos = sum(len(r["casos"]) for r in runs)
    dudosos = sum(1 for r in runs for c in r["casos"] if juez_banda(c["p"]))
    tipico = (entrada * pe + len(textos) * salida * ps) / 1e6
    return {"modelo": modelo, "llamadas": len(textos), "tokens_entrada": entrada,
            "usd_tipico": round(tipico, 4), "usd_peor_caso": round((entrada * pe + len(textos) * tope * ps) / 1e6, 4),
            "usd_por_1000_correos": round(1000 * dudosos / correos * (tipico / len(textos)), 4) if textos and correos else 0.0,
            "precio_conocido": (pe, ps) != (0.0, 0.0)}


def _banda(texto: str) -> tuple[float, float]:
    a, b = (float(x) for x in texto.split(","))
    return a, b


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelo", help=f"proveedor/modelo o un atajo: {', '.join(MODELOS)} (por defecto, mockllm)")
    p.add_argument("--banda", type=_banda, default=BANDA, help="probabilidades dudosas que van al juez, «a,b»")
    p.add_argument("--semillas", default="1,2,3")
    p.add_argument("--episodios", type=int, default=300)
    p.add_argument("--tope-usd", type=float, default=TOPE_USD, help="se corta al llegar a este gasto")
    p.add_argument("--concurrencia", type=int, default=4)
    p.add_argument("--dry-run", action="store_true", help="solo el costo estimado, sin llamar a ningún modelo")
    p.add_argument("--json", type=Path, help="guarda el resumen en este archivo")
    p.add_argument("--pausa", type=float, default=0.0, help="segundos después de cada llamada (cuota por minuto)")
    p.add_argument("--cache", type=Path, help="veredictos en disco: sigue donde quedó una corrida cortada")
    p.add_argument("--barrido", action="store_true", help="recalcula bandas más angostas y elige el punto de operación")
    p.add_argument("--max-falsas", type=float, default=MAX_FALSAS, help="falsas alarmas máximas del punto de operación")
    a = p.parse_args(argv)
    semillas = [int(s) for s in a.semillas.split(",")]
    print(f"Entrenando el clasificador: 3 pliegues × {len(semillas)} semillas, {a.episodios} episodios, por familia…")
    runs = corridas(semillas, a.episodios)
    if a.dry_run:
        modelos = [resolver(a.modelo)] if a.modelo else list(MODELOS.values())
        print(f"\nCosto estimado del juez, banda {a.banda[0]}-{a.banda[1]} (sin llamar a nada):")
        print("| Modelo | Llamadas | Tokens de entrada | Típico (US$) | Peor caso (US$) | Por 1.000 correos (US$) |\n|---|---|---|---|---|---|")
        for m in modelos:
            e = estimar(runs, m, a.banda)
            nota = "" if e["precio_conocido"] else f" ({precio_texto(m)}: cuenta 0)"
            print(f"| {m}{nota} | {e['llamadas']} | {e['tokens_entrada']} | {e['usd_tipico']} | {e['usd_peor_caso']} | "
                  f"{e['usd_por_1000_correos']} |")
        print(f"\nTope por corrida: US${a.tope_usd:.2f}.")
        return 0
    modelo = resolver(a.modelo)
    if not modelo.startswith("mockllm/"):
        from scripts.atacante_adaptativo import _cargar_env  # deja las llaves de .env en el entorno, sin imprimirlas
        _cargar_env(None)
    pe, ps = precio_de(modelo)
    juez = Juez(modelo, banda=a.banda, gasto=Gasto(tope_usd=a.tope_usd, precio_entrada=pe, precio_salida=ps),
                pausa=a.pausa, cache=cargar_cache(a.cache, str(get_model(modelo))))
    previos = len(juez.cache)
    def al_juzgar() -> None:   # cada veredicto queda en disco: un corte no lo pierde
        guardar_cache(a.cache, juez)
        print(f"  {juez.llamadas} llamadas, {juez.fallas} fallas", flush=True)
    juez.al_juzgar = al_juzgar
    try:
        r = resumir(asyncio.run(medir(juez, runs, a.concurrencia)), juez)
    finally:
        guardar_cache(a.cache, juez)
    r["precio"] = precio_texto(modelo)
    r["veredictos_previos"] = previos
    r["episodios"], r["semillas"] = a.episodios, semillas
    if a.barrido and r["sin_juez"] and not r["cortado"]:
        r["barrido"] = barrer(juez, runs)
        r["max_falsas"] = a.max_falsas
        r["punto_operacion"] = elegir(r["barrido"], a.max_falsas)
        base = r["sin_juez"]["falsas_alarmas"]["media"]
        if r["punto_operacion"] is None:
            r["motivo"] = (f"El clasificador solo ya tiene {base:.0%} de falsas alarmas medias, sobre el máximo de "
                           f"{a.max_falsas:.0%}, y el juez solo puede subir la sospecha." if base > a.max_falsas else
                           f"Con el juez, las falsas alarmas pasan del máximo de {a.max_falsas:.0%} en todas las bandas.")
    if r["sin_juez"]:
        print(f"\nJuez {r['modelo']}, banda {r['banda'][0]}-{r['banda'][1]}, {r['corridas']} corridas"
              + (f" (cortado: {r['cortado']})" if r["cortado"] else "") + ":")
        print("| | Cobertura | Precisión | Falsas alarmas |\n|---|---|---|---|")
        for k, nombre in (("sin_juez", "Clasificador solo"), ("con_juez", "Clasificador + juez")):
            print(f"| {nombre} | " + " | ".join(f"{r[k][m]['media']:.2f} [{r[k][m]['min']:.2f}-{r[k][m]['max']:.2f}]"
                                              for m in ("recall", "precision", "falsas_alarmas")) + " |")
    print(f"\nDudosos: {r['dudosos']} de {r['correos']} correos ({100 * r['fraccion_dudosa']:.1f} %); "
          f"{r['llamadas']} llamadas, {r['fallas']} fallas; gasto US${r['gasto']['gastado_usd']:.4f}; "
          f"US${r['usd_por_1000_correos']:.4f} por 1.000 correos.")
    if r.get("barrido"):
        print(f"\nBarrido (los mismos veredictos, sin llamar de nuevo); punto de operación con falsas alarmas <= {a.max_falsas:.0%}:")
        print("| Banda | Al juez | Cobertura | Precisión | Falsas alarmas | Δ cobertura | Δ falsas alarmas |\n|---|---|---|---|---|---|---|")
        for f in r["barrido"]:
            marca = " <-" if f is r["punto_operacion"] else ""
            c = f["con_juez"]
            print(f"| {f['banda'][0]:g}-{f['banda'][1]:g}{marca} | {100 * f['fraccion_dudosa']:.1f} % | "
                  + " | ".join(f"{c[m]['media']:.2f} [{c[m]['min']:.2f}-{c[m]['max']:.2f}]"
                               for m in ("recall", "precision", "falsas_alarmas"))
                  + f" | {f['delta_recall']:+.2f} | {f['delta_falsas']:+.2f} |")
        if r["punto_operacion"] is None:
            print(r["motivo"])
    print(f"Precio: {r['precio']}.")
    if r["llamadas"] and r["fallas"] == r["llamadas"]:
        print("Aviso: el juez no dio ningún veredicto (mockllm, o sin llave o sin saldo). Todo dudoso quedó marcado: "
              "la fila «con juez» es el techo de la banda, no una medición del juez.")
    if a.json:
        a.json.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
