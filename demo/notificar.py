"""Punto de enchufe de las alertas al dueño.

`notificar(alerta)` reparte la alerta a cada canal registrado. Hoy el único canal real es el
celular dibujado en la web (lo pinta el navegador); aquí solo queda anotada. El canal de Telegram (#20)
vive en `demo/telegram.py`: con TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el entorno, el servidor lo registra
con `registrar_canal` al arrancar. Cualquier otro canal es una función `canal(alerta) -> None`.

La alerta es un dict con: escenario, idioma, defensa, destinatario, monto, cuenta, dominio,
correos, cuenta_inscrita, cuenta_inscrita_numero, nombre_inscrita y motivo.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

Alerta = dict[str, Any]
Canal = Callable[[Alerta], None]

log = logging.getLogger("scamshield.demo")
_CANALES: list[Canal] = []


def registrar_canal(canal: Canal) -> None:
    _CANALES.append(canal)


def notificar(alerta: Alerta) -> list[str]:
    """Manda la alerta a cada canal. Devuelve los nombres de los canales que la recibieron."""
    entregados = []
    for canal in _CANALES:
        try:
            canal(alerta)
            entregados.append(getattr(canal, "__name__", repr(canal)))
        except Exception:  # un canal caído no detiene a los demás
            log.exception("falló el canal %r", canal)
    log.info("alerta: %s paga %s a %s (de %s); canales=%s", alerta.get("destinatario"), alerta.get("monto"),
             alerta.get("cuenta"), alerta.get("dominio"), entregados)
    return entregados
