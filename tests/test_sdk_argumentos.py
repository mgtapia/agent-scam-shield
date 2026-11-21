"""La política recibe los valores efectivos de la llamada, incluidos defaults y **kwargs."""
from __future__ import annotations

import asyncio

import pytest

from grifter import escudo


INSCRITA = "33-7741-0092"
ESTAFADOR = "90-1188-4417"
CUENTAS = {"Silicio Austral": INSCRITA}


@pytest.mark.parametrize("asincrona", [False, True])
@pytest.mark.parametrize("nombre", ["pagar", "enviar_dinero"])
def test_kwargs_no_omiten_revision_explicita_ni_automatica(asincrona, nombre):
    ejecutadas = []
    alertas = []

    if asincrona:
        async def herramienta(**datos):
            ejecutadas.append(datos)
            return "ok"
    else:
        def herramienta(**datos):
            ejecutadas.append(datos)
            return "ok"

    protegida = escudo({nombre: herramienta}, cuentas_inscritas=CUENTAS,
                      avisar=lambda alerta: alertas.append(alerta) or False)[nombre]
    datos = {"cuenta": ESTAFADOR, "monto": 1000}
    resultado = protegida(**datos)
    if asincrona:
        resultado = asyncio.run(resultado)
    assert resultado.startswith("Grifter retuvo")
    assert ejecutadas == []
    assert len(alertas) == 1
    assert alertas[0].args == datos
    assert alertas[0].valor == ESTAFADOR


@pytest.mark.parametrize("asincrona", [False, True])
def test_kwargs_permitidos_conservan_argumentos_y_resultado(asincrona):
    ejecutadas = []

    if asincrona:
        async def enviar_dinero(moneda="CLP", **datos):
            ejecutadas.append((moneda, datos))
            return {"estado": "pagado"}
    else:
        def enviar_dinero(moneda="CLP", **datos):
            ejecutadas.append((moneda, datos))
            return {"estado": "pagado"}

    (protegida,) = escudo([enviar_dinero], cuentas_inscritas=CUENTAS)
    datos = {"cuenta": INSCRITA, "monto": 1000, "datos": "referencia"}
    resultado = protegida(**datos)
    if asincrona:
        resultado = asyncio.run(resultado)
    assert resultado == {"estado": "pagado"}
    assert ejecutadas == [("CLP", datos)]


def test_defaults_de_pago_se_revisan_sin_argumentos_explicitos():
    ejecutadas = []

    def enviar_dinero(cuenta=ESTAFADOR, monto=1000, **datos):
        ejecutadas.append((cuenta, monto, datos))
        return "ok"

    (protegida,) = escudo([enviar_dinero], cuentas_inscritas=CUENTAS)
    assert protegida().startswith("Grifter retuvo")
    assert ejecutadas == []


def test_argumentos_normales_y_kwargs_se_revisan_juntos():
    ejecutadas = []

    def enviar_dinero(monto, **datos):
        ejecutadas.append((monto, datos))
        return "ok"

    (protegida,) = escudo([enviar_dinero], cuentas_inscritas=CUENTAS)
    assert protegida(1000, cuenta=ESTAFADOR).startswith("Grifter retuvo")
    assert protegida(1000, cuenta=INSCRITA) == "ok"
    assert ejecutadas == [(1000, {"cuenta": INSCRITA})]


def test_kwargs_se_revisan_con_regla_personalizada():
    ejecutadas = []

    def girar(**datos):
        ejecutadas.append(datos)
        return "ok"

    (protegida,) = escudo([girar], cuentas_inscritas=CUENTAS, sensibles={"girar": "para"})
    assert protegida(para=ESTAFADOR).startswith("Grifter retuvo")
    assert ejecutadas == []


def test_credenciales_en_kwargs_no_omiten_revision():
    ejecutadas = []

    def compartir_dato(**datos):
        ejecutadas.append(datos)
        return "ok"

    (protegida,) = escudo([compartir_dato], cuentas_inscritas=CUENTAS,
                         datos_dueno={"clave_banca": "Sol-9921-xk"})
    resultado = protegida(destinatario="Silicio Austral", dato="Sol-9921-xk")
    assert resultado.startswith("Grifter retuvo")
    assert "clave" in resultado.lower()
    assert ejecutadas == []


@pytest.mark.parametrize("posicional,adicional", [(INSCRITA, ESTAFADOR), (ESTAFADOR, INSCRITA)])
def test_colision_con_parametro_posicional_exclusivo_falla_cerrada(posicional, adicional):
    ejecutadas = []

    def enviar_dinero(cuenta, /, **datos):
        ejecutadas.append((cuenta, datos))
        return "ok"

    (protegida,) = escudo([enviar_dinero], cuentas_inscritas=CUENTAS)
    with pytest.raises(TypeError, match="Grifter.*nombres repetidos"):
        protegida(posicional, cuenta=adicional, monto=1000)
    assert ejecutadas == []


def test_no_se_aplanan_diccionarios_de_parametros_normales():
    def consultar(detalle):
        return detalle

    (protegida,) = escudo([consultar], cuentas_inscritas=CUENTAS)
    detalle = {"cuenta": ESTAFADOR, "monto": 1000}
    assert protegida(detalle) is detalle
