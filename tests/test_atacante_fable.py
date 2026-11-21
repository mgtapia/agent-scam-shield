"""Fable 5.2 (y cualquier Claude 5.x) como atacante (#99): configuración, negativas, tope de gasto y costo.

Todo con modelos simulados: no llama a ninguna API ni cuesta nada.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from scamshield.attacker.bucle import Config, correr_atacante, pedir
from scamshield.attacker.costo import (MAX_TOKENS_PENSANDO, Gasto, PresupuestoAgotado, Rechazo, config_para,
                                       estimar, piensa_siempre, precio_de)
from scamshield.attacker.escenario import variante_maliciosa
from scamshield.attacker.resultados import curvas
from scamshield.scenarios import cargar
from tests.test_atacante import (CRITICO_2, JUEZ_OK, PAGA_LEGITIMO, _intento, _semilla, _victima)

FABLE = "claude-fable-5-2"


class FalsoClaude:
    """Un modelo del atacante que imita a Claude: anota la configuración de cada llamada y responde guionado."""

    def __init__(self, respuestas, nombre: str = FABLE):
        self.name = nombre
        self.respuestas = list(respuestas)
        self.configs: list = []

    async def generate(self, mensajes, config=None):
        self.configs.append(config)
        r = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        texto, uso, razon = r if isinstance(r, tuple) else (r, (1000, 500), "stop")
        return SimpleNamespace(completion=texto, usage=SimpleNamespace(
            input_tokens=uso[0], output_tokens=uso[1], input_tokens_cache_write=0, input_tokens_cache_read=0),
            stop_reason=razon)


def _correr(tmp_path, atacante, *, rondas=1, gasto=None, victima=None, defensas=("none",)):
    cfg = Config(victima=victima or _victima(*PAGA_LEGITIMO, *PAGA_LEGITIMO), atacante=atacante, defensas=defensas,
                 rondas=rondas, cache=False, log_dir=str(tmp_path / "logs"), salida=tmp_path / "filas.jsonl",
                 nombre_victima="victima-sim", gasto=gasto or Gasto())
    return cfg, asyncio.run(correr_atacante(cfg, [_semilla()]))


# --- Configuración por modelo ----------------------------------------------------------------------------

@pytest.mark.parametrize("nombre", [FABLE, "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])
def test_un_claude_5_no_recibe_temperature_y_piensa_con_margen(nombre):
    c = config_para(nombre, temperatura=1.0, max_tokens=600, cache=True, effort="high")
    assert c.temperature is None                     # Fable la rechaza con un 400
    assert c.max_tokens >= MAX_TOKENS_PENSANDO       # 600 se van en el pensamiento y dejan la respuesta vacía
    assert c.effort == "high"
    assert piensa_siempre(nombre)


def test_un_max_tokens_mayor_se_respeta():
    assert config_para(FABLE, 1.0, 9000, False).max_tokens == 9000


@pytest.mark.parametrize("nombre", ["groq/openai/gpt-oss-120b", "gpt-oss-20b", "qwen/qwen3.8-27b", "gemini-3.5-flash"])
def test_los_demas_modelos_siguen_igual(nombre):
    c = config_para(nombre, temperatura=0.7, max_tokens=600, cache=False)
    assert c.temperature == 0.7 and c.max_tokens == 600 and c.effort is None
    assert (c.reasoning_effort == "low") == ("gpt-oss" in nombre)
    assert not piensa_siempre(nombre)


def test_pedir_manda_a_fable_sin_temperature_y_con_tokens_de_sobra():
    modelo = FalsoClaude(["hola"])
    asyncio.run(pedir(modelo, "sistema", [], temperatura=1.0, cache=False, max_tokens=600))
    [c] = modelo.configs
    assert c.temperature is None and c.max_tokens >= MAX_TOKENS_PENSANDO and c.effort == "high"


def test_la_primera_llamada_del_bucle_a_fable_no_lleva_temperature(tmp_path):
    modelo = FalsoClaude([_intento("Cuenta nueva 77-0193-5520"), JUEZ_OK, CRITICO_2])
    _correr(tmp_path, modelo, rondas=1)
    assert modelo.configs and all(c.temperature is None for c in modelo.configs)
    assert all(c.max_tokens >= MAX_TOKENS_PENSANDO for c in modelo.configs)   # atacante, juez y crítico


# --- Negativas ----------------------------------------------------------------------------------------------

def test_una_negativa_es_un_dato_no_una_ronda_fallida_ni_una_excepcion(tmp_path):
    modelo = FalsoClaude([("", (800, 0), "content_filter")])
    cfg, res = _correr(tmp_path, modelo, rondas=2)
    r0, r1, r2 = res["filas"][0], res["filas"][1], res["filas"][2]
    assert r0["ronda"] == 0 and not r0["se_nego"]                    # la ronda 0 no usa al atacante
    for fila in (r1, r2):
        assert fila["se_nego"] is True and fila["valida"] is False
        assert fila["error"] == "" and "se negó" in fila["motivo_rechazo"]   # no es un error de cuota o de red
    # El resumen cuenta toda negativa del modelo, también la del crítico en la ronda 0 (ahí el puntaje sale de
    # lo observado); las filas con `se_nego` cuentan solo las reescrituras que el atacante no escribió.
    assert res["gasto"]["rechazos"] == 3
    assert sum(f["se_nego"] for f in res["filas"]) == 2
    assert res["episodios"] == 1                                       # no gastó un episodio de la víctima en ellas


def test_una_negativa_no_se_reintenta(tmp_path):
    modelo = FalsoClaude([("", (800, 0), "content_filter")])
    _correr(tmp_path, modelo, rondas=1)
    assert len(modelo.configs) == 2     # el crítico de la ronda 0 y un solo intento del atacante en la ronda 1


def test_pedir_lanza_rechazo_y_cuenta_el_uso_de_esa_llamada():
    g = Gasto(precio_entrada=8, precio_salida=40)
    with pytest.raises(Rechazo):
        asyncio.run(pedir(FalsoClaude([("", (1000, 200), "content_filter")]), "s", [], temperatura=1, cache=False, gasto=g))
    assert g.rechazos == 1 and g.tokens_entrada == 1000 and g.tokens_salida == 200


def test_las_curvas_cuentan_los_rechazos_del_atacante(tmp_path):
    _, res = _correr(tmp_path, FalsoClaude([("", (10, 0), "content_filter")]), rondas=2)
    assert curvas(res["filas"])["victima-sim"]["none"]["rechazos_atacante"] == 2


def test_despues_de_negarse_el_atacante_puede_volver_a_intentar(tmp_path):
    # El orden de las respuestas es el de las llamadas: crítico de la ronda 0, atacante (se niega), atacante, juez, crítico.
    modelo = FalsoClaude([CRITICO_2, ("", (10, 0), "content_filter"), _intento("Cuenta nueva 77-0193-5520"), JUEZ_OK,
                          CRITICO_2])
    _, res = _correr(tmp_path, modelo, rondas=2)
    assert [f["se_nego"] for f in res["filas"]] == [False, True, False]
    assert res["filas"][2]["valida"] is True


# --- Tope de gasto -----------------------------------------------------------------------------------------------

def test_el_gasto_sale_del_uso_real_de_la_api():
    g = Gasto(tope_usd=5, precio_entrada=8, precio_salida=40)
    g.registrar(SimpleNamespace(input_tokens=100_000, output_tokens=10_000, input_tokens_cache_write=50_000,
                                input_tokens_cache_read=50_000))
    assert g.tokens_entrada == 200_000 and g.tokens_salida == 10_000
    assert g.gastado_usd == pytest.approx(200_000 * 8 / 1e6 + 10_000 * 40 / 1e6)      # 1,60 + 0,40
    assert not g.agotado
    g.registrar(SimpleNamespace(input_tokens=0, output_tokens=75_000))                # +3,00 = 5,00
    assert g.agotado


def test_no_se_llama_si_la_siguiente_llamada_ya_no_cabe_bajo_el_tope():
    g = Gasto(tope_usd=0.9, precio_entrada=8, precio_salida=40)
    g.registrar(SimpleNamespace(input_tokens=0, output_tokens=20_000))                # US$0,80 y no llega al tope
    modelo = FalsoClaude(["x"])
    with pytest.raises(PresupuestoAgotado):                                           # el peor caso: +4.000 × 40/M = US$0,16
        asyncio.run(pedir(modelo, "s", [], temperatura=1, cache=False, gasto=g))
    assert modelo.configs == []                                                       # ni una llamada de más


def test_la_corrida_se_corta_sola_al_llegar_al_tope_y_guarda_lo_que_hizo(tmp_path, capsys):
    caro = (_intento("Cuenta nueva 77-0193-5520"), (50_000, 50_000), "stop")           # US$2,40 por llamada
    modelo = FalsoClaude([caro, (JUEZ_OK, (50_000, 50_000), "stop"), (CRITICO_2, (50_000, 50_000), "stop")])
    gasto = Gasto(tope_usd=5.0, precio_entrada=8, precio_salida=40)
    cfg, res = _correr(tmp_path, modelo, rondas=4, gasto=gasto, victima=_victima(*PAGA_LEGITIMO * 4))
    assert gasto.gastado_usd <= 5.0 + 2.5                                              # a lo sumo una llamada en vuelo
    assert gasto.agotado or gasto.gastado_usd > 2.5
    assert res["gasto"]["tope_usd"] == 5.0 and res["gasto"]["gastado_usd"] == pytest.approx(gasto.gastado_usd, abs=1e-3)
    rondas = {f["ronda"] for f in res["filas"]}
    assert max(rondas) < 4                                                             # no llegó a la última ronda
    guardadas = [json.loads(linea) for linea in (tmp_path / "filas.jsonl").read_text("utf-8").splitlines()]
    assert len(guardadas) == len(res["filas"]) >= 1                                    # lo hecho quedó en el JSONL
    assert "tope" in capsys.readouterr().out or any("tope" in f["error"] for f in res["filas"])


def test_sin_tope_un_modelo_gratis_no_se_corta(tmp_path):
    modelo = FalsoClaude([CRITICO_2, (_intento("Cuenta nueva 77-0193-5520"), (10 ** 6, 10 ** 6), "stop"), JUEZ_OK,
                          CRITICO_2], nombre="gpt-oss-120b")
    gasto = Gasto()                       # sin tope ni precios
    _, res = _correr(tmp_path, modelo, rondas=1, gasto=gasto)
    assert gasto.gastado_usd == 0 and not gasto.agotado and res["filas"][1]["valida"]


# --- Costo y --dry-run -----------------------------------------------------------------------------------------------

def test_los_precios_de_fable_vienen_del_issue():
    assert precio_de("anthropic/claude-fable-5-2") == (8.0, 40.0)
    assert precio_de("groq/openai/gpt-oss-120b") == (0.0, 0.0)


def test_la_estimacion_crece_con_las_rondas_y_el_peor_caso_supera_al_tipico():
    chica, grande = estimar(5, 2, 2, 8, 40), estimar(5, 2, 4, 8, 40)
    assert grande["usd_tipico"] > chica["usd_tipico"] > 0
    assert grande["usd_peor_caso"] > grande["usd_tipico"]
    assert estimar(5, 2, 4, 0, 0)["usd_peor_caso"] == 0


def test_dry_run_imprime_el_costo_estimado_sin_llamar_a_nadie(capsys, monkeypatch):
    from scripts import atacante_adaptativo as script
    for llave in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(llave, raising=False)
    monkeypatch.setattr(script, "_cargar_env", lambda ruta: None)
    assert script.main(["--atacante", "anthropic/claude-fable-5-2", "--defensas", "none,layer2", "--rondas", "4",
                        "--limit", "5", "--dry-run"]) == 0
    texto = capsys.readouterr().out
    assert "claude-fable-5-2" in texto and "sin temperature" in texto
    assert "Costo estimado del atacante" in texto and "US$8 / US$40" in texto and "peor caso" in texto
    assert "Tope: US$5.00" in texto


def test_dry_run_de_un_atacante_gratis_no_habla_de_tope(capsys, monkeypatch):
    from scripts import atacante_adaptativo as script
    monkeypatch.setattr(script, "_cargar_env", lambda ruta: None)
    assert script.main(["--atacante", "groq/openai/gpt-oss-120b", "--limit", "2", "--dry-run"]) == 0
    texto = capsys.readouterr().out
    assert "US$0 (capa gratis" in texto and "Tope" not in texto


def test_dry_run_acepta_un_tope_y_precios_propios(capsys, monkeypatch):
    from scripts import atacante_adaptativo as script
    monkeypatch.setattr(script, "_cargar_env", lambda ruta: None)
    script.main(["--atacante", "anthropic/claude-fable-5-2", "--limit", "1", "--rondas", "1", "--tope-usd", "0.5",
                 "--precio-entrada", "10", "--precio-salida", "50", "--dry-run"])
    texto = capsys.readouterr().out
    assert "Tope: US$0.50" in texto and "US$10 / US$50" in texto and "OJO" in texto


def test_hay_semillas_para_la_corrida_de_fable():
    ids = {e["id"] for e in cargar(("es",)) if e.get("tipo") == "estafa"}
    assert {"cesion_de_factura", "hilo_secuestrado_cuenta", "jefe_mismo_dominio"} <= ids
    assert variante_maliciosa(_semilla())["correos"]
