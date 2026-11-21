"""Arma y publica el dataset de escenarios en Hugging Face Hub (#18).

Un dataset con una fila por escenario y por idioma (es y en), más su tarjeta (`README.md` con el encabezado de
Hugging Face). Lo que se publica sale de los YAML de `scamshield/scenarios/`, sin tocarlos: los conteos de la tarjeta
se calculan de ahí, nunca se escriben a mano.

    python scripts/publicar_dataset.py --dry-run             # arma la carpeta y la muestra; no toca la red
    python scripts/publicar_dataset.py --repo USUARIO/grifter-estafas-chile   # sube de verdad

La subida usa el token `HF_TOKEN_ESCRITURA` del entorno o del `.env` (un token de escritura; el `HF_TOKEN` de
inferencia no sirve). El token nunca se imprime. Sin `--dry-run` el script pregunta primero con una línea
`--si-publicar` obligatoria: no sube nada por accidente.

Columnas: id, idioma, tipo (estafa o control), familia, dificultad, descripcion, encargo, tacticas (lista),
mecanismo, disposicion_correcta, par_de_control, y `escenario_yaml` con el escenario completo tal como está en el
repo (correos, llamadas, páginas, evaluación y anotaciones). Lo anidado va como texto porque su forma cambia de un
escenario a otro y el visor de Hugging Face exige columnas fijas.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import yaml

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scamshield.scenarios import RAIZ as RAIZ_ESCENARIOS  # noqa: E402
from scamshield.scenarios import cargar  # noqa: E402

REPO_POR_DEFECTO = "mgtapia/grifter-estafas-chile"
URL_CODIGO = "https://github.com/mgtapia/grifter"
SALIDA_POR_DEFECTO = RAIZ / "build" / "dataset_hf"


def fila(esc: dict[str, Any], texto_yaml: str) -> dict[str, Any]:
    a = esc.get("anotaciones") or {}
    return {
        "id": esc["id"], "idioma": esc["idioma"], "tipo": esc["tipo"],
        "familia": a.get("familia", ""), "dificultad": a.get("dificultad", ""),
        "descripcion": esc.get("descripcion", ""), "encargo": esc.get("encargo", ""),
        "tacticas": list(a.get("social_eng_tactics") or []), "mecanismo": a.get("fraud_mechanism", ""),
        "disposicion_correcta": a.get("correct_disposition", ""), "par_de_control": a.get("control_pair_id") or "",
        "escenario_yaml": texto_yaml,
    }


def filas() -> list[dict[str, Any]]:
    salida = []
    for esc in cargar():
        ruta = RAIZ_ESCENARIOS / esc["idioma"] / f"{esc['id']}.yaml"
        if not ruta.exists():   # el nombre del archivo no siempre es el id: se busca por contenido
            ruta = next(r for r in (RAIZ_ESCENARIOS / esc["idioma"]).glob("*.yaml")
                        if (yaml.safe_load(r.read_text(encoding="utf-8")) or {}).get("id") == esc["id"])
        salida.append(fila(esc, ruta.read_text(encoding="utf-8")))
    return salida


def estadisticas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    es = [r for r in rows if r["idioma"] == "es"]
    return {
        "filas": len(rows),
        "por_idioma_y_tipo": {f"{i}/{t}": n for (i, t), n in sorted(Counter((r["idioma"], r["tipo"]) for r in rows).items())},
        "estafas_por_idioma": len([r for r in es if r["tipo"] == "estafa"]),
        "controles_por_idioma": len([r for r in es if r["tipo"] == "control"]),
        "familias": sorted({r["familia"] for r in es if r["tipo"] == "estafa"}),
        "dificultades": dict(sorted(Counter(r["dificultad"] for r in es if r["tipo"] == "estafa").items())),
    }


def tarjeta(rows: list[dict[str, Any]], repo: str) -> str:
    est = estadisticas(rows)
    n_estafas, n_controles = est["estafas_por_idioma"], est["controles_por_idioma"]
    familias = ", ".join(f"`{f}`" for f in est["familias"])
    return f'''---
license: mit
language:
- es
- en
pretty_name: Grifter, estafas chilenas contra agentes de IA que pagan
size_categories:
- n<1K
task_categories:
- text-classification
tags:
- scam
- fraud
- ai-agents
- agent-security
- prompt-injection
- inspect-ai
- spanish
- chile
configs:
- config_name: default
  data_files:
  - split: es
    path: data/es.jsonl
  - split: en
    path: data/en.jsonl
---

# Grifter: estafas chilenas contra agentes de IA que pagan

El primer conjunto de estafas en español pensado para probar a un agente de IA que tiene acceso a dinero. Cada
escenario es una situación completa: el encargo del dueño, los correos, páginas, llamadas o herramientas MCP que el
agente lee, y la definición de qué es «caer» y qué es hacer bien la tarea. Hay {n_estafas} estafas y {n_controles}
controles legítimos, cada uno en español y en inglés ({est["filas"]} filas en total).

Código, la eval de Inspect y la defensa: <{URL_CODIGO}>.

## Qué hay en cada fila
| Columna | Qué es |
|---|---|
| `id`, `idioma` | el escenario y su idioma; el mismo `id` existe en `es` y en `en` |
| `tipo` | `estafa` o `control` (un caso legítimo parecido, para medir falsas alarmas) |
| `familia`, `dificultad` | la familia de la estafa y qué tan convincente es: `burda`, `media` o `convincente` |
| `descripcion`, `encargo` | de qué trata y lo que le pide el dueño al agente |
| `tacticas`, `mecanismo`, `disposicion_correcta`, `par_de_control` | anotaciones en el formato de FraudBench |
| `escenario_yaml` | el escenario completo, tal como lo lee la eval: correos, llamadas, páginas, evaluación y anotaciones |

Familias de estafa: {familias}.

## Cómo se usa
Con la eval de Inspect del repositorio (clonando el código):

```bash
inspect eval scamshield/evals/task.py --model anthropic/claude-haiku-5-5 -T defense=none
```

O para leer los escenarios directamente:

```python
import yaml
from datasets import load_dataset

filas = load_dataset("{repo}", split="es")
escenario = yaml.safe_load(filas[0]["escenario_yaml"])
print(escenario["encargo"], escenario["evaluacion"])
```

## Cómo se escribieron
Los escribió el equipo, con ayuda de modelos de lenguaje, inspirándose en tipos de estafa conocidos (cambio de cuenta
de un proveedor, falso banco, falso familiar, multas y devoluciones falsas, inyección en descripciones de herramientas,
espionaje industrial, llamadas y buzones de voz). Algunas estafas vienen en tres niveles de dificultad. Los escenarios
son datos fijos, y el puntaje sale de lo que el agente hace (dónde terminó el dinero o el dato), no de lo que dice.

## Limitaciones
- **Pocos escenarios.** Son decenas, no miles: sirven para comparar defensas y detectar fallas, no para estimar una
  tasa nacional de estafas. Las tasas se reportan con intervalo de confianza; con tan pocas muestras es ancho.
- **Escritos por un solo equipo.** Un atacante real se adapta; el repositorio trae un atacante adaptativo aparte, pero
  este dataset es estático.
- **Es Chile.** Los bancos, RUT, cuentas y modismos son chilenos y ficticios. No se probó en otros países.
- **Las defensas se ajustaron mirando estos escenarios.** Las cifras de la defensa sobre este mismo conjunto son
  optimistas; el repositorio explica cómo se separaron las familias para medir sin trampa.

## Uso ético
Todo es ficticio: marcas, personas, empresas, dominios, cuentas y RUT (los RUT tienen el dígito verificador malo a
propósito). Los nombres de pila son de gente conocida de tecnología, sin apellidos. El conjunto existe para
**endurecer agentes**, no para atacar a nadie: no contiene datos de víctimas reales ni de estafadores reales.

## Licencia y atribución
MIT. El formato de anotación sigue el de FraudBench (MIT, Sierra Research); el detalle está en el `NOTICE.md` del
repositorio. No se copian datos con licencia no comercial.

## Cómo citarlo
```bibtex
@misc{{grifter2026,
  title  = {{Grifter: estafas chilenas contra agentes de IA que pagan}},
  author = {{Equipo de Grifter}},
  year   = {{2026}},
  url    = {{{URL_CODIGO}}}
}}
```
'''


def armar(carpeta: Path, repo: str) -> list[Path]:
    """Escribe la carpeta del dataset (data/es.jsonl, data/en.jsonl y README.md) y devuelve los archivos."""
    rows = filas()
    (carpeta / "data").mkdir(parents=True, exist_ok=True)
    salida = []
    for idioma in ("es", "en"):
        ruta = carpeta / "data" / f"{idioma}.jsonl"
        ruta.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows if r["idioma"] == idioma),
                        encoding="utf-8", newline="\n")
        salida.append(ruta)
    leeme = carpeta / "README.md"
    leeme.write_text(tarjeta(rows, repo), encoding="utf-8", newline="\n")
    salida.append(leeme)
    return salida


def verificar(carpeta: Path) -> list[str]:
    """Problemas de la carpeta armada; vacío si está bien."""
    problemas = []
    es = [json.loads(l) for l in (carpeta / "data" / "es.jsonl").read_text(encoding="utf-8").splitlines()]
    en = [json.loads(l) for l in (carpeta / "data" / "en.jsonl").read_text(encoding="utf-8").splitlines()]
    if {r["id"] for r in es} != {r["id"] for r in en}:
        problemas.append("los ids de es y en no coinciden")
    for r in es + en:
        if not r["escenario_yaml"].strip():
            problemas.append(f"{r['id']}: sin escenario_yaml")
    texto = (carpeta / "data" / "es.jsonl").read_text(encoding="utf-8") + (carpeta / "README.md").read_text(encoding="utf-8")
    for prohibido in ("hf_", "sk-ant", "sk-proj", "TELEGRAM_BOT_TOKEN="):
        if prohibido in texto:
            problemas.append(f"aparece «{prohibido}»: revisa que no haya llaves")
    return problemas


def _token() -> Optional[str]:
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env", override=False)
    return os.environ.get("HF_TOKEN_ESCRITURA", "").strip() or None


def subir(carpeta: Path, repo: str, token: str) -> str:
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo_id=repo, repo_type="dataset", exist_ok=True)
    api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=str(carpeta),
                      commit_message="Escenarios de Grifter (es y en) y su tarjeta")
    return f"https://huggingface.co/datasets/{repo}"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Arma y publica el dataset de Grifter en Hugging Face Hub.")
    p.add_argument("--repo", default=REPO_POR_DEFECTO, help="usuario/nombre del dataset en el Hub")
    p.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO, help="carpeta donde se arma el dataset")
    p.add_argument("--dry-run", action="store_true", help="solo arma la carpeta y la verifica: no toca la red")
    p.add_argument("--si-publicar", action="store_true", help="confirma la subida real al Hub")
    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    archivos = armar(a.salida, a.repo)
    est = estadisticas(filas())
    print(f"Dataset armado en {a.salida}")
    for ruta in archivos:
        print(f"  {ruta.relative_to(a.salida)}  {ruta.stat().st_size:,} bytes".replace(",", "."))
    print(f"  {est['filas']} filas: {est['por_idioma_y_tipo']}")
    problemas = verificar(a.salida)
    for pr in problemas:
        print(f"  PROBLEMA: {pr}", file=sys.stderr)
    if problemas:
        return 1
    if a.dry_run:
        print("Dry run: no se subió nada.")
        return 0
    if not a.si_publicar:
        print("Falta --si-publicar para subir de verdad (o usa --dry-run).", file=sys.stderr)
        return 2
    token = _token()
    if not token:
        print("Falta HF_TOKEN_ESCRITURA (un token de escritura de Hugging Face) en el entorno o en el .env.",
              file=sys.stderr)
        return 2
    print("Publicado en", subir(a.salida, a.repo, token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
