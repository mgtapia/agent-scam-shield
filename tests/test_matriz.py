"""scripts/correr_matriz.py sin red: la matriz según las llaves, que no se filtren y una corrida con mockllm."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "correr_matriz.py"
_spec = importlib.util.spec_from_file_location("correr_matriz", RUTA)
matriz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(matriz)

SECRETOS = {
    "GOOGLE_API_KEY": "valor-secreto-google-123",
    "GROQ_API_KEY": "valor-secreto-groq-456",
    "HF_TOKEN": "valor-secreto-hf-789",
    "ANTHROPIC_API_KEY": "valor-secreto-anthropic-000",
    "OPENAI_API_KEY": "valor-secreto-openai-111",
}


@pytest.fixture
def entorno(monkeypatch):
    """Entorno sin ninguna llave conocida y sin cargar ningún .env real."""
    for llave in matriz.MODELOS_POR_LLAVE:
        monkeypatch.delenv(llave, raising=False)
    monkeypatch.setattr(matriz, "cargar_dotenv", lambda ruta: None)
    return monkeypatch


def test_llaves_presentes_ignora_vacias_y_desconocidas():
    env = {"GOOGLE_API_KEY": "x", "GROQ_API_KEY": "", "HF_TOKEN": "   ", "OTRA_LLAVE": "y"}
    assert matriz.llaves_presentes(env) == ["GOOGLE_API_KEY"]
    assert matriz.modelos_disponibles(env) == matriz.MODELOS_POR_LLAVE["GOOGLE_API_KEY"]


def test_la_matriz_sale_de_las_llaves_presentes():
    env = {"GOOGLE_API_KEY": "x", "HF_TOKEN": "y"}
    modelos = matriz.modelos_disponibles(env)
    esperados = matriz.MODELOS_POR_LLAVE["GOOGLE_API_KEY"] + matriz.MODELOS_POR_LLAVE["HF_TOKEN"]
    assert modelos == esperados
    for llave in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        assert not set(matriz.MODELOS_POR_LLAVE[llave]) & set(modelos)

    celdas = matriz.armar_matriz(modelos, matriz.DEFENSAS, matriz.IDIOMAS)
    assert len(celdas) == len(matriz.DEFENSAS) * len(modelos) * len(matriz.IDIOMAS)
    assert {c[0] for c in celdas} == set(matriz.DEFENSAS)
    assert {c[1] for c in celdas} == set(modelos)
    assert {c[2] for c in celdas} == {"es", "en"}


def test_las_defensas_coinciden_con_la_tarea():
    from scamshield.evals.task import DEFENSAS

    assert set(matriz.DEFENSAS) == set(DEFENSAS)


def test_dry_run_usa_solo_proveedores_con_llave(entorno, capsys):
    entorno.setenv("GROQ_API_KEY", SECRETOS["GROQ_API_KEY"])
    assert matriz.main(["--dry-run", "--defensas", "none,both", "--idiomas", "es"]) == 0
    salida = capsys.readouterr().out
    assert "GROQ_API_KEY" in salida
    for modelo in matriz.MODELOS_POR_LLAVE["GROQ_API_KEY"]:
        assert modelo in salida
    for modelo in matriz.MODELOS_POR_LLAVE["GOOGLE_API_KEY"]:
        assert modelo not in salida


def test_nunca_imprime_el_valor_de_una_llave(entorno, capsys):
    for llave, valor in SECRETOS.items():
        entorno.setenv(llave, valor)
    assert matriz.main(["--dry-run"]) == 0
    salida = capsys.readouterr()
    for valor in SECRETOS.values():
        assert valor not in salida.out
        assert valor not in salida.err
    assert all(llave in salida.out for llave in SECRETOS)


def test_dotenv_se_carga_sin_imprimir_la_llave(monkeypatch, tmp_path, capsys):
    for llave in matriz.MODELOS_POR_LLAVE:
        monkeypatch.delenv(llave, raising=False)
    # setenv y luego delenv: así monkeypatch deja las llaves como estaban al terminar,
    # aunque load_dotenv las escriba en os.environ.
    for llave in ("HF_TOKEN", "GROQ_API_KEY"):
        monkeypatch.setenv(llave, "x")
        monkeypatch.delenv(llave)
    env = tmp_path / ".env"
    env.write_text(f"HF_TOKEN={SECRETOS['HF_TOKEN']}\nGROQ_API_KEY=\n", encoding="utf-8")

    assert matriz.main(["--dry-run", "--env", str(env)]) == 0
    salida = capsys.readouterr()
    assert SECRETOS["HF_TOKEN"] not in salida.out + salida.err
    assert matriz.MODELOS_POR_LLAVE["HF_TOKEN"][0] in salida.out
    assert matriz.MODELOS_POR_LLAVE["GROQ_API_KEY"][0] not in salida.out


def test_sin_llaves_ni_modelos_falla_claro(entorno, capsys):
    entorno.setenv("GROQ_API_KEY", "")
    assert matriz.main(["--dry-run"]) != 0
    err = capsys.readouterr().err
    assert "no hay ningún proveedor con llave" in err
    assert "GOOGLE_API_KEY" in err and "--modelos" in err


def test_rechaza_defensas_e_idiomas_desconocidos(entorno, capsys):
    assert matriz.main(["--modelos", "mockllm/model", "--defensas", "capa9", "--dry-run"]) == 2
    assert matriz.main(["--modelos", "mockllm/model", "--idiomas", "fr", "--dry-run"]) == 2


def test_corrida_real_con_mockllm(entorno, tmp_path, capsys):
    codigo = matriz.main([
        "--modelos", "mockllm/model",
        "--defensas", "layer2",
        "--idiomas", "es",
        "--limit", "1",
        "--log-dir", str(tmp_path),
        "--display", "none",
    ])
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "layer2" in salida and "mockllm/model" in salida and "success" in salida
    assert list(tmp_path.glob("*.eval")), "la corrida no dejó logs en log_dir"


def test_groq_corre_con_una_conexion_y_reintentos_por_su_limite_de_tokens():
    from scripts.correr_matriz import opciones_de_proveedor

    assert opciones_de_proveedor("groq/openai/gpt-oss-20b", 4) == {"max_connections": 1, "retry_on_error": 4}
    assert opciones_de_proveedor("groq/openai/gpt-oss-20b", None)["max_connections"] == 1
    # Los demás proveedores no cambian.
    assert opciones_de_proveedor("anthropic/claude-haiku-5-5", 4) == {"max_connections": 4}
    assert opciones_de_proveedor("google/gemini-3.5-flash", None) == {"max_connections": None}
