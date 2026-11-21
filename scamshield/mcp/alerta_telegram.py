"""Telegram para el proxy MCP: la alerta de un pago retenido, el cambio de política y el latido.

Tres ganchos del proxy, con el mismo bot y el mismo chat del dueño (`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, en el
`.env`, nunca en el repo):

- `escalar`: cuando Grifter retiene un pago, le manda al dueño el aviso con los tres botones de la demo (pagar a mi
  cuenta inscrita, no pagar y pagar igual). Solo «pagar igual» confirmado aprueba, y solo si se pidió esperar.
- `aprobador`: cuando `grifter.yaml` cambió respecto de la política aprobada, le manda el diff con dos botones
  (aprobar el cambio / rechazar). Hasta el toque, el proxy retiene todo lo sensible (#102).
- `latido`: avisa al arrancar y al detenerse el proxy, con las capas activas.

Un solo sondeo (`getUpdates`) atiende los tres: dos sondeos sobre el mismo bot se roban las novedades. Solo se sondea
cuando hay algo pendiente, así que no choca con el long polling del servidor de la demo salvo que haya una alerta
esperando respuesta. El proxy sigue reteniendo pase lo que pase: sin respuesta, o si Telegram falla, no se paga.
"""
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .integridad import Cambio
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


def texto_de_cambio(cambio: Cambio) -> str:
    return ("Grifter: la política cambió\n" + cambio.texto +
            "\n\nTodos los pagos y envíos de datos quedan retenidos hasta tu decisión.")


def texto_de_latido(evento: str, datos: Mapping[str, Any]) -> str:
    capas = ", ".join(f"{k}: {'activa' if v else 'APAGADA'}" for k, v in sorted((datos.get("capas") or {}).items()))
    base = "Grifter arrancó" if evento == "arranque" else "Grifter se detuvo"
    lineas = [base, f"Capas: {capas or 'sin datos'}"]
    if datos.get("huella"):
        lineas.append(f"Política aprobada: {datos['huella']}")
    if evento == "arranque":
        lineas.append({"inicial": "Primer arranque: quedó registrada la política inicial.",
                       "igual": "La política es la que aprobaste.",
                       "cambio": "La política CAMBIÓ: todo queda retenido hasta tu decisión.",
                       "sin_vigilancia": "Sin vigilancia de la política (no hay grifter.yaml)."}
                      .get(str(datos.get("politica")), ""))
    return "\n".join(l for l in lineas if l)


def _canal_con_politica():
    """Crea la clase del canal: el de la demo, más los botones de aprobar o rechazar un cambio de política."""
    from demo.telegram import CanalTelegram   # import tardío: el proxy no depende de la demo

    class CanalProxy(CanalTelegram):
        def __init__(self, *a: Any, **k: Any):
            super().__init__(*a, **k)
            self._politicas: dict[str, Optional[bool]] = {}

        def pedir_politica(self, cambio: Cambio) -> str:
            id_ = secrets.token_hex(4)
            self._politicas[id_] = None
            self._api("sendMessage", chat_id=self.chat_id, text=texto_de_cambio(cambio),
                      reply_markup={"inline_keyboard": [[
                          {"text": "Aprobar el cambio", "callback_data": f"{id_}:ap"},
                          {"text": "Rechazar", "callback_data": f"{id_}:re"}]]})
            return id_

        def decision(self, id_: str) -> Optional[bool]:
            return self._politicas.get(id_)

        def _atender(self, cb: Mapping[str, Any]) -> None:
            id_, _, accion = str(cb.get("data", "")).partition(":")
            chat = str(((cb.get("message") or {}).get("chat") or {}).get("id", ""))
            if id_ not in self._politicas or chat != self.chat_id:
                return super()._atender(cb)
            if self._politicas[id_] is not None or accion not in ("ap", "re"):
                self._responder(cb, "Ya respondiste esta alerta.")
                return
            self._politicas[id_] = accion == "ap"
            texto = "Elegiste: aprobar el cambio." if accion == "ap" else "Elegiste: rechazar el cambio."
            self._editar(cb.get("message") or {}, texto, {"inline_keyboard": []})
            self._responder(cb, texto)

    return CanalProxy


class AprobadorTelegram:
    """El gancho `aprobador` del proxy: pide el visto bueno de un cambio de política y consulta si ya respondió."""

    def __init__(self, canal: Any):
        self.canal, self._id = canal, ""

    def pedir(self, cambio: Cambio) -> None:
        try:
            self._id = self.canal.pedir_politica(cambio)
        except Exception as e:   # falla cerrada: sin aviso, todo sigue retenido
            self._id = ""
            log.warning("no se pudo avisar el cambio de política por Telegram: %s", e)

    def estado(self) -> Optional[bool]:
        if not self._id:
            return None
        try:
            self.canal.sondear_una_vez(0)
        except Exception as e:
            log.warning("%s", e)
        return self.canal.decision(self._id)


@dataclass
class Ganchos:
    escalar: Escalar
    aprobador: AprobadorTelegram
    latido: Callable[[str, dict[str, Any]], None]


def ganchos_desde_entorno(entorno: Optional[Mapping[str, str]] = None, esperar_s: float = 0.0,
                          cuenta_inscrita: str = "", al_elegir: Optional[Callable[[dict[str, Any]], Any]] = None,
                          reloj: Callable[[], float] = time.monotonic) -> Optional[Ganchos]:
    """Los tres ganchos, o None si faltan el token o el chat (todo sigue como antes).

    Con `esperar_s` > 0, `escalar` espera ese tiempo a que el dueño apriete un botón; solo «pagar igual» confirmado
    devuelve True. Con 0 (lo normal en la demo), solo avisa y la llamada queda retenida.
    """
    import os

    from demo.telegram import API_POR_DEFECTO

    entorno = os.environ if entorno is None else entorno
    token, chat = entorno.get("TELEGRAM_BOT_TOKEN", "").strip(), entorno.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return None
    elecciones: list[str] = []

    def registrar(etiqueta: dict[str, Any]) -> None:
        elecciones.append(str(etiqueta.get("eleccion", "")))
        if al_elegir:
            al_elegir(etiqueta)

    canal = _canal_con_politica()(token, chat, registrar, entorno.get("TELEGRAM_API_BASE", "").strip() or API_POR_DEFECTO)

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

    def latido(evento: str, datos: dict[str, Any]) -> None:
        canal._api("sendMessage", chat_id=canal.chat_id, text=texto_de_latido(evento, datos))

    return Ganchos(escalar, AprobadorTelegram(canal), latido)


def escalar_telegram(entorno: Optional[Mapping[str, str]] = None, esperar_s: float = 0.0,
                     cuenta_inscrita: str = "", al_elegir: Optional[Callable[[dict[str, Any]], Any]] = None,
                     reloj: Callable[[], float] = time.monotonic) -> Optional[Escalar]:
    """Solo el gancho `escalar` (la alerta de un pago retenido), o None si faltan el token o el chat."""
    ganchos = ganchos_desde_entorno(entorno, esperar_s, cuenta_inscrita, al_elegir, reloj)
    return ganchos.escalar if ganchos else None
