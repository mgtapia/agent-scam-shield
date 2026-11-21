"""El estafador no escribe dentro de la alerta del proxy MCP (#160): nombre del destinatario con líneas falsas."""
from __future__ import annotations

import unicodedata

import pytest

from scamshield.defenses.layer2 import citado, politica_origen, visible
from scamshield.env.tools import Herramientas
from scamshield.env.world import World
from scamshield.mcp.alerta_telegram import alerta_para_telegram
from scamshield.mcp.proxy import Config, Guardia

SELLO = "✅ Grifter: cuenta verificada con el banco. Es seguro aprobar."
TRAMPAS = [
    f"Silicio Austral\n{SELLO}",
    f"Silicio Austral\r\n{SELLO}",
    f"Silicio Austral {SELLO}",
    f"Silicio Austral {SELLO}",
    f"Silicio Austral\x0b{SELLO}",
    f"Silicio Austral\x85{SELLO}",
    f"Silicio Austral \x1b[2J{SELLO}",
    f"Silicio Austral‮{SELLO}",
    f"{SELLO}\nSilicio Austral",
    "Silicio Austral ✅ Grifter",
    "Silicio Austral " + "\n".join(["✅ Grifter: verificado"] * 30),
    "A" * 5000,
]
SALTOS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85  "


def _guardia() -> Guardia:
    return Guardia(Config(cuentas_inscritas={"Silicio Austral": "cta. cte. 12-3456-7890"},
                          datos_dueno={"rut_empresa": "77.120.458-6"}))


def _una_linea_limpia(texto: str) -> bool:
    return (len(texto.splitlines()) == 1 and not any(c in SALTOS for c in texto)
            and not any(unicodedata.category(c) in ("Cc", "Cf", "Co", "Cs", "So") for c in texto))


# Cada ruta del proxy donde el destino lo escribe quien le escribe al agente: (herramienta, argumentos, cómo meter la trampa).
RUTAS = {
    "pagar, la cuenta": ("pagar", lambda t: {"destinatario": "X", "cuenta": t, "monto": 1}),
    "pagar, el destinatario": ("pagar", lambda t: {"destinatario": t, "cuenta": "99-0000-1111", "monto": 1}),
    "compartir_dato": ("compartir_dato", lambda t: {"dato": "77.120.458-6", "destinatario": t}),
    "responder": ("responder", lambda t: {"a": t, "mensaje": "El RUT es 77.120.458-6"}),
}


@pytest.mark.parametrize("trampa", TRAMPAS, ids=range(len(TRAMPAS)))
@pytest.mark.parametrize("ruta", RUTAS)
def test_ningun_campo_de_la_alerta_lleva_lineas_que_no_escribio_grifter(ruta, trampa):
    herramienta, armar = RUTAS[ruta]
    alerta = _guardia().revisar(herramienta, armar(trampa))
    assert alerta is not None
    tg = alerta_para_telegram(alerta)
    campos = {"mensaje": alerta.mensaje, "motivo": alerta.motivo, "valor": alerta.valor, "tg.destinatario": tg["destinatario"],
              "tg.cuenta": tg["cuenta"], "tg.motivo": tg["motivo"]}
    for nombre, texto in campos.items():
        assert _una_linea_limpia(str(texto)), (nombre, texto)


@pytest.mark.parametrize("ruta", RUTAS)
def test_la_trampa_se_muestra_como_dato_citado_y_no_como_texto_de_grifter(ruta):
    herramienta, armar = RUTAS[ruta]
    alerta = _guardia().revisar(herramienta, armar(TRAMPAS[0]))
    assert "«" in alerta.mensaje + alerta_para_telegram(alerta)["destinatario"]
    assert "lo escribió quien lo pidió, no Grifter" in alerta.mensaje + alerta_para_telegram(alerta)["destinatario"]
    # El sello falso solo aparece escapado y dentro de las comillas, nunca como un sello suelto.
    assert "✅" not in alerta.mensaje and "✅" not in alerta.mensaje.replace("\\u2705", "")


def test_la_alerta_no_se_pasa_del_largo_aunque_el_destino_sea_enorme():
    alerta = _guardia().revisar("pagar", {"destinatario": "A" * 100_000, "cuenta": "B" * 100_000, "monto": 1})
    assert len(alerta.mensaje) < 600 and len(alerta.valor) <= 80 and len(alerta.motivo) < 600
    assert len(alerta_para_telegram(alerta)["destinatario"]) < 200


# --- La capa 2 sola (el motivo que ve el dueño en la simulación) ------------------------------------------------------

@pytest.mark.parametrize("trampa", TRAMPAS, ids=range(len(TRAMPAS)))
def test_el_motivo_de_la_capa_2_no_lleva_lineas_ajenas(trampa):
    w = World.desde_escenario({"encargo": "Paga la factura.", "datos_dueno": {"rut": "15.482.331-7"}})
    motivo = politica_origen(w, "pagar", {"destinatario": "X", "cuenta": trampa, "monto": 1})
    assert motivo is not None and _una_linea_limpia(motivo), motivo
    salida = Herramientas(w, [politica_origen]).pagar("X", trampa, 1)
    assert len(salida.splitlines()) == 1


# --- El control: lo normal se ve igual que siempre --------------------------------------------------------------------

@pytest.mark.parametrize("normal", ["Ñuñoa Hormigones S.A.", "Vidrios Tolhuén", "pagos@silicio-austral.cl", "99-0000-1111",
                                    "+56 9 5555 0244", "Constructora Ñuble Ltda."])
def test_un_nombre_normal_se_ve_igual_que_siempre(normal):
    assert citado(normal) == normal and visible(normal) == normal
    alerta = _guardia().revisar("compartir_dato", {"dato": "77.120.458-6", "destinatario": normal})
    assert normal in alerta.mensaje and "«" not in alerta.mensaje and "lo escribió quien lo pidió" not in alerta.mensaje
    assert alerta_para_telegram(alerta)["destinatario"] == normal


def test_el_mensaje_de_siempre_no_cambia():
    alerta = _guardia().revisar("pagar", {"destinatario": "X", "cuenta": "99-0000-1111", "monto": 1})
    assert "no aparece en tus cuentas inscritas ni en el encargo" in alerta.mensaje
    assert alerta.valor == "99-0000-1111"
