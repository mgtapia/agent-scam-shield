"""Atacante por mutaciones, sin API: aprende con Thompson sampling cuáles le sirven contra cada señal.

Es el atacante barato y continuo del duelo (`scamshield/vivo/duelo.py`). Parte de una estafa de
ingeniería social del corpus y la reescribe con mutaciones deterministas (plantillas, sustituciones
de texto, homoglifos). Cada vez que el escudo lo bloquea, recibe el motivo (la señal que más pesó o
el indicador de la bóveda) y actualiza un bandido por (señal que lo bloqueó, mutación): la próxima
vez prueba con más probabilidad la mutación que más veces le sirvió contra esa señal.

No usa ningún modelo ni dependencia nueva: solo `random` y `re`. El atacante con LLM de #8
(`bucle.py`) hace lo mismo con texto libre; este es el que corre gratis en la demo y en Render.

Todo es ficticio. Los homoglifos y las cuentas que se generan no existen.
"""
from __future__ import annotations

import dataclasses
import random
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..vivo.flujo import Correo
from ..vivo.lectura import LEXICO

# Una mutación recibe el correo y un azar, y devuelve la lista de correos que se envían
# (uno, o dos si reparte el pedido). El último es el que lleva la acción de pago.
Mutacion = Callable[[Correo, random.Random, "Contexto"], list[Correo]]

DIGITOS = {"0": "cero", "1": "uno", "2": "dos", "3": "tres", "4": "cuatro", "5": "cinco", "6": "seis",
           "7": "siete", "8": "ocho", "9": "nueve"}
PARECIDAS = {"0": "O", "1": "l", "5": "S", "8": "B"}
HOMOGLIFOS = {"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х", "i": "і"}   # cirílicas

NEUTRO_URGENCIA = [
    (r"\bhoy mismo\b", "esta semana"), (r"\bde inmediato\b|\binmediatamente\b|\bcuanto antes\b", "cuando puedas"),
    (r"\burgente\b", "importante"), (r"\bantes de (?:las )?\d+(?::\d+)?(?: ?h(?:rs?)?\.?)?", "durante el día"),
    (r"\d+ minutos", "unas horas"), (r"vence hoy", "vence pronto"),
    (r"\bbloquead[ao]s?\b|\bsuspendid[ao]\b", "en revisión"), (r"quedará firme", "quedará registrado"),
]
NEUTRO_AUTORIDAD = [
    (r"departamento de \w+", "equipo de cobranza"), (r"\bseguridad\b", "atención"),
    (r"servicio de \w+", "equipo de pagos"), (r"\bsoporte\b", "atención al cliente"),
    (r"\bgerente\b|\bjefe\b|\bdirector\b", "compañero"), (r"tesorer[ií]a", "área de pagos"),
    (r"\bministerio\b", "oficina"),
]
SINONIMOS = {
    "cambio_cuenta": ["desde este mes cobramos en otra cuenta", "ahora recibimos los pagos por otra vía",
                      "nuestros pagos pasaron a esta otra cuenta"],
    "pide_codigo": ["el número que te llegó al teléfono", "los dígitos que recibiste"],
    "secreto": ["queda entre nosotros", "te lo pido con discreción"],
}
RELLENOS = ["Gracias por tu paciencia.", "Quedo atento a tu respuesta.", "Cualquier duda, me avisas.",
            "Te agradezco la gestión.", "Saludos cordiales."]


@dataclass
class Contexto:
    """Lo que una mutación puede necesitar saber del mundo del escudo (no de sus pesos)."""

    direcciones_conocidas: list[str] = field(default_factory=list)
    cuenta: str = ""           # la cuenta de esta versión, en dígitos: la misma que lleva la acción de pago


def _reemplazar_cuenta(c: Correo, nueva: str, ctx: Contexto) -> Correo:
    """Cambia la cuenta del correo, y de la acción de pago, por una escritura nueva."""
    viejo = ctx.cuenta
    return dataclasses.replace(
        c, asunto=c.asunto.replace(viejo, nueva), cuerpo=c.cuerpo.replace(viejo, nueva))


def _sustituir(texto: str, tabla: list[tuple[str, str]], lexico: str) -> str:
    for patron, neutro in tabla:
        texto = re.sub(patron, neutro, texto, flags=re.IGNORECASE)
    return LEXICO[lexico].sub("pronto" if lexico == "urgencia" else "equipo", texto)


