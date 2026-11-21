"""Herramientas del agente sobre el mundo simulado, independientes del framework.

Las acciones sensibles (pagar, transferir, compartir_dato) pasan antes por la defensa activa.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..defenses.deposito import FUERA_DE_CANAL, es_motivo_fuera_de_canal
from .world import CORREO, HERRAMIENTA, LLAMADA, MCP, WEB, WHATSAPP, World

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
                f"[{c.id}] De: {c.de}\n"
                + (("Autenticación: " + ", ".join(f"{k.upper()} {v}" for k, v in c.autenticacion.items()) + "\n")
                   if c.autenticacion else "")
                + f"Asunto: {c.asunto}\n{c.cuerpo}" for c in self.w.correos
            )
        self.w.registrar("leer_correos", {}, "ok")
        return self.w.leer(CORREO, texto)

    def escuchar_llamadas(self) -> str:
        """Las llamadas recibidas, como transcripción. Cada una queda con origen LLAMADA (no confiable)."""
        if not self.w.llamadas:
            texto = "Sin llamadas."
        else:
            texto = "\n\n".join(
                f"[{c.id}] Llamada de: {c.de} (dice ser: {c.quien_dice_ser})\n{c.transcripcion}"
                for c in self.w.llamadas
            )
        self.w.registrar("escuchar_llamadas", {}, "ok")
        return self.w.leer(LLAMADA, texto)

    def leer_whatsapp(self) -> str:
        """Los mensajes de chat recibidos, con sus notas de voz y adjuntos como texto. Cada uno queda con origen WHATSAPP."""
        texto = "\n\n".join(m.completo() for m in self.w.chat) if self.w.chat else "Sin mensajes."
        self.w.registrar("leer_whatsapp", {}, "ok")
        return self.w.leer(WHATSAPP, texto)

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
    def pagar(self, destinatario: str, cuenta: str, monto: int, concepto: str = "", moneda: str = "",
              producto: str = "", cantidad: Optional[int] = None, recurrencia: str = "",
              cargos_extra: Optional[list[str]] = None) -> str:
        """Los campos de una compra (moneda, producto, cantidad, recurrencia, cargos extra) son opcionales y
        solo entran a los argumentos si vienen: así el mandato del dueño (#103) los compara con lo aprobado."""
        args = {"destinatario": destinatario, "cuenta": cuenta, "monto": int(monto), "concepto": concepto}
        compra = {"moneda": moneda, "producto": producto, "cantidad": cantidad, "recurrencia": recurrencia,
                  "cargos_extra": list(cargos_extra) if cargos_extra else None}
        args.update({k: v for k, v in compra.items() if v not in (None, "")})
        return self._sensible("pagar", args)

    def transferir(self, cuenta: str, monto: int, motivo: str = "", beneficiario: str = "") -> str:
        return self._sensible("transferir", {"cuenta": cuenta, "monto": int(monto), "motivo": motivo,
                                             "beneficiario": beneficiario})

    def compartir_dato(self, dato: str, destinatario: str) -> str:
        return self._sensible("compartir_dato", {"dato": dato, "destinatario": destinatario})

    def responder(self, a: str, mensaje: str) -> str:
        args = {"a": a, "mensaje": mensaje}
        bloqueo = self._revisar("responder", args)
        if bloqueo:
            return bloqueo
        self.w.registrar("responder", args, "enviado")
        return f"Mensaje enviado a {a}."

    # --- El banco: el libro de movimientos y el reverso (#129) ---
    def consultar_movimientos(self) -> str:
        """El libro de movimientos del banco. La glosa la escribe quien deposita: queda como no confiable."""
        if self.w.movimientos is None:
            texto = "El banco no entrega el libro de movimientos de esta cuenta."
        elif not self.w.movimientos:
            texto = "Sin movimientos."
        else:
            texto = "\n".join(_linea_de_movimiento(m) for m in self.w.movimientos)
        self.w.registrar("consultar_movimientos", {}, "ok")
        return self.w.leer(HERRAMIENTA, texto)

    def revertir_deposito(self, movimiento: str) -> str:
        """Devuelve un depósito por el reverso del banco: la plata vuelve a su cuenta de origen, a ninguna otra."""
        m = next((x for x in self.w.movimientos or [] if str(x.get("id")) == str(movimiento)), None)
        args = {"movimiento": str(movimiento), "monto": int(m.get("monto", 0)) if m else 0,
                "cuenta": str(m.get("origen", "")) if m else ""}
        bloqueo = self._revisar("revertir_deposito", args)
        if bloqueo:
            return bloqueo
        ya = any(a.herramienta == "revertir_deposito" and a.resultado == "ejecutada"
                 and a.args.get("movimiento") == args["movimiento"] for a in self.w.registro)
        if m is None or args["monto"] <= 0 or ya:
            motivo = ("ese depósito ya se revirtió" if ya
                      else "no hay ningún depósito con ese número en el libro del banco")
            self.w.registrar("revertir_deposito", args, "rechazada", motivo=motivo)
            return f"El banco no hizo el reverso: {motivo}."
        self.w.saldo -= args["monto"]
        self.w.registrar("revertir_deposito", args, "ejecutada")
        return f"Listo: el banco devolvió {_pesos(args['monto'])} a la cuenta de origen {args['cuenta']}."

    def avisar_contacto(self, mensaje: str) -> str:
        """Avisa al contacto de confianza que el dueño inscribió (un familiar)."""
        if not self.w.avisar("contacto", mensaje):
            return "El dueño no tiene un contacto de confianza inscrito."
        return f"Aviso enviado a {self.w.contacto_confianza.get('nombre', 'el contacto de confianza')}."

    def _revisar(self, nombre: str, args: dict) -> Optional[str]:
        """Pasa la acción por las defensas. Si una la retiene, la registra y devuelve el aviso para el agente.

        Si el motivo es una instrucción para salir del canal (#129), Grifter no puede frenar lo físico: avisa
        al dueño y al contacto de confianza antes de que la persona salga a la calle.
        """
        for defensa in self.defensas:
            motivo = defensa(self.w, nombre, args)
            if motivo:
                self.w.registrar(nombre, args, "bloqueada", bloqueada=True, motivo=motivo)
                if es_motivo_fuera_de_canal(motivo):
                    self.w.avisar("dueno", FUERA_DE_CANAL, por="grifter")
                    self.w.avisar("contacto", FUERA_DE_CANAL, por="grifter")
                return (f"ACCIÓN BLOQUEADA por la defensa: {motivo} "
                        "Pide confirmación al dueño antes de continuar.")
        return None

    def _sensible(self, nombre: str, args: dict) -> str:
        bloqueo = self._revisar(nombre, args)
        if bloqueo:
            return bloqueo
        if nombre in ("pagar", "transferir"):
            if args["monto"] > self.w.saldo:
                self.w.registrar(nombre, args, "saldo insuficiente")
                return "Saldo insuficiente."
            self.w.saldo -= args["monto"]
            self.w.registrar(nombre, args, "ejecutada")
            return f"Listo: se enviaron ${args['monto']:,} a la cuenta {args['cuenta']}.".replace(",", ".")
        self.w.registrar(nombre, args, "ejecutada")
        return f"Listo: se compartió el dato con {args['destinatario']}."


def _pesos(monto: int) -> str:
    return f"${monto:,}".replace(",", ".")


def _linea_de_movimiento(m: dict) -> str:
    monto = int(m.get("monto", 0))
    linea = f"[{m.get('id', '')}] {'Abono' if monto > 0 else 'Cargo'} de {_pesos(abs(monto))}"
    if m.get("origen"):
        linea += f" desde la cuenta {m['origen']}"
    if m.get("glosa"):
        linea += f". Glosa: {m['glosa']}"
    return linea
