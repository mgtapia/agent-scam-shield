"""El runner de AgentDojo banking: el plan sin inspect_evals y una corrida guionada, sin modelo."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "agentdojo_banking.py"


def _runner():
    spec = importlib.util.spec_from_file_location("agentdojo_banking", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_dry_run_no_importa_inspect_evals(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "inspect_evals", None)  # si se importara, fallaría
    _runner().main(["--dry-run", "--model", "openai/x"])
    salida = capsys.readouterr().out
    assert salida.count("workspace': 'banking'") == 4
    assert salida.count('politicas_capa2("agentdojo_banking")') == 2


def test_corrida_guionada_arma_la_tabla(tmp_path, capsys):
    pytest.importorskip("inspect_evals.agentdojo")
    _runner().main(["--agente", "guionado", "--log-dir", str(tmp_path),
                    "--user-tasks", "0,3", "--injection-tasks", "0"])
    tabla = (tmp_path / "tabla.md").read_text(encoding="utf-8")
    filas = {f.split("|")[1].strip(): [c.strip() for c in f.split("|")[2:-1]]
             for f in tabla.splitlines() if f.startswith("| sin_defensa") or f.startswith("| capa2")}
    # Columnas: utilidad sin ataque, utilidad con ataque, ASR, seguridad, rechazos, muestras.
    assert filas["sin_defensa"][0] == "100.0 %" and filas["sin_defensa"][2] == "100.0 %"
    assert filas["capa2"][2] == "0.0 %"
    # La cuenta leída de la boleta (u0) se frena; la que escribe el dueño (u3) no.
    assert "banking-u0" in tabla.splitlines()[-1] and "banking-u3" not in tabla.splitlines()[-1]