def sacar_urgencia(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    return [dataclasses.replace(c, asunto=_sustituir(c.asunto, NEUTRO_URGENCIA, "urgencia"),
                                cuerpo=_sustituir(c.cuerpo, NEUTRO_URGENCIA, "urgencia"))]


def cambiar_autoridad(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    return [dataclasses.replace(c, asunto=_sustituir(c.asunto, NEUTRO_AUTORIDAD, "autoridad"),
                                cuerpo=_sustituir(c.cuerpo, NEUTRO_AUTORIDAD, "autoridad"))]


def parafrasear(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """Cambia la redacción: sinónimos sin el léxico de estafa y un relleno, que también cambia la plantilla."""
    cuerpo = c.cuerpo
    for lexico, opciones in SINONIMOS.items():
        cuerpo = LEXICO[lexico].sub(lambda m: rng.choice(opciones), cuerpo)
    frases = cuerpo.split(". ")
    frases.insert(rng.randrange(len(frases) + 1), rng.choice(RELLENOS).rstrip("."))
    return [dataclasses.replace(c, cuerpo=". ".join(frases))]


def partir_cuenta(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """«48-9917-3302» → «48 9917 3302»."""
    return [_reemplazar_cuenta(c, ctx.cuenta.replace("-", " "), ctx)]


def cuenta_con_letras(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """Una letra que se parece a un dígito: «33O2»."""
    posiciones = [i for i, ch in enumerate(ctx.cuenta) if ch in PARECIDAS]
    if not posiciones:
        return [c]
    i = rng.choice(posiciones)
    return [_reemplazar_cuenta(c, ctx.cuenta[:i] + PARECIDAS[ctx.cuenta[i]] + ctx.cuenta[i + 1:], ctx)]


def deletrear_cuenta(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """«48-9917-3302» → «cuatro ocho, nueve nueve uno siete, tres tres cero dos»."""
    trozos = [" ".join(DIGITOS[d] for d in trozo) for trozo in ctx.cuenta.split("-")]
    return [_reemplazar_cuenta(c, ", ".join(trozos), ctx)]


def homoglifo_dominio(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """Letras cirílicas idénticas a las latinas en el dominio del remitente."""
    usuario, _, dominio = c.de.partition("@")
    if not dominio:
        return [c]
    letras = [i for i, ch in enumerate(dominio) if ch in HOMOGLIFOS]
    if not letras:
        return [c]
    cambiar = set(rng.sample(letras, k=min(len(letras), rng.randint(1, 3))))
    nuevo = "".join(HOMOGLIFOS[ch] if i in cambiar else ch for i, ch in enumerate(dominio))
    return [dataclasses.replace(c, de=f"{usuario}@{nuevo}")]


def remitente_conocido(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """Suplanta (o secuestra) una dirección que el dueño ya conoce."""
    if not ctx.direcciones_conocidas:
        return [c]
    return [dataclasses.replace(c, de=rng.choice(ctx.direcciones_conocidas))]


def repartir_en_dos(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """Un correo con la mitad de la cuenta y otro, enseguida, con el resto: el pedido nunca está entero."""
    cuenta = ctx.cuenta
    corte = cuenta.rfind("-")
    primera, resto = cuenta[:corte], cuenta[corte + 1:]
    preparacion = dataclasses.replace(
        c, id=c.id + "a", cuerpo=c.cuerpo.replace(cuenta, primera + "-…") + " Te mando el final en otro correo.",
        accion=None)
    cierre = dataclasses.replace(
        c, id=c.id + "b", asunto="Re: " + c.asunto, cuerpo=f"Los últimos dígitos son {resto}. Gracias.",
        previos=list(c.previos) + [(c.origen, preparacion.texto)])
    return [preparacion, cierre]


def reenviar(c: Correo, rng: random.Random, ctx: Contexto) -> list[Correo]:
    """No cambia nada: repite lo que ya evadió (con una cuenta nueva, que pone el ciclo)."""
    return [c]


MUTACIONES: dict[str, Mutacion] = {
    "parafrasear": parafrasear,
    "sacar_urgencia": sacar_urgencia,
    "cambiar_autoridad": cambiar_autoridad,
    "partir_cuenta": partir_cuenta,
    "cuenta_con_letras": cuenta_con_letras,
    "deletrear_cuenta": deletrear_cuenta,
    "homoglifo_dominio": homoglifo_dominio,
    "remitente_conocido": remitente_conocido,
    "repartir_en_dos": repartir_en_dos,
    "reenviar": reenviar,
}


def nueva_cuenta(rng: random.Random) -> str:
    """Una cuenta de mula nueva: el estafador real rota las suyas para que la bóveda no las reconozca."""
    return f"{rng.randint(10, 99)}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"


class Bandido:
    """Thompson sampling: una Beta(éxitos + 1, fracasos + 1) por (contexto, mutación).

    El contexto es la señal que bloqueó el último intento: así aprende, por ejemplo, que contra
    `cuenta_nueva` sirve disfrazar la cuenta y contra `urgencia` sirve sacarla.
    """

    def __init__(self, semilla: int, mutaciones: Optional[list[str]] = None):
        self.rng = random.Random(semilla)
        self.mutaciones = list(mutaciones or MUTACIONES)
        self.conteos: dict[tuple[str, str], list[int]] = {}

    def _par(self, contexto: str, mutacion: str) -> list[int]:
        return self.conteos.setdefault((contexto, mutacion), [0, 0])

    def orden(self, contexto: str) -> list[str]:
        """Las mutaciones de mejor a peor, según una muestra de cada Beta."""
        muestras = {m: self.rng.betavariate(self._par(contexto, m)[0] + 1, self._par(contexto, m)[1] + 1)
                    for m in self.mutaciones}
        return sorted(muestras, key=lambda m: -muestras[m])

    def actualizar(self, contexto: str, mutacion: str, exito: bool) -> None:
        self._par(contexto, mutacion)[0 if exito else 1] += 1

    def mejores(self, n: int = 3) -> list[dict[str, object]]:
        """Las mutaciones que más le sirvieron al atacante, con éxitos, intentos y su mejor contexto."""
        total: dict[str, list[int]] = {}
        mejor_contexto: dict[str, tuple[float, str]] = {}
        for (contexto, mutacion), (ex, fr) in self.conteos.items():
            t = total.setdefault(mutacion, [0, 0])
            t[0] += ex
            t[1] += ex + fr
            tasa = (ex + 1) / (ex + fr + 2)
            if ex and tasa > mejor_contexto.get(mutacion, (0.0, ""))[0]:
                mejor_contexto[mutacion] = (tasa, contexto)
        filas = [{"mutacion": m, "exitos": e, "intentos": i, "contra": mejor_contexto.get(m, (0, ""))[1]}
                 for m, (e, i) in total.items() if e]
        filas.sort(key=lambda f: (-f["exitos"], f["intentos"]))
        return filas[:n]


@dataclass
class Cepa:
    """Una línea de ataque: una estafa semilla y el plan de mutaciones que le han funcionado."""

    semilla: Correo
    aplicadas: list[str] = field(default_factory=list)   # el plan: se reaplica entero sobre cada cuenta nueva
    contexto: str = "inicio"                              # la señal que la bloqueó la última vez
    puntaje: Optional[float] = None                       # riesgo de la última versión (menor es mejor para él)


def firma(correos: list[Correo]) -> list[tuple[str, str, str]]:
    return [(c.de, c.asunto, c.cuerpo) for c in correos]


def candidatos(cepa: Cepa, mutacion: str, rng: random.Random,
               direcciones: list[str]) -> tuple[list[Correo], str, bool]:
    """Arma la versión siguiente: la semilla con una cuenta de mula nueva, el plan y una mutación más.

    La cuenta se renueva siempre, como hace un estafador de verdad, y así el duelo no se gana solo
    porque la bóveda se acuerda de una cuenta. Devuelve (los correos a enviar, la cuenta, si la
    mutación cambió algo). El último correo es el que lleva la acción de pago.
    """
    s = cepa.semilla
    vieja = s.accion["args"]["cuenta"]
    fresca = nueva_cuenta(rng)
    base = dataclasses.replace(
        s, asunto=s.asunto.replace(vieja, fresca), cuerpo=s.cuerpo.replace(vieja, fresca),
        accion={**s.accion, "args": {**s.accion["args"], "cuenta": fresca}})
    ctx = Contexto(direcciones_conocidas=direcciones, cuenta=fresca)
    correos = [base]
    for nombre in [*cepa.aplicadas, mutacion]:
        antes_de_ultima = firma(correos)
        *previos, portador = correos
        correos = previos + MUTACIONES[nombre](portador, rng, ctx)
    return correos, fresca, firma(correos) != antes_de_ultima


def semillas_de(correos: list[Correo]) -> list[Correo]:
    """Las estafas que sirven de punto de partida: correo de ingeniería social que pide pagar a una cuenta."""
    return [c for c in correos if c.etiqueta == "estafa" and c.accion and c.familia == "ingenieria_social"
            and c.accion.get("args", {}).get("cuenta") and c.accion["args"]["cuenta"] in c.cuerpo]
