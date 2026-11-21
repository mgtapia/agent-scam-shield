"""El tope por cuenta en una ventana de 30 días, de punta a punta en el proxy MCP, alimentado con grifter_eventos.jsonl (#149)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import mcp.types as types
import yaml

from scamshield.mcp.integridad import politica_canonica
from scamshield.mcp.proxy import Config, Grifter, cargar_config

CUENTA, ALERCE = "47-3310-9082", "33-7741-2056"


class SesionFalsa:
    def __init__(self):
        self.llamadas = []

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, args))
        return types.CallToolResult(content=[types.TextContent(type="text", text="pago anotado")], isError=False)


def _proxy(tmp_path, tope=150_000, escalar=lambda a: False, inscritas=None, **extra):
    config = Config(encargo=f"Haz mi aporte de este mes a la cuenta {CUENTA} y paga el arriendo a la cuenta {ALERCE}.",
                    cuentas_inscritas=inscritas or {}, registro=tmp_path / "grifter_eventos.jsonl",
                    tope_ventana=tope, **extra)
    g = Grifter(config, escalar=escalar)
    abajo = SesionFalsa()
    g.sesiones["banco"] = abajo
    g.rutas["pagar"] = ("banco", "pagar")
    return g, abajo


def _pagar(g, monto, cuenta=CUENTA):
    return asyncio.run(g.llamar("pagar", {"destinatario": "Plataforma Cumbre", "cuenta": cuenta, "monto": monto}))


def _sembrar(tmp_path, *pagos):
    """Eventos de pago de antes: (monto, hace_dias, evento, cuenta)."""
    ahora = datetime.now(timezone.utc)
    filas = []
    for monto, hace, evento, cuenta in pagos:
        args = {"destinatario": "Plataforma Cumbre", "cuenta": cuenta, "monto": monto}
        base = {"ts": (ahora - timedelta(days=hace)).isoformat(), "evento": evento}
        filas.append({**base, "herramienta": "pagar", "servidor": "banco", "args": args} if evento == "permitido"
                     else {**base, "herramienta": "pagar", "servidor": "banco", "args": args, "valor": cuenta, "motivo": "m",
                           "mensaje": "m", "fuentes": []})
    (tmp_path / "grifter_eventos.jsonl").write_text("\n".join(json.dumps(f) for f in filas) + "\n", encoding="utf-8")


def test_los_aportes_crecientes_del_catalogo_se_retienen(tmp_path):
    avisos = []
    g, abajo = _proxy(tmp_path, escalar=lambda a: avisos.append(a) or False)
    _sembrar(tmp_path, (120_000, 21, "permitido", CUENTA), (140_000, 9, "aprobado_por_dueno", CUENTA))
    r = _pagar(g, 150_000)
    assert r.isError and abajo.llamadas == []
    assert "llevas $410.000 a esta cuenta" in r.content[0].text and "este mes" in r.content[0].text
    assert avisos and avisos[0].motivo.startswith("llevas $410.000")


def test_en_vivo_el_segundo_aporte_que_pasa_el_tope_se_retiene(tmp_path):
    g, abajo = _proxy(tmp_path)
    assert not _pagar(g, 100_000).isError and len(abajo.llamadas) == 1   # el primero pasa y queda en el registro
    r = _pagar(g, 60_000)                                                # 160.000 en total
    assert r.isError and len(abajo.llamadas) == 1
    assert not _pagar(g, 50_000).isError and len(abajo.llamadas) == 2    # justo en el tope (150.000)


def test_lo_retenido_no_cuenta_como_pagado(tmp_path):
    g, abajo = _proxy(tmp_path)
    assert _pagar(g, 200_000).isError   # un primer pago grande se retiene
    assert not _pagar(g, 100_000).isError and len(abajo.llamadas) == 1


def test_lo_que_el_dueno_aprueba_cuenta_para_el_mes_siguiente(tmp_path):
    g, abajo = _proxy(tmp_path, escalar=lambda a: True)
    assert not _pagar(g, 200_000).isError   # el dueño lo aprobó
    g.escalar = lambda a: False
    r = _pagar(g, 10_000)
    assert r.isError and "$210.000" in r.content[0].text


def test_lo_de_hace_mas_de_30_dias_no_cuenta(tmp_path):
    g, abajo = _proxy(tmp_path)
    _sembrar(tmp_path, (140_000, 31, "permitido", CUENTA), (140_000, 90, "permitido", CUENTA))
    assert not _pagar(g, 150_000).isError and len(abajo.llamadas) == 1


def test_el_arriendo_mensual_a_una_cuenta_inscrita_sale_sin_friccion(tmp_path):
    g, abajo = _proxy(tmp_path, inscritas={"Rentas Alerce": f"Banco Litoral cta. cte. {ALERCE}"})
    _sembrar(tmp_path, (450_000, 30, "permitido", ALERCE), (450_000, 1, "permitido", ALERCE))
    assert not _pagar(g, 450_000, cuenta=ALERCE).isError and len(abajo.llamadas) == 1


def test_sin_tope_el_proxy_se_comporta_como_antes(tmp_path):
    g, abajo = _proxy(tmp_path, tope=0)
    _sembrar(tmp_path, (900_000, 1, "permitido", CUENTA))
    assert not _pagar(g, 900_000).isError and len(abajo.llamadas) == 1


def test_sin_registro_no_hay_historial_pero_el_pago_se_revisa_igual(tmp_path):
    g, abajo = _proxy(tmp_path)
    g.config.registro = None
    assert _pagar(g, 150_001).isError and abajo.llamadas == []
    assert not _pagar(g, 150_000).isError


def test_un_registro_con_lineas_rotas_no_tumba_el_pago(tmp_path):
    g, abajo = _proxy(tmp_path)
    (tmp_path / "grifter_eventos.jsonl").write_text("{rota\n\n[]\n", encoding="utf-8")
    assert not _pagar(g, 100_000).isError


# --- La política: el tope es parte de la huella solo si está, y se lee del yaml --------------------------------------

def test_la_huella_no_cambia_si_no_hay_tope_y_cambia_si_lo_hay():
    sin = politica_canonica(Config())
    assert "tope_ventana" not in sin
    con = politica_canonica(Config(tope_ventana=150_000, ventana_dias=30))
    assert con["tope_ventana"] == {"monto": 150_000, "dias": 30}


def test_el_yaml_declara_el_tope(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    ruta.write_text(yaml.safe_dump({"servidores": {}, "tope_ventana": 150000, "ventana_dias": 15}), encoding="utf-8")
    config = cargar_config(ruta)
    assert (config.tope_ventana, config.ventana_dias) == (150_000, 15)
    ruta.write_text(yaml.safe_dump({"servidores": {}}), encoding="utf-8")
    config = cargar_config(ruta)
    assert (config.tope_ventana, config.ventana_dias) == (0, 30)
