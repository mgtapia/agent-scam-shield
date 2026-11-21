"""Demo en vivo del pitch: el pedido de aprobación de Pablo llega de verdad por WhatsApp (Kapso).

En el acto 1 del modo demo, Marta toca «Pagar igual» y la doble autorización le pide la aprobación a Pablo, su hijo.
Con `?whatsapp=1`, la página llama una vez a `POST /api/demo/alerta-en-vivo` y este módulo le manda al teléfono del
presentador (KAPSO_OWNER_NUMBER) el mismo pedido que manda la doble autorización por WhatsApp
(scamshield/mcp/alerta_whatsapp.py): el texto «Grifter pide aprobación…» y los botones Aprobar y Rechazar.

Seguridad:
- La ruta existe solo con GRIFTER_DEMO_WHATSAPP=1 en el entorno: sin eso responde 404. En Render nunca está.
- Pide una clave: GRIFTER_DEMO_CLAVE de .env o, si no hay, una de un solo uso que se genera al arrancar y se imprime en
  la consola local. Se compara en tiempo constante.
- Un envío cada 30 s como máximo, para todos.
- Las llaves de Kapso salen del entorno y nunca van a la respuesta ni a los registros: los errores dicen solo el tipo.

No hay webhook público: los botones llegan al teléfono, pero lo que se toca allí no vuelve a la demo.
"""
from __future__ import annotations

import hmac
import logging
import os
import secrets
import threading
import time
from typing import Any, Callable, Mapping, Optional

from demo import whatsapp
from scamshield.mcp.aprobaciones import desafio

log = logging.getLogger("scamshield.demo.en_vivo")

VARIABLE = "GRIFTER_DEMO_WHATSAPP"
VARIABLE_CLAVE = "GRIFTER_DEMO_CLAVE"
INTERVALO_S = 30.0

# El pedido de aprobación del acto 1, en el formato de QuorumWhatsApp.notificar (alerta_whatsapp.py).
CUENTA, MONTO = "48-2210-7735", 650_000
TEXTOS = {
    "es": {
        "detalle": "Marta quiere pagar $650.000 a J. Contreras V. La cuenta salió de una llamada de número privado que dice ser su nieto.",
        "progreso": "0 de 1 aprobaciones",
        "pie": "Para aprobar, saca el código de tu digipass para el desafío {d} y escríbelo aquí.",
        "titulo": "Grifter pide aprobación ({id})", "aprobar": "Aprobar", "rechazar": "Rechazar",
    },
    "en": {
        "detalle": "Marta wants to pay $650,000 to J. Contreras V. The account came from a call from a private number claiming to be her grandson.",
        "progreso": "0 of 1 approvals",
        "pie": "To approve, get the code from your digipass for challenge {d} and type it here.",
        "titulo": "Grifter asks for approval ({id})", "aprobar": "Approve", "rechazar": "Reject",
    },
}


def activa(entorno: Optional[Mapping[str, str]] = None) -> bool:
    entorno = os.environ if entorno is None else entorno
    return entorno.get(VARIABLE, "").strip() == "1"


class EnVivo:
    """La clave, el tope de 30 s y el envío. Una instancia por arranque del servidor."""

    def __init__(self, entorno: Optional[Mapping[str, str]] = None, reloj: Callable[[], float] = time.monotonic,
                 canal: Optional[Any] = None):
        self.entorno = os.environ if entorno is None else entorno
        self.reloj = reloj
        self._canal = canal
        self._candado = threading.Lock()
        self._ultimo: Optional[float] = None
        self._clave_de_un_uso = secrets.token_urlsafe(9)

    def clave(self) -> str:
        """La clave vigente: la de .env si está, o la de un solo uso de este arranque."""
        return self.entorno.get(VARIABLE_CLAVE, "").strip() or self._clave_de_un_uso

    def clave_valida(self, dada: str) -> bool:
        return bool(dada) and hmac.compare_digest(str(dada).encode(), self.clave().encode())

    def permitir(self) -> tuple[bool, int]:
        """(ok, segundos para reintentar). Solo cuenta el intento si se permite."""
        ahora = self.reloj()
        with self._candado:
            if self._ultimo is not None and ahora - self._ultimo < INTERVALO_S:
                return False, max(1, int(INTERVALO_S - (ahora - self._ultimo)))
            self._ultimo = ahora
            return True, 0

    def canal(self) -> Optional[Any]:
        return self._canal or whatsapp.desde_entorno(lambda etiqueta: None, self.entorno)

    def mensaje(self, idioma: str = "es") -> tuple[str, str, list[tuple[str, str]]]:
        """(id, texto, botones) del pedido de aprobación de Pablo."""
        t = TEXTOS.get(idioma, TEXTOS["es"])
        id_ = f"demo-{secrets.token_hex(2)}"
        texto = f"{t['titulo'].format(id=id_)}\n{t['detalle']}\n\n{t['progreso']}. {t['pie'].format(d=desafio(id_, MONTO, CUENTA))}"
        return id_, texto, [(f"{id_}:ap", t["aprobar"]), (f"{id_}:re", t["rechazar"])]

    def enviar(self, idioma: str = "es") -> dict[str, Any]:
        """Manda el pedido al teléfono del presentador. Lanza ErrorWhatsApp si Kapso no lo acepta."""
        canal = self.canal()
        if canal is None:
            raise LookupError("faltan KAPSO_API_KEY, KAPSO_PHONE_NUMBER_ID o KAPSO_OWNER_NUMBER")
        id_, texto, botones = self.mensaje(idioma)
        canal.enviar({"to": canal.dueno, "type": "interactive", "interactive": {
            "type": "button", "body": {"text": texto[:whatsapp.MAX_CUERPO]},
            "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": b[:whatsapp.MAX_BOTON]}} for i, b in botones]}}})
        return {"ok": True, "id": id_}


def anunciar_clave(en_vivo: EnVivo, imprimir: Callable[[str], None] = lambda s: print(s, flush=True)) -> None:
    """Al arrancar con la variable, dice en la consola local cómo abrir la demo. La clave de .env no se imprime."""
    if en_vivo.entorno.get(VARIABLE_CLAVE, "").strip():
        imprimir("Demo con WhatsApp en vivo: usa la clave GRIFTER_DEMO_CLAVE (de .env o del entorno) en la URL (&clave=...).")
    else:
        imprimir(f"Demo con WhatsApp en vivo. Clave de un solo uso de este arranque: {en_vivo.clave()}")
