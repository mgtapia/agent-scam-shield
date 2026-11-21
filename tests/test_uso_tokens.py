"""El conteo de tokens desde las transcripciones de Claude Code (scripts/uso_tokens.py)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "uso_tokens.py"
spec = importlib.util.spec_from_file_location("uso_tokens", RUTA)
ut = importlib.util.module_from_spec(spec)
sys.modules["uso_tokens"] = ut   # las dataclasses lo necesitan registrado antes de ejecutarlo
spec.loader.exec_module(ut)


def _linea(id_, ts, modelo="claude-opus-5-5", entrada=10, salida=5, lectura=100):
    return json.dumps({"timestamp": ts, "message": {"id": id_, "model": modelo, "usage": {
        "input_tokens": entrada, "output_tokens": salida, "cache_read_input_tokens": lectura,
        "cache_creation_input_tokens": 0}}})


def test_cuenta_una_vez_por_respuesta_y_desde_la_fecha(tmp_path):
    t = tmp_path / "sesion.jsonl"
    t.write_text("\n".join([
        json.dumps({"customTitle": "core-gerente"}),
        _linea("a", "2026-11-20T10:00:00Z"),          # antes del inicio: no cuenta
        _linea("b", "2026-11-21T02:00:00Z"),
        _linea("b", "2026-11-21T02:00:01Z"),          # mismo mensaje, otro bloque: no se repite
        _linea("c", "2026-11-21T03:00:00Z", modelo="<synthetic>"),
        _linea("d", "2026-11-21T04:00:00Z", modelo="claude-sonnet-5-5"),
    ]) + "\n", encoding="utf-8")
    d = ut.como_dict(ut.armar("2026-11-21T01:30:00Z", [str(t)], []))
    filas = {f["modelo"]: f for f in d["filas"]}
    assert set(filas) == {"claude-opus-5-5", "claude-sonnet-5-5"}
    assert filas["claude-opus-5-5"]["respuestas"] == 1 and filas["claude-opus-5-5"]["total"] == 115
    assert all(f["fuente"] == "Claude Code · coordinador" for f in d["filas"])  # el alias, no el nombre local
    assert d["total_tokens"] == 230


def test_el_costo_usa_precio_de_lista():
    u = ut.Uso(entrada=1_000_000, salida=1_000_000)
    assert u.costo("claude-opus-5-5") == 24.0
    assert u.costo("groq/openai/gpt-oss-20b") is None
