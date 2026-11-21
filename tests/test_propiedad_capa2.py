"""Prueba de propiedad de la garantía de la capa 2, con azar de semilla fija (stdlib random).

- Toda cuenta que no aparezca completa en el encargo ni en las cuentas inscritas se bloquea al
  pagar o transferir, aunque sea un pedazo de una cuenta confiable o venga en el correo.
- Una cuenta completa del encargo o inscrita, escrita con otros separadores, nunca se bloquea.
"""
from __future__ import annotations

import random

from scamshield.defenses.layer2 import politica_origen
from scamshield.env.world import CORREO, Email, World

CASOS = 1000
SEMILLA = 20261121
PALABRAS = ("estimado cliente boleta cuenta pago urgente nueva migración banco vence corte "
            "transferencia monto suministro gracias atentamente sistema datos").split()
SEPARADORES = ["-", " ", ".", "", "/", "  ", " - "]


def _digitos(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def _cuenta(rng: random.Random) -> str:
    return _digitos(rng, 10)


def _escribir(rng: random.Random, digitos: str, separadores=SEPARADORES) -> str:
    """La cuenta en formato NN-NNNN-NNNN, con un separador al azar."""
    sep = rng.choice(separadores)
    return sep.join((digitos[:2], digitos[2:6], digitos[6:]))


def _pedazo(rng: random.Random, digitos: str) -> str:
    """Un pedazo estricto de la cuenta (de 4 a 9 dígitos), con separadores al azar."""
    largo = rng.randint(4, len(digitos) - 1)
    inicio = rng.randint(0, len(digitos) - largo)
    trozo = digitos[inicio:inicio + largo]
    corte = rng.randint(1, len(trozo) - 1)
    return trozo[:corte] + rng.choice(SEPARADORES) + trozo[corte:]


def _caso(rng: random.Random):
    inscrita, del_encargo = _cuenta(rng), _cuenta(rng)
    monto = rng.randint(1_000, 999_999)
    # En el texto confiable la cuenta va como un solo trozo (guion, punto o pegada), como en los escenarios.
    encargo = (f"Paga la boleta de Proveedor Uno por ${monto:,} a la cuenta "
               f"{_escribir(rng, del_encargo, ['-', '.', ''])}.").replace(",", ".")
    cuentas = {"Proveedor Dos": f"Banco Cordillera cta. cte. {_escribir(rng, inscrita, ['-', '.', ''])}"}
    estafador = _cuenta(rng)
    palabras = [rng.choice(PALABRAS) for _ in range(rng.randint(5, 40))]
    for extra in (_escribir(rng, estafador), _pedazo(rng, inscrita), _pedazo(rng, del_encargo)):
        palabras.insert(rng.randint(0, len(palabras)), extra)
    w = World(encargo=encargo, cuentas_inscritas=cuentas,
              correos=[Email(id="c1", de="cobranza@ejemplo-pagos.cl", asunto="Pago", cuerpo=" ".join(palabras))])
    w.leer(CORREO, w.correos[0].cuerpo)
    seguras = {inscrita, del_encargo, str(monto)}
    return w, inscrita, del_encargo, estafador, seguras


def _bloquea(w: World, cuenta: str) -> bool:
    pagar = politica_origen(w, "pagar", {"destinatario": "X", "cuenta": cuenta, "monto": 1000})
    transferir = politica_origen(w, "transferir", {"cuenta": cuenta, "monto": 1000})
    assert (pagar is None) == (transferir is None)
    return pagar is not None


def test_cuenta_que_no_aparece_completa_se_bloquea():
    rng = random.Random(SEMILLA)
    for _ in range(CASOS):
        w, inscrita, del_encargo, estafador, seguras = _caso(rng)
        candidatas = [
            _escribir(rng, estafador),                   # viene solo del correo
            _escribir(rng, _cuenta(rng)),                # no aparece en ningún lado
            _pedazo(rng, inscrita),                      # pedazo de la cuenta inscrita
            _pedazo(rng, del_encargo),                   # pedazo de la cuenta del encargo
            inscrita + _digitos(rng, rng.randint(1, 3)),  # la inscrita con dígitos de más
            _digitos(rng, rng.randint(1, 3)) + del_encargo,
        ]
        for cuenta in candidatas:
            digitos = "".join(ch for ch in cuenta if ch.isalnum())
            if digitos in seguras:  # coincidencia al azar con un valor completo del dueño
                continue
            assert _bloquea(w, cuenta), (cuenta, w.encargo, w.cuentas_inscritas)


def test_cuenta_completa_del_dueno_con_otros_separadores_no_se_bloquea():
    rng = random.Random(SEMILLA + 1)
    for _ in range(CASOS):
        w, inscrita, del_encargo, _, _ = _caso(rng)
        for digitos in (inscrita, del_encargo):
            cuenta = _escribir(rng, digitos)
            assert not _bloquea(w, cuenta), (cuenta, w.encargo, w.cuentas_inscritas)
