"""Tope por cuenta en una ventana de 30 días, desde el registro de eventos del proxy (#149)."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from scamshield.mcp.ventana import EVENTOS_PAGADOS, esta_inscrita, leer_registro, motivo_ventana, pagado_en_ventana

AHORA = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
CUENTA, OTRA, ALERCE = "47-3310-9082", "55-8120-3344", "33-7741-2056"
TOPE, DIAS = 150_000, 30


def _fila(cuenta=CUENTA, monto=100_000, hace=1.0, evento="permitido", **extra):
    args = {"destinatario": "X", "cuenta": cuenta, "monto": monto}
    fila = {"ts": (AHORA - timedelta(days=hace)).isoformat(), "evento": evento, "herramienta": "pagar", "servidor": "banco"}
    fila.update({"args": args} if evento == "permitido" else {"args": args, "valor": cuenta, "motivo": "m", "mensaje": "m", "fuentes": []})
    fila.update(extra)
    return fila


def _motivo(filas, monto, cuenta=CUENTA, inscritas=None):
    return motivo_ventana(filas, {"destinatario": "X", "cuenta": cuenta, "monto": monto}, "cuenta", TOPE, DIAS,
                          inscritas or {}, AHORA)


def test_los_aportes_crecientes_del_catalogo_se_retienen_con_su_alerta():
    filas = [_fila(monto=120_000, hace=21), _fila(monto=140_000, hace=9, evento="aprobado_por_dueno")]
    motivo = _motivo(filas, 150_000)
    assert motivo and "llevas $410.000 a esta cuenta" in motivo and "este mes" in motivo


def test_el_primer_aporte_bajo_el_tope_pasa():
    assert _motivo([], TOPE) is None
    assert _motivo([], TOPE + 1) is not None


@pytest.mark.parametrize("semilla", range(60))
def test_retiene_exactamente_cuando_lo_de_la_ventana_mas_el_pago_pasa_el_tope(semilla):
    rng = random.Random(semilla)
    filas = [_fila(cuenta=rng.choice([CUENTA, "47 3310 9082", "47-3310-9082 "]), monto=rng.randint(1, 140) * 1000,
                   hace=rng.uniform(0, DIAS - 0.01), evento=rng.choice(EVENTOS_PAGADOS)) for _ in range(rng.randint(0, 4))]
    monto = rng.randint(1, 150) * 1000
    esperado = sum(f["args"]["monto"] for f in filas) + monto > TOPE
    assert (_motivo(filas, monto) is not None) == esperado, (filas, monto)


@pytest.mark.parametrize("semilla", range(30))
def test_lo_que_queda_fuera_de_la_ventana_o_no_se_pago_no_cuenta(semilla):
    rng = random.Random(semilla)
    filas = [_fila(monto=rng.randint(100, 400) * 1000, hace=rng.choice([DIAS + 0.1, DIAS + 15, 90, 400]))
             for _ in range(rng.randint(1, 3))]
    filas += [_fila(monto=400_000, hace=1, evento=e) for e in ("retenido", "retenido_sin_preguntar", "error_de_revision",
                                                              "servidor_inalcanzable", "capa2_apagada")]
    assert _motivo(filas, rng.randint(1, 150) * 1000) is None


def test_lo_pagado_a_otra_cuenta_no_se_suma():
    assert _motivo([_fila(cuenta=OTRA, monto=140_000)], 100_000) is None


def test_una_cuenta_inscrita_no_pasa_por_el_tope():
    inscritas = {"Rentas Alerce": f"Banco Litoral cta. cte. {ALERCE}"}
    filas = [_fila(cuenta=ALERCE, monto=450_000, hace=h) for h in (30, 1)]
    assert _motivo(filas, 450_000, cuenta=ALERCE, inscritas=inscritas) is None
    assert _motivo(filas, 450_000, cuenta=ALERCE) is not None   # sin inscribir, el mismo pago se retiene


def test_el_tope_cero_apaga_la_ventana():
    assert motivo_ventana([_fila(monto=900_000)], {"cuenta": CUENTA, "monto": 900_000}, "cuenta", 0, DIAS, {}, AHORA) is None


def test_un_monto_ilegible_a_una_cuenta_no_inscrita_se_retiene():
    for monto in ("mucho", None, float("inf"), True):
        assert _motivo([], monto) is not None, monto


@pytest.mark.parametrize("fila", [
    {}, {"evento": "permitido"}, {"evento": "permitido", "ts": "ayer", "args": {"cuenta": CUENTA, "monto": 900_000}},
    {"evento": "permitido", "ts": AHORA.isoformat(), "args": "cuenta"}, {"evento": "permitido", "ts": None},
    {"evento": "permitido", "ts": (AHORA + timedelta(days=3)).isoformat(), "args": {"cuenta": CUENTA, "monto": 900_000}},
    {"evento": "permitido", "ts": AHORA.isoformat(), "args": {"cuenta": CUENTA, "monto": "mucho"}},
])
def test_una_fila_ilegible_o_del_futuro_no_se_suma_ni_tumba_nada(fila):
    assert pagado_en_ventana([fila], CUENTA, DIAS, AHORA) == 0


def test_una_hora_sin_zona_se_toma_como_utc():
    fila = _fila(monto=100_000, hace=2)
    fila["ts"] = (AHORA - timedelta(days=2)).replace(tzinfo=None).isoformat()
    assert pagado_en_ventana([fila], CUENTA, DIAS, AHORA) == 100_000


def test_el_borde_de_la_ventana_es_inclusivo():
    assert pagado_en_ventana([_fila(hace=DIAS)], CUENTA, DIAS, AHORA) == 100_000
    assert pagado_en_ventana([_fila(hace=DIAS + 0.001)], CUENTA, DIAS, AHORA) == 0


# --- El registro en disco -----------------------------------------------------------------------------------------

def test_leer_registro_salta_lineas_rotas_y_el_archivo_que_no_existe(tmp_path):
    assert leer_registro(None) == [] and leer_registro(tmp_path / "no_hay.jsonl") == []
    ruta = tmp_path / "grifter_eventos.jsonl"
    ruta.write_text("\n".join([json.dumps(_fila(monto=120_000, hace=3)), "{rota", "", "[1, 2]",
                               json.dumps(_fila(monto=140_000, hace=2))]), encoding="utf-8")
    filas = leer_registro(ruta)
    assert len(filas) == 2 and pagado_en_ventana(filas, CUENTA, DIAS, AHORA) == 260_000


def test_esta_inscrita_mira_el_texto_de_la_cuenta_y_no_un_pedazo():
    assert esta_inscrita("33-7741-2056", {"Rentas": "cta. cte. 33-7741-2056"})
    assert not esta_inscrita("7741", {"Rentas": "cta. cte. 33-7741-2056"})   # un pedazo de otra cuenta no cuenta
    assert not esta_inscrita("33-7741-20", {"Rentas": "cta. cte. 33-7741-2056"})
    assert not esta_inscrita("", {"Rentas": "cta. cte. 33-7741-2056"})
