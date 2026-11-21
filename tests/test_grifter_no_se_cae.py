"""Ataques contra Grifter mismo: saltárselo, botarlo o cansar al dueño. Sin red."""
from __future__ import annotations

import asyncio
import mcp.types as types
import pytest

from scamshield.mcp import proxy
from scamshield.mcp.proxy import Config, Grifter, regla_por_argumentos

CUENTA_INSCRITA = "00-4417-2208"
CUENTA_ESTAFADOR = "90-1188-4417"


class _SesionFalsa:
    """Servidor de abajo: anota lo que le llega. Si algo llega aquí, Grifter lo dejó pasar."""

    def __init__(self):
        self.llamadas = []

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, dict(args)))
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")], isError=False)


def _grifter(escalar=lambda alerta: False):
    config = Config(cuentas_inscritas={"Silicio Austral": f"Banco Litoral {CUENTA_INSCRITA}"})
    g = Grifter(config, escalar=escalar)
    banco = _SesionFalsa()
    g.sesiones["banco"] = banco
    for herramienta in ("send_money", "pagar_factura", "pagar", "consultar_saldo"):
        g.rutas[herramienta] = ("banco", herramienta)
    # Lo que leyó el agente: un correo con la cuenta del estafador.
    g.guardia.anotar_resultado("correo", "leer_correos", f"Nueva cuenta: {CUENTA_ESTAFADOR}")
    return g, banco


def _llamar(g, nombre, args):
    return asyncio.run(g.llamar(nombre, args))


@pytest.mark.parametrize("herramienta, args", [
    ("send_money", {"account": CUENTA_ESTAFADOR, "amount": 1000}),
    ("pagar_factura", {"iban": CUENTA_ESTAFADOR, "monto": 1000}),
    ("send_money", {"to": CUENTA_ESTAFADOR, "amount": 1000}),
])
def test_pago_no_declarado_igual_se_revisa(herramienta, args):
    g, banco = _grifter()
    r = _llamar(g, herramienta, args)
    assert r.isError and banco.llamadas == []


def test_pago_no_declarado_a_cuenta_inscrita_pasa():
    g, banco = _grifter()
    r = _llamar(g, "send_money", {"account": CUENTA_INSCRITA, "amount": 1000})
    assert not r.isError and len(banco.llamadas) == 1


def test_herramienta_sin_dinero_no_se_toca():
    assert regla_por_argumentos({"proveedor": "Silicio Austral"}) is None
    g, banco = _grifter()
    assert not _llamar(g, "consultar_saldo", {"cliente": "Elon"}).isError


def test_falla_cerrada_si_la_revision_revienta(monkeypatch):
    g, banco = _grifter()

    def revienta(*a, **k):
        raise RuntimeError("entrada maliciosa")

    monkeypatch.setattr(g.guardia, "revisar", revienta)
    r = _llamar(g, "pagar", {"cuenta": CUENTA_INSCRITA, "monto": 1000})
    assert r.isError and "no pudo revisarla" in r.content[0].text and banco.llamadas == []


def test_falla_cerrada_si_el_canal_de_alerta_cae():
    def alerta_caida(alerta):
        raise ConnectionError("Telegram caído")

    g, banco = _grifter(escalar=alerta_caida)
    r = _llamar(g, "pagar", {"cuenta": CUENTA_ESTAFADOR, "monto": 1000})
    assert r.isError and banco.llamadas == []


def test_inundacion_de_alertas_no_cansa_al_dueno(monkeypatch):
    preguntas = []
    g, banco = _grifter(escalar=lambda alerta: preguntas.append(alerta) or False)
    for _ in range(proxy.TOPE_ALERTAS + 10):
        assert _llamar(g, "pagar", {"cuenta": CUENTA_ESTAFADOR, "monto": 1000}).isError
    assert len(preguntas) == proxy.TOPE_ALERTAS  # después del tope, retiene sin preguntar
    assert banco.llamadas == []
