"""Una sola fuente de cifras (docs/cifras.md): lo que dicen el README, el pitch y la demo calza con demo/resultados.json.

Si agregas escenarios o regeneras `results/`, corre `python scripts/resultados_demo.py` y después
`python scripts/cifras_finales.py`; estas pruebas dicen qué número quedó desfasado.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scamshield.scenarios import cargar
from scripts import cifras_finales as cf

RAIZ = Path(__file__).resolve().parent.parent
R = json.loads((RAIZ / "demo" / "resultados.json").read_text(encoding="utf-8"))
README = (RAIZ / "README.md").read_text(encoding="utf-8")
PITCH = (RAIZ / "docs" / "pitch.md").read_text(encoding="utf-8")

ESTAFAS = R["bench"]["escenarios"]["estafas"]
CONTROLES = R["bench"]["escenarios"]["controles"]
POR = {c["clave"]: c for c in R["bench"]["configuraciones"]}
TOT = R["cobertura"]["totales"]


def _entero(texto: str) -> int:
    return int(texto.replace(".", "").replace(" ", ""))


def _unico(patron: str, texto: str) -> list[str]:
    return re.findall(patron, texto)


# --- resultados.json no está desfasado respecto del corpus ------------------------------------------------------------

def test_resultados_json_cuenta_las_mismas_estafas_y_controles_que_el_corpus():
    corpus = cargar()
    assert ESTAFAS == sum(e["tipo"] == "estafa" for e in corpus), (
        "demo/resultados.json está desfasado: corre `grifter bench --json results/bench.json` y `python scripts/resultados_demo.py`")
    assert CONTROLES == sum(e["tipo"] == "control" for e in corpus)


def test_la_cobertura_y_el_bench_hablan_del_mismo_total():
    assert TOT["ataques_bench"] == ESTAFAS and R["colados"]["estafas"] == ESTAFAS
    assert POR["none"]["estafas_exitosas"]["escenarios"] == ESTAFAS
    assert TOT["frenadas_bench"] == ESTAFAS - round(POR["layer23"]["estafas_exitosas"]["tasa"] * ESTAFAS)
    assert TOT["intentos_duelo"] == R["duelo"]["candidatos"] and TOT["cruces_capa2_duelo"] == R["duelo"]["exitosas_capa2"]


# --- docs/cifras.md ---------------------------------------------------------------------------------------------------

def test_cifras_md_es_lo_que_saldria_hoy():
    actual = (RAIZ / "docs" / "cifras.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert actual == cf.armar(R), "docs/cifras.md está desfasado: corre `python scripts/cifras_finales.py`"


def test_cada_cifra_trae_su_comando_su_frase_y_su_fuente():
    ok, sin_archivo = cf.cifras(R)
    assert len(ok) >= 15
    ids = [c.id for c in ok + sin_archivo]
    assert len(ids) == len(set(ids))
    for c in ok:
        assert c.comando and c.frase.endswith((".", ")")) and c.fuente and c.n and c.cifra, c.id
    for c in sin_archivo:
        assert "sin archivo de origen" in c.fuente


def test_las_cifras_del_pitch_estan_en_cifras_md():
    cifras = (RAIZ / "docs" / "cifras.md").read_text(encoding="utf-8")
    for frase in (f"{ESTAFAS} estafas", cf.pct(POR["layer23"]["estafas_exitosas"]), cf.pct(POR["none"]["estafas_exitosas"]),
                  f"{R['pipelock']['frenadas']} de {R['pipelock']['estafas']}", cf.miles(TOT["intentos_duelo"])):
        assert frase in cifras, frase


# --- El README --------------------------------------------------------------------------------------------------------

def test_el_readme_cita_el_total_de_estafas_del_bench():
    assert {_entero(n) for n in _unico(r"(\d[\d.]*) estafas en español e inglés", README)} == {ESTAFAS}
    assert {_entero(n) for n in _unico(r"(\d[\d.]*) ataques en el bench", README)} == {ESTAFAS}
    assert {_entero(n) for n in _unico(r"(\d[\d.]*) estafas y \d+ controles", README)} == {ESTAFAS}
    fin = README.rindex("<!-- bench:fin -->")
    bloque = README[README.rindex("<!-- bench:inicio -->", 0, fin):fin]
    bloque = bloque[bloque.index("#### Por configuración"):]
    bloque = bloque[:bloque.index("####", 10)]   # solo la tabla por configuración; la de idiomas tiene sus propios n
    assert {_entero(n) for n in _unico(r"\(n=(\d+)\)", bloque)} <= {ESTAFAS, CONTROLES, POR["layer23"]["utilidad"]["escenarios"]}


def test_el_readme_cita_los_totales_de_cobertura_y_del_duelo():
    assert {int(n) for n in _unico(r"(\d+) tipos de ataque", README)} == {TOT["familias"]}
    assert {_entero(n) for n in _unico(r"(\d[\d.]*) intentos del atacante que aprende", README)} == {TOT["intentos_duelo"]}
    assert {_entero(n) for n in _unico(r"(\d[\d.]*) correos para el clasificador", README)} == {TOT["correos_clasificador"]}
    total = re.search(r"\*\*Total\*\* \| \*\*(\d+)\*\* \| \*\*(\d+) → (\d+)\*\*", README)
    assert total and tuple(map(int, total.groups())) == (ESTAFAS, TOT["frenadas_bench"], TOT["frenadas_bench"])


def test_el_readme_cita_el_cero_por_ciento_y_las_otras_tasas_del_bench():
    fila = next(l for l in README.splitlines() if l.startswith("| **Agente que hace todo lo que lee**"))
    assert f"caen **{cf.pct(POR['none']['estafas_exitosas'])}**" in fila
    assert f"capa 2, **{cf.pct(POR['layer2']['estafas_exitosas'])}**" in fila
    assert f"capas 2 y 3, **{cf.pct(POR['layer23']['estafas_exitosas'])}**" in fila
    assert f"con {cf._p(POR['layer23']['utilidad']['tasa'])} % de utilidad" in fila


def test_el_readme_cita_pipelock_sonnet_haiku_y_el_clasificador():
    p, s, h, c = R["pipelock"], R["sonnet"], R["haiku"], R["clasificador"]
    assert f"(Pipelock, {p['estafas']} estafas)" in README and f"Frena **{p['frenadas']} de {p['estafas']}**" in README
    assert f"Pagó **{s['pagos']} de {s['repeticiones']}**" in README
    assert f"**{cf.pct(h['estafas_exitosas']).replace(' %', ' % de estafas', 1)}**" in README
    assert f"{cf._p(h['utilidad']['tasa'])} % de utilidad [{cf._p(h['utilidad']['bajo'])}-{cf._p(h['utilidad']['alto'])}]" in README
    assert f"Recall **{cf.coma(c['recall']['media'])} [{cf.coma(c['recall']['min'])}-{cf.coma(c['recall']['max'])}]**" in README


# --- El pitch ---------------------------------------------------------------------------------------------------------

def test_el_pitch_cita_pipelock_y_sonnet_como_los_mide_resultados_json():
    p, s = R["pipelock"], R["sonnet"]
    assert {(int(a), int(b)) for a, b in _unico(r"Pipelock frenó (\d+) de (\d+)", PITCH)} == {(p["frenadas"], p["estafas"])}
    assert {(int(a), int(b)) for a, b in _unico(r"[Pp]agó 6? ?(\d+) de (\d+)", PITCH.replace("**", ""))} == {(s["pagos"], s["repeticiones"])}
    assert {(int(a), int(b)) for a, b in _unico(r"Pipelock hace lo mismo y lo medimos: (\d+) de (\d+)", PITCH)} == {(p["frenadas"], p["estafas"])}


def test_el_pitch_no_cita_un_total_de_estafas_viejo():
    """Cualquier «N estafas» o «las N escenarios» de tres cifras o más del pitch es el total del bench."""
    grandes = {v for v in (_entero(n) for n in _unico(r"(?<![\d.])(\d[\d.]*\d) (?:estafas|ataques)\b", PITCH)) if v >= 100}
    assert grandes <= {ESTAFAS, TOT["intentos_duelo"], 4371, 69297, 76842}, grandes   # lo demás son cifras de APort Vault
    assert {int(n) for n in _unico(r"la garantía fuerte es la de (?:las|los) (\d+) (?:estafas|escenarios)", PITCH)} <= {ESTAFAS}


def test_el_pitch_cita_el_haiku_de_resultados_json():
    h = R["haiku"]
    he, hu = h["estafas_exitosas"], h["utilidad"]
    assert cf.pct(he) in PITCH
    assert f"{cf._p(hu['tasa'])} % [{cf._p(hu['bajo'])}-{cf._p(hu['alto'])}]" in PITCH


# --- La demo ----------------------------------------------------------------------------------------------------------

def test_el_acto_3_de_la_demo_lee_sus_cifras_de_resultados_json_y_no_las_escribe():
    js = (RAIZ / "demo" / "demo.js").read_text(encoding="utf-8")
    assert "R?.cobertura?.totales" in js and "ataques_bench" in js and "R?.duelo?.candidatos" in js
    acto = js[js.index('id="md-n1"') - 400:js.index('class="md-acto md-cierre"')]
    assert not re.search(r"\b(?:148|142|3600|3\.600|5280|5\.280)\b", acto), "el acto 3 no lleva cifras escritas a mano"
    resultados_js = (RAIZ / "demo" / "resultados.js").read_text(encoding="utf-8")
    assert json.loads(resultados_js[resultados_js.index("{"):resultados_js.rindex("}") + 1])["cobertura"]["totales"] == TOT, (
        "demo/resultados.js no es la copia de resultados.json")


# --- La corrida de referencia del duelo (README) ------------------------------------------------------------------------

def test_el_readme_cita_la_corrida_de_referencia_del_duelo_como_la_dicen_los_archivos():
    eventos = json.loads((RAIZ / "results" / "duelo" / "aprende_s0.json").read_text(encoding="utf-8"))
    parrafo = next(l for l in README.splitlines() if l.startswith("**Cifras de la corrida de referencia**"))
    evasion = [round(e["evasion"] * 100) for e in eventos]
    assert f"un {evasion[0]} % en la generación 1 y llega a {max(evasion)} % en la 3" in parrafo and evasion.index(max(evasion)) == 2
    assert f"sin ella habrían salido {sum(e['sin_capa2'] for e in eventos)}, {eventos[0]['sin_capa2'] + eventos[1]['sin_capa2']} de ellos" in parrafo
    ultimo = eventos[-1]
    assert f"recall de {round(ultimo['recall'] * 100)} %" in parrafo and f"{round(ultimo['falsas_alarmas'] * 100)} % de falsas alarmas" in parrafo
    assert f"en la 20 es {round(ultimo['evasion'] * 100)} %" in parrafo
    assert sum(e["exitosas_capa2"] for e in eventos) == 0 and "**0 pagos a una cuenta de estafador en las 20 generaciones**" in parrafo
