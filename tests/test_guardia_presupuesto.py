"""El presupuesto de falsas alarmas de la guardia se redondea hacia arriba a correos enteros.

Con 27 legítimos apartados el 10 % son 2,7 correos: una versión con 3 falsas alarmas (11,1 %) se rechazaba por una
décima y el calentamiento del motor en vivo terminaba en 1.0.0 con recall 0 (en 7 de 10 semillas, medido en main).
"""
from __future__ import annotations

import numpy as np
import pytest

from scamshield.vivo.clasificador import Clasificador, Rasgos, SENALES
from scamshield.vivo.flujo import Flujo
from scamshield.vivo.motor import Motor


def _apartado(legitimos: int, estafas: int = 10):
    nulo = Rasgos({k: 0.0 for k in SENALES}, {})
    return [(nulo, 0)] * legitimos + [(nulo, 1)] * estafas


@pytest.mark.parametrize("legitimos,permitidos", [(27, 3), (20, 2), (10, 1), (5, 1), (100, 10), (11, 2), (1, 1)])
def test_el_presupuesto_es_el_diez_por_ciento_redondeado_hacia_arriba_a_correos_enteros(legitimos, permitidos):
    c = Clasificador(_apartado(legitimos))
    assert c._presupuesto_falsas_alarmas() == pytest.approx(permitidos / legitimos)


def test_sin_legitimos_apartados_queda_el_presupuesto_original():
    assert Clasificador(_apartado(0))._presupuesto_falsas_alarmas() == Clasificador.PRESUPUESTO_FALSAS_ALARMAS


def test_el_presupuesto_nunca_pasa_de_un_correo_de_mas_sobre_el_diez_por_ciento():
    for n in range(1, 200):
        p = Clasificador(_apartado(n))._presupuesto_falsas_alarmas()
        assert Clasificador.PRESUPUESTO_FALSAS_ALARMAS - 1e-9 <= p < Clasificador.PRESUPUESTO_FALSAS_ALARMAS + 1 / n + 1e-9


def _con_urgentes(urgentes: int, legitimos: int = 27, estafas: int = 10):
    """Un apartado donde `urgentes` legítimos comparten la señal que las estafas: aprender «urgencia = estafa» los marca."""
    nulo = Rasgos({k: 0.0 for k in SENALES}, {})
    urgente = Rasgos({**{k: 0.0 for k in SENALES}, "urgencia": 1.0}, {})
    return ([(nulo, 0)] * (legitimos - urgentes) + [(urgente, 0)] * urgentes + [(urgente, 1)] * estafas), urgente


def test_tres_falsas_alarmas_de_27_entran_en_el_presupuesto_y_cuatro_no():
    apartado, urgente = _con_urgentes(3)
    cl = Clasificador(apartado, tasa=0.1)   # una tasa chica: el sesgo no sube tanto como para marcar también a los demás
    for _ in range(6):
        cl.aprender(urgente, 1)
    assert cl.n_version == 1 and cl.revertidas == 0 and cl.metricas["falsas_alarmas"] == pytest.approx(3 / 27, abs=1e-3)

    apartado, urgente = _con_urgentes(4)
    cl = Clasificador(apartado, tasa=0.1)   # una tasa chica: el sesgo no sube tanto como para marcar también a los demás
    for _ in range(6):
        cl.aprender(urgente, 1)
    assert cl.n_version == 0 and cl.revertidas == 1   # 4 de 27 = 14,8 %: pasa el presupuesto, se revierte
