"""El juez LLM de los casos dudosos (#131): solo sube la sospecha, nunca deja un «seguro» por defecto. Sin API."""
from __future__ import annotations

import asyncio

import pytest
from inspect_ai.model import ModelOutput, get_model

from scamshield.attacker.costo import Gasto, PresupuestoAgotado, Rechazo, precio_de
from scamshield.vivo.flujo import Flujo
from scamshield.vivo.juez import SISTEMA, Juez, combinar, leer_respuesta, metricas
from scripts.juez_vivo import estimar, medir, resolver, resumir


def _mock(*textos: str):
    return get_model("mockllm/model", custom_outputs=[ModelOutput.from_content("mockllm/model", t) for t in textos])


def _correr(coro):
    return asyncio.run(coro)


# --- Leer la respuesta ---

def test_lee_el_json_de_una_linea():
    v = leer_respuesta('{"veredicto": "estafa", "porque": "pide el código de verificación"}')
    assert v.estafa is True and v.porque.startswith("pide") and v.marca
    v = leer_respuesta('Mi análisis: {"veredicto": "legitimo", "porque": "cuenta inscrita"}')
    assert v.estafa is False and not v.marca


def test_sin_veredicto_queda_marcado():
    v = leer_respuesta("No estoy seguro, depende.")
    assert v.estafa is None and v.marca   # no hay «seguro» por defecto


# --- El juez con un modelo ---

def test_el_juez_consulta_al_modelo_y_guarda_lo_juzgado():
    juez = Juez(_mock('{"veredicto": "estafa", "porque": "urgencia y cuenta nueva"}'))
    v1 = _correr(juez.juzgar("De: a@b.cl\nAsunto: urgente\nPaga hoy", "correo"))
    v2 = _correr(juez.juzgar("De: a@b.cl\nAsunto: urgente\nPaga hoy", "correo"))
    assert v1.estafa is True and v2 is v1 and juez.llamadas == 1


def _falla(excepcion):
    async def pedir(*_a, **_k):
        raise excepcion
    return pedir


@pytest.mark.parametrize("excepcion", [RuntimeError("sin saldo"), Rechazo("se negó")])
def test_si_el_juez_se_cae_o_se_niega_el_dudoso_queda_marcado(excepcion):
    juez = Juez("mockllm/model", pedir=_falla(excepcion))
    v = _correr(juez.juzgar("texto", "whatsapp"))
    assert v.estafa is None and v.marca and juez.fallas == 1


def test_el_tope_de_gasto_corta_la_medicion():
    juez = Juez("mockllm/model", pedir=_falla(PresupuestoAgotado("tope")))
    with pytest.raises(PresupuestoAgotado):
        _correr(juez.juzgar("texto", "correo"))


def test_la_banda_no_incluye_lo_que_el_clasificador_ya_marco():
    juez = Juez("mockllm/model", banda=(0.2, 0.8))
    assert juez.dudoso(0.3) and juez.dudoso(0.5) and not juez.dudoso(0.6) and not juez.dudoso(0.1)
    with pytest.raises(ValueError):
        Juez("mockllm/model", banda=(0.6, 0.2))


def test_el_juez_solo_sube_la_sospecha():
    legitimo = leer_respuesta('{"veredicto": "legitimo", "porque": "x"}')
    assert combinar(0.9, 0.5, legitimo) is True         # no baja lo que el clasificador marcó
    assert combinar(0.3, 0.5, legitimo) is False
    assert combinar(0.3, 0.5, leer_respuesta('{"veredicto": "estafa"}')) is True
    assert combinar(0.3, 0.5, None) is False             # fuera de la banda manda el clasificador


# --- La medición ---

