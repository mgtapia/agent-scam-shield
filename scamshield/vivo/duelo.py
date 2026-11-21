"""El duelo: un atacante que aprende de cómo lo bloquean, y un escudo que aprende de él.

Cada generación el atacante (`scamshield/attacker/mutador.py`, sin API) manda varias estafas
mutadas, una o dos por cada línea de ataque. El escudo real las evalúa sin haberlas visto:

- la bóveda y el clasificador dan su veredicto (seguro, sospechoso o estafa);
- el agente ingenuo intenta pagar, y las capas 1 y 2 deciden sobre el pago.

El atacante recibe el motivo del bloqueo (la señal que más pesó, o el indicador de la bóveda) y
actualiza su bandido. Después el dueño simulado confirma que todas eran estafas: eso reentrena el
clasificador y llena la bóveda, y también etiqueta unos correos legítimos para que no aprenda a
sospechar de todo. El conjunto apartado del clasificador nunca se entrena.

Lo que muestra:
- el hacker aprende a engañar al clasificador (sube la evasión);
- el escudo responde al reentrenar (baja la evasión, sube el recall en mutaciones nuevas);
- la capa 2 no se entrena y no se mueve: ninguna mutación llega a ejecutar un pago, porque la cuenta
  sale de un correo y no del dueño. `sin_capa2` cuenta cuántos pagos habrían salido sin ella.

Es la misma simulación del modo en vivo, con el mismo clasificador y la misma bóveda.
"""
from __future__ import annotations

import dataclasses
import random
from collections import Counter, deque
from typing import TYPE_CHECKING, Any, Optional

from ..attacker.mutador import Bandido, Cepa, candidatos, semillas_de
from ..defenses.layer2 import politica_origen
from .clasificador import Clasificador
from .flujo import Correo

if TYPE_CHECKING:  # el motor importa este módulo, no al revés
    from .motor import Motor

RIESGO = {"seguro": 0, "sospechoso": 1, "estafa": 2}
MEJORA_MINIMA = 0.02   # cuánto tiene que bajar el riesgo para contar como un acierto del atacante


def senal_de_bloqueo(v: dict[str, Any]) -> str:
    """El motivo que recibe el atacante: qué señal o qué indicador bloqueó el correo."""
    if v["decision"] == "seguro":
        return "ninguna"
    if v["fuente"] == "boveda":
        return v["senales"][0]["nombre"] if v["senales"] else "boveda"
    if v["fuente"] == "origen":
        return "cuenta_nueva" if v["capa"] == "2" else "instruccion_oculta"
    return v["senales"][0]["nombre"] if v["senales"] else "clasificador"


