"""La lectura de un correo: los tramos del cuerpo que importan, con su riesgo y por qué.

Los tramos de cuenta usan las mismas funciones de origen de la capa 2: el trozo se busca con el
mismo patrón de `_TOKEN` del mundo y su procedencia sale de `origenes_en` sobre lo que el agente
leyó (el encargo y las cuentas inscritas del dueño cuentan como origen seguro). Los tramos de
lenguaje (urgencia, código, autoridad) llevan como riesgo el peso que el clasificador aprendió
para esa señal, así que cambian a medida que aprende. Los de inyección usan los patrones reales de
la capa 1.

Los offsets `inicio` y `fin` son posiciones en `cuerpo`, tal como se emitió en `correo_nuevo`.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping, Optional

from ..defenses.layer1 import PATRONES_INYECCION
from ..defenses.layer2 import ORIGENES_SEGUROS
from ..env.world import _TOKEN, _normalizar, origenes_en
from .flujo import CUENTA, DIRECCION, URL, Correo, Libreta

_F = re.IGNORECASE

LEXICO: dict[str, re.Pattern] = {
    "urgencia": re.compile(
        r"\burgente\b|hoy mismo|de inmediato|inmediatamente|cuanto antes|antes de (?:las|\d+)|"
        r"vence hoy|se cierra|último aviso|bloquead[ao]s?|suspendid[ao]|quedará firme|"
        r"\d+ minutos|\burgent\b|immediately|right away|as soon as possible|within \d+|"
        r"last notice|will be (?:blocked|suspended|closed)|closes? (?:on|this)|expires? today", _F),
    "pide_codigo": re.compile(
        r"c[oó]digo|\bclave\b|contraseña|\bpin\b|\bsms\b|\.env\b|api[ _-]?key|password|"
        r"passcode|verification code|\bcode\b|\btoken\b", _F),
    "cambio_cuenta": re.compile(
        r"cambi\w* de (?:banco|cuenta)|cuenta nueva|nueva cuenta|actualiz\w* (?:los |sus |tus )?datos|"
        r"cuenta (?:anterior|antigua)|recaudaci[oó]n centralizada|new (?:bank )?account|"
        r"chang\w* (?:our |of )?(?:bank|account)|updated? (?:bank|account|payment) details|"
        r"(?:old|previous) account|centrali[sz]ed collection", _F),
    "autoridad": re.compile(
        r"\bgerente\b|departamento de \w+|\bseguridad\b|tesorer[ií]a|ministerio|servicio de \w+|"
        r"\bsoporte\b|\bjefe\b|\bdirector\b|\bmanager\b|security (?:team|department)|"
        r"\bdepartment\b|\bgovernment\b|\bsupport team\b|\btreasury\b|\bceo\b|\bboss\b", _F),
    "secreto": re.compile(
        r"confidencial|no (?:lo|se lo) (?:comentes|menciones|digas)|con nadie|"
        r"confidential|do not (?:tell|mention|share)|don't tell|with anyone", _F),
}
INYECCION = [re.compile(p, _F) for p in PATRONES_INYECCION] + [
    re.compile(r"display\s*:\s*none", _F),
    re.compile(r"(?:nota|note) (?:para|for) (?:asistentes|assistants?|agentes|agents)", _F),
]
MONTO = re.compile(r"(?:US)?\$\s?\d{1,3}(?:[.,]\d{3})+|(?:US)?\$\s?\d+")

NOTAS = {
    "urgencia": "presiona con el tiempo",
    "pide_codigo": "pide un código, una clave o un secreto",
    "cambio_cuenta": "anuncia un cambio de cuenta",
    "autoridad": "invoca una autoridad",
    "secreto": "pide reserva",
}
CLASE = {"urgencia": "urgencia", "pide_codigo": "codigo", "cambio_cuenta": "cuenta",
         "autoridad": "autoridad", "secreto": "urgencia"}


def sigmoide(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def monto_en(texto: str) -> list[tuple[int, int, int]]:
    """(inicio, fin, valor en pesos) de cada monto. Los montos en US$ no se convierten."""
    salida = []
    for m in MONTO.finditer(texto):
        digitos = re.sub(r"\D", "", m.group(0))
        if digitos:
            salida.append((m.start(), m.end(), int(digitos)))
    return salida


def cuentas_en(correo: Correo) -> list[tuple[int, int, str, bool]]:
    """(inicio, fin, cuenta, segura) de cada cuenta del cuerpo.

    La cuenta se reconoce con el patrón `_TOKEN` del mundo (el mismo que usa `_tokens`) y su
    procedencia con `origenes_en` sobre lo que el agente leyó, excluyendo este mismo correo.
    """
    previos = correo.mundo(con_extra=False).leidos[:-1]
    salida = []
    for m in _TOKEN.finditer(correo.cuerpo):
        for c in CUENTA.finditer(m.group(0)):
            valor = c.group(0)
            segura = bool(origenes_en(previos, valor) & ORIGENES_SEGUROS)
            salida.append((m.start() + c.start(), m.start() + c.end(), valor, segura))
    return salida


def dominios_en(correo: Correo) -> list[tuple[int, int, str]]:
    salida = []
    for patron in (DIRECCION, URL):
        for m in patron.finditer(correo.cuerpo):
            salida.append((m.start(1), m.end(1), m.group(1).lower()))
    return salida


def tramos(correo: Correo, libreta: Libreta, pesos: Mapping[str, float],
           umbral_monto: int, cuentas_boveda: Optional[set[str]] = None) -> list[dict[str, Any]]:
    """Los tramos marcados del cuerpo, sin solaparse, en orden de aparición."""
    cuerpo = correo.cuerpo
    boveda = {_normalizar(c) for c in (cuentas_boveda or set())}
    t: list[dict[str, Any]] = []

    def agregar(inicio, fin, clase, riesgo, nota):
        t.append({"inicio": inicio, "fin": fin, "texto": cuerpo[inicio:fin], "clase": clase,
                  "riesgo": round(max(0.0, min(1.0, riesgo)), 2), "nota": nota})

    for inicio, fin, valor, segura in cuentas_en(correo):
        if _normalizar(valor) in boveda:
            agregar(inicio, fin, "cuenta", 1.0, "cuenta en la bóveda: ya se usó en una estafa")
        elif segura:
            agregar(inicio, fin, "cuenta", 0.05, "está en tus cuentas inscritas o en tu encargo")
        else:
            agregar(inicio, fin, "cuenta", 0.9, "no está en tus cuentas inscritas ni en tu encargo")

    for inicio, fin, dominio in dominios_en(correo):
        parecido = libreta.parecido(dominio)
        if parecido:
            agregar(inicio, fin, "dominio", 0.9, f"se parece a {parecido}, pero no es")
        elif libreta.dominio_conocido(dominio):
            agregar(inicio, fin, "dominio", 0.1, "dominio conocido")
        else:
            agregar(inicio, fin, "dominio", 0.5, "dominio que nunca te escribió")

    for inicio, fin, valor in monto_en(cuerpo):
        if valor > umbral_monto:
            agregar(inicio, fin, "monto", sigmoide(pesos.get("monto_inusual", 0.0) + 1.0),
                    "monto muy por sobre lo habitual")
        else:
            agregar(inicio, fin, "monto", 0.15, "monto dentro de lo habitual")

    for senal, patron in LEXICO.items():
        riesgo = sigmoide(pesos.get(senal, 0.0))
        for m in patron.finditer(cuerpo):
            agregar(m.start(), m.end(), CLASE[senal], riesgo,
                    f"{NOTAS[senal]} · peso aprendido {pesos.get(senal, 0.0):+.2f}")

    for patron in INYECCION:
        for m in patron.finditer(cuerpo):
            agregar(m.start(), m.end(), "inyeccion", 1.0,
                    "instrucción escondida para el agente: la frena la capa 1")

    return _sin_solapes(t)


def _sin_solapes(t: list[dict[str, Any]]) -> list[dict[str, Any]]:
    t.sort(key=lambda x: (x["inicio"], -x["riesgo"], -(x["fin"] - x["inicio"])))
    salida: list[dict[str, Any]] = []
    for x in t:
        if x["fin"] <= x["inicio"]:
            continue
        if salida and x["inicio"] < salida[-1]["fin"]:
            continue
        salida.append(x)
    return salida
