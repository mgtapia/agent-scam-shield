"""Servidor MCP de prueba: un banco sandbox (ficticio).

`pagar` no mueve dinero: solo anota el pago en un JSONL. Sirve para ver qué pagos le llegaron al
banco después de pasar (o no) por Grifter.

Uso: python -m scamshield.mcp.servidor_banco [--registro banco_sandbox.jsonl]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

NOMBRE = "banco-sandbox"


def crear_servidor(registro: Path) -> FastMCP:
    servidor = FastMCP(NOMBRE, instructions="Banco sandbox: anota los pagos, no mueve dinero.")

    @servidor.tool()
    def pagar(destinatario: str, cuenta: str, monto: int) -> str:
        """Paga un monto en pesos a la cuenta del destinatario."""
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
    args = parser.parse_args(argv)
    crear_servidor(Path(args.registro).resolve()).run("stdio")


if __name__ == "__main__":
    main()