class Duelo:
    def __init__(self, motor: "Motor", semilla: int = 0, por_cepa: int = 2, legitimos: Optional[int] = None,
                 entrenar: bool = True):
        self.motor = motor
        self.entrenar = entrenar
        self.por_cepa = por_cepa
        self.legitimos = 0   # se fija abajo, cuando se sabe cuántas líneas de ataque hay
        self.rng = random.Random(semilla)
        self.bandido = Bandido(semilla + 1)
        self.generacion_n = 0
        self.historial: deque[dict[str, Any]] = deque(maxlen=50)
        self.ultimo_lote: list[dict[str, Any]] = []
        flujo = motor.flujo
        propias = random.Random(semilla + 2)    # sin tocar el azar del flujo en vivo
        correos: list[Correo] = []
        for u in flujo.unidades:
            if u.familia == "ingenieria_social" and u.clave not in flujo.claves_evaluacion and "es" in u.escenarios:
                correos += flujo.episodio(clave=u.clave, idioma="es", rng=propias, prefijo="d")
        self.cepas = [Cepa(c) for c in semillas_de(correos)]
        self._controles = [u.clave for u in flujo.unidades
                           if u.familia == "control" and u.clave not in flujo.claves_evaluacion]
        if not self.cepas:
            raise ValueError("el corpus no tiene estafas de ingeniería social con una cuenta que mutar")
        # Tantos legítimos como estafas: con menos, el clasificador «se recupera» marcando todo.
        self.legitimos = legitimos if legitimos is not None else por_cepa * len(self.cepas)

    # --- una estafa contra el escudo -----------------------------------------------------------------
    def _evaluar(self, correos: list[Correo]) -> dict[str, Any]:
        """Lo que hace el escudo con una estafa de uno o dos correos, sin entrenar con ella."""
        m = self.motor
        evaluados = []
        for c in correos:
            ras = m._rasgos(c)
            v = m._veredicto(c, ras, m.boveda.revisar(c))
            evaluados.append((c, v, m.clasificador.probabilidad(ras)))
        # El pedido se evade solo si ningún correo del grupo levanta la alarma: vale el peor.
        peor_c, peor_v, _ = max(evaluados, key=lambda t: (RIESGO[t[1]["decision"]], t[2]))
        portador, v_portador, p_portador = evaluados[-1]
        accion = m._accion(portador, v_portador)
        capa2 = politica_origen(portador.mundo(), portador.accion["herramienta"], portador.accion["args"])
        decision = peor_v["decision"]
        p_max = max(p for *_, p in evaluados)
        return {
            "decision": decision, "p": p_max, "p_clasificador": p_portador,
            "senal": senal_de_bloqueo(peor_v), "capa": peor_v["capa"], "fuente": peor_v["fuente"],
            "resultado": accion["resultado"], "capa_pago": accion["capa"], "motivo_pago": accion["motivo"],
            "capa2_retiene": capa2 is not None,
            "sin_capa2": decision == "seguro",   # sin capa 2, el agente ingenuo habría pagado
            "puntaje": RIESGO[decision] + p_max,
        }

    def _intento(self, cepa: Cepa, direcciones: list[str], n: int, k: int) -> dict[str, Any]:
        primera = cepa.puntaje is None
        orden = ["reenviar"] if primera else self.bandido.orden(cepa.contexto)
        contexto = cepa.contexto
        for nombre in orden:
            correos, cuenta, cambio = candidatos(cepa, nombre, self.rng, direcciones)
            if cambio or nombre == "reenviar":
                break
        correos = [dataclasses.replace(c, id=f"d{n:03d}-{k:03d}-{j}", etiqueta="estafa")
                   for j, c in enumerate(correos)]
        r = self._evaluar(correos)
        if not primera:
            exito = r["puntaje"] < cepa.puntaje - MEJORA_MINIMA or (r["decision"] == "seguro" and contexto == "ninguna")
            self.bandido.actualizar(contexto, nombre, exito)
        else:
            exito = True
        if exito or r["puntaje"] <= (cepa.puntaje or 0) + MEJORA_MINIMA:
            if cambio and nombre != "reenviar":
                cepa.aplicadas.append(nombre)
            cepa.puntaje, cepa.contexto = r["puntaje"], r["senal"]
        return {**r, "mutacion": nombre, "contexto": contexto, "exito": exito, "correos": correos,
                "cuenta": cuenta, "linea": cepa.semilla.unidad}

    # --- una generación ----------------------------------------------------------------------------------
    def generacion(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Corre una generación. Devuelve (el evento `duelo`, los eventos `modelo` y `boveda` que dejó)."""
        m = self.motor
        self.generacion_n += 1
        n = self.generacion_n
        direcciones = sorted(m.libreta.direcciones)
        lote: list[dict[str, Any]] = []
        for cepa in self.cepas:
            for _ in range(self.por_cepa):
                lote.append(self._intento(cepa, direcciones, n, len(lote)))
        total = len(lote)
        evadidas = [r for r in lote if r["decision"] == "seguro"]
        motivos = Counter(r["senal"] for r in lote if r["decision"] != "seguro")
        top = self.bandido.mejores(3)
        extras: list[dict[str, Any]] = []
        if self.entrenar:
            extras = self._aprender(lote)
        cl = m.clasificador
        evento = {
            "tipo": "duelo", "generacion": n, "candidatos": total,
            "evasion": round(len(evadidas) / total, 3),
            "recall": cl.metricas["recall"],                     # en el conjunto apartado
            "recall_mutaciones": round(sum(r["p_clasificador"] >= Clasificador.UMBRAL for r in lote) / total, 3),
            "falsas_alarmas": cl.metricas["falsas_alarmas"],
            "exitosas_capa2": sum(r["resultado"] == "ejecutada" for r in lote),
            "sin_capa2": len(evadidas),
            "mutacion_top": top[0]["mutacion"] if top else "",
            "top_mutaciones": top,
            "motivo_bloqueo": motivos.most_common(1)[0][0] if motivos else "ninguna",
            "motivos": dict(motivos),
            "version_modelo": cl.version,
        }
        self.historial.append(evento)
        self.ultimo_lote = lote
        return evento, extras

    def _aprender(self, lote: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """El dueño simulado confirma las estafas y etiqueta unos legítimos: reentrena clasificador y bóveda."""
        m = self.motor
        extras: list[dict[str, Any]] = []
        ts = m.reloj()
        for r in lote:
            for c in r["correos"]:
                for ind in m.boveda.confirmar(c, ts):
                    extras.append({"tipo": "boveda", "indicador": ind.a_dict()})
                ev = m.clasificador.aprender(m._rasgos(c), 1)
                if ev:
                    extras.append(ev)
        for c in self._legitimos_de_la_generacion():
            m.boveda.vio_legitimo(c)
            ev = m.clasificador.aprender(m._rasgos(c), 0)
            if ev:
                extras.append(ev)
        return extras

    def _legitimos_de_la_generacion(self) -> list[Correo]:
        salida: list[Correo] = []
        while self._controles and len(salida) < self.legitimos:
            clave = self.rng.choice(self._controles)
            salida += [c for c in self.motor.flujo.episodio(clave=clave, idioma="es", rng=self.rng, prefijo="dl")
                       if c.etiqueta == "legitimo"]
        return salida[:self.legitimos]


def tabla(historial: list[dict[str, Any]]) -> str:
    """La tabla del duelo en markdown, una fila por generación."""
    filas = ["| Gen. | Evasión | Recall apartado | Recall mutaciones | Falsas alarmas | Pagos con capa 2 "
             "| Pagos sin capa 2 | Mutaciones que más le sirven | Lo que más lo bloquea |",
             "|---|---|---|---|---|---|---|---|---|"]
    for e in historial:
        top = ", ".join(f"{t['mutacion']} ({t['exitos']})" for t in e["top_mutaciones"]) or "—"
        filas.append(f"| {e['generacion']} | {e['evasion']:.0%} | {e['recall']:.0%} | {e['recall_mutaciones']:.0%} "
                     f"| {e['falsas_alarmas']:.0%} | {e['exitosas_capa2']} | {e['sin_capa2']} | {top} "
                     f"| {e['motivo_bloqueo']} |")
    return "\n".join(filas)
