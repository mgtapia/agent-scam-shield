"""El clasificador que aprende en línea: regresión logística sobre señales y texto con hashing.

Es real: entrena con cada etiqueta (el feedback simulado del dueño, que sale de la etiqueta del
escenario), sube de versión cada `cada` etiquetas y se evalúa en un conjunto apartado que nunca
se usa para entrenar. Las métricas del evento `modelo` salen de esa evaluación.

Lo que aprende solo sube la sospecha: puede escalar un pago al dueño, pero no deja pasar nada que
la capa 1 o la capa 2 retengan.

Solo usa numpy (ya está en el entorno) y zlib para un hashing estable entre corridas.
"""
from __future__ import annotations

import random
import re
import zlib
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from ..env.world import CORREO
from .flujo import Correo, Libreta, dominio_de
from .lectura import INYECCION, LEXICO, URL, cuentas_en, dominios_en, monto_en

SENALES = (
    "dominio_parecido",   # el remitente o un dominio del cuerpo imita a uno conocido
    "primer_contacto",    # el remitente no está en la libreta de contactos
    "urgencia",
    "pide_codigo",        # código, clave, .env, API key
    "cambio_cuenta",      # «cambiamos de banco», «cuenta nueva»
    "cuenta_nueva",       # una cuenta del cuerpo que no viene del encargo ni de las inscritas
    "monto_inusual",
    "autoridad",
    "secreto",
    "instruccion_oculta", # patrones de la capa 1
    "enlace",
)
DIM_HASH = 2 ** 11
_PALABRA = re.compile(r"[a-záéíóúñü]{3,}")


@dataclass
class Rasgos:
    senales: dict[str, float]
    hash: dict[int, float]


def rasgos(correo: Correo, libreta: Libreta, umbral_monto: int) -> Rasgos:
    """Las señales nombradas y el texto con hashing de un correo."""
    texto = f"{correo.asunto}\n{correo.cuerpo}"
    remitente = correo.de.lower()
    dom = dominio_de(remitente)
    s = {k: 0.0 for k in SENALES}
    if (dom and libreta.parecido(dom)) or any(libreta.parecido(d) for _, _, d in dominios_en(correo)):
        s["dominio_parecido"] = 1.0
    if correo.origen == CORREO and not libreta.conocido(remitente):
        s["primer_contacto"] = 1.0
    for senal in ("urgencia", "pide_codigo", "cambio_cuenta", "autoridad", "secreto"):
        if LEXICO[senal].search(texto):
            s[senal] = 1.0
    if any(not segura for *_, segura in cuentas_en(correo)):
        s["cuenta_nueva"] = 1.0
    if any(v > umbral_monto for *_, v in monto_en(correo.cuerpo)):
        s["monto_inusual"] = 1.0
    if any(p.search(correo.cuerpo) for p in INYECCION):
        s["instruccion_oculta"] = 1.0
    if URL.search(correo.cuerpo):
        s["enlace"] = 1.0
    palabras = _PALABRA.findall(texto.lower())
    terminos = palabras + [a + "_" + b for a, b in zip(palabras, palabras[1:])]
    h: dict[int, float] = {}
    if terminos:
        valor = 1.0 / np.sqrt(len(terminos))
        for t in terminos:
            i = zlib.crc32(t.encode("utf-8")) % DIM_HASH
            h[i] = h.get(i, 0.0) + valor
    return Rasgos(s, h)


class Clasificador:
    """Regresión logística en línea (SGD con L2), con versiones 1.0.N y evaluación apartada."""

    UMBRAL = 0.5

    def __init__(self, apartado: list[tuple[Rasgos, int]], cada: int = 6, tasa: float = 0.5,
                 l2: float = 1e-3, sesgo: float = -1.5, semilla: int = 3):
        self.apartado = apartado
        self.cada = cada
        self.tasa = tasa
        self.l2 = l2
        self.w = np.zeros(len(SENALES))
        self.wh = np.zeros(DIM_HASH)
        self.b = sesgo
        self.n_version = 0
        self.ejemplos = 0
        self._memoria: list[tuple[Rasgos, int]] = []
        self._rng = random.Random(semilla)
        self._pesos_version = self.pesos()
        self.metricas = self.evaluar()

    @property
    def version(self) -> str:
        return f"1.0.{self.n_version}"

    def pesos(self) -> dict[str, float]:
        return {k: float(v) for k, v in zip(SENALES, self.w)}

    def _vector(self, r: Rasgos) -> np.ndarray:
        return np.array([r.senales[k] for k in SENALES])

    def _z(self, r: Rasgos) -> float:
        z = self.b + float(self.w @ self._vector(r))
        for i, v in r.hash.items():
            z += self.wh[i] * v
        return z

    def probabilidad(self, r: Rasgos) -> float:
        return float(1.0 / (1.0 + np.exp(-self._z(r))))

    def contribuciones(self, r: Rasgos, n: int = 4) -> list[dict[str, Any]]:
        """Las señales activas del correo con su peso aprendido, de mayor a menor."""
        activas = [(k, float(w)) for k, w, x in zip(SENALES, self.w, self._vector(r)) if x]
        activas.sort(key=lambda kv: -kv[1])
        return [{"nombre": k, "peso": round(w, 3)} for k, w in activas[:n]]

    def _paso(self, r: Rasgos, y: int) -> None:
        x = self._vector(r)
        g = self.probabilidad(r) - y
        self.w -= self.tasa * (g * x + self.l2 * self.w)
        self.b -= self.tasa * g
        for i, v in r.hash.items():
            self.wh[i] -= self.tasa * (g * v + self.l2 * self.wh[i])

    def aprender(self, r: Rasgos, y: int) -> Optional[dict[str, Any]]:
        """Entrena con una etiqueta. Cada `cada` etiquetas sube la versión y devuelve el evento."""
        self._paso(r, y)
        self._memoria.append((r, y))
        self.ejemplos += 1
        if self.ejemplos % self.cada:
            return None
        # Reentrenamiento incremental: dos pasadas sobre lo visto, en otro orden.
        for _ in range(2):
            orden = list(self._memoria)
            self._rng.shuffle(orden)
            for ri, yi in orden:
                self._paso(ri, yi)
        antes = self._pesos_version
        self.n_version += 1
        self._pesos_version = self.pesos()
        self.metricas = self.evaluar()
        cambios = [{"senal": k, "peso_antes": round(antes[k], 3), "peso_despues": round(v, 3)}
                   for k, v in self._pesos_version.items() if abs(v - antes[k]) >= 0.005]
        cambios.sort(key=lambda c: -abs(c["peso_despues"] - c["peso_antes"]))
        return self.evento_modelo(cambios)

    def evaluar(self) -> dict[str, Any]:
        """Precisión, recall y falsas alarmas (FP / (FP + TN)) en el conjunto apartado."""
        tp = fp = tn = fn = 0
        for r, y in self.apartado:
            pred = self.probabilidad(r) > self.UMBRAL
            if pred and y:
                tp += 1
            elif pred:
                fp += 1
            elif y:
                fn += 1
            else:
                tn += 1
        return {
            "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
            "falsas_alarmas": round(fp / (fp + tn), 3) if fp + tn else 0.0,
            "evaluado_en": len(self.apartado),
        }

    def evento_modelo(self, cambios: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        return {"tipo": "modelo", "version": self.version, "ejemplos": self.ejemplos,
                **self.metricas, "cambios": cambios or []}
