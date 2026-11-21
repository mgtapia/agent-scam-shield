"""Canal de WhatsApp para las alertas al dueño (#116), con Kapso (API de WhatsApp Business).

Calca `demo/telegram.py`: `CanalWhatsApp` es un canal de `demo/notificar.py`. Manda la alerta con tres botones de
respuesta (pagar a la cuenta inscrita, no pagar y pagar igual) y, cuando el dueño aprieta uno, deja la etiqueta con la
misma función que usan la página y Telegram (`al_elegir`). Pagar igual pide una segunda confirmación. Sin respuesta no
se paga: el canal solo avisa y registra lo que se elija.

Cómo habla Kapso (docs.kapso.ai):
- Enviar: POST {api}/v24.0/{phone_number_id}/messages con la cabecera `X-API-Key` y un mensaje `interactive` de tipo
  `button` (hasta 3 botones `reply` con `id` y `title` de hasta 20 caracteres) o un `text`.
- Recibir: Kapso llama a un webhook. Un toque llega como `message.type = "interactive"` con
  `interactive.button_reply.{id,title}`; un texto, como `message.type = "text"` con `text.body`. El nombre del evento va
  en la cabecera `X-Webhook-Event`, no en el cuerpo. Con buffering los envíos vienen en un sobre
  `{"type", "batch": true, "data": [...]}`. La firma es `X-Webhook-Signature`: HMAC-SHA256 en hexadecimal del cuerpo
  crudo con el secreto del webhook. Las entregas son «al menos una vez» (`X-Idempotency-Key` se repite en los reintentos).

Configuración, en `.env` (nunca en el repo; los agentes no la leen):
    KAPSO_API_KEY          la llave de Kapso
    KAPSO_PHONE_NUMBER_ID  el id del número de WhatsApp Business desde el que se manda
    KAPSO_OWNER_NUMBER     el número del dueño (solo sus respuestas cuentan), con código de país y sin «+»
    KAPSO_WEBHOOK_SECRET   el secreto con el que Kapso firma el webhook
Si falta cualquiera, no hay canal y todo sigue como antes, sin fallar.

Falla cerrada: sin secreto, o con una firma mala o ausente, el webhook se rechaza y no cuenta nada. Un botón de otro
número se ignora. Un botón apretado dos veces, o una entrega repetida, no registra dos etiquetas. La llave no se escribe
nunca en los registros: los errores dicen el método y el estado, no la URL ni las cabeceras. `KAPSO_API_BASE` cambia el
servidor (las pruebas usan uno falso).

Solo usa la biblioteca estándar.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping, Optional

from demo.notificar import Alerta, registrar_canal
from demo.telegram import ACCIONES, TEXTOS, texto_de_alerta

log = logging.getLogger("scamshield.demo.whatsapp")

API_POR_DEFECTO = "https://api.kapso.ai/meta/whatsapp"
VERSION_API = "v24.0"
MAX_ALERTAS = 200      # alertas pendientes de respuesta que se recuerdan
MAX_ENTREGAS = 2000    # claves de idempotencia que se recuerdan
MAX_CUERPO = 1024      # largo máximo del texto de un mensaje con botones
MAX_BOTON = 20         # largo máximo del título de un botón

Etiquetar = Callable[[dict[str, Any]], Any]
# Un manejador recibe (número, tipo, valor) y devuelve True si atendió el mensaje. `tipo` es «boton» (valor = id) o
# «texto» (valor = el texto).
Manejador = Callable[[str, str, str], bool]

BOTONES = {
    "es": {"pi": "Pagar a mi inscrita", "np": "No pagar", "pg": "Pagar igual", "pgc": "Sí, pagar igual", "pgx": "Cancelar"},
    "en": {"pi": "Pay my registered", "np": "Don't pay", "pg": "Pay anyway", "pgc": "Yes, pay anyway", "pgx": "Cancel"},
}


class ErrorWhatsApp(RuntimeError):
    """Un fallo al hablar con Kapso. Dice el método y el estado, nunca la URL ni la llave."""


def solo_digitos(numero: Any) -> str:
    return re.sub(r"\D", "", str(numero or ""))


def firma_valida(secreto: str, cuerpo: bytes, firma: Optional[str]) -> bool:
    """HMAC-SHA256 en hexadecimal del cuerpo crudo, comparado en tiempo constante. Sin secreto o sin firma, no."""
    if not secreto or not firma:
        return False
    esperada = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma.strip().lower())


def _cortar(texto: str, largo: int) -> str:
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


def _cabecera(cabeceras: Mapping[str, str], nombre: str) -> Optional[str]:
    for k, v in cabeceras.items():
        if k.lower() == nombre.lower():
            return v
    return None


class CanalWhatsApp:
    """Manda la alerta por WhatsApp y recoge el botón que aprieta el dueño, por el webhook de Kapso."""

    __name__ = "whatsapp"

    def __init__(self, api_key: str, phone_number_id: str, dueno: str, al_elegir: Etiquetar, secreto_webhook: str = "",
                 api: str = API_POR_DEFECTO, timeout: float = 8.0):
        self._llave, self.phone_number_id, self.dueno = api_key, str(phone_number_id), solo_digitos(dueno)
        self.al_elegir, self._secreto, self.api, self.timeout = al_elegir, secreto_webhook, api.rstrip("/"), timeout
        self._alertas: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._entregas: "OrderedDict[str, None]" = OrderedDict()
        self._candado = threading.Lock()
        self._manejadores: list[Manejador] = [self._atender_dueno]

    def __repr__(self) -> str:   # el log de notificar() imprime el canal: nunca debe llevar la llave
        return f"<CanalWhatsApp dueno=…{self.dueno[-4:]}>"

    def agregar_manejador(self, manejador: Manejador) -> None:
        """Otros destinatarios de los mensajes (por ejemplo, los aprobadores de la doble autorización)."""
        self._manejadores.append(manejador)

    # --- Kapso ---------------------------------------------------------------------------------
    def enviar(self, cuerpo: dict[str, Any]) -> Any:
        req = urllib.request.Request(
            f"{self.api}/{VERSION_API}/{self.phone_number_id}/messages",
            data=json.dumps({"messaging_product": "whatsapp", **cuerpo}).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "X-API-Key": self._llave})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise ErrorWhatsApp(f"enviar: Kapso respondió {e.code}") from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ErrorWhatsApp(f"enviar: no se pudo hablar con Kapso ({type(e).__name__})") from None

    def texto(self, numero: str, texto: str) -> None:
        self.enviar({"to": solo_digitos(numero), "type": "text", "text": {"body": texto}})

    def botones(self, numero: str, texto: str, botones: list[tuple[str, str]]) -> None:
        """Un mensaje con hasta 3 botones de respuesta: (id, título)."""
        self.enviar({"to": solo_digitos(numero), "type": "interactive", "interactive": {
            "type": "button", "body": {"text": _cortar(texto, MAX_CUERPO)},
            "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": _cortar(t, MAX_BOTON)}}
                                   for i, t in botones[:3]]}}})

    def _botones_alerta(self, id_: str, idioma: Optional[str]) -> list[tuple[str, str]]:
        b = BOTONES.get(idioma, BOTONES["es"])
        return [(f"{id_}:{a}", b[a]) for a in ("pi", "np", "pg")]

    def __call__(self, alerta: Alerta) -> None:
        """Canal de `notificar()`: manda la alerta con sus botones."""
        id_ = secrets.token_hex(4)
        with self._candado:
            self._alertas[id_] = dict(alerta)
            while len(self._alertas) > MAX_ALERTAS:
                self._alertas.popitem(last=False)
        self.botones(self.dueno, texto_de_alerta(alerta), self._botones_alerta(id_, alerta.get("idioma")))

    # --- Webhook -------------------------------------------------------------------------------
    def atender_webhook(self, cuerpo: bytes, cabeceras: Mapping[str, str]) -> tuple[int, str]:
        """Atiende una entrega de Kapso. Devuelve (estado HTTP, motivo). Falla cerrada: sin secreto o con mala firma, 401."""
        if not self._secreto:
            return 503, "falta KAPSO_WEBHOOK_SECRET: el webhook está apagado"
        if not firma_valida(self._secreto, cuerpo, _cabecera(cabeceras, "X-Webhook-Signature")):
            log.warning("webhook con firma mala o ausente: se rechaza")
            return 401, "firma inválida"
        clave = _cabecera(cabeceras, "X-Idempotency-Key")
        if clave:
            with self._candado:
                if clave in self._entregas:   # un reintento de la misma entrega
                    return 200, "repetida"
                self._entregas[clave] = None
                while len(self._entregas) > MAX_ENTREGAS:
                    self._entregas.popitem(last=False)
        try:
            datos = json.loads(cuerpo)
        except ValueError:
            return 400, "no es JSON"
        evento = _cabecera(cabeceras, "X-Webhook-Event") or (datos.get("type") if isinstance(datos, dict) else "")
        if evento and evento != "whatsapp.message.received":
            return 200, "ignorado"
        items = datos.get("data") if isinstance(datos, dict) and datos.get("batch") else [datos]
        for item in items if isinstance(items, list) else []:
            try:
                self._procesar(item)
            except ErrorWhatsApp as e:   # el aviso visual falla, la etiqueta ya quedó guardada
                log.warning("%s", e)
        return 200, "ok"

    def _procesar(self, item: Any) -> None:
        mensaje = (item or {}).get("message") or {}
        numero = solo_digitos(mensaje.get("from"))
        if mensaje.get("type") == "interactive":
            br = (mensaje.get("interactive") or {}).get("button_reply") or {}
            tipo, valor = "boton", str(br.get("id", ""))
        elif mensaje.get("type") == "text":
            tipo, valor = "texto", str((mensaje.get("text") or {}).get("body", ""))
        else:
            return
        if not numero or not valor:
            return
        for manejador in self._manejadores:
            if manejador(numero, tipo, valor):
                return

    def _atender_dueno(self, numero: str, tipo: str, valor: str) -> bool:
        if tipo != "boton" or numero != self.dueno:   # solo cuenta el número del dueño
            return False
        id_, _, accion = valor.partition(":")
        with self._candado:
            alerta = self._alertas.get(id_)
        if alerta is None:
            return False
        t = TEXTOS.get(alerta.get("idioma"), TEXTOS["es"])
        b = BOTONES.get(alerta.get("idioma"), BOTONES["es"])
        if accion == "pg":   # pagar igual pide una segunda confirmación
            self.botones(numero, f"{texto_de_alerta(alerta)}\n\n{t['confirma']}",
                         [(f"{id_}:pgc", b["pgc"]), (f"{id_}:pgx", b["pgx"])])
            return True
        if accion == "pgx":
            self.botones(numero, texto_de_alerta(alerta), self._botones_alerta(id_, alerta.get("idioma")))
            return True
        eleccion = "pagar_igual" if accion == "pgc" else ACCIONES.get(accion)
        if eleccion is None:
            return True
        with self._candado:   # un botón apretado dos veces no registra dos etiquetas
            if self._alertas.pop(id_, None) is None:
                return True
        self.al_elegir({**alerta, "ts": datetime.now(timezone.utc).isoformat(), "eleccion": eleccion,
                       "canal": "whatsapp"})
        try:
            self.texto(numero, t["hecho_" + eleccion])
        except ErrorWhatsApp as e:
            log.warning("%s", e)
        return True


def desde_entorno(al_elegir: Etiquetar, entorno: Optional[Mapping[str, str]] = None) -> Optional[CanalWhatsApp]:
    """El canal si están la llave, el número de envío y el del dueño; si falta alguno, None y todo sigue como antes."""
    entorno = os.environ if entorno is None else entorno
    llave, pid = entorno.get("KAPSO_API_KEY", "").strip(), entorno.get("KAPSO_PHONE_NUMBER_ID", "").strip()
    dueno = entorno.get("KAPSO_OWNER_NUMBER", "").strip()
    if not llave or not pid or not dueno:
        return None
    return CanalWhatsApp(llave, pid, dueno, al_elegir, entorno.get("KAPSO_WEBHOOK_SECRET", "").strip(),
                         entorno.get("KAPSO_API_BASE", "").strip() or API_POR_DEFECTO)


def iniciar_desde_entorno(al_elegir: Etiquetar, entorno: Optional[Mapping[str, str]] = None) -> Optional[CanalWhatsApp]:
    """Crea el canal y lo registra en `notificar()`. El webhook lo atiende el servidor. None si no hay configuración."""
    canal = desde_entorno(al_elegir, entorno)
    if canal is None:
        log.info("WhatsApp desactivado: faltan KAPSO_API_KEY, KAPSO_PHONE_NUMBER_ID o KAPSO_OWNER_NUMBER")
        return None
    if not canal._secreto:
        log.warning("WhatsApp: falta KAPSO_WEBHOOK_SECRET; se manda la alerta pero no se aceptan respuestas")
    registrar_canal(canal)
    log.info("WhatsApp activado")
    return canal


def servir_webhook(canal: CanalWhatsApp, puerto: int, host: str = "127.0.0.1",
                   ruta: str = "/webhook") -> ThreadingHTTPServer:
    """Un servidor mínimo para el webhook, para quien no tiene el servidor de la demo (el proxy MCP). En un hilo."""

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            pass

        def do_POST(self) -> None:
            largo = min(int(self.headers.get("Content-Length") or 0), 1_000_000)
            cuerpo = self.rfile.read(largo)
            estado, motivo = (404, "no existe") if self.path != ruta else canal.atender_webhook(
                cuerpo, dict(self.headers.items()))
            self.send_response(estado)
            self.end_headers()
            self.wfile.write(motivo.encode("utf-8"))

    servidor = ThreadingHTTPServer((host, puerto), Manejador)
    threading.Thread(target=servidor.serve_forever, name="whatsapp-webhook", daemon=True).start()
    return servidor
