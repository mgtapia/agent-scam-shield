"""Sincronización con repositorios Git locales, sin red ni credenciales."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sincronizar_hackathon.sh"
METADATA = {
    "GUIA.md": "# Guía de Grifter\n",
    "platanus-hack-project.jsonc": '{"name": "Grifter"}\n',
    "project-description.md": "Escudo para agentes de IA que pagan.\n",
}


def _git(ruta: Path, *argumentos: str) -> str:
    resultado = subprocess.run(
        ["git", "-C", str(ruta), *argumentos],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return resultado.stdout.strip()


def _identidad_local(ruta: Path) -> None:
    _git(ruta, "config", "user.name", "Equipo de prueba")
    _git(ruta, "config", "user.email", "equipo@example.invalid")
    _git(ruta, "config", "commit.gpgsign", "false")


def _confirmar(ruta: Path, mensaje: str, cambios: dict[str, str | None]) -> str:
    for nombre, contenido in cambios.items():
        archivo = ruta / nombre
        if contenido is None:
            archivo.unlink()
        else:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(contenido, encoding="utf-8")
    _git(ruta, "add", "--all")
    _git(ruta, "commit", "-m", mensaje)
    return _git(ruta, "rev-parse", "HEAD")


@dataclass(frozen=True)
class Repositorios:
    origen: Path
    destino: Path
    trabajo: Path


@pytest.fixture
def repositorios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repositorios:
    # Aísla las identidades y preferencias del usuario; Git solo admite rutas locales.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    for variable in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT"):
        monkeypatch.delenv(variable, raising=False)

    origen = tmp_path / "origen"
    destino = tmp_path / "destino.git"
    trabajo = tmp_path / "trabajo"
    _git(tmp_path, "init", "--initial-branch=main", str(origen))
    _identidad_local(origen)
    _confirmar(
        origen,
        "Integra el código y la metadata de la hackathon",
        {**METADATA, "codigo.py": "version = 1\n", "obsoleto.txt": "Archivo anterior\n"},
    )
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(destino))
    _git(origen, "push", str(destino), "main")
    _git(tmp_path, "clone", "--no-hardlinks", str(destino), str(trabajo))
    _identidad_local(trabajo)
    return Repositorios(origen=origen, destino=destino, trabajo=trabajo)


def _sincronizar(repositorios: Repositorios, destino: str = "origin") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), str(repositorios.origen), destino],
        cwd=repositorios.trabajo,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _comprobar_metadata(destino: Path) -> None:
    for nombre, contenido in METADATA.items():
        assert _git(destino, "show", f"main:{nombre}") == contenido.strip()


@pytest.mark.parametrize("usar_ruta", [False, True], ids=["remoto", "ruta-local"])
def test_avanza_al_sha_exacto_del_origen_y_conserva_metadata_integrada(repositorios, usar_ruta):
    nuevo_sha = _confirmar(repositorios.origen, "Actualiza el código", {"codigo.py": "version = 2\n"})

    destino = str(repositorios.destino) if usar_ruta else "origin"
    resultado = _sincronizar(repositorios, destino)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert _git(repositorios.destino, "rev-parse", "main") == nuevo_sha
    assert _git(repositorios.destino, "show", "main:codigo.py") == "version = 2"
    _comprobar_metadata(repositorios.destino)


def test_repetir_la_sincronizacion_no_crea_commits(repositorios):
    nuevo_sha = _confirmar(repositorios.origen, "Actualiza el código", {"codigo.py": "version = 2\n"})
    primera = _sincronizar(repositorios)
    assert primera.returncode == 0, primera.stdout + primera.stderr
    historial = _git(repositorios.destino, "rev-list", "main")

    segunda = _sincronizar(repositorios)

    assert segunda.returncode == 0, segunda.stdout + segunda.stderr
    assert _git(repositorios.destino, "rev-parse", "main") == nuevo_sha
    assert _git(repositorios.destino, "rev-list", "main") == historial


def test_rechaza_historiales_divergentes_y_conserva_el_destino(repositorios):
    _confirmar(repositorios.origen, "Cambio del origen", {"codigo.py": "version = 2\n"})
    sha_destino = _confirmar(repositorios.trabajo, "Cambio propio del destino", {"solo_destino.txt": "Conservar\n"})
    _git(repositorios.trabajo, "push", "origin", "main")
    historial = _git(repositorios.destino, "rev-list", "main")

    resultado = _sincronizar(repositorios)

    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert _git(repositorios.destino, "rev-parse", "main") == sha_destino
    assert _git(repositorios.destino, "rev-list", "main") == historial
    assert _git(repositorios.destino, "show", "main:solo_destino.txt") == "Conservar"
    _comprobar_metadata(repositorios.destino)


def test_rechaza_un_destino_adelantado_sin_retroceder_su_main(repositorios):
    sha_destino = _confirmar(repositorios.trabajo, "Adelanta el destino", {"solo_destino.txt": "Conservar\n"})
    _git(repositorios.trabajo, "push", "origin", "main")

    resultado = _sincronizar(repositorios)

    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert _git(repositorios.destino, "rev-parse", "main") == sha_destino
    assert _git(repositorios.destino, "show", "main:solo_destino.txt") == "Conservar"


def test_replica_la_eliminacion_de_archivos_del_origen(repositorios):
    nuevo_sha = _confirmar(repositorios.origen, "Elimina un archivo obsoleto", {"obsoleto.txt": None})

    resultado = _sincronizar(repositorios)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert _git(repositorios.destino, "rev-parse", "main") == nuevo_sha
    assert "obsoleto.txt" not in _git(repositorios.destino, "ls-tree", "-r", "--name-only", "main").splitlines()
    _comprobar_metadata(repositorios.destino)
