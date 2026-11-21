"""Tope de pedidos por IP para las rutas abiertas de la demo (#50).

«Intenta estafarlo» lo puede usar cualquiera con la URL, así que se limita por IP (por minuto y por hora) y
también en total, para que un ataque repartido entre muchas IP tampoco sature el servidor. Es en memoria y
acotado: nunca recuerda más de `max_ips` direcciones, así que mandar pedidos desde miles de IP no llena la memoria.

La IP real viene de la conexión. Detrás de un proxy de confianza (Render), `GRIFTER_PROXY_CONFIABLE=1` toma la última
dirección de `X-Forwarded-For`, la que agregó el proxy y no el cliente; sin esa variable el encabezado se ignora, porque
cualquiera puede escribirlo.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque
from typing import Any, Callable, Mapping

PROXY_CONFIABLE = "GRIFTER_PROXY_CONFIABLE"


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


def ip_cliente(cliente: Any, encabezados: Mapping[str, str], entorno: Mapping[str, str] | None = None) -> str:
    """La IP del pedido. `cliente` es `request.client` de Starlette (o None)."""
    entorno = os.environ if entorno is None else entorno
    if entorno.get(PROXY_CONFIABLE) == "1":
        reenviadas = [x.strip() for x in encabezados.get("x-forwarded-for", "").split(",") if x.strip()]
        if reenviadas:
            return reenviadas[-1]
    return getattr(cliente, "host", None) or "desconocida"
