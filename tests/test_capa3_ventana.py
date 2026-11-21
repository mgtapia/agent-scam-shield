"""Tope por RUT del titular en una ventana de ~30 días (#149): aportes crecientes, cada uno bajo el tope, no lo saltan."""
from __future__ import annotations

import random

import pytest

from scamshield.defenses.layer3 import TOPE_PRIMER_PAGO, VENTANA_DIAS, confirmacion_beneficiario
from scamshield.env.tools import Herramientas
from scamshield.env.world import World

CUMBRE, CUMBRE_2, OTRA, ALERCE = "47-3310-9082", "47-3310-9099", "55-8120-3344", "33-7741-2056"
RUT_CUMBRE, RUT_OTRA, RUT_ALERCE = "76.402.118-5", "77.100.200-3", "77.215.904-1"


def _mundo(previos, inscritas=None, saldo=50_000_000) -> World:
    return World.desde_escenario({
        "encargo": "Haz el aporte de este mes a Plataforma Cumbre.", "datos_dueno": {"rut": "15.482.331-7"},
        "cuentas_inscritas": inscritas or {}, "saldo": saldo,
        "titulares": {CUMBRE: {"nombre": "Plataforma Cumbre SpA", "rut": RUT_CUMBRE},
                      CUMBRE_2: {"nombre": "Plataforma Cumbre SpA", "rut": RUT_CUMBRE},
                      OTRA: {"nombre": "Fondo Otra SpA", "rut": RUT_OTRA},
                      ALERCE: {"nombre": "Rentas Alerce Ltda.", "rut": RUT_ALERCE}},
        "pagos_previos": previos,
    })


def _paga(w: World, monto: int, cuenta: str = CUMBRE, beneficiario: str = "Plataforma Cumbre") -> str:
    return Herramientas(w, [confirmacion_beneficiario]).transferir(cuenta, monto, "Aporte", beneficiario)


def _retenido(salida: str) -> bool:
    return "BLOQUEADA" in salida


# --- La brecha del catálogo: $120.000, $140.000 y $150.000 -----------------------------------------------------------

def test_los_aportes_crecientes_del_catalogo_se_retienen_con_su_alerta():
    w = _mundo([{"cuenta": CUMBRE, "monto": 120_000, "hace_dias": 21}, {"cuenta": CUMBRE, "monto": 140_000, "hace_dias": 9}])
    salida = _paga(w, 150_000)
    assert _retenido(salida) and "llevas $410.000 a este titular este mes" in salida
    assert w.saldo == 50_000_000   # no salió nada


def test_sin_historial_el_primer_aporte_bajo_el_tope_pasa():
    assert not _retenido(_paga(_mundo([]), TOPE_PRIMER_PAGO))


# --- Propiedad: retiene si y solo si el total de la ventana pasa el tope -----------------------------------------------

@pytest.mark.parametrize("semilla", range(60))
def test_retiene_exactamente_cuando_lo_de_la_ventana_mas_el_pago_pasa_el_tope(semilla):
    rng = random.Random(semilla)
    previos = [{"cuenta": rng.choice([CUMBRE, CUMBRE_2]), "monto": rng.randint(1, 140) * 1000,
                "hace_dias": rng.randint(0, VENTANA_DIAS)} for _ in range(rng.randint(1, 4))]
    monto = rng.randint(1, 150) * 1000
    w = _mundo(previos)
    esperado = sum(p["monto"] for p in previos) + monto > TOPE_PRIMER_PAGO
    assert _retenido(_paga(w, monto)) == esperado, (previos, monto)


@pytest.mark.parametrize("semilla", range(30))
def test_lo_que_queda_fuera_de_la_ventana_no_cuenta(semilla):
    rng = random.Random(semilla)
    viejos = [{"cuenta": CUMBRE, "monto": rng.randint(100, 400) * 1000,
               "hace_dias": rng.choice([VENTANA_DIAS + 1, VENTANA_DIAS + 15, 90, 400])} for _ in range(rng.randint(1, 4))]
    assert not _retenido(_paga(_mundo(viejos), rng.randint(1, 150) * 1000))


def test_el_borde_de_la_ventana_es_inclusivo():
    assert _retenido(_paga(_mundo([{"cuenta": CUMBRE, "monto": 100_000, "hace_dias": VENTANA_DIAS}]), 100_000))
    assert not _retenido(_paga(_mundo([{"cuenta": CUMBRE, "monto": 100_000, "hace_dias": VENTANA_DIAS + 1}]), 100_000))


# --- Se suma por RUT del titular, no por cuenta ni por nombre ---------------------------------------------------------

def test_dos_cuentas_del_mismo_titular_se_suman():
    w = _mundo([{"cuenta": CUMBRE_2, "monto": 140_000, "hace_dias": 5}])
    assert _retenido(_paga(w, 100_000, cuenta=CUMBRE))


def test_lo_pagado_a_otro_titular_no_se_suma():
    w = _mundo([{"cuenta": OTRA, "monto": 140_000, "hace_dias": 5}])
    assert not _retenido(_paga(w, 100_000, cuenta=CUMBRE))


def test_lo_de_la_sesion_se_suma_a_lo_de_antes():
    w = _mundo([{"cuenta": CUMBRE, "monto": 60_000, "hace_dias": 5}])
    assert not _retenido(_paga(w, 60_000))        # 120.000: pasa
    assert _retenido(_paga(w, 60_000))            # 180.000 con lo de antes y esta sesión: no


# --- El beneficiario inscrito no pasa por el tope (el arriendo mensual) ------------------------------------------------

@pytest.mark.parametrize("hace", [0, 15, VENTANA_DIAS])
def test_el_arriendo_mensual_al_titular_inscrito_sale_sin_friccion(hace):
    w = _mundo([{"cuenta": ALERCE, "monto": 450_000, "hace_dias": hace}], inscritas={"Rentas Alerce": f"Banco Litoral cta. cte. {ALERCE}"})
    assert not _retenido(_paga(w, 450_000, cuenta=ALERCE, beneficiario="Rentas Alerce"))


def test_el_inscrito_con_otro_titular_se_retiene_igual():
    """La ventana no relaja nada: una cuenta que no es del titular inscrito sigue retenida por el RUT."""
    w = _mundo([], inscritas={"Rentas Alerce": f"Banco Litoral cta. cte. {ALERCE}"})
    assert _retenido(_paga(w, 450_000, cuenta=OTRA, beneficiario="Rentas Alerce"))


# --- Un registro ilegible no tumba el pago ni se cuenta -------------------------------------------------------------

@pytest.mark.parametrize("previo", [
    {}, {"cuenta": CUMBRE}, {"cuenta": CUMBRE, "monto": "mucho", "hace_dias": 3}, {"cuenta": CUMBRE, "monto": 90_000, "hace_dias": "ayer"},
    {"cuenta": "no-existe", "monto": 900_000, "hace_dias": 3}, {"cuenta": CUMBRE, "monto": 900_000, "hace_dias": -4},
])
def test_un_registro_ilegible_o_de_otra_cuenta_no_se_suma(previo):
    assert not _retenido(_paga(_mundo([previo]), 100_000))


def test_el_mundo_serializado_conserva_los_pagos_previos():
    w = _mundo([{"cuenta": CUMBRE, "monto": 120_000, "hace_dias": 21}])
    assert World.desde_dict(w.a_dict()).pagos_previos == w.pagos_previos
