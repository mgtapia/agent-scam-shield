"""scripts/falsas_alarmas_vivo.py: las opciones para bajar las falsas alarmas, medidas sin tocar el motor. Sin API."""
from __future__ import annotations

from scamshield.vivo.flujo import Flujo
from scripts.falsas_alarmas_vivo import (REGLAS, UMBRAL, autenticado, correr, curva, remitente_confiable,
                                         umbral_calibrado)


def test_el_umbral_calibrado_nunca_baja_del_fijo():
    assert umbral_calibrado([0.1] * 10) == UMBRAL                 # con pocos legítimos, el fijo
    assert umbral_calibrado([0.1] * 90 + [0.8] * 10) == 0.8       # el percentil 95
    assert umbral_calibrado([0.1] * 100) == UMBRAL                # nunca bajo 0,5


def test_el_remitente_confirmado_y_autenticado_solo_cuenta_sin_pedido():
    c = next(c for c in Flujo(semilla=1).episodio(clave="control_infra_cobro_inscrito", idioma="es") if c.autenticacion)
    assert autenticado(c)
    limpio = {"cuenta_nueva": 0.0}
    assert not remitente_confiable(c, limpio, set())                      # el dueño todavía no lo confirmó
    assert remitente_confiable(c, limpio, {c.de.lower()})
    assert not remitente_confiable(c, {"cuenta_nueva": 1.0}, {c.de.lower()})   # con cuenta nueva, no (#127)
    sin_auth = type(c)(**{**c.__dict__, "autenticacion": {}})
    assert not remitente_confiable(sin_auth, limpio, {c.de.lower()})


def test_una_corrida_mide_las_cuatro_reglas_y_la_curva():
    fila = correr(pliegue=0, semilla=1, episodios=40)
    assert set(REGLAS) <= set(fila) and fila["umbral_calibrado"] >= UMBRAL
    for regla in REGLAS:   # ninguna regla marca más que el umbral fijo: solo pueden bajar la sospecha
        assert fila[regla]["tp"] + fila[regla]["fp"] <= fila["fijo"]["tp"] + fila["fijo"]["fp"]
    c = curva([fila])
    assert c[0]["umbral"] == 0.45 and all(a["falsas_alarmas"] >= b["falsas_alarmas"] for a, b in zip(c, c[1:]))
