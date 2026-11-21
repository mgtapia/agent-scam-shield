"""El exportador de resultados para la demo, con logs reales de Inspect hechos con mockllm (sin API)."""
from __future__ import annotations

from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval

from scamshield.evals.task import scamshield
from scripts.exportar_resultados import (CONFIGURACION_BASE, TACTICAS, agregados_de, escribir, exportar,
                                         tacticas_de)
from scripts.resumen_resultados import agregar


def _correr(carpeta: Path, **args) -> Path:
    [log] = inspect_eval(scamshield(idiomas="es", **args), model="mockllm/model", log_dir=str(carpeta),
                         display="none", limit=6)
    assert log.status == "success", log.error
    return Path(log.location)


@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    c = tmp_path_factory.mktemp("logs")
    return {"base": _correr(c, defense="layer2", epochs=2),
            "sin_lista": _correr(c, defense="layer2", cuentas_visibles=False),
            "con_dueno": _correr(c, defense="layer2_approver", dueno_simulado=True)}


def test_por_defecto_solo_entra_la_configuracion_base(logs):
    datos = exportar(list(logs.values()))
    assert [r["archivo"] for r in datos["registros"]] == [logs["base"].name]
    assert {m["archivo"]: m["motivo"] for m in datos["omitidos"]} == {
        logs["sin_lista"].name: "configuración distinta de la base",
        logs["con_dueno"].name: "configuración distinta de la base"}
    assert {(f["lista_cuentas"], f["aviso_escudo"], f["dueno_simulado"]) for f in datos["filas"]} == {(True, False, False)}


def test_con_todas_ninguna_configuracion_pisa_a_otra(logs):
    datos = exportar(list(logs.values()), todas=True)
    assert len(datos["registros"]) == 3 and not datos["omitidos"]
    configs = {(f["defensa"], f["lista_cuentas"], f["dueno_simulado"]) for f in datos["filas"]}
    assert configs == {("layer2", True, False), ("layer2", False, False), ("layer2_approver", True, True)}


def test_las_filas_llevan_la_repeticion_y_los_none_donde_la_metrica_no_aplica(logs):
    filas = exportar([logs["base"]])["filas"]
    assert {f["epoch"] for f in filas} == {1, 2}
    for f in filas:
        if f["tipo"] == "control":
            assert f["seguridad"] is None
        else:
            assert f["falsa_alarma"] is None


def test_dos_registros_de_la_misma_configuracion_dejan_el_mas_reciente(logs, tmp_path):
    otro = _correr(tmp_path, defense="layer2", epochs=2)
    datos = exportar([logs["base"], otro])
    assert len(datos["registros"]) == 1 and [m["motivo"] for m in datos["omitidos"]] == ["repetido"]


def test_escribe_el_json_y_su_copia_js(logs, tmp_path):
    json_, js = escribir(exportar([logs["base"]]), tmp_path)
    assert json_.read_text(encoding="utf-8").lstrip().startswith("{")
    assert js.read_text(encoding="utf-8").startswith("// Generado por scripts/exportar_resultados.py")


def test_la_configuracion_base_es_la_de_la_tarea_por_defecto():
    assert CONFIGURACION_BASE == {"lista_cuentas": True, "aviso_escudo": False, "dueno_simulado": False}


@pytest.mark.parametrize("anotaciones, esperadas", [
    ({"social_eng_tactics": ["urgency", "authority"], "fraud_mechanism": "otp_phishing"},
     ["urgencia", "autoridad", "pedido_codigo"]),
    ({"social_eng_tactics": [], "fraud_mechanism": "business_email_compromise"}, ["cambio_cuenta"]),
    ({"social_eng_tactics": ["rivalry"], "fraud_mechanism": "none"}, []),
])
def test_tacticas_de_un_escenario(anotaciones, esperadas):
    assert tacticas_de({"anotaciones": anotaciones}) == esperadas


def test_corridas_de_idiomas_distintos_no_se_pisan(tmp_path):
    es = _correr(tmp_path, defense="layer2")
    [log_en] = inspect_eval(scamshield(idiomas="en", defense="layer2"), model="mockllm/model",
                            log_dir=str(tmp_path), display="none", limit=6)
    datos = exportar([es, Path(log_en.location)])
    assert len(datos["registros"]) == 2 and not datos["omitidos"]
    assert {f["idioma"] for f in datos["filas"]} == {"es", "en"}


# --- Agregados con intervalo ---

def _fila_de_prueba(escenario, epoch, tipo="estafa", seguridad="C", utilidad=None, falsa_alarma=None,
                    valida=True, idioma="es", tacticas=("urgencia",), con_tarea=False, modelo="m", defensa="d"):
    return {"modelo": modelo, "defensa": defensa, **CONFIGURACION_BASE, "epoch": epoch, "idioma": idioma,
            "escenario": escenario, "tipo": tipo, "tacticas": list(tacticas), "valida": valida,
            "con_tarea": con_tarea, "seguridad": seguridad, "utilidad": utilidad, "falsa_alarma": falsa_alarma}


def _como_muestras(filas):
    return [{"escenario": f"{f['escenario']}__{f['idioma']}", "tipo": f["tipo"], "tiene_tarea": f["con_tarea"],
             "cayo": f["seguridad"] == "I", "tarea_ok": f["utilidad"] == "C", "falsa_alarma": bool(f["falsa_alarma"])}
            for f in filas if f["valida"]]


def _grupo(datos, idioma="todos", **clave):
    [g] = [a for a in datos["agregados"] if a["idioma"] == idioma
           and all(a[k] == v for k, v in clave.items())]
    return g


