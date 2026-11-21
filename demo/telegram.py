"""Canal de Telegram para las alertas al dueño (#20), por long polling: sin URL pública ni webhook.

`CanalTelegram` es un canal de `demo/notificar.py`: manda la alerta con tres botones (pagar a la cuenta
inscrita, no pagar y pagar igual) y, cuando el dueño aprieta uno, deja la etiqueta con la misma función
que usa la página (`al_elegir`). Sin respuesta no se paga: el bot solo avisa y registra lo que se elija.

Configuración, en `.env` (nunca en el repo):
    TELEGRAM_BOT_TOKEN   el token que da BotFather al crear el bot
    TELEGRAM_CHAT_ID     el chat del dueño; solo las respuestas de ese chat cuentan
Si falta alguna, no hay canal y todo sigue como antes, sin fallar.

Pagar igual pide una segunda confirmación, como en la página. Un botón apretado dos veces no registra dos
etiquetas. El token no se escribe nunca en los registros: los errores dicen el método y el estado, no la URL.

Solo usa la biblioteca estándar. `TELEGRAM_API_BASE` cambia el servidor (las pruebas usan uno falso).
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from demo.notificar import Alerta, registrar_canal

log = logging.getLogger("scamshield.demo.telegram")

API_POR_DEFECTO = "https://api.telegram.org"
MAX_ALERTAS = 200   # alertas pendientes de respuesta que se recuerdan

Etiquetar = Callable[[dict[str, Any]], Any]

TEXTOS = {
    "es": {
        "titulo": "Grifter retuvo un pago",
        "a": "A", "cuenta": "Cuenta", "inscrita": "Inscrita", "de": "Apareció en",
        "pagar_inscrita": "Pagar a mi cuenta inscrita", "no_pagar": "No pagar", "pagar_igual": "Pagar igual",
        "sigue": "Pagar igual a la cuenta nueva", "cancelar": "Cancelar",
        "confirma": "¿Seguro? Es una cuenta que no está inscrita.",
        "hecho_pagar_inscrita": "Elegiste: pagar a la cuenta inscrita.", "hecho_no_pagar": "Elegiste: no pagar.",
        "hecho_pagar_igual": "Elegiste: pagar igual a la cuenta nueva.", "ya": "Ya respondiste esta alerta.",
    },
    "en": {
        "titulo": "Grifter held a payment",
        "a": "To", "cuenta": "Account", "inscrita": "Registered", "de": "Appeared in",
        "pagar_inscrita": "Pay my registered account", "no_pagar": "Don't pay", "pagar_igual": "Pay anyway",
        "sigue": "Pay anyway to the new account", "cancelar": "Cancel",
        "confirma": "Sure? This account is not registered.",
        "hecho_pagar_inscrita": "You chose: pay the registered account.", "hecho_no_pagar": "You chose: don't pay.",
        "hecho_pagar_igual": "You chose: pay anyway to the new account.", "ya": "You already answered this alert.",
    },
}

# callback_data tiene un límite de 64 bytes: un id corto y una acción de pocas letras.
ACCIONES = {"pi": "pagar_inscrita", "np": "no_pagar", "pg": "pagar_igual"}


class ErrorTelegram(RuntimeError):
    """Un fallo al hablar con Telegram. Dice el método y el estado, nunca la URL (lleva el token)."""


def _pesos(monto: Any) -> str:
    try:
        return "$" + f"{int(monto):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(monto or "")


def texto_de_alerta(alerta: Alerta) -> str:
    t = TEXTOS.get(alerta.get("idioma"), TEXTOS["es"])
    lineas = [t["titulo"], f"{t['a']}: {alerta.get('destinatario', '')}  {_pesos(alerta.get('monto'))}",
              f"{t['cuenta']}: {alerta.get('cuenta', '')}"]
    if alerta.get("dominio"):
        lineas.append(f"{t['de']}: {alerta['dominio']}")
    if alerta.get("cuenta_inscrita_numero"):
        lineas.append(f"{t['inscrita']}: {alerta['cuenta_inscrita_numero']}")
    if alerta.get("motivo"):
        lineas.append(str(alerta["motivo"]))
    return "\n".join(lineas)


class CanalTelegram:
    """Manda la alerta por Telegram y recoge el botón que aprieta el dueño."""

    __name__ = "telegram"

    def __init__(self, token: str, chat_id: str, al_elegir: Etiquetar, api: str = API_POR_DEFECTO,
                 timeout: float = 5.0):
        self._token, self.chat_id = token, str(chat_id)
        self.al_elegir, self.api, self.timeout = al_elegir, api.rstrip("/"), timeout
        self._alertas: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._candado = threading.Lock()
        self._offset = 0
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None

    def __repr__(self) -> str:   # el log de notificar() imprime el canal: nunca debe llevar el token
        return f"<CanalTelegram chat={self.chat_id}>"

    # --- Telegram ------------------------------------------------------------------------------
    def _api(self, metodo: str, espera: float = 0.0, **datos: Any) -> Any:
        req = urllib.request.Request(
            f"{self.api}/bot{self._token}/{metodo}", data=json.dumps(datos).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout + espera) as r:
                cuerpo = json.load(r)
        except urllib.error.HTTPError as e:
            raise ErrorTelegram(f"{metodo}: Telegram respondió {e.code}") from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ErrorTelegram(f"{metodo}: no se pudo hablar con Telegram ({type(e).__name__})") from None
        if not cuerpo.get("ok"):
            raise ErrorTelegram(f"{metodo}: Telegram no aceptó la llamada")
        return cuerpo.get("result")

    def _botones(self, id_: str, idioma: Optional[str]) -> dict[str, Any]:
        t = TEXTOS.get(idioma, TEXTOS["es"])
        boton = lambda clave, accion: {"text": t[clave], "callback_data": f"{id_}:{accion}"}  # noqa: E731
        return {"inline_keyboard": [[boton("pagar_inscrita", "pi")], [boton("no_pagar", "np"),
                                                                       boton("pagar_igual", "pg")]]}

    def __call__(self, alerta: Alerta) -> None:
        """Canal de `notificar()`: manda la alerta con sus botones."""
        id_ = secrets.token_hex(4)
        with self._candado:
            self._alertas[id_] = dict(alerta)
            while len(self._alertas) > MAX_ALERTAS:
                self._alertas.popitem(last=False)
        self._api("sendMessage", chat_id=self.chat_id, text=texto_de_alerta(alerta),
                  reply_markup=self._botones(id_, alerta.get("idioma")))

    # --- Respuestas ----------------------------------------------------------------------------
    def sondear_una_vez(self, espera: float = 0.0) -> int:
        """Pide las novedades a Telegram y atiende los botones. Devuelve cuántas atendió."""
        novedades = self._api("getUpdates", espera=espera, offset=self._offset, timeout=int(espera),
                              allowed_updates=["callback_query"]) or []
        for n in novedades:
            self._offset = max(self._offset, int(n.get("update_id", 0)) + 1)
            if "callback_query" in n:
                self._atender(n["callback_query"])
        return len(novedades)

    def _atender(self, cb: Mapping[str, Any]) -> None:
        chat = str(((cb.get("message") or {}).get("chat") or {}).get("id", ""))
        if chat != self.chat_id:   # solo cuenta el chat del dueño
            log.warning("botón de un chat que no es el configurado: se ignora")
            return
        id_, _, accion = str(cb.get("data", "")).partition(":")
        mensaje = cb.get("message") or {}
        with self._candado:
            alerta = self._alertas.get(id_)
        t = TEXTOS.get((alerta or {}).get("idioma"), TEXTOS["es"])
        if alerta is None:
            self._responder(cb, t["ya"])
            return
        if accion == "pg":   # pagar igual pide una segunda confirmación
            self._editar(mensaje, f"{texto_de_alerta(alerta)}\n\n{t['confirma']}", {"inline_keyboard": [[
                {"text": t["sigue"], "callback_data": f"{id_}:pgc"},
                {"text": t["cancelar"], "callback_data": f"{id_}:pgx"}]]})
            self._responder(cb, "")
            return
        if accion == "pgx":
            self._editar(mensaje, texto_de_alerta(alerta), self._botones(id_, alerta.get("idioma")))
            self._responder(cb, "")
            return
        eleccion = "pagar_igual" if accion == "pgc" else ACCIONES.get(accion)
        if eleccion is None:
            return
        with self._candado:   # un botón apretado dos veces no registra dos etiquetas
            if self._alertas.pop(id_, None) is None:
                self._responder(cb, t["ya"])
                return
        self.al_elegir({"ts": datetime.now(timezone.utc).isoformat(), "eleccion": eleccion, "canal": "telegram",
                        **alerta})
        self._editar(mensaje, f"{texto_de_alerta(alerta)}\n\n{t['hecho_' + eleccion]}", {"inline_keyboard": []})
        self._responder(cb, t["hecho_" + eleccion])

    def _responder(self, cb: Mapping[str, Any], texto: str) -> None:
        self._intentar("answerCallbackQuery", callback_query_id=cb.get("id"), text=texto)

    def _editar(self, mensaje: Mapping[str, Any], texto: str, botones: dict[str, Any]) -> None:
        self._intentar("editMessageText", chat_id=self.chat_id, message_id=mensaje.get("message_id"),
                       text=texto, reply_markup=botones)

    def _intentar(self, metodo: str, **datos: Any) -> None:
        try:
            self._api(metodo, **datos)
        except ErrorTelegram as e:   # el aviso visual falla, la etiqueta ya quedó guardada
            log.warning("%s", e)

    # --- Hilo ----------------------------------------------------------------------------------
    def iniciar_en_hilo(self, espera: int = 25) -> None:
        def bucle() -> None:
            while not self._parar.is_set():
                try:
                    self.sondear_una_vez(espera)
                except ErrorTelegram as e:
                    log.warning("%s", e)
                    self._parar.wait(5)

        self._hilo = threading.Thread(target=bucle, name="telegram", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()


def desde_entorno(al_elegir: Etiquetar, entorno: Optional[Mapping[str, str]] = None) -> Optional[CanalTelegram]:
    """El canal si están el token y el chat; si falta alguno, None y todo sigue como antes."""
    entorno = os.environ if entorno is None else entorno
    token, chat = entorno.get("TELEGRAM_BOT_TOKEN", "").strip(), entorno.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return None
    return CanalTelegram(token, chat, al_elegir, entorno.get("TELEGRAM_API_BASE", "").strip() or API_POR_DEFECTO)


def iniciar_desde_entorno(al_elegir: Etiquetar, entorno: Optional[Mapping[str, str]] = None) -> Optional[CanalTelegram]:
    """Crea el canal, lo registra en `notificar()` y arranca el long polling. None si no hay configuración."""
    canal = desde_entorno(al_elegir, entorno)
    if canal is None:
        log.info("Telegram desactivado: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return None
    registrar_canal(canal)
    canal.iniciar_en_hilo()
    log.info("Telegram activado para el chat %s", canal.chat_id)
    return canal
