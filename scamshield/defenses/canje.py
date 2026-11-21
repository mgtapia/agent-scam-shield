"""Lo que vale plata sin ser un dato del dueño: el código de una tarjeta de regalo y el destinatario final que viaja
en la referencia de un pago (#142).

La capa 2 mira el **destino** de lo que sale y si lo que sale es un dato del dueño. Dos estafas pasan por el medio:

1. **Código de tarjeta de regalo.** El código lo genera la compra: no está en `datos_dueno`, llega por el correo o el
   resultado de la tienda. Un «soporte» pide «el código completo para activarla» y el agente lo manda con `responder`
   o `compartir_dato`. Un código de canje es plata al portador: quien lo tiene lo gasta.
   Regla: un código de canje que apareció en lo que leyó el agente (no en el encargo) solo sale a un destino que
   el dueño nombró en su encargo. Se reconoce un código por su forma (letras y números en grupos, o 10 dígitos o más) y por
   estar junto a una palabra de canje (`tarjeta de regalo`, `gift card`, `cupón`, `PIN`, `canje`...).

2. **Pago a un intermediario de confianza.** La pasarela está inscrita, así que la cuenta pasa. Pero el destinatario real
   va en la referencia o en el alias («abónalo a vidrios.tolhuen.pagos»), y esa referencia nadie la revisaba. Regla: un
   alias, un correo, una cuenta o una arroba que va en la referencia de un pago tiene que venir del dueño o de un registro
   confiable, igual que la cuenta de destino.

Límite honesto: se reconoce un código por su forma y su vecindad; uno escrito sin una palabra de canje cerca, en una
imagen o dictado, no se ve. Y un destinatario final escrito como un nombre («a nombre de Constructora Ñuble», sin alias
ni cuenta) tampoco se distingue de un concepto cualquiera: ahí manda la capa 3 (titular de la cuenta).
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional

from ..env.world import DUENO, origenes_en

_F = re.IGNORECASE

# Una palabra que dice «esto se canjea por plata o por un servicio».
_PALABRA_DE_CANJE = re.compile(
    r"tarjetas? de regalo|tarjetas? regalo|gift ?cards?|tarjetas? (?:de )?prepago|prepaid|cup[oó]n|vouchers?|\bpin\b|"
    r"canje|canjea|redeem|c[oó]digo de (?:activaci[oó]n|recarga|regalo|descuento)|activation code|recharge code|"
    r"saldo a favor|recarga", _F)

# La forma de un código: grupos con guion (GC-7QK4-92XM-LP38), grupos de cuatro (1234 5678 9012 3456) o una tirada larga.
_CODIGO = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"[A-Za-z0-9]{2,6}(?:-[A-Za-z0-9]{3,6}){1,5}"
    r"|(?:[A-Za-z0-9]{4}[ -]){2,5}[A-Za-z0-9]{3,4}"
    r"|[A-Za-z0-9]{10,}"
    r")(?![A-Za-z0-9])")

_ANTES, _DESPUES = 60, 140

# Los argumentos donde un pago lleva texto libre: ahí puede ir escondido el destinatario final.
CAMPOS_DE_REFERENCIA = {
    "concepto", "motivo", "referencia", "glosa", "alias", "nota", "comentario", "descripcion", "descripción",
    "beneficiario", "beneficiario_final", "reference", "memo", "note", "description", "beneficiary",
    "final_beneficiary", "purpose",
}

# Lo que en un texto libre señala a alguien a quien llega la plata.
_DESTINOS = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"                                  # correo
    r"|(?<![\w@])@[A-Za-z0-9_.]{3,}"                                 # @usuario
    r"|(?<![\w.])[A-Za-z0-9_-]{2,}(?:\.[A-Za-z0-9_-]{2,})+(?![\w.]*@)"   # alias o dominio con puntos
    r"|(?<!\d)\d{2,}(?:-\d{2,})+(?!\d)"                              # cuenta con guiones
    r"|(?<!\d)\d{8,}(?!\d)")                                         # cuenta sin guiones


def _norm(texto: object) -> str:
    from .layer2 import _norm as n   # import tardío: layer2 importa este módulo
    return n(texto)


def codigos_de_canje(leidos: Iterable[tuple[str, str]]) -> set[str]:
    """Los códigos de canje (normalizados) que aparecieron en lo que leyó el agente, sin contar lo que escribió el dueño."""
    codigos: set[str] = set()
    for origen, texto in leidos:
        if origen == DUENO:
            continue
        texto = str(texto)
        for palabra in _PALABRA_DE_CANJE.finditer(texto):
            ventana = texto[max(0, palabra.start() - _ANTES):palabra.end() + _DESPUES]
            for m in _CODIGO.finditer(ventana):
                crudo = m.group(0)
                limpio = _norm(crudo)
                if len(limpio) >= 8 and any(c.isdigit() for c in limpio):
                    codigos.add(limpio)
    return codigos


def _saliente(args: Mapping[str, Any], *nombres: Optional[str]) -> str:
    return " ".join(str(args.get(n, "")) for n in nombres if n)


def motivo_codigo(procedencia: Any, args: Mapping[str, Any], destino_arg: str, *textos: Optional[str]) -> Optional[str]:
    """Si lo que sale lleva un código de canje y el encargo no nombra el destino: el motivo de la retención."""
    from .layer2 import _variantes   # import tardío
    codigos = codigos_de_canje(getattr(procedencia, "leidos", None) or ())
    if not codigos:
        return None
    saliente = _saliente(args, *textos)
    junto = [_norm(saliente), *_variantes(saliente)]
    if not any(c in v for c in codigos for v in junto):
        return None
    destino = args.get(destino_arg)
    encargo = str(getattr(procedencia, "encargo", "") or "")
    if destino not in (None, "") and encargo and origenes_en([(DUENO, encargo)], str(destino)):
        return None   # el dueño pidió mandárselo a ese destino
    from .layer2 import citado
    return (f"Tu agente intentó mandar el código de una tarjeta de regalo (o de canje) a {citado(destino)}. "
            "Lo generó una compra y es plata para quien lo tenga: solo sale a quien el encargo nombra.")


def motivo_referencia(procedencia: Any, args: Mapping[str, Any], destino_arg: str) -> Optional[str]:
    """Si la referencia de un pago lleva un destinatario final que no viene del dueño: el motivo de la retención."""
    from .layer2 import ORIGENES_SEGUROS, _es_dato_del_dueno, citado
    cuenta = _norm(args.get(destino_arg, ""))
    for campo, valor in args.items():
        if str(campo).lower() not in CAMPOS_DE_REFERENCIA or not isinstance(valor, str):
            continue
        for m in _DESTINOS.finditer(valor):
            token = m.group(0).rstrip(".")
            if not any(c.isalpha() for c in token) and "-" not in token and len(_norm(token)) < 8:
                continue
            if _norm(token) == cuenta or _es_dato_del_dueno(procedencia, token):
                continue
            if procedencia.origenes_de(token) & ORIGENES_SEGUROS:
                continue
            return (f"La referencia del pago lleva a otro destinatario ({citado(token)}) que no viene del encargo "
                    "ni de las cuentas inscritas del dueño: el pago pasa por un intermediario y la plata terminaría ahí.")
    return None
