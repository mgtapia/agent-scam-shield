"""Tope de pedidos por IP para las rutas abiertas de la demo (#50).

«Intenta estafarlo» lo puede usar cualquiera con la URL, así que se limita por IP (por minuto y por hora) y
también en total, para que un ataque repartido entre muchas IP tampoco sature el servidor. Es en memoria y
acotado: nunca recuerda más de `max_ips` direcciones, así que mandar pedidos desde miles de IP no llena la memoria.

La IP real viene de la conexión. Detrás de un proxy de confianza (Render), `GRIFTER_PROXY_CONFIABLE=1` toma la última
dirección de `X-Forwarded-For`, la que agregó el proxy y no el cliente; sin esa variable el encabezado se ignora, porque
cualquiera puede escribirlo.

Modo evento (`GRIFTER_EVENTO=1`): en un pitch o una feria, el jurado comparte el wifi y por lo tanto la IP, así que 30 personas
con 3 intentos cada una en 2 minutos son 45 pedidos por minuto desde una sola dirección. El modo evento sube **solo el tope por
IP** (por minuto y por hora) y deja el **tope global** igual: un ataque repartido entre muchas IP sigue topado, y una sola IP que
comparte medio auditorio también. Es una variable de entorno, no un parámetro del pedido: nadie de afuera puede prenderla.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque
from typing import Any, Callable, Mapping

PROXY_CONFIABLE = "GRIFTER_PROXY_CONFIABLE"
EVENTO = "GRIFTER_EVENTO"

# Los topes de cada ruta abierta: (por minuto, por hora, global por hora). El modo evento solo cambia los dos primeros.
TOPES = {"probar": (6, 60, 600), "mcp": (60, 600, 6000)}
TOPES_EVENTO_POR_IP = {"probar": (120, 1200), "mcp": (240, 2400)}


class LimitePorIP:
    def __init__(self, por_minuto: int = 6, por_hora: int = 60, global_por_hora: int = 600, max_ips: int = 5000,
                 reloj: Callable[[], float] = time.monotonic):
        self.por_minuto, self.por_hora, self.global_por_hora, self.max_ips = por_minuto, por_hora, global_por_hora, max_ips
        self.reloj = reloj
        self._por_ip: "OrderedDict[str, deque[float]]" = OrderedDict()
        self._global: deque[float] = deque()
        self._candado = threading.Lock()

    @staticmethod
    def _podar(cola: "deque[float]", ahora: float, ventana: float) -> None:
        while cola and ahora - cola[0] >= ventana:
            cola.popleft()

    def permitir(self, ip: str) -> tuple[bool, int]:
        """(ok, segundos para reintentar). Solo cuenta el pedido si se permite."""
        ahora = self.reloj()
        with self._candado:
            self._podar(self._global, ahora, 3600)
            if len(self._global) >= self.global_por_hora:
                return False, max(1, int(3600 - (ahora - self._global[0])))
            cola = self._por_ip.get(ip)
            if cola is None:
                cola = self._por_ip[ip] = deque()
                while len(self._por_ip) > self.max_ips:   # acotado: se olvida la IP más antigua
                    self._por_ip.popitem(last=False)
            else:
                self._por_ip.move_to_end(ip)
            self._podar(cola, ahora, 3600)
            ultimo_minuto = [t for t in cola if ahora - t < 60]
            if len(ultimo_minuto) >= self.por_minuto:
                return False, max(1, int(60 - (ahora - ultimo_minuto[0])))
            if len(cola) >= self.por_hora:
                return False, max(1, int(3600 - (ahora - cola[0])))
            cola.append(ahora)
            self._global.append(ahora)
            return True, 0


def modo_evento(entorno: Mapping[str, str] | None = None) -> bool:
    """True si el proceso arrancó con `GRIFTER_EVENTO=1` (el jurado comparte la IP)."""
    return (os.environ if entorno is None else entorno).get(EVENTO, "").strip() == "1"


def limite_de(ruta: str, entorno: Mapping[str, str] | None = None) -> LimitePorIP:
    """El tope de una ruta abierta (`probar` o `mcp`), con el tope por IP más alto en modo evento y el global intacto."""
    por_minuto, por_hora, global_por_hora = TOPES[ruta]
    if modo_evento(entorno):
        por_minuto, por_hora = TOPES_EVENTO_POR_IP[ruta]
    return LimitePorIP(por_minuto=por_minuto, por_hora=por_hora, global_por_hora=global_por_hora)


def ip_cliente(cliente: Any, encabezados: Mapping[str, str], entorno: Mapping[str, str] | None = None) -> str:
    """La IP del pedido. `cliente` es `request.client` de Starlette (o None)."""
    entorno = os.environ if entorno is None else entorno
    if entorno.get(PROXY_CONFIABLE) == "1":
        reenviadas = [x.strip() for x in encabezados.get("x-forwarded-for", "").split(",") if x.strip()]
        if reenviadas:
            return reenviadas[-1]
    return getattr(cliente, "host", None) or "desconocida"
