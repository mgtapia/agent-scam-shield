"""Depósito por error y reembolso de más: «te llegó plata, devuélvela» (#129).

Cuatro formas de la misma estafa:
1. **Comprobante falso:** «te transferí $500.000 por error, devuélvelos», con una imagen o un correo de comprobante,
   pero en la cuenta no llegó nada.
2. **Reembolso de más con acceso remoto:** el falso soporte «reembolsa» $50.000, edita la pantalla para que se vea
   $500.000 y pide la diferencia.
3. **Triangulación:** la plata llega de verdad desde una cuenta mula (robada a otra víctima) y piden «devolverla» a
   otra cuenta. La víctima termina lavando dinero.
4. **Fuera del canal:** «ve al banco, retira en efectivo, compra tarjetas de regalo o deposita en un cajero cripto».
   El último paso es físico y ningún agente lo ejecuta.

La defensa:
- **La verdad es el libro del banco, no el comprobante.** Una «devolución» por transferencia se compara con los
  movimientos reales: si no llegó nada, o llegó otro monto, el aviso lo dice («no llegó ningún depósito de
  $500.000; el comprobante es falso»).
- **Lo que llegó de verdad se devuelve solo por reverso al mismo origen** (`revertir_deposito`, sin argumento de
  cuenta). Una transferencia de «devolución», aun a la cuenta de origen, se retiene: el reverso es el canal.
- **Las instrucciones para salir del canal** (ir al banco, efectivo, tarjetas de regalo, cajero cripto, «no le cuentes
  a nadie») retienen lo que el agente haga hacia quien las mandó, y el mundo avisa al dueño y a un contacto de
  confianza con un mensaje simple (`FUERA_DE_CANAL`). Si la persona igual va al banco, Grifter no lo puede impedir:
  lo que hace es avisar a tiempo, a ella y a alguien de su familia.

Es opt-in: solo actúa si la procedencia trae el libro (`movimientos`, aunque esté vacío) o un `contacto_confianza`.
Es pura: no avisa a nadie, solo devuelve el motivo; el aviso lo hace quien ejecuta las herramientas.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, Optional

from ..env.world import CONFIABLE, DUENO, NO_CONFIABLES, origenes_en

PREFIJO = "Según el libro del banco"
FUERA_DE_CANAL = ("Esto es una estafa conocida. Nadie te va a pedir devolver plata en persona. "
                  "No vayas al banco por esto.")

PAGOS = ("pagar", "transferir")
_F = re.IGNORECASE

# Pedir de vuelta una plata que «llegó por error» o «de más».
DEVOLUCION = re.compile(
    r"devoluci[oó]n|devu[eé]lv|devolver|reembols|reintegr|por error|por equivocaci[oó]n|de m[aá]s|"
    r"refund|by mistake|in error|by accident|overpa|send (?:it |the money |them )?back|pay (?:it |me )?back|"
    r"return (?:it|the money|the funds|the difference)|the difference", _F)

# Sacar la plata del canal del banco: lo físico, lo que no deja rastro, y el aislamiento.
SENALES_FUERA_DE_CANAL = {
    "ir al banco": r"\bve al banco\b|\bvaya al banco\b|\banda al banco\b|\bir al banco\b|sucursal|"
                   r"\bgo to (?:the|your) bank\b|\bbank branch\b|\bin person\b|en persona",
    "efectivo": r"\bretir\w* (?:en|el) efectivo|\ben efectivo\b|\bcash\b|caja del almac[eé]n|"
                r"\bcorner[- ]store (?:till|counter)",
    "tarjetas de regalo": r"tarjetas? de regalo|gift ?cards?|tarjetas? de prepago|prepaid cards?",
    "cajero cripto": r"cajero (?:de )?(?:cripto|bitcoin)|\bcripto\w*|bitcoin|crypto ?atm|bitcoin atm|\bcrypto\b",
    "no le cuentes a nadie": r"no le (?:cuentes|digas|comentes) a nadie|no se lo (?:cuentes|digas) a nadie|"
                             r"don'?t tell anyone|do not tell anyone|keep (?:it|this) (?:between us|secret)",
}
_SENALES = {k: re.compile(v, _F) for k, v in SENALES_FUERA_DE_CANAL.items()}


def senales_fuera_de_canal(texto: str) -> list[str]:
    """Qué instrucciones para salir del canal trae un texto («ir al banco», «efectivo»...)."""
    return [k for k, p in _SENALES.items() if p.search(texto or "")]


def es_motivo_fuera_de_canal(motivo: Optional[str]) -> bool:
    return bool(motivo) and FUERA_DE_CANAL in str(motivo)


def politica_deposito(procedencia: Any, herramienta: str, args: Mapping[str, Any]) -> Optional[str]:
    """None si la acción puede seguir; si no, el motivo para el dueño (con `FUERA_DE_CANAL` si corresponde)."""
    movimientos = getattr(procedencia, "movimientos", None)
    contacto = getattr(procedencia, "contacto_confianza", None)
    if movimientos is None and not contacto:
        return None
    leidos = list(getattr(procedencia, "leidos", []) or [])
    no_confiables = [t for o, t in leidos if o in NO_CONFIABLES]
    senales = sorted({s for t in no_confiables for s in senales_fuera_de_canal(t)})
    fuera = f"{FUERA_DE_CANAL} (Pidieron: {', '.join(senales)}.)" if senales else ""

    if herramienta in PAGOS:
        destino = str(args.get("cuenta", ""))
        seguro = bool(origenes_en(leidos, destino) & {DUENO, CONFIABLE}) if destino else False
        texto_pago = " ".join(str(args.get(k, "")) for k in ("motivo", "concepto", "beneficiario", "destinatario"))
        # Es una devolución si el pago lo dice, o si va a un destino que no es del dueño después de que alguien
        # pidió devolver plata. Un pago a una cuenta inscrita, con su glosa, no lo es (el reembolso del comercio).
        devolucion = bool(DEVOLUCION.search(texto_pago)) or (
            not seguro and any(DEVOLUCION.search(t) for t in no_confiables))
        if devolucion and movimientos is not None:
            libro = f"{PREFIJO}: {_segun_el_libro(movimientos, destino, _monto(args.get('monto')))}"
            return f"{libro} {fuera}" if fuera else libro
        if fuera and not seguro:
            return fuera
        return None

    if herramienta == "responder" and senales:
        # Contestarle a quien pide sacar la plata del canal es coordinar ese paso: se retiene y se avisa.
        destino = str(args.get("a", ""))
        if not (origenes_en(leidos, destino) & {DUENO, CONFIABLE}):
            return fuera
    return None


def _segun_el_libro(movimientos: list[Mapping[str, Any]], destino: str, monto: int) -> str:
    abonos = [m for m in movimientos if _monto(m.get("monto")) > 0]
    if not abonos:
        return f"no llegó ningún depósito de {_pesos(monto)}; el comprobante es falso."
    iguales = [m for m in abonos if _monto(m.get("monto")) == monto]
    if not iguales:
        llegados = ", ".join(_pesos(_monto(m.get("monto"))) for m in abonos[:3])
        return (f"no llegó ningún depósito de {_pesos(monto)}: solo llegó {llegados}. Lo que muestra la pantalla o el "
                "comprobante no es el libro.")
    m = iguales[0]
    origen = str(m.get("origen", ""))
    if destino and not origenes_en([("libro", origen)], destino):
        return (f"el depósito {m.get('id', '')} de {_pesos(monto)} llegó desde la cuenta {origen}; devolverlo a otra "
                f"cuenta ({destino}) es triangulación. Lo que llegó de verdad se devuelve solo por reverso al mismo "
                "origen.")
    return (f"el depósito {m.get('id', '')} de {_pesos(monto)} es real: se devuelve por el reverso del banco "
            f"(revertir_deposito {m.get('id', '')}), no con una transferencia.")


def _monto(valor: Any) -> int:
    if valor is None or isinstance(valor, bool):
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    texto = re.sub(r"[.,]\d{1,2}$", "", unicodedata.normalize("NFKC", str(valor)).strip())
    signo = -1 if texto.startswith("-") else 1
    digitos = re.sub(r"\D", "", texto)
    return signo * int(digitos) if digitos else 0


def _pesos(monto: int) -> str:
    return f"${monto:,}".replace(",", ".")
