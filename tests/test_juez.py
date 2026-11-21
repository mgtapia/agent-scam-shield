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


# --- Barrido, punto de operación, caché en disco y precio ---

def test_el_barrido_reusa_los_veredictos_y_elige_el_punto_de_operacion():
    from scripts.juez_vivo import barrer, elegir

    async def pedir(_m, _s, mensajes, **_k):
        return '{"veredicto": "estafa"}' if "estafa" in mensajes[0].content else '{"veredicto": "estafa"}'
    juez = Juez("mockllm/model", banda=(0.0, 0.5), pedir=pedir)
    _correr(medir(juez, _runs()))
    llamadas = juez.llamadas
    filas = barrer(juez, _runs(), desde=(0.0, 0.2, 0.4))
    assert juez.llamadas == llamadas                     # no vuelve a llamar
    assert [f["banda"][0] for f in filas] == [0.0, 0.2, 0.4]
    # Desde 0 marca todo (falsas alarmas 100 %); desde 0,2 marca el control dudoso (50 %); desde 0,4, nada más.
    assert [f["con_juez"]["falsas_alarmas"]["media"] for f in filas] == [1.0, 0.5, 0.0]
    assert elegir(filas, 0.08)["banda"][0] == 0.4
    assert elegir(filas, 0.6)["banda"][0] == 0.2         # más cobertura con un presupuesto mayor
    assert elegir([f for f in filas if f["banda"][0] < 0.4], 0.08) is None


def test_la_cache_en_disco_guarda_solo_veredictos(tmp_path):
    from scripts.juez_vivo import cargar_cache, guardar_cache
    from scamshield.vivo.juez import Veredicto
    juez = Juez("mockllm/model")
    juez.cache.update({"a": Veredicto(True, "x"), "b": Veredicto(None, "", "caído")})
    ruta = tmp_path / "c.json"
    guardar_cache(ruta, juez)
    leido = cargar_cache(ruta, "mockllm/model")
    assert set(leido) == {"a"} and leido["a"].estafa is True
    assert cargar_cache(ruta, "google/otro") == {}       # la caché de otro modelo no sirve


def test_sin_precio_verificado_gemini_va_como_plan_gratuito():
    from scripts.juez_vivo import precio_texto
    assert precio_texto("google/gemini-3.5-flash") == "gratis (plan gratuito)"
    assert precio_texto("anthropic/claude-haiku-5-5").startswith("US$0.1 / US$0.5")


def test_un_429_de_cuota_corta_la_medicion_sin_esperar():
    from scamshield.vivo.juez import CuotaAgotada, pedir

    class Modelo:
        name = "gemini-x"

        async def generate(self, *_a, **_k):
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded on Free Tier")
    with pytest.raises(CuotaAgotada):
        _correr(pedir(Modelo(), "s", [], max_tokens=10, gasto=Gasto()))
    juez = Juez("mockllm/model", pedir=_falla(CuotaAgotada("cuota")))
    medido = _correr(medir(juez, _runs()))
    assert medido["filas"] == [] and "cuota" in medido["cortado"]


def test_cada_veredicto_nuevo_avisa_para_guardarse():
    vistos = []
    juez = Juez(_mock('{"veredicto": "legitimo"}'), al_juzgar=lambda: vistos.append(1))
    _correr(juez.juzgar("a", "correo"))
    _correr(juez.juzgar("a", "correo"))
    assert vistos == [1]
