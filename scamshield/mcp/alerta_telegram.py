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
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .aprobaciones import Aprobaciones, AprobadorQuorum, RegistroEncadenado, Solicitud, aprobadores_de, cargar_semillas
from .integridad import Cambio
from ..defenses.layer2 import citado, visible
from .proxy import Alerta, Escalar

log = logging.getLogger("grifter")


def alerta_para_telegram(alerta: Alerta, cuenta_inscrita: str = "") -> dict[str, Any]:
    """La alerta del proxy en el formato de `demo/telegram.py`."""
    return {
        "idioma": "es",
        # Lo que puso quien pide el pago va en una línea, escapado y entre «» si no es normal (#160): no puede imitar a Grifter.
        "destinatario": citado(alerta.args.get("destinatario") or "") or visible(alerta.servidor or alerta.herramienta),
        "monto": alerta.args.get("monto", ""),
        "cuenta": visible(alerta.valor, 80),
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
    canal: Any = None


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

    return Ganchos(escalar, AprobadorTelegram(canal), latido, canal)


def escalar_telegram(entorno: Optional[Mapping[str, str]] = None, esperar_s: float = 0.0,
                     cuenta_inscrita: str = "", al_elegir: Optional[Callable[[dict[str, Any]], Any]] = None,
                     reloj: Callable[[], float] = time.monotonic) -> Optional[Escalar]:
    """Solo el gancho `escalar` (la alerta de un pago retenido), o None si faltan el token o el chat."""
    ganchos = ganchos_desde_entorno(entorno, esperar_s, cuenta_inscrita, al_elegir, reloj)
    return ganchos.escalar if ganchos else None


CODIGO = re.compile(r"^\s*(\d{6})\s*$")


class QuorumTelegram:
    """Pide y cuenta las aprobaciones de varias personas por Telegram, cada una desde su propio chat.

    Cada aprobador recibe la solicitud con dos botones. «Rechazar» rechaza al tiro. «Aprobar» le pide el código de su
    digipass, atado a esa solicitud (id, monto y cuenta); con el código bueno el voto cuenta. Todo lo que pasa queda en
    el registro encadenado. Un solo sondeo (`getUpdates`) atiende a todos.
    """

    def __init__(self, canal: Any, aprobaciones: Aprobaciones):
        self.canal, self.aprobaciones = canal, aprobaciones
        self._offset = 0
        self._esperando: dict[str, str] = {}   # chat -> solicitud a la que le falta el código
        self._chats = {a.nombre: a.canal for a in aprobaciones.aprobadores.values()}

    def aprobador_de_politica(self) -> AprobadorQuorum:
        return AprobadorQuorum(self)

    def reconfigurar(self, politica: Mapping[str, Any]) -> None:
        lista, q = aprobadores_de(politica)
        if lista:
            self.aprobaciones.aprobadores = {a.nombre: a for a in lista}
            self.aprobaciones.quorum = q
            self._chats = {a.nombre: a.canal for a in lista}

    def _nombre_de(self, chat: str) -> Optional[str]:
        return next((n for n, c in self._chats.items() if c and str(c) == str(chat)), None)

    def _decir(self, chat: str, texto: str, botones: Optional[dict[str, Any]] = None) -> None:
        datos: dict[str, Any] = {"chat_id": chat, "text": texto}
        if botones:
            datos["reply_markup"] = botones
        try:
            self.canal._api("sendMessage", **datos)
        except Exception as e:
            log.warning("%s", e)

    def notificar(self, s: Solicitud) -> None:
        """Le manda la solicitud a cada aprobador (menos a quien la inició)."""
        texto = (f"Grifter pide aprobación ({s.id})\n{s.detalle}\n\n{self.aprobaciones.progreso(s.id)}. "
                 f"Para aprobar, saca el código de tu digipass para el desafío {s.desafio} y escríbelo aquí.")
        botones = {"inline_keyboard": [[{"text": "Aprobar", "callback_data": f"{s.id}:ap"},
                                        {"text": "Rechazar", "callback_data": f"{s.id}:re"}]]}
        for nombre, chat in self._chats.items():
            if chat and nombre != s.iniciador:
                self._decir(chat, texto, botones)

    def sondear(self) -> None:
        try:
            novedades = self.canal._api("getUpdates", offset=self._offset, timeout=0,
                                        allowed_updates=["callback_query", "message"]) or []
        except Exception as e:
            log.warning("%s", e)
            return
        for n in novedades:
            self._offset = max(self._offset, int(n.get("update_id", 0)) + 1)
            if "callback_query" in n:
                self._boton(n["callback_query"])
            elif "message" in n:
                self._texto(n["message"])

    def _boton(self, cb: Mapping[str, Any]) -> None:
        chat = str(((cb.get("message") or {}).get("chat") or {}).get("id", ""))
        nombre = self._nombre_de(chat)
        id_, _, accion = str(cb.get("data", "")).partition(":")
        if nombre is None or id_ not in self.aprobaciones.solicitudes:
            return
        if accion == "re":
            r = self.aprobaciones.votar(id_, nombre, False, canal="telegram")
            self._decir(chat, r.mensaje)
            if r.ok:
                self._avisar_a_los_demas(nombre, f"{nombre} rechazó la solicitud {id_}.")
        elif accion == "ap":
            self._esperando[chat] = id_
            self._decir(chat, f"Escribe el código de tu digipass para {id_} "
                              f"(desafío {self.aprobaciones.solicitudes[id_].desafio}).")

    def _texto(self, msg: Mapping[str, Any]) -> None:
        chat = str((msg.get("chat") or {}).get("id", ""))
        nombre = self._nombre_de(chat)
        m = CODIGO.match(str(msg.get("text", "")))
        if nombre is None or m is None or chat not in self._esperando:
            return
        id_ = self._esperando[chat]
        r = self.aprobaciones.votar(id_, nombre, True, m.group(1), canal="telegram")
        if r.ok or r.estado != "pendiente" or "bloqueado" in r.mensaje:
            self._esperando.pop(chat, None)
        self._decir(chat, r.mensaje)
        if r.ok:
            self._avisar_a_los_demas(nombre, f"{nombre} aprobó la solicitud {id_}: {self.aprobaciones.progreso(id_)}.")

    def _avisar_a_los_demas(self, quien: str, texto: str) -> None:
        for nombre, chat in self._chats.items():
            if chat and nombre != quien:
                self._decir(chat, texto)


def aprobaciones_desde(config: Any, integridad: Any, entorno: Mapping[str, str]) -> Aprobaciones:
    """Las aprobaciones con los aprobadores de la política aprobada (si hay) y las semillas de fuera del repo."""
    lista, q = list(config.aprobadores), config.quorum
    if integridad is not None:
        try:
            aprobada = integridad.estado()
        except Exception:
            aprobada = None
        if aprobada is not None and aprobada.politica.get("aprobadores"):
            lista, q = aprobadores_de(aprobada.politica)
    semillas = cargar_semillas(str(config.semillas) if config.semillas else None, entorno)
    ruta = config.registro_aprobaciones or (config.ruta.parent / "grifter_aprobaciones.jsonl" if config.ruta else None)
    return Aprobaciones(lista, q, semillas, RegistroEncadenado(ruta))


def quorum_desde_entorno(config: Any, integridad: Any, canal: Any, entorno: Mapping[str, str]) -> QuorumTelegram:
    """El quórum por Telegram."""
    return QuorumTelegram(canal, aprobaciones_desde(config, integridad, entorno))
