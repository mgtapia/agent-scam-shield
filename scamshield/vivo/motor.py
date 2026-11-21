"""El motor del modo «Centro de operaciones»: agentes simulados con defensas reales.

Simulado: los agentes (Elon, Sam, Jensen, Jeff, Sergey y Steve), sus bandejas y el flujo de correos, y el
feedback del dueño (sale de la etiqueta del escenario).
Real, sobre cada correo y cada acción:
- la capa 1 (`reglas_inyeccion`) y la capa 2 (`politica_origen`), antes de cada pago, sobre el
  `World` real del episodio;
- la bóveda de indicadores (verificación inmediata, como un antivirus);
- el clasificador que aprende, con versiones y métricas sobre un conjunto apartado.

El motor es un generador de `(espera, evento)`: el hilo de `iniciar()` duerme la espera (según la
velocidad y la pausa) y publica el evento. Las pruebas avanzan paso a paso sin dormir.
"""
from __future__ import annotations

import random
import statistics
import threading
import time
from collections import deque
from typing import Any, Callable, Iterator, Optional

from .. import estandares
from ..defenses.layer1 import reglas_inyeccion
from ..defenses.layer2 import politica_origen
from ..env.world import LLAMADA, MCP, WEB, WHATSAPP
from .boveda import Boveda
from .clasificador import Clasificador, rasgos
from .duelo import Duelo
from .flujo import AGENTES, Correo, Flujo, _destino
from .lectura import tramos

EVENTOS_GUARDADOS = 2000
VELOCIDADES = (1, 2, 4)
IDIOMAS = {"es": ("es",), "en": ("en",), "ambos": ("es", "en")}


