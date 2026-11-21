"""Alerta del proxy MCP por Telegram: el gancho `Escalar` de Grifter, con los tres botones de la demo.

Cuando el proxy retiene una llamada, `escalar_telegram` le manda al dueño el aviso con los botones (pagar a mi
cuenta inscrita, no pagar y pagar igual). No usa `getUpdates` salvo que se pida esperar: así no choca con el
long polling del servidor de la demo (Telegram da 409 si dos procesos hacen polling con el mismo bot).

El proxy sigue reteniendo la llamada pase lo que pase: aquí «aprobar» solo existe si el dueño aprieta «pagar
igual» y lo confirma, y solo cuando se pidió esperar. Sin respuesta, o si Telegram falla, no se paga.

Configuración, en `.env` (nunca en el repo): TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID. Sin ellas no hay canal.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Mapping, Optional

from .proxy import Alerta, Escalar

log = logging.getLogger("grifter")


def alerta_para_telegram(alerta: Alerta, cuenta_inscrita: str = "") -> dict[str, Any]:
    """La alerta del proxy en el formato de `demo/telegram.py`."""
    return {
        "idioma": "es",
        "destinatario": alerta.args.get("destinatario") or alerta.servidor or alerta.herramienta,
        "monto": alerta.args.get("monto", ""),
        "cuenta": alerta.valor,
        "dominio": ", ".join(alerta.fuentes),
        "cuenta_inscrita_numero": cuenta_inscrita,
        "motivo": alerta.mensaje,
        "escenario": f"mcp:{alerta.herramienta}",
        "defensa": "grifter-mcp",
    }


def escalar_telegram(entorno: Optional[Mapping[str, str]] = None, esperar_s: float = 0.0,
                     cuenta_inscrita: str = "", al_elegir: Optional[Callable[[dict[str, Any]], Any]] = None,
                     reloj: Callable[[], float] = time.monotonic) -> Optional[Escalar]:
    """El gancho para `Grifter(escalar=...)`, o None si faltan el token o el chat (todo sigue como antes).

    Con `esperar_s` > 0 espera ese tiempo a que el dueño apriete un botón; solo «pagar igual» confirmado
    devuelve True. Con 0 (lo normal en la demo), solo avisa y la llamada queda retenida.
    """
    from demo.telegram import desde_entorno   # import tardío: el proxy no depende de la demo

    elecciones: list[str] = []

    def registrar(etiqueta: dict[str, Any]) -> None:
        elecciones.append(str(etiqueta.get("eleccion", "")))
        if al_elegir:
            al_elegir(etiqueta)

    canal = desde_entorno(registrar, entorno)
    if canal is None:
        return None

    def escalar(alerta: Alerta) -> Optional[bool]:
        elecciones.clear()
        try:
            canal(alerta_para_telegram(alerta, cuenta_inscrita))
        except Exception as e:   # falla cerrada: sin aviso no hay pago
            log.warning("no se pudo avisar por Telegram: %s", e)
            return None
        limite = reloj() + esperar_s
        while esperar_s > 0 and not elecciones and reloj() < limite:
            try:
                canal.sondear_una_vez(min(5.0, max(0.0, limite - reloj())))
            except Exception as e:
                log.warning("%s", e)
                break
        return True if elecciones and elecciones[-1] == "pagar_igual" else None

    return escalar
