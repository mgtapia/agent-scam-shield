"""Plan B del atacante (#131): modelos abiertos (Qwen por Groq, DeepSeek y Kimi por OpenRouter) si un Claude se niega.

Todo sin red y sin gastar: el costo sale de `--dry-run` y el resto, de modelos simulados y de archivos de ejemplo.
"""
from __future__ import annotations

import json

import pytest

from scamshield.attacker.costo import PRECIOS, config_para, llave_de, piensa_siempre, precio_de
from scamshield.attacker.resultados import SEP_ATACANTE, curvas, svg
from scripts import atacante_adaptativo as script
from tests.test_atacante import CRITICO_2, JUEZ_OK, _intento
from tests.test_atacante_fable import FalsoClaude, _correr

OPENROUTER = ("openrouter/deepseek/deepseek-chat", "openrouter/moonshotai/kimi-k2")


def _fila(atacante, defensa="none", ronda=0, exito=False, escenario="e1", modelo="victima"):
    f = {"modelo": modelo, "defensa": defensa, "escenario": escenario, "idioma": "es", "ronda": ronda, "valida": True,
         "exito": exito, "intento": exito, "se_nego": False, "error": ""}
    if atacante is not None:
        f["atacante"] = atacante
    return f


# --- Precios y llaves ---

def test_los_modelos_abiertos_tienen_precio_y_los_gratis_no():
    for m in OPENROUTER:
        ent, sal = precio_de(m)
        assert ent > 0 and sal > ent
    assert precio_de("groq/qwen/qwen3.8-27b") == (0.0, 0.0)   # capa gratis: el límite es la cuota
    assert {"deepseek", "kimi"} <= set(PRECIOS)


@pytest.mark.parametrize("modelo,llave", [("openrouter/deepseek/deepseek-chat", "OPENROUTER_API_KEY"),
                                          ("groq/qwen/qwen3.8-27b", "GROQ_API_KEY"),
                                          ("anthropic/claude-fable-5-2", "ANTHROPIC_API_KEY"), ("mockllm/model", "")])
def test_cada_modelo_sabe_cual_es_su_llave(modelo, llave):
    assert llave_de(modelo) == llave


def test_un_modelo_abierto_se_llama_con_temperature_normal():
    assert not any(piensa_siempre(m) for m in (*OPENROUTER, "groq/qwen/qwen3.8-27b"))
    assert config_para(OPENROUTER[0], 1.0, 600, False).temperature == 1.0


# --- El script ---

def _sin_llaves(monkeypatch):
    monkeypatch.setattr(script, "_cargar_env", lambda ruta: None)
    for v in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(v, raising=False)


def test_dry_run_del_plan_b_imprime_cada_atacante_su_costo_y_el_total(capsys, monkeypatch):
    _sin_llaves(monkeypatch)
    assert script.main(["--plan-b", "--defensas", "none,layer2", "--limit", "3", "--rondas", "3", "--dry-run"]) == 0
    t = capsys.readouterr().out
    assert "3 estafas × 2 defensas × 4 rondas" in t
    for m in script.PLAN_B:
        assert f"Atacante: {m}" in t
    assert "US$0 (capa gratis" in t                                  # Qwen por Groq
    assert t.count("Costo estimado del atacante") == 2               # DeepSeek y Kimi
    assert "Total de los 3 atacantes" in t
    assert "define OPENROUTER_API_KEY" in t and "define GROQ_API_KEY" in t