def _runs():
    caso = lambda t, y, p, fam: {"texto": t, "canal": "correo", "y": y, "p": p, "familia": fam, "escenario": fam}
    return [{"pliegue": 0, "semilla": 1, "casos": [
        caso("estafa clara", 1, 0.9, "banco"), caso("estafa dudosa", 1, 0.3, "jefe"),
        caso("estafa muy baja", 1, 0.05, "soporte"), caso("control dudoso", 0, 0.35, "control"),
        caso("control limpio", 0, 0.02, "control")]}]


def test_medir_compara_con_y_sin_juez():
    async def pedir(_m, _s, mensajes, **_k):
        return '{"veredicto": "estafa"}' if "estafa" in mensajes[0].content else '{"veredicto": "legitimo"}'
    juez = Juez("mockllm/model", pedir=pedir)
    r = resumir(_correr(medir(juez, _runs())), juez)
    assert r["sin_juez"]["recall"]["media"] == 0.333 and r["con_juez"]["recall"]["media"] == 0.667
    assert r["con_juez"]["falsas_alarmas"]["media"] == 0.0 and r["dudosos"] == 2 and r["llamadas"] == 2
    # La que el juez no alcanza a ver (bajo la banda) sigue colada.
    assert r["colados_por_familia_con"]["soporte"]["colados"] == 1 and r["colados_por_familia_con"]["jefe"]["colados"] == 0


def test_medir_con_el_juez_caido_marca_los_dudosos_y_cuenta_las_fallas():
    juez = Juez("mockllm/model", pedir=_falla(RuntimeError("caído")))
    r = resumir(_correr(medir(juez, _runs())), juez)
    assert r["fallas"] == 2 and r["con_juez"]["falsas_alarmas"]["media"] == 0.5


def test_medir_se_corta_en_el_tope_y_lo_dice():
    juez = Juez("mockllm/model", pedir=_falla(PresupuestoAgotado("tope de US$2")))
    medido = _correr(medir(juez, _runs()))
    assert medido["filas"] == [] and "tope" in medido["cortado"]


def test_metricas():
    filas = [{"y": 1, "m": True}, {"y": 1, "m": False}, {"y": 0, "m": True}, {"y": 0, "m": False}]
    assert metricas(filas, "m") == {"precision": 0.5, "recall": 0.5, "falsas_alarmas": 0.5, "tp": 1, "fp": 1, "fn": 1, "tn": 1}


# --- Costo y honestidad del prompt ---

def test_precios_de_los_jueces_y_estimacion():
    assert precio_de("anthropic/claude-haiku-5-5") == (0.10, 0.50)
    assert precio_de("anthropic/claude-sonnet-5-5") == (2.0, 10.0)
    assert precio_de("anthropic/claude-fable-5-2") == (8.0, 40.0)
    assert resolver("haiku") == "anthropic/claude-haiku-5-5" and resolver(None) == "mockllm/model"
    haiku, fable = (estimar(_runs(), resolver(m), (0.2, 0.5)) for m in ("haiku", "fable"))
    assert haiku["llamadas"] == fable["llamadas"] == 2
    assert 0 < haiku["usd_tipico"] < fable["usd_tipico"] <= fable["usd_peor_caso"]


def test_el_gasto_registra_el_uso_real():
    g = Gasto(tope_usd=2.0, precio_entrada=0.10, precio_salida=0.50)
    salida = ModelOutput.from_content("mockllm/model", '{"veredicto": "estafa"}')
    juez = Juez(get_model("mockllm/model", custom_outputs=[salida]), gasto=g)
    _correr(juez.juzgar("hola", "correo"))
    assert g.llamadas == 1


def test_el_prompt_describe_senales_y_no_los_escenarios():
    """Para no hacer trampa con el conjunto apartado: ni ids, ni dominios, ni cuentas del corpus."""
    texto = SISTEMA.lower()
    flujo = Flujo(semilla=1)
    for u in flujo.unidades:
        assert u.clave.replace("_", " ") not in texto and u.clave not in texto
    for d in flujo.libreta.dominios:
        assert d not in texto
    assert ".cl" not in texto and "@" not in texto
