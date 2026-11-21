"""El exportador de resultados para la demo, con logs reales de Inspect hechos con mockllm (sin API)."""
from __future__ import annotations

from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval

from scamshield.evals.task import scamshield
from scripts.exportar_resultados import CONFIGURACION_BASE, escribir, exportar, tacticas_de


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