def test_el_dry_run_no_imprime_ningun_valor_de_llave(capsys, monkeypatch):
    _sin_llaves(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-SECRETO-123")
    script.main(["--plan-b", "--limit", "1", "--dry-run"])
    t = capsys.readouterr().out
    assert "SECRETO" not in t and "define OPENROUTER_API_KEY" not in t   # existe: no avisa, y nunca la imprime


def test_atacantes_a_mano_separados_por_coma(capsys, monkeypatch):
    _sin_llaves(monkeypatch)
    script.main(["--atacante", "groq/qwen/qwen3.8-27b,openrouter/deepseek/deepseek-chat", "--limit", "1", "--dry-run"])
    t = capsys.readouterr().out
    assert "Atacante: groq/qwen/qwen3.8-27b" in t and "Atacante: openrouter/deepseek/deepseek-chat" in t
    assert "kimi" not in t


def test_sin_llave_una_corrida_real_se_detiene_antes_de_gastar(monkeypatch):
    _sin_llaves(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    with pytest.raises(SystemExit, match="falta la llave de .*OPENROUTER_API_KEY"):
        script.main(["--plan-b", "--limit", "1", "--rondas", "1"])


def test_plan_b_y_atacante_o_salida_con_varios_son_excluyentes(monkeypatch):
    _sin_llaves(monkeypatch)
    with pytest.raises(SystemExit, match="excluyentes"):
        script.main(["--plan-b", "--atacante", "groq/x", "--dry-run"])
    with pytest.raises(SystemExit, match="no uses --salida"):
        script.main(["--plan-b", "--salida", "x.jsonl", "--dry-run"])


# --- El atacante en las filas y las curvas lado a lado ---

def test_cada_fila_dice_que_atacante_la_escribio(tmp_path):
    atacante = FalsoClaude([_intento("Cuenta nueva 77-0193-5520"), JUEZ_OK, CRITICO_2], nombre="openrouter/deepseek/deepseek-chat")
    _, res = _correr(tmp_path, atacante, defensas=("none",))
    assert {f["atacante"] for f in res["filas"]} == {"openrouter/deepseek/deepseek-chat"}


def test_con_un_solo_atacante_las_curvas_quedan_como_siempre():
    c = curvas([_fila("A"), _fila("A", ronda=1, exito=True), _fila("A", defensa="layer2")])
    assert list(c) == ["victima"] and set(c["victima"]) == {"none", "layer2"}


def test_con_varios_atacantes_hay_un_panel_por_atacante_y_victima():
    filas = [_fila("groq/qwen", ronda=0), _fila("groq/qwen", ronda=1, exito=True),
             _fila("openrouter/deepseek", ronda=0), _fila("openrouter/deepseek", ronda=1),
             _fila("openrouter/deepseek", defensa="layer2", ronda=1)]
    c = curvas(filas)
    assert set(c) == {f"groq/qwen {SEP_ATACANTE} victima", f"openrouter/deepseek {SEP_ATACANTE} victima"}
    assert c[f"groq/qwen {SEP_ATACANTE} victima"]["none"]["exitos"] == [0, 1]
    assert c[f"openrouter/deepseek {SEP_ATACANTE} victima"]["none"]["exitos"] == [0, 0]
    dibujo = svg(c)
    assert "groq/qwen" in dibujo and "openrouter/deepseek" in dibujo   # los dos paneles, lado a lado


def test_una_corrida_vieja_sin_atacante_se_mezcla_con_una_nueva_sin_romper():
    c = curvas([_fila(None), _fila("A")])
    assert len(c) == 2 and any("atacante sin nombre" in k for k in c)


def test_las_negativas_de_un_atacante_se_cuentan_por_panel():
    f = _fila("anthropic/claude-fable-5-2")
    f["se_nego"], f["valida"] = True, False
    c = curvas([f, _fila("groq/qwen")])
    assert c[f"anthropic/claude-fable-5-2 {SEP_ATACANTE} victima"]["none"]["rechazos_atacante"] == 1
    assert c[f"groq/qwen {SEP_ATACANTE} victima"]["none"]["rechazos_atacante"] == 0


# --- La vista Resultados ---

def test_resultados_separa_las_series_por_atacante(tmp_path):
    from scripts import resultados_demo as rd
    filas = [_fila("groq/qwen"), _fila("groq/qwen", ronda=1, exito=True), _fila("openrouter/deepseek"),
             _fila("openrouter/deepseek", ronda=1)]
    ruta = tmp_path / "plan_b_curvas.json"
    ruta.write_text(json.dumps(curvas(filas)), encoding="utf-8")
    a = rd.atacante(elegida=ruta)
    assert a["estado"] == "ok"
    assert {s["atacante"] for s in a["series"]} == {"groq/qwen", "openrouter/deepseek"}
    assert {s["modelo"] for s in a["series"]} == {"victima"}
    por = {s["atacante"]: s for s in a["series"]}
    assert por["groq/qwen"]["exitos"] == [0, 1] and por["openrouter/deepseek"]["exitos"] == [0, 0]


def test_resultados_con_un_atacante_no_agrega_el_campo(tmp_path):
    from scripts import resultados_demo as rd
    ruta = tmp_path / "una_curvas.json"
    ruta.write_text(json.dumps(curvas([_fila("A"), _fila("A", ronda=1)])), encoding="utf-8")
    assert all("atacante" not in s for s in rd.atacante(elegida=ruta)["series"])
