"""El clasificador que aprende en línea: regresión logística sobre señales y texto con hashing.

Es real: entrena con cada etiqueta (el feedback simulado del dueño, que sale de la etiqueta del
escenario), sube de versión cada `cada` etiquetas y se evalúa en un conjunto apartado que nunca
se usa para entrenar. Las métricas del evento `modelo` salen de esa evaluación.

Lo que aprende solo sube la sospecha: puede escalar un pago al dueño, pero no deja pasar nada que
la capa 1 o la capa 2 retengan.

Guardia contra el envenenamiento de etiquetas: un atacante que logra que el dueño etiquete como
legítimos muchos correos inocuos con lenguaje de estafa («urgente», «cuenta nueva»...) baja de a poco
el peso de esas señales, hasta que una estafa real sale «segura». Cada versión nueva se evalúa en el
conjunto apartado (que nunca entrena): si la probabilidad media que da a las estafas apartadas cae más
de `DERIVA_MAX` respecto de la mejor versión aceptada, se vuelve a los pesos de la última versión
buena y se descarta el último lote de etiquetas. Se mide la probabilidad y no el recall porque el
apartado tiene pocas estafas y el recall salta de a una: una deriva fuerte puede costar solo un punto.
El daño posible queda acotado a esa deriva.

La misma guardia tiene un presupuesto de falsas alarmas: contra un atacante que le quita todas las
señales a sus estafas, la salida fácil es subir el sesgo y marcar todo (el duelo, `duelo.py`, llegó a
66 % de falsas alarmas en el apartado). Una versión que sube las falsas alarmas del apartado más de
`PRESUPUESTO_FALSAS_ALARMAS` sobre las que tenía al arrancar también se revierte.

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
    MEMORIA_MAX = 1500   # etiquetas que se guardan para reentrenar; las más viejas se olvidan
    REENTRENO_MAX = 240  # etiquetas por pasada de reentrenamiento: acota el costo cuando el duelo corre sin fin
    PRESUPUESTO_FALSAS_ALARMAS = 0.1   # cuánto pueden subir las falsas alarmas del apartado, en puntos
    DERIVA_MAX = 0.1   # cuánta probabilidad media en las estafas apartadas puede perder una versión nueva

    def __init__(self, apartado: list[tuple[Rasgos, int]], cada: int = 6, tasa: float = 0.5,
                 l2: float = 1e-3, sesgo: float = -1.5, semilla: int = 3,
                 meta: Optional[list[dict[str, Any]]] = None):
        self.apartado = apartado
        # Lo que se sabe de cada correo apartado (escenario, familia, mecanismo, canal), en el mismo orden. Sirve para
        # decir qué estafas se colaron; sin él, `colados` sale vacío.
        if meta is not None and len(meta) != len(apartado):
            raise ValueError("meta tiene que traer una entrada por correo apartado")
        self.meta = meta
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
        self.mejor_p_estafas = self.p_medio_estafas()
        self.falsas_alarmas_base = self.metricas["falsas_alarmas"]
        self.revertidas = 0                    # versiones descartadas por la guardia de deriva
        self._estado_bueno = self._estado()

    def p_medio_estafas(self) -> float:
        """Probabilidad media que el modelo da hoy a las estafas del conjunto apartado."""
        ps = [self.probabilidad(r) for r, y in self.apartado if y]
        return float(sum(ps) / len(ps)) if ps else 0.0

    def _estado(self) -> tuple[np.ndarray, np.ndarray, float]:
        return self.w.copy(), self.wh.copy(), self.b

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
        if len(self._memoria) > self.MEMORIA_MAX:
            del self._memoria[0]
        self.ejemplos += 1
        if self.ejemplos % self.cada:
            return None
        # Reentrenamiento incremental: dos pasadas sobre lo visto, en otro orden.
        base = self._memoria
        if len(base) > self.REENTRENO_MAX:   # una muestra al azar de lo visto, más las etiquetas del último lote
            base = self._rng.sample(self._memoria[:-self.cada], self.REENTRENO_MAX - self.cada) + self._memoria[-self.cada:]
        for _ in range(2):
            orden = list(base)
            self._rng.shuffle(orden)
            for ri, yi in orden:
                self._paso(ri, yi)
        metricas = self.evaluar()
        p_estafas = self.p_medio_estafas()
        if (p_estafas < self.mejor_p_estafas - self.DERIVA_MAX
                or metricas["falsas_alarmas"] > self.falsas_alarmas_base + self.PRESUPUESTO_FALSAS_ALARMAS):
            # Deriva sospechosa: se vuelve a la última versión buena y se descarta el lote que la causó.
            self.w, self.wh, self.b = (a.copy() if hasattr(a, "copy") else a for a in self._estado_bueno)
            del self._memoria[-self.cada:]
            self.revertidas += 1
            return None
        antes = self._pesos_version
        self.n_version += 1
        self._pesos_version = self.pesos()
        self.metricas = metricas
        self.mejor_p_estafas = max(self.mejor_p_estafas, p_estafas)
        self._estado_bueno = self._estado()
        cambios = [{"senal": k, "peso_antes": round(antes[k], 3), "peso_despues": round(v, 3)}
                   for k, v in self._pesos_version.items() if abs(v - antes[k]) >= 0.005]
        cambios.sort(key=lambda c: -abs(c["peso_despues"] - c["peso_antes"]))
        return self.evento_modelo(cambios)

    def evaluar(self) -> dict[str, Any]:
        """Precisión, recall y falsas alarmas (FP / (FP + TN)) en el conjunto apartado, y las estafas que se colaron.

        `colados` son las estafas apartadas que el modelo dejó bajo el umbral (los falsos negativos del recall),
        agrupadas por escenario y canal: cuántos correos se colaron (`n`) de cuántos había (`de`) y la probabilidad
        media y máxima que les dio. Lo que se cuela aquí no se paga solo: la capa 1 y la capa 2 corren igual.
        """
        tp = fp = tn = fn = 0
        colados: dict[tuple[str, str], dict[str, Any]] = {}
        estafas: dict[tuple[str, str], int] = {}
        for i, (r, y) in enumerate(self.apartado):
            p = self.probabilidad(r)
            pred = p > self.UMBRAL
            m = self.meta[i] if self.meta is not None else None
            clave = (str(m.get("escenario")), str(m.get("canal"))) if m else None
            if y and clave:
                estafas[clave] = estafas.get(clave, 0) + 1
            if pred and y:
                tp += 1
            elif pred:
                fp += 1
            elif y:
                fn += 1
                if clave:
                    c = colados.setdefault(clave, {**m, "n": 0, "_ps": []})
                    c["n"] += 1
                    c["_ps"].append(p)
            else:
                tn += 1
        lista = []
        for clave, c in colados.items():
            ps = c.pop("_ps")
            lista.append({**c, "de": estafas[clave], "probabilidad": round(sum(ps) / len(ps), 3),
                          "probabilidad_max": round(max(ps), 3)})
        lista.sort(key=lambda c: (-c["n"], c["probabilidad"], c["escenario"], c["canal"]))
        return {
            "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
            "falsas_alarmas": round(fp / (fp + tn), 3) if fp + tn else 0.0,
            "evaluado_en": len(self.apartado),
            "colados": lista,
        }

    def evento_modelo(self, cambios: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        return {"tipo": "modelo", "version": self.version, "ejemplos": self.ejemplos,
                **self.metricas, "cambios": cambios or []}
