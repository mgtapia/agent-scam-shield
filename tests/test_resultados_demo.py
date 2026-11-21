"""scripts/resultados_demo.py: los números de la vista Resultados salen de results/ y el JSON es válido."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.resultados_demo import armar, atacante, colados, duelo, escribir


def _curva(ruta: Path, rondas: int, n: int, exitos: list[int], errores: int = 0) -> Path:
    datos = {"m/x": {"none": {"n": n, "rondas": rondas, "exitos": exitos, "intentos": exitos,
                              "unidades_exitos": [[1] * e + [0] * (n - e) for e in exitos],
                              "no_validas": 0, "errores": errores}}}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


def test_arma_todos_los_bloques_sin_nan(tmp_path):
    datos = armar()
    assert {"bench", "pipelock", "sonnet", "haiku", "clasificador", "atacante", "duelo"} <= set(datos)
    # Lo que no tiene archivo de origen lo dice.
    assert datos["pipelock"]["sin_archivo"] and datos["pipelock"]["fuente"]
    # Sin NaN: el JSON de la demo tiene que poder leerlo el navegador.
    json_, js = escribir(datos, tmp_path)
    json.loads(json_.read_text(encoding="utf-8"))
    assert js.read_text(encoding="utf-8").startswith("// Generado por scripts/resultados_demo.py")


def test_los_numeros_son_los_del_readme():
    datos = armar()
    por = {c["clave"]: c for c in datos["bench"]["configuraciones"]}
    assert round(por["none"]["estafas_exitosas"]["tasa"] * 100) == 100
    # La capa 2 sola deja pasar algunas (el número exacto cambia con el corpus); las capas 2 y 3, ninguna.
    assert 0 < por["layer2"]["estafas_exitosas"]["tasa"] < 0.25
    assert round(por["layer23"]["estafas_exitosas"]["tasa"] * 100) == 0
    assert (datos["sonnet"]["pagos"], datos["sonnet"]["repeticiones"]) == (6, 6)
    assert (datos["pipelock"]["frenadas"], datos["pipelock"]["estafas"]) == (4, 42)
    assert datos["clasificador"]["tipo_intervalo"] == "rango"


def test_atacante_sin_archivo(tmp_path):
    assert atacante(tmp_path)["estado"] == "sin_archivo"


def test_atacante_solo_ronda_cero(tmp_path):
    _curva(tmp_path / "a_curvas.json", 0, 14, [0])
    assert atacante(tmp_path)["estado"] == "sin_rondas"


def test_atacante_elige_por_contenido_y_no_por_fecha(tmp_path):
    # Una curva con muchos errores no le gana a una limpia, aunque tenga más rondas.
    _curva(tmp_path / "sucia_curvas.json", 3, 5, [0, 1, 1, 2], errores=6)
    _curva(tmp_path / "limpia_curvas.json", 2, 10, [1, 2, 3])
    a = atacante(tmp_path)
    assert a["estado"] == "ok" and a["fuente"].endswith("limpia_curvas.json")
    # Sin las unidades crudas y con un intervalo por ronda.
    s = a["series"][0]
    assert "unidades_exitos" not in s and len(s["ic"]) == 3


def test_atacante_lee_el_resumen_y_marca_rondas_incompletas(tmp_path):
    # El formato de resumen_curva_atacante.py, con la capa 2 cortada por la cuota en las rondas 2 y 3.
    rondas = lambda exitosas, validas: [{"ronda": r, "exitosas": e, "n": 5, "tasa": e / 5, "wilson_95": [0.0, 0.43],
                                         "intentadas": 4, "estafas_con_ronda_valida": v}
                                        for r, (e, v) in enumerate(zip(exitosas, validas))]
    datos = {"m/victima": {"none": {"estafas": [], "rondas": rondas([4, 4, 4, 4], [5, 5, 5, 5])},
                           "layer2": {"estafas": [], "rondas": rondas([0, 0, 0, 0], [5, 5, 2, 1])}}}
    (tmp_path / "x_curva.json").write_text(json.dumps(datos), encoding="utf-8")
    a = atacante(tmp_path)
    assert a["estado"] == "ok"
    capa2 = next(s for s in a["series"] if s["defensa"] == "layer2")
    assert [i["ronda"] for i in capa2["incompletas"]] == [2, 3] and capa2["exitos"] == [0, 0, 0, 0]


def test_atacante_con_demasiados_errores(tmp_path):
    _curva(tmp_path / "sucia_curvas.json", 3, 5, [0, 1, 1, 2], errores=6)
    assert atacante(tmp_path)["estado"] == "con_errores"


def test_duelo_capa2_en_cero_y_el_escudo_que_aprende_termina_en_cero():
    d = duelo()
    assert d["estado"] == "ok" and d["exitosas_capa2"] == 0
    for modo in ("congelado", "aprende"):
        m = d[modo]
        assert [x["semilla"] for x in m["semillas"]] == [0, 1, 2]
        assert m["exitosas_capa2"] == 0 and m["candidatos"] == sum(x["candidatos"] for x in m["semillas"])
        for x in m["semillas"]:
            assert len(x["evasion"]) == x["generaciones"] == 20
            assert x["fuente"] == f"results/duelo/{modo}_s{x['semilla']}.json"
    # Congelado, el hacker termina arriba de donde empezó; contra el que aprende termina en 0, y la guardia de
    # deriva revirtió versiones en el camino.
    assert all(x["final"] > x["inicio"] for x in d["congelado"]["semillas"])
    assert all(x["final"] == 0 and x["revertidas"] > 0 for x in d["aprende"]["semillas"])
    assert d["congelado"]["sin_capa2"] > d["aprende"]["sin_capa2"]


def test_duelo_sin_archivos(tmp_path):
    d = duelo(tmp_path)
    assert d["estado"] == "sin_archivo" and d["congelado"]["semillas"] == []


# --- Qué se cuela, por capa y por familia ---

def test_con_las_capas_2_y_3_no_se_cuela_ninguna_y_la_capa_2_sola_deja_las_que_dicta_el_dueno():
    c = colados()
    assert c["totales"]["layer23"] == 0 and c["totales"]["none"] == c["estafas"]
    assert 0 < c["totales"]["layer2"] == c["dueno_dicta"]["layer2"]   # todo lo que cruza la capa 2, lo dicta el dueño
    assert c["dueno_dicta"]["layer3"] == 0                             # y la capa 3 lo frena
    assert sum(f["por_capa"]["layer2"] for f in c["familias"]) == c["totales"]["layer2"]
    # El clasificador: la suma por familia es el total, y viene de la validación cruzada.
    assert c["clasificador"]["colados"] == sum((f["clasificador"] or {}).get("colados", 0) for f in c["familias"])
    assert c["corridas"] == 9 and "results/clasificador.json" in c["fuente"]


def test_colados_con_archivos_propios(tmp_path):
    fila = lambda esc, fam, dicta, cae: {"escenario": esc, "tipo": "estafa", "familia": fam, "dueno_dicta": dicta,
                                         "resultados": {k: {"cayo": k in cae} for k in ("none", "layer1", "layer2", "layer3", "layer23")}}
    bench = {"por_escenario": [fila("a__es", "banco", True, {"none", "layer1", "layer2"}),
                               fila("b__es", "jefe", False, {"none", "layer1", "layer3"}),
                               {"escenario": "c__es", "tipo": "control", "resultados": {}}]}
    (tmp_path / "b.json").write_text(json.dumps(bench), encoding="utf-8")
    c = colados(tmp_path / "b.json", tmp_path / "no_existe.json")
    assert c["estafas"] == 2 and c["totales"] == {"none": 2, "layer1": 2, "layer2": 1, "layer3": 1, "layer23": 0}
    assert c["familias"][0]["familia"] == "banco" and c["familias"][0]["escenarios"]["layer2"] == ["a"]
    assert c["clasificador"] is None and c["familias"][0]["clasificador"] is None


# --- El juez LLM de los casos dudosos ---

def test_juez_sin_archivo_y_con_archivo(tmp_path):
    from scripts.resultados_demo import juez
    assert juez(tmp_path / "no.json")["estado"] == "sin_archivo"
    m = lambda r, fa: {"recall": {"media": r}, "precision": {"media": 0.9}, "falsas_alarmas": {"media": fa}}
    fila = lambda lo, r, fa: {"banda": [lo, 0.5], "fraccion_dudosa": 0.1, "usd_por_1000_correos": 0.0, "con_juez": m(r, fa)}
    datos = {"modelo": "google/x", "precio": "gratis (plan gratuito)", "corridas": 9, "max_falsas": 0.08,
             "sin_juez": m(0.85, 0.04), "barrido": [fila(0.0, 1.0, 0.5), fila(0.3, 0.9, 0.06)],
             "llamadas": 10, "fallas": 0, "gasto": {"gastado_usd": 0.0}}
    datos["punto_operacion"] = datos["barrido"][1]
    (tmp_path / "j.json").write_text(json.dumps(datos), encoding="utf-8")
    j = juez(tmp_path / "j.json")
    assert j["estado"] == "ok" and j["punto_operacion"]["banda"] == [0.3, 0.5] and len(j["barrido"]) == 2
    datos["punto_operacion"] = None
    (tmp_path / "j.json").write_text(json.dumps(datos), encoding="utf-8")
    assert juez(tmp_path / "j.json")["estado"] == "sin_punto"


def test_solo_json_no_toca_resultados_js(tmp_path):
    escritos = escribir({"a": 1}, tmp_path, solo_json=True)
    assert [p.name for p in escritos] == ["resultados.json"] and not (tmp_path / "resultados.js").exists()
