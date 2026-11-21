"""Servidor MCP de prueba: un banco sandbox (ficticio).

`pagar` no mueve dinero: solo anota el pago en un JSONL. Sirve para ver qué pagos le llegaron al
banco después de pasar (o no) por Grifter.

Con `--clave-env NOMBRE`, el banco solo paga si esa variable de entorno tiene valor: es la credencial del banco, y vive
en la configuración del proxy (`env` de este servidor en grifter.yaml), nunca en el agente. Un agente que levante este
servidor por su cuenta, sin pasar por Grifter, no la tiene y el banco rechaza todo: falla cerrada (#102).

Uso: python -m scamshield.mcp.servidor_banco [--registro banco_sandbox.jsonl] [--clave-env BANCO_CLAVE]
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

NOMBRE = "banco-sandbox"


def crear_servidor(registro: Path, clave_env: str = "") -> FastMCP:
    servidor = FastMCP(NOMBRE, instructions="Banco sandbox: anota los pagos, no mueve dinero.")

    @servidor.tool()
    def pagar(destinatario: str, cuenta: str, monto: int) -> str:
        """Paga un monto en pesos a la cuenta del destinatario."""
        if clave_env and not os.environ.get(clave_env):
            return f"El banco rechazó el pago: falta la credencial {clave_env}. Solo Grifter la tiene."
        pago = {"ts": datetime.now(timezone.utc).isoformat(), "destinatario": destinatario,
                "cuenta": cuenta, "monto": monto}
        registro.parent.mkdir(parents=True, exist_ok=True)
        with registro.open("a", encoding="utf-8") as f:
            f.write(json.dumps(pago, ensure_ascii=False) + "\n")
        monto_txt = f"${int(monto):,}".replace(",", ".")
        return f"Pago anotado en el sandbox: {monto_txt} a {destinatario}, cuenta {cuenta}."

    return servidor


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registro", default="banco_sandbox.jsonl",
                        help="JSONL donde se anotan los pagos")
    parser.add_argument("--clave-env", default="",
                        help="variable de entorno con la credencial del banco; sin ella no se paga")
    args = parser.parse_args(argv)
    crear_servidor(Path(args.registro).resolve(), args.clave_env).run("stdio")


if __name__ == "__main__":
    main()
