"""Demo en vivo del pitch: el pedido de aprobación de Pablo llega de verdad por WhatsApp (Kapso).

En el acto 1 del modo demo, Marta toca «Pagar igual» y la doble autorización le pide la aprobación a Pablo, su hijo.
Con `?whatsapp=1`, la página llama una vez a `POST /api/demo/alerta-en-vivo` y este módulo le manda al teléfono del
presentador (KAPSO_OWNER_NUMBER) el mismo pedido que manda la doble autorización por WhatsApp
(scamshield/mcp/alerta_whatsapp.py): el texto «Grifter pide aprobación…» y los botones Aprobar y Rechazar.

Seguridad:
- La ruta existe solo con GRIFTER_DEMO_WHATSAPP=1 en el entorno: sin eso responde 404. En Render nunca está.
- Pide una clave de un solo uso que se genera al arrancar y se imprime en la consola local. Va en la URL, que se
  proyecta y queda en el historial y en el log de acceso: por eso nunca es una clave fija de .env, y muere al reiniciar.
  Se compara en tiempo constante.
- Tope a las claves malas: después de 5 en un minuto, la ruta responde 429 hasta que pase la ventana.
- Un envío cada 30 s como máximo, para todos. Si Kapso no acepta el envío, el cupo se devuelve y se puede reintentar.
- Las llaves de Kapso salen del entorno y nunca van a la respuesta ni a los registros: los errores dicen solo el tipo.

El rechazo de Pablo puede ser real: si Kapso llega al servidor (un túnel público hacia /api/whatsapp/webhook, firmado
con KAPSO_WEBHOOK_SECRET), el «Rechazar» del número del aprobador marca el pedido como rechazado, con la latencia
medida, y la página lo consulta con GET /api/demo/alerta-en-vivo/estado. Sin túnel, la demo sigue su guion simulado.
"""
from __future__ import annotations

import hmac
import re
import logging
import os
import secrets
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Mapping, Optional

from demo import whatsapp
from scamshield.mcp.aprobaciones import desafio

log = logging.getLogger("scamshield.demo.en_vivo")

VARIABLE = "GRIFTER_DEMO_WHATSAPP"
VARIABLE_CLAVE = "GRIFTER_DEMO_CLAVE"   # ya no se usa: si está, se avisa que se ignora
INTERVALO_S = 30.0
MAX_FALLOS, VENTANA_FALLOS_S = 5, 60.0
MAX_PEDIDOS = 20
BOTON = re.compile(r"^(demo-[0-9a-f]{4}):(ap|re)$")

