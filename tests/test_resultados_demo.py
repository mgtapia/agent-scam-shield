"""scripts/resultados_demo.py: los números de la vista Resultados salen de results/ y el JSON es válido."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.resultados_demo import armar, atacante, duelo, escribir


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
