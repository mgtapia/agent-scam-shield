"""WhatsApp (Kapso) para el proxy MCP: alerta de pago retenido, latido y doble autorización con TOTP (#116).

Es lo mismo que `alerta_telegram.py` con otro canal (`demo/whatsapp.py`). La diferencia es que Telegram se consulta
(`getUpdates`) y WhatsApp empuja: las respuestas llegan por el webhook de Kapso, así que aquí `sondear` no hace nada y
los votos se cuentan cuando llega el mensaje. El proxy levanta un servidor mínimo para ese webhook
(`KAPSO_WEBHOOK_PORT`, 8788 por defecto); hay que exponerlo a Kapso (un túnel, por ejemplo) y poner su URL en Kapso.

Falla cerrada, igual que Telegram: sin llaves no hay canal; si Kapso falla o nadie responde, no se paga; el webhook sin
firma válida no cuenta nada. Solo los números de los aprobadores votan, y cada «Aprobar» pide el código del digipass
de esa persona, atado a la solicitud.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable, Mapping, Optional

from .alerta_telegram import Ganchos, alerta_para_telegram, texto_de_cambio, texto_de_latido, aprobaciones_desde
from .aprobaciones import Aprobaciones, AprobadorQuorum, Solicitud, aprobadores_de
from .proxy import Alerta

log = logging.getLogger("grifter")

CODIGO = re.compile(r"^\s*(\d{6})\s*$")
PUERTO_POR_DEFECTO = 8788


def _canal(entorno: Mapping[str, str], al_elegir: Callable[[dict[str, Any]], Any]):
    from demo.whatsapp import desde_entorno   # import tardío: el proxy no depende de la demo

    return desde_entorno(al_elegir, entorno)


class QuorumWhatsApp:
    """Pide y cuenta las aprobaciones de varias personas por WhatsApp, cada una desde su propio número.

    Cada aprobador recibe la solicitud con dos botones. «Rechazar» rechaza al tiro. «Aprobar» le pide el código de su
    digipass, atado a esa solicitud (id, monto y cuenta); con el código bueno el voto cuenta. Todo queda en el
    registro encadenado. Los números son los `canal` de cada aprobador en `grifter.yaml`.
    """

    def __init__(self, canal: Any, aprobaciones: Aprobaciones):
        from demo.whatsapp import solo_digitos

        self._digitos = solo_digitos
        self.canal, self.aprobaciones = canal, aprobaciones
        self._esperando: dict[str, str] = {}   # número -> solicitud a la que le falta el código
        self._numeros = self._de(aprobaciones)
        canal.agregar_manejador(self.atender)

    def _de(self, aprobaciones: Aprobaciones) -> dict[str, str]:
        return {a.nombre: self._digitos(a.canal) for a in aprobaciones.aprobadores.values()}

    def aprobador_de_politica(self) -> AprobadorQuorum:
        return AprobadorQuorum(self)

    def reconfigurar(self, politica: Mapping[str, Any]) -> None:
        lista, q = aprobadores_de(politica)
        if lista:
            self.aprobaciones.aprobadores = {a.nombre: a for a in lista}
            self.aprobaciones.quorum = q
            self._numeros = self._de(self.aprobaciones)

    def sondear(self) -> None:
        """WhatsApp empuja los votos por el webhook: no hay nada que consultar."""

    def _nombre_de(self, numero: str) -> Optional[str]:
        return next((n for n, c in self._numeros.items() if c and c == numero), None)

    def _decir(self, numero: str, texto: str) -> None:
        try:
            self.canal.texto(numero, texto)
        except Exception as e:
            log.warning("%s", e)

    def notificar(self, s: Solicitud) -> None:
        """Le manda la solicitud a cada aprobador (menos a quien la inició)."""
        texto = (f"Grifter pide aprobación ({s.id})\n{s.detalle}\n\n{self.aprobaciones.progreso(s.id)}. "
                 f"Para aprobar, saca el código de tu digipass para el desafío {s.desafio} y escríbelo aquí.")
        for nombre, numero in self._numeros.items():
            if numero and nombre != s.iniciador:
                try:
                    self.canal.botones(numero, texto, [(f"{s.id}:ap", "Aprobar"), (f"{s.id}:re", "Rechazar")])
                except Exception as e:
                    log.warning("%s", e)

    def atender(self, numero: str, tipo: str, valor: str) -> bool:
        """Manejador del canal: True si el mensaje era de un aprobador y de una solicitud nuestra."""
        nombre = self._nombre_de(numero)
        if nombre is None:
            return False
        if tipo == "boton":
            id_, _, accion = valor.partition(":")
            if id_ not in self.aprobaciones.solicitudes:
                return False
            if accion == "re":
                r = self.aprobaciones.votar(id_, nombre, False, canal="whatsapp")
                self._decir(numero, r.mensaje)
                if r.ok:
                    self._avisar_a_los_demas(nombre, f"{nombre} rechazó la solicitud {id_}.")
            elif accion == "ap":
                self._esperando[numero] = id_
                self._decir(numero, f"Escribe el código de tu digipass para {id_} "
                                    f"(desafío {self.aprobaciones.solicitudes[id_].desafio}).")
            return True
        m = CODIGO.match(valor)
        if m is None or numero not in self._esperando:
            return False
        id_ = self._esperando[numero]
        r = self.aprobaciones.votar(id_, nombre, True, m.group(1), canal="whatsapp")
        if r.ok or r.estado != "pendiente" or "bloqueado" in r.mensaje:
            self._esperando.pop(numero, None)
        self._decir(numero, r.mensaje)
        if r.ok:
            self._avisar_a_los_demas(nombre, f"{nombre} aprobó la solicitud {id_}: {self.aprobaciones.progreso(id_)}.")
        return True

    def _avisar_a_los_demas(self, quien: str, texto: str) -> None:
        for nombre, numero in self._numeros.items():
            if numero and nombre != quien:
                self._decir(numero, texto)


def ganchos_desde_entorno(entorno: Optional[Mapping[str, str]] = None, esperar_s: float = 0.0,
                          cuenta_inscrita: str = "", al_elegir: Optional[Callable[[dict[str, Any]], Any]] = None,
                          reloj: Callable[[], float] = time.monotonic) -> Optional[Ganchos]:
    """`escalar` y `latido` por WhatsApp, o None si faltan las llaves (todo sigue como antes).

    Con `esperar_s` > 0, `escalar` espera ese tiempo a que el dueño apriete un botón (el webhook lo despierta); solo
    «pagar igual» confirmado devuelve True. Con 0, solo avisa y la llamada queda retenida. El cambio de política sin
    aprobadores no tiene botón aquí: con aprobadores, pasa por el quórum.
    """
    import os

    entorno = os.environ if entorno is None else entorno
    elecciones: list[str] = []
    despierta = threading.Event()

    def registrar(etiqueta: dict[str, Any]) -> None:
        elecciones.append(str(etiqueta.get("eleccion", "")))
        despierta.set()
        if al_elegir:
            al_elegir(etiqueta)

    canal = _canal(entorno, registrar)
    if canal is None:
        return None

    def escalar(alerta: Alerta) -> Optional[bool]:
        elecciones.clear()
        despierta.clear()
        try:
            canal(alerta_para_telegram(alerta, cuenta_inscrita))
        except Exception as e:   # falla cerrada: sin aviso no hay pago
            log.warning("no se pudo avisar por WhatsApp: %s", e)
            return None
        limite = reloj() + esperar_s
        while esperar_s > 0 and not elecciones and reloj() < limite:
            despierta.wait(min(1.0, max(0.0, limite - reloj())))
        return True if elecciones and elecciones[-1] == "pagar_igual" else None

    def latido(evento: str, datos: dict[str, Any]) -> None:
        canal.texto(canal.dueno, texto_de_latido(evento, datos))

    return Ganchos(escalar, None, latido, canal)   # type: ignore[arg-type]


def quorum_desde_entorno(config: Any, integridad: Any, canal: Any, entorno: Mapping[str, str]) -> QuorumWhatsApp:
    """El quórum con los aprobadores de la política aprobada (si hay) y las semillas de fuera del repo."""
    return QuorumWhatsApp(canal, aprobaciones_desde(config, integridad, entorno))