def _igual(metrica, esperada):
    for campo in ("tasa", "bajo", "alto"):
        if esperada["escenarios"] == 0:
            assert metrica[campo] is None
        else:
            assert metrica[campo] == pytest.approx(esperada[campo])
    assert metrica["escenarios"] == esperada["escenarios"]
    assert metrica["repeticiones"] == esperada["repeticiones"]


def test_el_json_trae_agregados_que_coinciden_con_el_resumen(logs):
    datos = exportar([logs["base"]])
    assert datos["agregados"]
    filas = datos["filas"]
    g = _grupo(datos, defensa="layer2")
    esperado = agregar(_como_muestras(filas))
    for nombre in ("estafas_exitosas", "utilidad", "falsas_alarmas"):
        _igual(g[nombre], esperado[nombre])
    assert g["muestras"] == len(filas) and g["validas"] == len(filas)
    # Por táctica, solo el éxito de la estafa y solo sobre las estafas con esa táctica.
    for t in TACTICAS:
        con = [f for f in filas if f["tipo"] == "estafa" and t["clave"] in f["tacticas"]]
        _igual(g["tacticas"][t["clave"]], agregar(_como_muestras(con))["estafas_exitosas"])


def test_cada_metrica_se_calcula_solo_donde_aplica():
    filas = [_fila_de_prueba("e1", 1, seguridad="I", con_tarea=True, utilidad="C"),
             _fila_de_prueba("e2", 1, seguridad="C", con_tarea=True, utilidad="I"),
             _fila_de_prueba("e3", 1, seguridad="C"),
             _fila_de_prueba("c1", 1, tipo="control", seguridad=None, falsa_alarma=1.0, con_tarea=True, utilidad="C"),
             _fila_de_prueba("c2", 1, tipo="control", seguridad=None, falsa_alarma=0.0)]
    [g] = [a for a in agregados_de(filas) if a["idioma"] == "todos"]
    assert (g["estafas_exitosas"]["escenarios"], g["estafas_exitosas"]["tasa"]) == (3, pytest.approx(1 / 3))
    assert (g["utilidad"]["escenarios"], g["utilidad"]["tasa"]) == (3, pytest.approx(2 / 3))
    assert (g["falsas_alarmas"]["escenarios"], g["falsas_alarmas"]["tasa"]) == (2, 0.5)


def test_un_escenario_con_repeticiones_cuenta_una_sola_vez():
    # Un escenario cayó 1 de 3 veces; el otro, 0 de 3: dos escenarios y seis repeticiones, no seis muestras.
    filas = [_fila_de_prueba("a", e, seguridad="I" if e == 1 else "C") for e in (1, 2, 3)]
    filas += [_fila_de_prueba("b", e) for e in (1, 2, 3)]
    [g] = [a for a in agregados_de(filas) if a["idioma"] == "todos"]
    m = g["estafas_exitosas"]
    assert (m["escenarios"], m["repeticiones"]) == (2, 6)
    assert m["tasa"] == pytest.approx((1 / 3 + 0) / 2)
    # Dos escenarios dan un intervalo que sale de remuestrear escenarios, no de 6 muestras independientes.
    assert m["bajo"] == 0.0 and m["alto"] == pytest.approx(1 / 3)


def test_las_muestras_con_error_no_entran_pero_se_cuentan():
    filas = [_fila_de_prueba("a", 1, seguridad="I"), _fila_de_prueba("b", 1, seguridad="C"),
             _fila_de_prueba("c", 1, seguridad=None, valida=False)]
    [g] = [a for a in agregados_de(filas) if a["idioma"] == "todos"]
    m = g["estafas_exitosas"]
    assert (g["muestras"], g["validas"]) == (3, 2)
    assert (m["escenarios"], m["repeticiones"], m["repeticiones_totales"]) == (2, 2, 3)
    assert m["tasa"] == 0.5


def test_sin_muestras_validas_no_hay_tasa_inventada():
    filas = [_fila_de_prueba("a", 1, seguridad=None, valida=False)]
    [g] = [a for a in agregados_de(filas) if a["idioma"] == "todos"]
    for nombre in ("estafas_exitosas", "utilidad", "falsas_alarmas"):
        assert g[nombre]["tasa"] is None and g[nombre]["escenarios"] == 0
    assert g["tacticas"]["urgencia"]["tasa"] is None and g["tacticas"]["urgencia"]["repeticiones_totales"] == 1


def test_agregados_por_idioma_y_el_mismo_id_en_dos_idiomas_son_dos_escenarios():
    filas = [_fila_de_prueba("a", 1, idioma="es", seguridad="I"), _fila_de_prueba("a", 1, idioma="en")]
    datos = agregados_de(filas)
    assert {a["idioma"] for a in datos} == {"todos", "es", "en"}
    assert [a for a in datos if a["idioma"] == "todos"][0]["estafas_exitosas"]["escenarios"] == 2
    assert [a for a in datos if a["idioma"] == "es"][0]["estafas_exitosas"]["tasa"] == 1.0


def test_el_json_es_valido_sin_nan(logs, tmp_path):
    import json
    json_, _ = escribir(exportar([logs["base"]]), tmp_path)
    json.loads(json_.read_text(encoding="utf-8"), parse_constant=lambda c: pytest.fail(f"constante {c} en el JSON"))


def test_dos_registros_que_se_solapan_en_escenarios_fallan_en_lugar_de_contarse_doble(tmp_path):
    es = _correr(tmp_path, defense="layer2")
    [ambos] = inspect_eval(scamshield(idiomas="es,en", defense="layer2"), model="mockllm/model",
                           log_dir=str(tmp_path), display="none", limit=6)
    with pytest.raises(ValueError, match="se solapan"):
        exportar([es, Path(ambos.location)])