class Motor:
    def __init__(self, semilla: int = 7, reloj: Callable[[], float] = time.time,
                 flujo: Optional[Flujo] = None, cada: int = 6, duelo: bool = False):
        self.reloj = reloj
        self.rng = random.Random(semilla + 1)
        self.flujo = flujo or Flujo(semilla)
        self.libreta = self.flujo.libreta
        self.umbral_monto = self._umbral_monto()
        self.boveda = Boveda(self.libreta, self._cuentas_legitimas())
        self.evaluacion = evaluacion = self.flujo.conjunto_apartado()   # los correos apartados, en el orden del clasificador
        apartado = [(self._rasgos(c), int(c.etiqueta == "estafa")) for c in evaluacion]
        self.clasificador = Clasificador(apartado, cada=cada, meta=[ficha(c) for c in evaluacion])
        self.agentes: dict[str, dict[str, Any]] = {
            a: {"agente": a, "estado": "inactivo", "tarea": ""} for a in AGENTES}
        self.correos: deque[dict[str, Any]] = deque(maxlen=50)
        self._por_id: dict[str, dict[str, Any]] = {}
        self.bloqueos_por_capa = {"1": 0, "2": 0, "boveda": 0}
        self.totales = {"correos": 0, "estafas": 0, "pagos_ejecutados": 0, "retenidos": 0,
                        "escalados": 0}
        self.modelo = self.clasificador.evento_modelo()
        self.historial_modelo: deque[dict[str, Any]] = deque(maxlen=50)
        self.historial_bloqueos: deque[dict[str, Any]] = deque(maxlen=200)
        self.historial_duelo: deque[dict[str, Any]] = deque(maxlen=50)
        # El duelo (un atacante que aprende contra este mismo escudo) corre entre episodio y episodio.
        self._semilla = semilla
        self.duelo: Optional[Duelo] = None
        if duelo:
            self.activar_duelo()
        self._eventos: deque[tuple[int, dict[str, Any]]] = deque(maxlen=EVENTOS_GUARDADOS)
        self._seq = 0
        self._candado = threading.Lock()
        self._hilo: Optional[threading.Thread] = None
        self._pausa = threading.Event()
        self._despertar = threading.Event()
        self.velocidad = 1
        self._pasos = self.pasos()

    # --- configuración derivada del corpus -------------------------------------------------
    def _umbral_monto(self) -> int:
        montos = []
        for u in self.flujo.unidades:
            if u.familia != "control":
                continue
            for esc in u.escenarios.values():
                a = esc.get("evaluacion", {}).get("accion_legitima") or {}
                if "monto" in a.get("args", {}):
                    montos.append(int(a["args"]["monto"]))
        return int(3 * statistics.median(montos)) if montos else 2_000_000

    def _cuentas_legitimas(self) -> set[str]:
        cuentas = set()
        for u in self.flujo.unidades:
            for esc in u.escenarios.values():
                cuentas.update(str(v) for v in esc.get("cuentas_inscritas", {}).values())
                a = esc.get("evaluacion", {}).get("accion_legitima") or {}
                if a.get("args", {}).get("cuenta"):
                    cuentas.add(str(a["args"]["cuenta"]))
        return cuentas

    def _rasgos(self, c: Correo):
        return rasgos(c, self.libreta, self.umbral_monto)

    # --- generador de eventos --------------------------------------------------------------
    def pasos(self) -> Iterator[tuple[float, dict[str, Any]]]:
        yield 0.0, dict(self.modelo)
        for a in AGENTES:
            yield 0.05, {"tipo": "agente_estado", "agente": a, "estado": "inactivo", "tarea": ""}
        while True:
            yield from self.episodio(self.flujo.episodio())
            if self.duelo is not None:
                yield from self.paso_duelo()

    def activar_duelo(self) -> None:
        """Enciende el duelo. Va después de `precalentar()`: así el arranque no corre generaciones de más."""
        if self.duelo is None:
            self.duelo = Duelo(self, semilla=self._semilla)

    def paso_duelo(self) -> Iterator[tuple[float, dict[str, Any]]]:
        """Una generación del duelo: su evento, y lo que el escudo aprendió (modelo nuevo, bóveda)."""
        evento, extras = self.duelo.generacion()
        yield 0.3, evento
        for ev in extras:
            yield 0.05, ev

    def episodio(self, correos: list[Correo]) -> Iterator[tuple[float, dict[str, Any]]]:
        """Los eventos de un episodio: lo que le pasa a un agente con los correos de un escenario."""
        if not correos:
            return
        r = self.rng
        agente = correos[0].agente
        for i, c in enumerate(correos):
            yield (0.4 if i == 0 else r.uniform(0.6, 1.6)), self._estado(agente, "leyendo", c.tarea)
            # `canal` es opcional: sin él, el evento es un correo. Con `canal: "llamada"`, `de` es el número que
            # se muestra (falsificable), `asunto` dice quién dice ser quien llama y `cuerpo` es la transcripción.
            canal = {"canal": {LLAMADA: "llamada", WHATSAPP: "whatsapp"}[c.origen]} if c.origen in (LLAMADA, WHATSAPP) else {}
            yield 0.3, {"tipo": "correo_nuevo", "id": c.id, "agente": agente, "de": c.de,
                        "asunto": c.asunto, "cuerpo": c.cuerpo, "escenario": c.unidad, **canal}
            ras = self._rasgos(c)
            aciertos = self.boveda.revisar(c)
            veredicto = self._veredicto(c, ras, aciertos)
            if aciertos:
                # Verificación inmediata, antes de terminar de leer.
                yield 0.35, veredicto
                for ind in self.boveda.marcar(aciertos):
                    yield 0.1, {"tipo": "boveda", "indicador": ind.a_dict()}
            yield r.uniform(1.0, 3.0), {"tipo": "lectura", "id": c.id, "tramos": tramos(
                c, self.libreta, self.clasificador.pesos(), self.umbral_monto, self.boveda.cuentas())}
            if not aciertos:
                yield 0.3, self._estado(agente, "pensando", c.tarea)
                yield r.uniform(0.4, 0.9), veredicto
            if c.accion:
                yield 0.3, self._estado(agente, "pagando", _tarea_accion(c))
                yield r.uniform(0.5, 1.0), self._accion(c, veredicto)
            # Feedback simulado del dueño: la etiqueta del escenario.
            if c.etiqueta == "estafa":
                for ind in self.boveda.confirmar(c, self.reloj()):
                    yield 0.15, {"tipo": "boveda", "indicador": ind.a_dict()}
            elif c.etiqueta == "legitimo":
                self.boveda.vio_legitimo(c)
            if not self.flujo.es_evaluacion(c):
                ev = self.clasificador.aprender(ras, int(c.etiqueta == "estafa"))
                if ev:
                    yield 0.2, ev
        yield 0.3, self._estado(agente, "esperando", correos[-1].tarea)

    def _estado(self, agente: str, estado: str, tarea: str) -> dict[str, Any]:
        return {"tipo": "agente_estado", "agente": agente, "estado": estado, "tarea": tarea}

    def _veredicto(self, c: Correo, ras, aciertos) -> dict[str, Any]:
        p = self.clasificador.probabilidad(ras)
        senales = self.clasificador.contribuciones(ras)
        s = ras.senales
        tecnico = bool(s["instruccion_oculta"]) or c.origen in (WEB, MCP)
        if aciertos:
            decision, fuente, capa, confianza = "estafa", "boveda", "boveda", 0.99
            senales = [{"nombre": f"boveda_{i.tipo}", "peso": 1.0} for i in aciertos][:3] + senales
        elif s["instruccion_oculta"]:
            decision, fuente, capa, confianza = "estafa", "origen", "1", max(p, 0.95)
        elif p >= 0.7:
            decision, fuente, capa, confianza = "estafa", "clasificador", None, p
        elif s["cuenta_nueva"]:
            decision, fuente, capa, confianza = "sospechoso", "origen", "2", max(p, 0.6)
        elif p >= 0.45:
            decision, fuente, capa, confianza = "sospechoso", "clasificador", None, p
        else:
            decision, fuente, capa, confianza = "seguro", "clasificador", None, 1 - p
        familia = "legitimo" if decision == "seguro" else ("tecnico" if tecnico else "ingenieria_social")
        return {"tipo": "veredicto", "id": c.id, "decision": decision,
                "confianza": round(float(confianza), 3), "senales": senales, "fuente": fuente,
                "version_modelo": self.clasificador.version, "capa": capa, "familia": familia,
                "escenario": c.unidad}

    def _accion(self, c: Correo, veredicto: dict[str, Any]) -> dict[str, Any]:
        """El agente ingenuo intenta la acción que pide el correo. Antes corren la capa 1 y la 2."""
        herramienta = c.accion["herramienta"]
        args = dict(c.accion.get("args", {}))
        mundo = c.mundo()
        capa1 = reglas_inyeccion(mundo, herramienta, args)
        capa2 = politica_origen(mundo, herramienta, args)
        if capa1:
            resultado, capa, motivo = "retenida", "1", f"Capa 1: {capa1}"
        elif capa2:
            resultado, capa, motivo = "retenida", "2", f"Capa 2: {capa2}"
        elif veredicto["decision"] != "seguro":
            resultado = "escalada"
            capa = "boveda" if veredicto["fuente"] == "boveda" else None
            quien = "la bóveda" if capa else "el clasificador"
            motivo = (f"Las capas 1 y 2 la dejan pasar, pero {quien} la marca como "
                      f"{veredicto['decision']}: se le pregunta al dueño.")
        else:
            resultado, capa = "ejecutada", None
            motivo = "El destino viene del encargo o de las cuentas inscritas del dueño."
        return {"tipo": "accion", "id": c.id, "agente": c.agente, "herramienta": herramienta,
                "args": args, "resultado": resultado, "motivo": motivo, "capa": capa,
                "escenario": c.unidad}

    # --- publicación y estado --------------------------------------------------------------
    def publicar(self, ev: dict[str, Any]) -> dict[str, Any]:
        ev = dict(ev)
        ev["ts"] = round(self.reloj(), 3)
        with self._candado:
            self._seq += 1
            self._eventos.append((self._seq, ev))
            self._actualizar(ev)
        return ev

    def _actualizar(self, ev: dict[str, Any]) -> None:
        tipo = ev["tipo"]
        antes = dict(self.bloqueos_por_capa)
        self._actualizar_tipo(ev, tipo)
        if self.bloqueos_por_capa != antes:
            self.historial_bloqueos.append({"ts": ev["ts"], **self.bloqueos_por_capa})

    def _actualizar_tipo(self, ev: dict[str, Any], tipo: str) -> None:
        if tipo == "agente_estado":
            self.agentes[ev["agente"]] = {k: ev[k] for k in ("agente", "estado", "tarea", "ts")}
        elif tipo == "correo_nuevo":
            fila = {k: ev[k] for k in ("id", "agente", "de", "asunto", "cuerpo", "ts")}
            fila.update({"tramos": [], "veredicto": None, "accion": None, "juez": bool(ev.get("juez")),
                         "escenario": ev.get("escenario"), "canal": ev.get("canal", "correo")})
            self.correos.append(fila)
            self._por_id[ev["id"]] = fila
            vivos = {f["id"] for f in self.correos}
            self._por_id = {k: v for k, v in self._por_id.items() if k in vivos}
            self.totales["correos"] += 1
        elif tipo == "lectura" and ev["id"] in self._por_id:
            self._por_id[ev["id"]]["tramos"] = ev["tramos"]
        elif tipo == "veredicto":
            if ev["id"] in self._por_id:
                self._por_id[ev["id"]]["veredicto"] = {k: v for k, v in ev.items() if k not in ("tipo", "id")}
            if ev["fuente"] == "boveda":
                self.bloqueos_por_capa["boveda"] += 1
            if ev["decision"] == "estafa":
                self.totales["estafas"] += 1
        elif tipo == "accion":
            if ev["id"] in self._por_id:
                self._por_id[ev["id"]]["accion"] = {k: v for k, v in ev.items() if k not in ("tipo", "id")}
            if ev["resultado"] == "retenida":
                self.totales["retenidos"] += 1
                if ev["capa"] in ("1", "2"):
                    self.bloqueos_por_capa[ev["capa"]] += 1
            elif ev["resultado"] == "escalada":
                self.totales["escalados"] += 1
            else:
                self.totales["pagos_ejecutados"] += 1
        elif tipo == "modelo":
            self.modelo = ev
            self.historial_modelo.append(ev)
        elif tipo == "duelo":
            self.historial_duelo.append(ev)

    def siguiente(self) -> tuple[float, dict[str, Any]]:
        """El próximo paso del generador, publicado. Devuelve la espera que tenía y el evento."""
        espera, ev = next(self._pasos)
        return espera, self.publicar(ev)

    def precalentar(self, correos: int = 45, segundos_por_correo: float = 4.0) -> int:
        """Corre el mismo motor sin dormir hasta procesar unos correos, para no partir en frío.

        Es la misma simulación con las mismas defensas, solo que más rápida: el modelo ya sale
        con versión y métricas, y la bóveda con indicadores. Los ts quedan en el pasado reciente,
        como si el centro llevara unos minutos andando. Termina al cierre de un episodio.
        """
        reloj_real = self.reloj
        virtual = [reloj_real() - correos * segundos_por_correo]
        self.reloj = lambda: min(virtual[0], reloj_real())
        try:
            vistos = 0
            while True:
                espera, ev = next(self._pasos)
                virtual[0] += espera
                self.publicar(ev)
                if ev["tipo"] == "correo_nuevo":
                    vistos += 1
                if vistos >= correos and ev["tipo"] == "agente_estado" and ev["estado"] == "esperando":
                    return vistos
        finally:
            self.reloj = reloj_real

    def avanzar(self, n: int) -> list[dict[str, Any]]:
        """Publica `n` eventos sin dormir (para pruebas)."""
        return [self.siguiente()[1] for _ in range(n)]

    def foto(self) -> dict[str, Any]:
        with self._candado:
            return {
                "simulacion": "Simulación · motor real",
                "seq": self._seq,
                "pausa": self._pausa.is_set(),
                "velocidad": self.velocidad,
                "boveda": self.boveda.lista(),
                "modelo": dict(self.modelo),
                "agentes": [dict(v) for v in self.agentes.values()],
                "correos": [dict(f) for f in self.correos],
                "bloqueos_por_capa": dict(self.bloqueos_por_capa),
                "historial_modelo": [dict(e) for e in self.historial_modelo],
                "historial_bloqueos": [dict(e) for e in self.historial_bloqueos],
                "historial_duelo": [dict(e) for e in self.historial_duelo],
                "idioma": self.idioma,
                "totales": dict(self.totales),
            }

    def eventos_desde(self, seq: int) -> list[tuple[int, dict[str, Any]]]:
        with self._candado:
            return [(s, e) for s, e in self._eventos if s > seq]

    @property
    def seq(self) -> int:
        return self._seq

    # --- hilo -----------------------------------------------------------------------------
    def control(self, accion: str, valor: Any = None) -> dict[str, Any]:
        if accion == "pausa":
            self._pausa.set()
        elif accion == "seguir":
            self._pausa.clear()
        elif accion == "idioma":
            if valor not in IDIOMAS:
                raise ValueError(f"idioma debe ser uno de {sorted(IDIOMAS)}")
            self.flujo.activos = IDIOMAS[valor]
        elif accion == "velocidad":
            v = int(valor)
            if v not in VELOCIDADES:
                raise ValueError(f"velocidad debe ser una de {VELOCIDADES}")
            self.velocidad = v
        else:
            raise ValueError("accion debe ser pausa, seguir, velocidad o idioma")
        self._despertar.set()
        return {"pausa": self._pausa.is_set(), "velocidad": self.velocidad, "idioma": self.idioma}

    @property
    def idioma(self) -> str:
        return next((k for k, v in IDIOMAS.items() if v == tuple(self.flujo.activos)), "es")

    def iniciar(self) -> None:
        with self._candado:
            if self._hilo is not None:
                return
            self._hilo = threading.Thread(target=self._correr, name="vivo-motor", daemon=True)
        self._hilo.start()

    def _correr(self) -> None:
        while True:
            espera, ev = next(self._pasos)
            restante = espera
            while restante > 0 or self._pausa.is_set():
                if self._pausa.is_set():
                    self._despertar.wait(0.5)
                    self._despertar.clear()
                    continue
                tramo = min(restante, 0.25)
                self._despertar.wait(tramo / self.velocidad)
                self._despertar.clear()
                restante -= tramo
            self.publicar(ev)


