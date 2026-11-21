"""El resumen con intervalos: las cuentas a mano y un log real de mockllm con epochs (sin API)."""
from __future__ import annotations

import pytest
from inspect_ai import eval as inspect_eval

from scamshield.evals.task import scamshield
from scripts.resumen_resultados import agregar, main, resumir, tasa_con_intervalo


def _m(escenario, tipo, *, cayo=False, tarea=True, tarea_ok=False, falsa=False):
    return {"escenario": escenario, "tipo": tipo, "tiene_tarea": tarea, "cayo": cayo,
            "tarea_ok": tarea_ok, "falsa_alarma": falsa}


def test_las_repeticiones_de_un_escenario_cuentan_como_una_sola_muestra():
    # Un escenario con 3 repeticiones (cae en 1) y otro con 3 (nunca cae): tasa = (1/3 + 0) / 2.
    muestras = [_m("a", "estafa", cayo=True), _m("a", "estafa"), _m("a", "estafa"),
                _m("b", "estafa"), _m("b", "estafa"), _m("b", "estafa")]
    r = agregar(muestras)["estafas_exitosas"]
    assert r["tasa"] == pytest.approx(1 / 6)
    assert r["escenarios"] == 2 and r["repeticiones"] == 6


def test_cada_metrica_se_calcula_solo_donde_aplica():
    muestras = [_m("e1", "estafa", tarea=False, cayo=True),   # estafa sin tarea legítima
                _m("e2", "estafa", tarea=True, tarea_ok=True),
                _m("c1", "control", tarea=True, tarea_ok=True, falsa=True),
                _m("c2", "control", tarea=True, tarea_ok=True)]
    r = agregar(muestras)
    assert r["estafas_exitosas"]["escenarios"] == 2 and r["estafas_exitosas"]["tasa"] == 0.5
    assert r["utilidad"]["escenarios"] == 3 and r["utilidad"]["tasa"] == 1.0
    assert r["falsas_alarmas"]["escenarios"] == 2 and r["falsas_alarmas"]["tasa"] == 0.5


def test_el_intervalo_contiene_la_tasa_y_es_reproducible():
    datos = [0.0] * 18 + [1.0] * 3
    tasa, bajo, alto = tasa_con_intervalo(datos)
    assert bajo <= tasa <= alto and 0 <= bajo and alto <= 1
    assert tasa_con_intervalo(datos) == (tasa, bajo, alto)
    # Con 3 de 21 el intervalo es ancho: es justo la advertencia que se quiere mostrar.
    assert alto - bajo > 0.15


def test_sin_datos_no_inventa_numeros():
    tasa, bajo, alto = tasa_con_intervalo([])
    assert tasa != tasa and bajo != bajo and alto != alto  # NaN
    assert agregar([])["utilidad"]["escenarios"] == 0


def test_resumen_de_un_log_real_con_epochs(tmp_path, capsys):
    inspect_eval(scamshield(defense="layer2", idiomas="es", epochs=2), model="mockllm/model",
                 log_dir=str(tmp_path), display="none", limit=8)
    [fila] = resumir(tmp_path)
    assert fila["defensa"] == "layer2" and fila["cuentas_visibles"] is True
    assert fila["estafas_exitosas"]["tasa"] == 0.0  # un modelo sin herramientas no paga
    assert fila["estafas_exitosas"]["repeticiones"] == 2 * fila["estafas_exitosas"]["escenarios"]
    assert main([str(tmp_path)]) == 0
    assert "| mockllm/model | layer2 | sí | no |" in capsys.readouterr().out


def test_carpeta_sin_logs_falla_con_mensaje(tmp_path, capsys):
    assert main([str(tmp_path)]) == 2
    assert "No hay logs" in capsys.readouterr().err


def test_toques_por_100_es_la_razon_entre_totales_y_no_inventa_sin_base():
    from scripts.resumen_resultados import toques_por_100

    muestras = [{"escenario": "a", "toques": 1, "intentos": 2}, {"escenario": "a", "toques": 0, "intentos": 2},
                {"escenario": "b", "toques": 0, "intentos": 4}, {"escenario": "c", "toques": 1, "intentos": 2}]
    r = toques_por_100(muestras)
    assert r["tasa"] == pytest.approx(100 * 2 / 10) and r["bajo"] <= r["tasa"] <= r["alto"]
    sin_base = toques_por_100([{"escenario": "a", "toques": 0, "intentos": 0}])
    assert sin_base["tasa"] != sin_base["tasa"]  # NaN: no hay acciones sensibles sobre las que medir
