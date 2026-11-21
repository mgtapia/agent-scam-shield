"""Servidor mínimo de la demo: la página, los episodios y las etiquetas del dueño.

Uso, desde la raíz del repo:
    python -m demo.server                 # http://127.0.0.1:8765
    python -m demo.server --puerto 9000
    uvicorn demo.server:app --port 8765

Rutas:
    GET  /                      la página de los tres carriles
    GET  /episodios/...         los JSON de episodios (indice.json, <id>.json, episodios.js)
    POST /api/etiquetas         guarda la respuesta del dueño en demo/etiquetas.jsonl
    POST /api/alertas           pasa la alerta a notificar() (punto de enchufe para Telegram)
    GET  /api/salud             para comprobar que está arriba
"""
from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from demo.notificar import notificar

DEMO = Path(__file__).resolve().parent
ETIQUETAS = DEMO / "etiquetas.jsonl"
ELECCIONES = {"pagar_inscrita", "no_pagar", "pagar_igual"}

app = FastAPI(title="agent-scam-shield demo")
_candado = threading.Lock()


@app.get("/api/salud")
def salud() -> dict[str, Any]:
    episodios = sorted(p.name for p in (DEMO / "episodios").glob("*.json") if p.name != "indice.json")
    return {"ok": True, "episodios": len(episodios)}


@app.post("/api/etiquetas")
def guardar_etiqueta(etiqueta: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Una línea por respuesta del dueño, para entrenar el clasificador (#7)."""
    if etiqueta.get("eleccion") not in ELECCIONES:
        raise HTTPException(422, f"eleccion debe ser una de {sorted(ELECCIONES)}")
    fila = {**etiqueta, "recibida": datetime.now(timezone.utc).isoformat()}
    with _candado, ETIQUETAS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.post("/api/alertas")
def recibir_alerta(alerta: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return {"ok": True, "canales": notificar(alerta)}


# El montaje estático va al final: en «/» captura todo lo que no sea /api.
app.mount("/", StaticFiles(directory=DEMO, html=True), name="demo")


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="Servidor de la demo de agent-scam-shield")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8765)
    a = p.parse_args()
    print(f"Demo en http://{a.host}:{a.puerto}/")
    uvicorn.run(app, host=a.host, port=a.puerto)


if __name__ == "__main__":
    main()
