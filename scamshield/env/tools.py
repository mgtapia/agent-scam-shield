"""Herramientas del agente sobre el mundo simulado, independientes del framework.

Las acciones sensibles (pagar, transferir, compartir_dato) pasan antes por la defensa activa.
"""
from __future__ import annotations

from typing import Callable, Optional

from .world import CORREO, MCP, WEB, World

# Una defensa recibe (mundo, herramienta, args) y devuelve None si deja pasar, o el motivo si bloquea.
Defensa = Callable[[World, str, dict], Optional[str]]

SENSIBLES = {"pagar", "transferir", "compartir_dato"}


class Herramientas:
    def __init__(self, world: World, defensas: list[Defensa] | None = None):
        self.w = world
        self.defensas = defensas or []

    # --- Lectura (todo lo leído queda con su origen) ---
    def leer_correos(self) -> str:
        if not self.w.correos:
            texto = "Bandeja vacía."
        else:
            texto = "\n\n".join(
                f"[{c.id}] De: {c.de}\nAsunto: {c.asunto}\n{c.cuerpo}" for c in self.w.correos
            )
        self.w.registrar("leer_correos", {}, "ok")
        return self.w.leer(CORREO, texto)

    def abrir_web(self, url: str) -> str:
        texto = self.w.paginas.get(url, f"Error 404: no se encontró {url}")
        self.w.registrar("abrir_web", {"url": url}, "ok")
        return self.w.leer(WEB, texto)

    def usar_mcp(self, herramienta: str, consulta: str = "") -> str:
        desc = self.w.mcp_herramientas.get(herramienta)
        if desc is None:
            return f"La herramienta MCP {herramienta} no existe."
        self.w.registrar("usar_mcp", {"herramienta": herramienta, "consulta": consulta}, "ok")
        return self.w.leer(MCP, desc)

    # --- Acciones sensibles ---
    def pagar(self, destinatario: str, cuenta: str, monto: int, concepto: str = "") -> str:
        return self._sensible("pagar", {"destinatario": destinatario, "cuenta": cuenta,
                                        "monto": int(monto), "concepto": concepto})

    def transferir(self, cuenta: str, monto: int, motivo: str = "", beneficiario: str = "") -> str:
        return self._sensible("transferir", {"cuenta": cuenta, "monto": int(monto), "motivo": motivo,
                                             "beneficiario": beneficiario})

    def compartir_dato(self, dato: str, destinatario: str) -> str:
        return self._sensible("compartir_dato", {"dato": dato, "destinatario": destinatario})

    def responder(self, a: str, mensaje: str) -> str:
        args = {"a": a, "mensaje": mensaje}
        for defensa in self.defensas:
            motivo = defensa(self.w, "responder", args)
            if motivo:
                self.w.registrar("responder", args, "bloqueada", bloqueada=True, motivo=motivo)
                return (f"ACCIÓN BLOQUEADA por la defensa: {motivo} "
                        "Pide confirmación al dueño antes de continuar.")
        self.w.registrar("responder", args, "enviado")
        return f"Mensaje enviado a {a}."

    def _sensible(self, nombre: str, args: dict) -> str:
        for defensa in self.defensas:
            motivo = defensa(self.w, nombre, args)
            if motivo:
                self.w.registrar(nombre, args, "bloqueada", bloqueada=True, motivo=motivo)
                return (f"ACCIÓN BLOQUEADA por la defensa: {motivo} "
                        "Pide confirmación al dueño antes de continuar.")
        if nombre in ("pagar", "transferir"):
            if args["monto"] > self.w.saldo:
                self.w.registrar(nombre, args, "saldo insuficiente")
                return "Saldo insuficiente."
            self.w.saldo -= args["monto"]
            self.w.registrar(nombre, args, "ejecutada")
            return f"Listo: se enviaron ${args['monto']:,} a la cuenta {args['cuenta']}.".replace(",", ".")
        self.w.registrar(nombre, args, "ejecutada")
        return f"Listo: se compartió el dato con {args['destinatario']}."
