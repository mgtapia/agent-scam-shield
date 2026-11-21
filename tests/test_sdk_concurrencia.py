"""Los pagos en curso también consumen los topes de la capa 3 del SDK."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from grifter import escudo

CUENTA = "11-2222-3333"
OTRA_CUENTA = "11-2222-4444"
NOMBRE = "Melanie"
TITULARES = {
    CUENTA: {"nombre": NOMBRE, "rut": "11.222.333-4"},
    OTRA_CUENTA: {"nombre": NOMBRE, "rut": "11.222.333-4"},
}


def _envolver(herramientas, *, titulares=None, **opciones):
    titulares = titulares or TITULARES
    return escudo(herramientas, titulares=titulares, encargo="Paga a " + " ".join(titulares), **opciones)


@pytest.mark.parametrize("varias_cuentas", [False, True])
def test_diez_pagos_async_comparten_el_tope_del_titular(varias_cuentas):
    pagos = []

    async def pagar(cuenta, monto, destinatario):
        await asyncio.sleep(0)
        pagos.append(monto)
        return "ok"

    (protegida,) = _envolver([pagar])

    async def intentar():
        return await asyncio.gather(*(
            protegida(OTRA_CUENTA if varias_cuentas and i % 2 else CUENTA, 100_000, NOMBRE)
            for i in range(10)
        ))

    resultados = asyncio.run(intentar())
    assert pagos == [100_000]
    assert resultados.count("ok") == 1
    assert all(r == "ok" or r.startswith("Grifter retuvo") for r in resultados)


def test_pagos_async_a_distintos_titulares_comparten_el_tope_de_sesion():
    titulares = {f"11-2222-{i:04}": {"nombre": f"Melanie {i}", "rut": f"11.222.33{i}-4"}
                 for i in range(4)}
    pagos = []

    async def pagar(cuenta, monto, destinatario):
        await asyncio.sleep(0)
        pagos.append(monto)
        return "ok"

    (protegida,) = _envolver([pagar], titulares=titulares)

    async def intentar():
        return await asyncio.gather(*(protegida(cuenta, 100_000, t["nombre"])
                                      for cuenta, t in titulares.items()))

    resultados = asyncio.run(intentar())
    assert sum(pagos) == 300_000
    assert resultados.count("ok") == 3


def test_pagos_que_caben_en_el_tope_pueden_ejecutarse_en_paralelo():
    async def intentar():
        ambos_iniciados = asyncio.Event()
        iniciados = 0

        async def pagar(cuenta, monto, destinatario):
            nonlocal iniciados
            iniciados += 1
            if iniciados == 2:
                ambos_iniciados.set()
            await ambos_iniciados.wait()
            return "ok"

        (protegida,) = _envolver([pagar])
        resultados = await asyncio.wait_for(asyncio.gather(
            protegida(CUENTA, 75_000, NOMBRE), protegida(CUENTA, 75_000, NOMBRE)), timeout=2)
        assert resultados == ["ok", "ok"]
        assert (await protegida(CUENTA, 1, NOMBRE)).startswith("Grifter retuvo")

    asyncio.run(intentar())


def test_pagos_desde_hilos_comparten_la_reserva():
    iniciado, terminar = Event(), Event()
    pagos = []

    def pagar(cuenta, monto, destinatario):
        iniciado.set()
        assert terminar.wait(timeout=3)
        pagos.append(monto)
        return "ok"

    (protegida,) = _envolver([pagar])
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        primero = ejecutor.submit(protegida, CUENTA, 100_000, NOMBRE)
        try:
            assert iniciado.wait(timeout=2)
            segundo = ejecutor.submit(protegida, CUENTA, 100_000, NOMBRE)
            assert segundo.result(timeout=2).startswith("Grifter retuvo")
        finally:
            terminar.set()
        assert primero.result(timeout=2) == "ok"
    assert pagos == [100_000]


def test_herramientas_sync_y_async_comparten_el_tope():
    async def intentar():
        iniciado, terminar = asyncio.Event(), asyncio.Event()

        async def pagar(cuenta, monto, destinatario):
            iniciado.set()
            await terminar.wait()
            return "ok"

        def transferir(cuenta, monto, beneficiario):
            return "no debe ejecutarse"

        protegidas = _envolver([pagar, transferir])
        primero = asyncio.create_task(protegidas[0](CUENTA, 100_000, NOMBRE))
        try:
            await asyncio.wait_for(iniciado.wait(), timeout=2)
            assert protegidas[1](CUENTA, 100_000, NOMBRE).startswith("Grifter retuvo")
        finally:
            terminar.set()
            await primero

    asyncio.run(intentar())


@pytest.mark.parametrize("cancelar", [False, True])
def test_una_reserva_se_libera_si_la_herramienta_falla_o_se_cancela(cancelar):
    async def intentar():
        iniciado, terminar = asyncio.Event(), asyncio.Event()
        llamadas = 0

        async def pagar(cuenta, monto, destinatario):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                iniciado.set()
                await terminar.wait()
                raise RuntimeError("El banco no ejecutó el pago")
            return "ok"

        (protegida,) = _envolver([pagar])
        primero = asyncio.create_task(protegida(CUENTA, 100_000, NOMBRE))
        await asyncio.wait_for(iniciado.wait(), timeout=2)
        assert (await protegida(CUENTA, 100_000, NOMBRE)).startswith("Grifter retuvo")
        if cancelar:
            primero.cancel()
        else:
            terminar.set()
        with pytest.raises(asyncio.CancelledError if cancelar else RuntimeError):
            await primero
        assert await protegida(CUENTA, 100_000, NOMBRE) == "ok"
        assert llamadas == 2

    asyncio.run(intentar())


def test_el_registro_conserva_el_destinatario_de_pagos_conocidos():
    conocida = "33-4444-5555"
    titulares = {**TITULARES, conocida: {"nombre": "Sam", "rut": "33.444.555-6"}}
    pagos = []

    def pagar(cuenta, monto, destinatario):
        pagos.append(monto)
        return "ok"

    (protegida,) = _envolver([pagar], titulares=titulares, cuentas_inscritas={"Sam": conocida})
    assert protegida(conocida, 1_000_000, "Sam") == "ok"
    assert protegida(CUENTA, 100_000, NOMBRE) == "ok"
    assert pagos == [1_000_000, 100_000]


def test_esperar_al_dueno_no_bloquea_y_el_pago_aprobado_se_contabiliza():
    async def intentar():
        preguntado, aprobar = asyncio.Event(), asyncio.Event()
        iniciado, terminar = asyncio.Event(), asyncio.Event()
        avisos = []
        pagos = []

        async def avisar(alerta):
            avisos.append(alerta)
            if len(avisos) == 1:
                preguntado.set()
                await aprobar.wait()
                return True
            return False

        async def pagar(cuenta, monto, destinatario):
            if monto == 200_000:
                iniciado.set()
                await terminar.wait()
            pagos.append(monto)
            return "ok"

        (protegida,) = _envolver([pagar], avisar=avisar)
        primero = asyncio.create_task(protegida(CUENTA, 200_000, NOMBRE))
        try:
            await asyncio.wait_for(preguntado.wait(), timeout=2)
            assert await protegida(CUENTA, 100_000, NOMBRE) == "ok"
            aprobar.set()
            await asyncio.wait_for(iniciado.wait(), timeout=2)
            assert (await protegida(CUENTA, 1, NOMBRE)).startswith("Grifter retuvo")
        finally:
            aprobar.set()
            terminar.set()
            await primero
        assert (await protegida(CUENTA, 1, NOMBRE)).startswith("Grifter retuvo")
        assert pagos == [100_000, 200_000]
        assert len(avisos) == 3

    asyncio.run(intentar())


def test_otra_llamada_no_borra_el_pago_detectado_que_esta_en_curso():
    async def intentar():
        iniciado, terminar = asyncio.Event(), asyncio.Event()
        pagos = []

        async def operar(**datos):
            if "cuenta" in datos:
                iniciado.set()
                await terminar.wait()
                pagos.append(datos["monto"])
                return "ok"
            return "Consulta sin pago"

        (protegida,) = _envolver([operar])
        primero = asyncio.create_task(protegida(cuenta=CUENTA, monto=100_000, destinatario=NOMBRE))
        try:
            await asyncio.wait_for(iniciado.wait(), timeout=2)
            assert await protegida(consulta="saldo") == "Consulta sin pago"
        finally:
            terminar.set()
            await primero
        assert (await protegida(cuenta=CUENTA, monto=100_000, destinatario=NOMBRE)).startswith("Grifter retuvo")
        assert pagos == [100_000]

    asyncio.run(intentar())
