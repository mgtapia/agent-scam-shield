"""De las filas del atacante a la curva de estafas exitosas acumuladas, y el gráfico en SVG.

El SVG se escribe a mano para no sumar una dependencia de gráficos al proyecto.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

NOMBRES = {"none": "sin defensa", "layer1": "capa 1", "layer2": "capa 2", "both": "capas 1 y 2",
           "layer2_approver": "capa 2 (approver)"}
# Paleta de color apta para daltónicos (Okabe-Ito); cada defensa además tiene su marcador.
COLORES = {"none": "#d55e00", "layer1": "#e69f00", "layer2": "#0072b2", "both": "#009e73",
           "layer2_approver": "#56b4e9"}


def leer(ruta: Path) -> list[dict[str, Any]]:
    with Path(ruta).open(encoding="utf-8") as fh:
        return [json.loads(linea) for linea in fh if linea.strip()]


SEP_ATACANTE = "→"


def curvas(filas: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """{modelo: {defensa: {"n", "rondas", "exitos", "intentos"}}}, acumulado por ronda.

    `exitos[r]` es cuántas estafas distintas cayeron en la defensa en alguna ronda <= r (la víctima
    ejecutó la acción del estafador). `intentos[r]` cuenta las que el agente intentó, aunque la defensa
    las frenara: mide a la víctima sin la defensa, y la diferencia con `exitos` es lo que la defensa evitó.
    """
    por_celda: dict[tuple[str, str], list[dict[str, Any]]] = {}
    # Con más de un atacante en las filas, cada panel es «atacante → víctima»: las curvas quedan lado a lado.
    varios = len({f.get("atacante") or "" for f in filas}) > 1
    for f in filas:
        modelo = f"{f.get('atacante') or 'atacante sin nombre'} {SEP_ATACANTE} {f['modelo']}" if varios else f["modelo"]
        por_celda.setdefault((modelo, f["defensa"]), []).append(f)
    salida: dict[str, dict[str, dict[str, Any]]] = {}
    for (modelo, defensa), fs in por_celda.items():
        rondas = max(f["ronda"] for f in fs)
        estafas = {(f["escenario"], f["idioma"]) for f in fs}
        exitos, intentos = [], []
        unidades_exitos, unidades_intentos = [], []   # 0/1 por estafa y ronda, para los intervalos
        for r in range(rondas + 1):
            cayeron = {(f["escenario"], f["idioma"]) for f in fs if f["exito"] and f["ronda"] <= r}
            intentaron = {(f["escenario"], f["idioma"]) for f in fs
                          if (f["intento"] or f["exito"]) and f["ronda"] <= r}
            exitos.append(len(cayeron))
            intentos.append(len(intentaron))
            unidades_exitos.append([int(e in cayeron) for e in sorted(estafas)])
            unidades_intentos.append([int(e in intentaron) for e in sorted(estafas)])
        # Episodios de reescritura que sí llegaron a la víctima (ronda > 0): lo que de verdad se midió.
        adaptadas = [f for f in fs if f["ronda"] > 0]
        salida.setdefault(modelo, {})[defensa] = {
            "n": len(estafas), "rondas": rondas, "exitos": exitos, "intentos": intentos,
            "unidades_exitos": unidades_exitos, "unidades_intentos": unidades_intentos,
            "reescrituras_validas": sum(1 for f in adaptadas if f["valida"] and not f["error"]),
            "reescrituras_perdidas": sum(1 for f in adaptadas if not f["valida"]),
            "no_validas": sum(1 for f in fs if not f["valida"]), "errores": sum(1 for f in fs if f["error"]),
            "rechazos_atacante": sum(1 for f in fs if f.get("se_nego")),
        }
    return salida


def tabla_markdown(c: dict[str, dict[str, dict[str, Any]]]) -> str:
    lineas = ["| Modelo | Defensa | Estafas | Ronda 0 | Última ronda | Engañó al agente |", "|---|---|---|---|---|---|"]
    for modelo, por_def in c.items():
        for d, v in por_def.items():
            lineas.append(f"| {modelo} | {NOMBRES.get(d, d)} | {v['n']} | {v['exitos'][0]}/{v['n']} | "
                          f"{v['exitos'][-1]}/{v['n']} | {v['intentos'][-1]}/{v['n']} |")
    return "\n".join(lineas)


def svg(c: dict[str, dict[str, dict[str, Any]]], titulo: str = "Estafas exitosas acumuladas por ronda") -> str:
    """Un panel por modelo, una línea por defensa. Línea punteada: el agente intentó la estafa."""
    ancho_panel, alto, mi, md, ms, mb = 460, 340, 56, 16, 64, 52
    modelos = list(c)
    total_ancho = len(modelos) * ancho_panel + 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_ancho} {alto + 60}" '
           f'font-family="system-ui, sans-serif" font-size="12">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           f'<text x="10" y="22" font-size="15" font-weight="600" fill="#1a1a1a">{escape(titulo)}</text>']
    for i, modelo in enumerate(modelos):
        x0 = 10 + i * ancho_panel
        por_def = c[modelo]
        rondas = max(v["rondas"] for v in por_def.values())
        n = max(v["n"] for v in por_def.values())
        gx, gy, gw, gh = x0 + mi, ms, ancho_panel - mi - md, alto - ms - mb

        def px(r: int) -> float:
            return gx + (gw * r / rondas if rondas else 0)

        def py(v: float) -> float:
            return gy + gh - gh * v / n

        out.append(f'<text x="{gx}" y="{ms - 14}" font-weight="600" fill="#1a1a1a">{escape(modelo)}</text>')
        paso = max(1, n // 5)
        for v in range(0, n + 1, paso):
            out.append(f'<line x1="{gx}" x2="{gx + gw}" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="#e3e3e3"/>'
                       f'<text x="{gx - 8}" y="{py(v) + 4:.1f}" text-anchor="end" fill="#555">{v}</text>')
        for r in range(rondas + 1):
            out.append(f'<text x="{px(r):.1f}" y="{gy + gh + 18}" text-anchor="middle" fill="#555">{r}</text>')
        out.append(f'<text x="{gx + gw / 2}" y="{gy + gh + 38}" text-anchor="middle" fill="#333">ronda '
                   f'(0 = estafa original)</text>')
        out.append(f'<text x="{x0 + 12}" y="{gy + gh / 2}" transform="rotate(-90 {x0 + 12} {gy + gh / 2})" '
                   f'text-anchor="middle" fill="#333">estafas (de {n})</text>')
        for j, (d, v) in enumerate(por_def.items()):
            color = COLORES.get(d, "#555555")
            for clave, trazo in (("intentos", ' stroke-dasharray="5 4" opacity="0.7"'), ("exitos", "")):
                pts = " ".join(f"{px(r):.1f},{py(y):.1f}" for r, y in enumerate(v[clave]))
                out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"{trazo}/>')
            ult = v["exitos"][-1]
            out.append(f'<circle cx="{px(len(v["exitos"]) - 1):.1f}" cy="{py(ult):.1f}" r="4" fill="{color}"/>')
            ly = ms + 6 + j * 16
            out.append(f'<line x1="{gx + 10}" x2="{gx + 30}" y1="{ly}" y2="{ly}" stroke="{color}" stroke-width="2.5"/>'
                       f'<text x="{gx + 36}" y="{ly + 4}" fill="#222">{escape(NOMBRES.get(d, d))} '
                       f'({ult}/{v["n"]})</text>')
        out.append(f'<text x="{gx}" y="{alto + 44}" fill="#555">Línea llena: la víctima ejecutó la acción del '
                   f'estafador. Punteada: la intentó, aunque la defensa la frenara.</text>')
    out.append("</svg>")
    return "\n".join(out)