# El pedido de aprobación del acto 1, en el formato de QuorumWhatsApp.notificar (alerta_whatsapp.py): aprobadores
# Marta y Pablo con quórum 2; Marta ya aprobó con su código y falta Pablo.
CUENTA, MONTO = "48-2210-7735", 650_000
TEXTOS = {
    "es": {
        "detalle": "Marta quiere pagar $650.000 a J. Contreras V. La cuenta salió de una llamada de número privado que dice ser su nieto.",
        "progreso": "1 de 2 aprobaciones: Marta ya aprobó con su código",
        "pie": "Para aprobar, saca el código de tu digipass para el desafío {d} y escríbelo aquí.",
        "titulo": "Grifter pide aprobación ({id})", "aprobar": "Aprobar", "rechazar": "Rechazar",
    },
    "en": {
        "detalle": "Marta wants to pay $650,000 to J. Contreras V. The account came from a call from a private number claiming to be her grandson.",
        "progreso": "1 of 2 approvals: Marta already approved with her code",
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
                 canal: Optional[Any] = None, clave: Optional[str] = None):
        self.entorno = os.environ if entorno is None else entorno
        self.reloj = reloj
        self._canal = canal
        self._candado = threading.Lock()
        self._ultimo: Optional[float] = None
        self._previo: Optional[float] = None
        self._fallos: list[float] = []
        self._clave_de_un_uso = clave or secrets.token_urlsafe(9)   # `clave` solo para las pruebas
        self._pedidos: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    def usar_canal(self, canal: Optional[Any]) -> None:
        """El canal del servidor (el mismo del webhook): así el «Rechazar» de Pablo vuelve a este pedido."""
        if canal is not None:
            self._canal = canal
            canal.agregar_manejador(self.atender)

    def clave(self) -> str:
        """La clave de un solo uso de este arranque."""
        return self._clave_de_un_uso

    def clave_valida(self, dada: str) -> bool:
        """Compara en tiempo constante. Una clave mala cuenta para el tope (ver `bloqueada`)."""
        ok = bool(dada) and hmac.compare_digest(str(dada).encode(), self.clave().encode())
        if not ok:
            with self._candado:
                self._fallos.append(self.reloj())
        return ok

    def bloqueada(self) -> int:
        """Segundos que faltan si ya hubo MAX_FALLOS claves malas en la última ventana; 0 si se puede intentar."""
        ahora = self.reloj()
        with self._candado:
            self._fallos = [f for f in self._fallos if ahora - f < VENTANA_FALLOS_S]
            if len(self._fallos) < MAX_FALLOS:
                return 0
            return max(1, int(VENTANA_FALLOS_S - (ahora - self._fallos[0])) + 1)

    def permitir(self) -> tuple[bool, int]:
        """(ok, segundos para reintentar). Solo cuenta el intento si se permite."""
        ahora = self.reloj()
        with self._candado:
            if self._ultimo is not None and ahora - self._ultimo < INTERVALO_S:
                return False, max(1, int(INTERVALO_S - (ahora - self._ultimo)))
            self._previo, self._ultimo = self._ultimo, ahora
            return True, 0

    def devolver_cupo(self) -> None:
        """Si el envío falló, el intento no gasta los 30 s: el reintento del pitch puede salir de inmediato."""
        with self._candado:
            self._ultimo = self._previo

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
        with self._candado:
            self._pedidos[id_] = {"enviado": self.reloj(), "estado": "esperando", "latencia_s": None}
            while len(self._pedidos) > MAX_PEDIDOS:
                self._pedidos.popitem(last=False)
        return {"ok": True, "id": id_}

    def atender(self, numero: str, tipo: str, valor: str) -> bool:
        """Manejador del canal: el botón de Pablo (el número del aprobador, KAPSO_OWNER_NUMBER) sobre un pedido nuestro."""
        m = BOTON.match(valor) if tipo == "boton" else None
        canal = self._canal
        if not m or canal is None or numero != getattr(canal, "dueno", None):
            return False
        id_, accion = m.groups()
        with self._candado:
            p = self._pedidos.get(id_)
            if p is None or p["estado"] != "esperando":
                return p is not None
            p["estado"] = "rechazado" if accion == "re" else "aprobar"
            p["latencia_s"] = round(self.reloj() - p["enviado"], 1)
        try:   # como en la doble autorización: quien vota recibe la confirmación
            canal.texto(numero, "Rechazaste el pago. No se pagó nada." if accion == "re"
                        else "Para aprobar, escribe aquí el código de tu digipass.")
        except whatsapp.ErrorWhatsApp as e:
            log.warning("demo en vivo: %s", e)
        return True

    def estado(self, id_: str) -> Optional[dict[str, Any]]:
        """Lo que la página necesita saber del pedido, sin datos sensibles."""
        with self._candado:
            p = self._pedidos.get(id_)
            return None if p is None else {"id": id_, "estado": p["estado"], "latencia_s": p["latencia_s"]}


def anunciar_clave(en_vivo: EnVivo, imprimir: Callable[[str], None] = lambda s: print(s, flush=True)) -> None:
    """Al arrancar con la variable, dice en la consola local la clave de un solo uso de este arranque."""
    if en_vivo.entorno.get(VARIABLE_CLAVE, "").strip():
        imprimir(f"Aviso: {VARIABLE_CLAVE} se ignora; la clave de la URL es siempre la de un solo uso de cada arranque.")
    imprimir(f"Demo con WhatsApp en vivo. Clave de un solo uso de este arranque: {en_vivo.clave()}"
             " (en la URL: demo.html?whatsapp=1&clave=...). Muere al reiniciar el servidor.")
