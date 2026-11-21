"""Carga de escenarios desde YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).parent


def cargar(idiomas: tuple[str, ...] = ("es", "en")) -> list[dict[str, Any]]:
    escenarios = []
    for idioma in idiomas:
        for ruta in sorted((RAIZ / idioma).glob("*.yaml")):
            with ruta.open(encoding="utf-8") as f:
                esc = yaml.safe_load(f)
            esc.setdefault("idioma", idioma)
            escenarios.append(esc)
    return escenarios
