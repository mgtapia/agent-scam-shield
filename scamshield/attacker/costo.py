"""Costo, tope de gasto y configuración por modelo del atacante.

Pensado para Claude Fable 5.2 como atacante (#99), pero vale para cualquier modelo de la familia 5:

- **Sin `temperature`:** estos modelos la rechazan con un 400. `config_para` la omite.
- **Piensan siempre:** los 600 tokens que bastaban para un JSON corto se van en el pensamiento y dejan la
  respuesta vacía, así que el mínimo de `max_tokens` sube, y se fija `effort`.
- **Negativas:** `stop_reason: refusal` (Inspect lo informa como `content_filter`) no es un error ni una
  ronda fallida: es un dato, «el atacante se negó», y se cuenta aparte.
- **Tope de gasto:** el costo sale del uso real de tokens que informa la API y se corta al llegar al tope.
  La caché de respuestas de Inspect puede repetir el `usage` de una llamada ya pagada: se cuenta de todos
  modos, así que el gasto estimado nunca queda por debajo del real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from inspect_ai.model import GenerateConfig

# USD por millón de tokens (entrada, salida), solo para el tope y la estimación: el gasto real lo dice la
# factura. Si un precio cambia, se pasa por la línea de comandos. Fable 5.2 viene del issue #99; el de
# Haiku, de scripts/demo_real.py. Un modelo que no está aquí cuenta como gratis (Groq, Gemini en capa gratis).
PRECIOS: dict[str, tuple[float, float]] = {
    # Los más específicos primero: `precio_de` toma el primero que calza. Haiku 5.5 y Sonnet 5.5, de la lista de
    # precios de Anthropic (2026-11-03), para el juez LLM (#131).
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-fable-5": (8.0, 40.0),
    "claude-haiku-5": (1.0, 5.0),
}
TOPE_USD = 5.0
MAX_TOKENS_PENSANDO = 4000      # mínimo para un modelo que piensa siempre
CLAUDE_5 = re.compile(r"claude-(?:fable|opus|sonnet|haiku)-5")


class PresupuestoAgotado(RuntimeError):
    """Se llegó al tope de gasto: no se hace ninguna llamada más."""


class Rechazo(RuntimeError):
    """El modelo se negó a responder (`stop_reason: refusal`). Es un dato del informe, no un fallo."""


def precio_de(nombre: str) -> tuple[float, float]:
    """(entrada, salida) en USD por millón de tokens, o (0, 0) si el modelo no se cobra o no se conoce."""
    n = nombre.lower()
    return next((p for clave, p in PRECIOS.items() if clave in n), (0.0, 0.0))


def piensa_siempre(nombre: str) -> bool:
    """Los Claude de la familia 5 razonan siempre y no aceptan `temperature`."""
    return bool(CLAUDE_5.search(nombre.lower()))


def config_para(nombre: str, temperatura: float, max_tokens: int, cache: bool,
                effort: str = "high") -> GenerateConfig:
    """La configuración de una llamada según el modelo que ataca.

    Un Claude 5.x: sin `temperature`, con `effort` y con al menos `MAX_TOKENS_PENSANDO` de salida.
    gpt-oss: razonamiento bajo para gastar menos cuota. El resto, como siempre.
    """
    if piensa_siempre(nombre):
        return GenerateConfig(max_tokens=max(max_tokens, MAX_TOKENS_PENSANDO), effort=effort,  # type: ignore[arg-type]
                              cache=cache or None)
    return GenerateConfig(temperature=temperatura, max_tokens=max_tokens, cache=cache or None,
                          reasoning_effort="low" if "gpt-oss" in nombre.lower() else None)


@dataclass
class Gasto:
    """El uso real de tokens del atacante, el crítico y el juez, y lo que va costando."""

    tope_usd: Optional[float] = None
    precio_entrada: float = 0.0
    precio_salida: float = 0.0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    llamadas: int = 0
    rechazos: int = 0
    por_rechazo: list[str] = field(default_factory=list)

    @property
    def gastado_usd(self) -> float:
        return (self.tokens_entrada * self.precio_entrada + self.tokens_salida * self.precio_salida) / 1e6

    def peor_caso_usd(self, max_tokens: int) -> float:
        """Lo que podría costar una llamada más, contando su salida completa."""
        return max_tokens * self.precio_salida / 1e6

    def verificar(self, max_tokens: int = 0) -> None:
        """Corta antes de una llamada si ya no cabe bajo el tope."""
        if self.tope_usd is not None and self.gastado_usd + self.peor_caso_usd(max_tokens) > self.tope_usd:
            raise PresupuestoAgotado(
                f"se llegó al tope de US${self.tope_usd:.2f} (gastado ~US${self.gastado_usd:.3f})")

    @property
    def agotado(self) -> bool:
        return self.tope_usd is not None and self.gastado_usd >= self.tope_usd

    def registrar(self, uso: Any) -> None:
        """Suma el `usage` de una respuesta. Lo cacheado y lo escrito en caché cuentan a precio completo."""
        self.llamadas += 1
        if uso is None:
            return
        entrada = (getattr(uso, "input_tokens", 0) or 0) + (getattr(uso, "input_tokens_cache_write", 0) or 0) \
            + (getattr(uso, "input_tokens_cache_read", 0) or 0)
        self.tokens_entrada += int(entrada)
        self.tokens_salida += int(getattr(uso, "output_tokens", 0) or 0)

    def resumen(self) -> dict[str, Any]:
        return {"gastado_usd": round(self.gastado_usd, 4), "tope_usd": self.tope_usd, "llamadas": self.llamadas,
                "tokens_entrada": self.tokens_entrada, "tokens_salida": self.tokens_salida,
                "rechazos": self.rechazos}


# --- Estimación para --dry-run ---------------------------------------------------------------------------

# Tokens por llamada, medidos en las corridas de #8: el sistema del atacante pesa ~1.000, y con la historia
# de 3 intercambios sube a ~2.500 de entrada. Un modelo que piensa suele gastar la mitad del tope en pensar.
ENTRADA_ATACANTE, ENTRADA_JUEZ, ENTRADA_CRITICO = 2500, 1600, 900
SALIDA_TIPICA = {"atacante": 2200, "juez": 700, "critico": 600}


def estimar(estafas: int, defensas: int, rondas: int, precio_entrada: float, precio_salida: float,
            max_tokens: int = MAX_TOKENS_PENSANDO) -> dict[str, float]:
    """Costo del atacante, el crítico y el juez: típico y peor caso.

    Cada flujo (estafa × defensa) gasta, en cada ronda desde la 1, una llamada del atacante y una del juez;
    el crítico corre también en la ronda 0. El peor caso es que cada llamada use todo su `max_tokens` y que
    ninguna estafa caiga antes (una que cae deja de atacarse).
    """
    flujos = estafas * defensas
    llamadas_atacante = flujos * rondas
    llamadas_critico = flujos * (rondas + 1)
    entrada = (llamadas_atacante * (ENTRADA_ATACANTE + ENTRADA_JUEZ) + llamadas_critico * ENTRADA_CRITICO)
    salida_tipica = (llamadas_atacante * (SALIDA_TIPICA["atacante"] + SALIDA_TIPICA["juez"])
                     + llamadas_critico * SALIDA_TIPICA["critico"])
    salida_max = (llamadas_atacante * 2 + llamadas_critico) * max_tokens
    return {
        "llamadas": llamadas_atacante * 2 + llamadas_critico,
        "tokens_entrada": entrada, "tokens_salida_tipica": salida_tipica, "tokens_salida_maxima": salida_max,
        "usd_tipico": (entrada * precio_entrada + salida_tipica * precio_salida) / 1e6,
        "usd_peor_caso": (entrada * precio_entrada + salida_max * precio_salida) / 1e6,
    }
