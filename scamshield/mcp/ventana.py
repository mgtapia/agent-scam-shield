"""Tope por cuenta en una ventana de 30 días, alimentado con el registro de eventos de Grifter (#149).

La capa 3 de la simulación suma lo que se le pagó a un titular con `world.pagos_previos`. El proxy MCP no tiene el banco ni el
registro de titulares, pero tiene `grifter_eventos.jsonl`: cada llamada sensible que dejó pasar (`permitido`) o que el dueño
aprobó (`aprobado_por_dueno`) queda con su hora, su cuenta y su monto. Con eso se suma lo ya pagado a una cuenta en los
últimos `ventana_dias`, sin depender del banco.

Quién pasa por el tope: una cuenta que el dueño **no tiene inscrita** (llegó por el encargo, o el dueño aprobó una vez). Una
inscrita (el arriendo mensual) sale sin fricción. Lo retenido no se suma, porque no se pagó.

Límites honestos:
- Se suma por **cuenta**, no por RUT del titular: sin el banco no se sabe que dos cuentas son de la misma persona. Quien
  parte un monto entre cuentas de un mismo titular no lo salta en el proxy; la capa 3 de la simulación sí lo ve.
- La ventana depende de que el registro exista y de que el agente no pueda escribirlo. Sin registro, no hay historial y el
  tope solo ve lo que viene en esta llamada.
- Un pago que el dueño aprueba cuenta como pagado: el mes siguiente pide confirmar de nuevo si pasa el tope.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from ..env.world import CONFIABLE, origenes_en

EVENTOS_PAGADOS = ("permitido", "aprobado_por_dueno")
CLAVES_MONTO = ("monto", "amount", "importe", "valor", "total")


def _norm(texto: Any) -> str:
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())


def _monto(args: Mapping[str, Any]) -> Optional[int]:
    for k, v in args.items():
        if str(k).lower() in CLAVES_MONTO:
            if isinstance(v, bool):
                return None
            if isinstance(v, (int, float)):
                return abs(int(v)) if v == v and abs(v) != float("inf") else None
            digitos = "".join(ch for ch in str(v) if ch.isdigit())
            return int(digitos) if digitos else None
    return None


def _hora(ts: Any) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def leer_registro(ruta: Optional[Path]) -> list[dict[str, Any]]:
    """Las líneas legibles del registro; una línea rota se salta (el registro se escribe a medias si el proceso cae)."""
    if ruta is None or not Path(ruta).exists():
        return []
    filas = []
    for linea in Path(ruta).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            fila = json.loads(linea)
        except ValueError:
            continue
        if isinstance(fila, dict):
            filas.append(fila)
    return filas


def pagado_en_ventana(filas: Iterable[Mapping[str, Any]], cuenta: str, dias: int,
                      ahora: Optional[datetime] = None, destino: str = "cuenta") -> int:
    """Lo que el registro dice que ya se le pagó a esa cuenta en los últimos `dias` días (eventos pagados, hora legible)."""
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(days=dias)
    buscada = _norm(cuenta)
    if not buscada:
        return 0
    total = 0
    for fila in filas:
        if fila.get("evento") not in EVENTOS_PAGADOS:
            continue
        hora = _hora(fila.get("ts"))
        args = fila.get("args")
        if hora is None or not isinstance(args, Mapping) or not desde <= hora <= ahora + timedelta(minutes=5):
            continue   # sin hora legible, o de otra época, no se suma (la ventana nunca mira al futuro lejano)
        if _norm(args.get(destino, "")) != buscada:
            continue
        monto = _monto(args)
        if monto:
            total += monto
    return total


def esta_inscrita(cuenta: str, inscritas: Mapping[str, str]) -> bool:
    """La cuenta aparece en el texto de alguna cuenta que el dueño inscribió."""
    return bool(_norm(cuenta)) and any(origenes_en([(CONFIABLE, str(texto))], str(cuenta)) for texto in inscritas.values())


def _pesos(monto: int) -> str:
    return f"${monto:,}".replace(",", ".")


def motivo_ventana(filas: Iterable[Mapping[str, Any]], args: Mapping[str, Any], destino: str, tope: int, dias: int,
                   inscritas: Mapping[str, str], ahora: Optional[datetime] = None) -> Optional[str]:
    """None si el pago puede seguir; si no, el motivo («llevas $410.000 a esta cuenta este mes»)."""
    if tope <= 0:
        return None
    cuenta = args.get(destino)
    if cuenta in (None, "") or esta_inscrita(str(cuenta), inscritas):
        return None
    monto = _monto(args)
    previo = pagado_en_ventana(filas, str(cuenta), dias, ahora, destino)
    if monto is None:   # ante la duda se retiene, como el quórum con un monto ilegible
        return ("el monto del pago no se pudo leer y la cuenta no está inscrita: no se puede sumar a lo que ya se le pagó "
                f"este mes ({_pesos(previo)}).")
    if previo + monto <= tope:
        return None
    from ..defenses.layer2 import citado
    if previo:
        return (f"llevas {_pesos(previo + monto)} a esta cuenta ({citado(cuenta)}) este mes con este pago: ya se le pagaron "
                f"{_pesos(previo)} en los últimos {dias} días, y a una cuenta que no tienes inscrita no se le pasa de "
                f"{_pesos(tope)} sin tu confirmación. Varios aportes chicos que van creciendo son una estafa conocida.")
    return (f"este pago de {_pesos(monto)} a una cuenta que no tienes inscrita ({citado(cuenta)}) pasa el tope de "
            f"{_pesos(tope)}: queda retenido hasta que lo confirmes por un canal conocido.")