def ficha(c: Correo) -> dict[str, Any]:
    """Qué estafa es un correo, para decir qué se coló: escenario, familia, mecanismo, OWASP/ATLAS y canal.

    `familia` es `anotaciones.familia` (la misma que usa `--agrupar familia`), no la clase del flujo
    (`ingenieria_social` o `tecnico`), que va en `clase`. `canal` es por donde llegó: correo, llamada, web o mcp.
    """
    anot = c.escenario.get("anotaciones", {})
    mecanismo = str(anot.get("fraud_mechanism") or "")
    try:
        e = estandares.clasificar(c.escenario)
        owasp, atlas = e.owasp, e.atlas
    except KeyError:
        owasp = atlas = estandares.POR_CONFIRMAR
    return {"escenario": c.unidad, "familia": str(anot.get("familia") or c.unidad), "mecanismo": mecanismo,
            "clase": c.familia, "canal": c.origen, "owasp": owasp, "atlas": atlas}


def _tarea_accion(c: Correo) -> str:
    h = c.accion["herramienta"]
    a = c.accion.get("args", {})
    destino = _destino(c.accion)
    if "monto" in a:
        return f"{h.capitalize()} ${int(a['monto']):,}".replace(",", ".") + f" a {destino}"
    return f"{h.capitalize()} a {destino}"


_motor: Optional[Motor] = None
_candado_global = threading.Lock()


def motor_global() -> Motor:
    """El motor del servidor: uno por proceso, con su hilo encendido."""
    global _motor
    with _candado_global:
        if _motor is None:
            _motor = Motor(semilla=int(time.time()) % 10_000)
            _motor.precalentar()
            _motor.activar_duelo()
        _motor.iniciar()
        return _motor
