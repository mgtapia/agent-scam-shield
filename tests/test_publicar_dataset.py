"""El script que arma el dataset para Hugging Face (#18), sin red ni token."""
from __future__ import annotations

import json

import yaml

from scamshield.scenarios import cargar
from scripts import publicar_dataset as pd


def test_arma_una_fila_por_escenario_e_idioma_y_la_tarjeta(tmp_path):
    pd.armar(tmp_path, "usuario/prueba")
    es = [json.loads(l) for l in (tmp_path / "data" / "es.jsonl").read_text(encoding="utf-8").splitlines()]
    en = [json.loads(l) for l in (tmp_path / "data" / "en.jsonl").read_text(encoding="utf-8").splitlines()]
    esperado = cargar()
    assert len(es) + len(en) == len(esperado)
    assert {r["id"] for r in es} == {r["id"] for r in en}
    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith("---\nlicense: mit\n")


def test_el_escenario_yaml_de_cada_fila_es_el_escenario_completo(tmp_path):
    pd.armar(tmp_path, "usuario/prueba")
    fila = json.loads((tmp_path / "data" / "es.jsonl").read_text(encoding="utf-8").splitlines()[0])
    esc = yaml.safe_load(fila["escenario_yaml"])
    assert esc["id"] == fila["id"] and esc["tipo"] == fila["tipo"] and "evaluacion" in esc


def test_los_conteos_de_la_tarjeta_salen_de_los_escenarios(tmp_path):
    pd.armar(tmp_path, "usuario/prueba")
    es = [e for e in cargar(("es",))]
    tarjeta = " ".join((tmp_path / "README.md").read_text(encoding="utf-8").split())
    estafas = sum(e["tipo"] == "estafa" for e in es)
    controles = sum(e["tipo"] == "control" for e in es)
    assert f"Hay {estafas} estafas y {controles} controles" in tarjeta
    assert "usuario/prueba" in tarjeta


def test_la_carpeta_armada_no_tiene_problemas(tmp_path):
    pd.armar(tmp_path, "usuario/prueba")
    assert pd.verificar(tmp_path) == []


def test_verificar_avisa_si_hay_algo_con_forma_de_llave(tmp_path):
    pd.armar(tmp_path, "usuario/prueba")
    (tmp_path / "README.md").write_text("hf_" + "x" * 30, encoding="utf-8")
    assert any("llaves" in p for p in pd.verificar(tmp_path))


def test_dry_run_no_sube_nada_ni_pide_token(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "subir", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe subir")))
    monkeypatch.setattr(pd, "_token", lambda: (_ for _ in ()).throw(AssertionError("no debe pedir el token")))
    assert pd.main(["--dry-run", "--salida", str(tmp_path)]) == 0


def test_sin_confirmar_no_sube_aunque_haya_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pd, "_token", lambda: "hf_token-de-prueba")
    monkeypatch.setattr(pd, "subir", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe subir")))
    assert pd.main(["--salida", str(tmp_path)]) == 2
    assert "--si-publicar" in capsys.readouterr().err


def test_confirmado_pero_sin_token_de_escritura_falla_con_un_mensaje(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pd, "_token", lambda: None)
    assert pd.main(["--si-publicar", "--salida", str(tmp_path)]) == 2
    assert "HF_TOKEN_ESCRITURA" in capsys.readouterr().err


def test_confirmado_y_con_token_sube_y_no_imprime_el_token(tmp_path, monkeypatch, capsys):
    visto = {}
    monkeypatch.setattr(pd, "_token", lambda: "hf_TOKEN-SECRETO")
    monkeypatch.setattr(pd, "subir", lambda carpeta, repo, token: visto.update(repo=repo, token=token) or "https://x/y")
    assert pd.main(["--si-publicar", "--repo", "u/d", "--salida", str(tmp_path)]) == 0
    salida = capsys.readouterr()
    assert visto["repo"] == "u/d" and "TOKEN-SECRETO" not in salida.out + salida.err
