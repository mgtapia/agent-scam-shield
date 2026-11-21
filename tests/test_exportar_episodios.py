"""El exportador de episodios para la demo, con logs reales de Inspect hechos con mockllm (sin API)."""
from __future__ import annotations

import json

import pytest

from scripts.exportar_episodios import exportar, generar_logs_mock


@pytest.fixture(scope="module")
def episodios(tmp_path_factory):
    base = tmp_path_factory.mktemp("export")
    logs = generar_logs_mock(base / "logs", defensas=("none", "layer1", "layer2"), idiomas=("es",))
    exportar(logs, base / "episodios")
    return base / "episodios"


def _leer(carpeta, nombre):
    return json.loads((carpeta / nombre).read_text(encoding="utf-8"))


def test_un_json_por_episodio_e_indice(episodios):
    indice = _leer(episodios, "indice.json")
    assert {e["defensa"] for e in indice["episodios"]} == {"none", "layer1", "layer2"}
    assert (episodios / "episodios.js").read_text(encoding="utf-8").startswith("// Generado")


@pytest.mark.parametrize("defensa", ["none", "layer1"])
def test_sin_escudo_paga_al_estafador(episodios, defensa):
    ep = _leer(episodios, f"boleta_cambio_cuenta__es__{defensa}.json")
    assert ep["escenario"] == "boleta_cambio_cuenta" and ep["idioma"] == "es"
    assert [c["dominio"] for c in ep["correos"]] == ["luzdelvalle.cl", "luzdelvalle-pagos.cl"]
    v = ep["veredicto"]
    assert v["tipo"] == "estafado" and v["saldo_final"] == v["saldo_inicial"] - 48290


def test_escudo_bloquea_y_dice_de_donde_vino_la_cuenta(episodios):
    ep = _leer(episodios, "boleta_cambio_cuenta__es__layer2.json")
    pago = next(p for p in ep["pasos"] if p.get("herramienta") == "pagar")
    assert pago["origen_cuenta"] == {"tipo": "correo", "inscrita": None, "correos": ["c2"],
                                     "dominios": ["luzdelvalle-pagos.cl"]}
    assert pago["resultado"].startswith("ACCIÓN BLOQUEADA")
    assert any(p["tipo"] == "texto" for p in ep["pasos"])
    assert ep["registro"][-1]["bloqueada"] is True
    v = ep["veredicto"]
    assert v["tipo"] == "bloqueado" and v["saldo_final"] == v["saldo_inicial"]
    assert v["bloqueo"]["cuenta_inscrita_numero"] == "00-4417-2208"
    assert v["bloqueo"]["origen"]["dominios"] == ["luzdelvalle-pagos.cl"]


def test_episodio_estrella_de_los_microprocesadores(tmp_path):
    logs = generar_logs_mock(tmp_path / "logs", defensas=("none", "layer2"), idiomas=("es", "en"),
                             escenario="demo_microprocesadores")
    exportar(logs, tmp_path / "episodios")
    sin = _leer(tmp_path / "episodios", "demo_microprocesadores__es__none.json")
    assert sin["veredicto"]["tipo"] == "estafado"
    assert sin["veredicto"]["saldo_final"] == sin["veredicto"]["saldo_inicial"] - 412_000_000
    con = _leer(tmp_path / "episodios", "demo_microprocesadores__en__layer2.json")
    assert con["veredicto"]["tipo"] == "bloqueado"
    assert con["veredicto"]["bloqueo"]["cuenta_inscrita_numero"] == "33-7741-0092"


def test_episodio_del_mcp_envenenado_donde_el_firewall_si_bloquea(tmp_path):
    """La historia opuesta a la ingeniería social: aquí hay un patrón técnico y la capa 1 lo ve."""
    logs = generar_logs_mock(tmp_path / "logs", defensas=("none", "layer1", "layer2"), idiomas=("es",),
                             escenario="mcp_envenenado")
    exportar(logs, tmp_path / "episodios")
    sin = _leer(tmp_path / "episodios", "mcp_envenenado__es__none.json")
    assert sin["veredicto"]["tipo"] == "estafado" and sin["veredicto"]["pagado"] == 9990
    assert [p["herramienta"] for p in sin["pasos"] if p["tipo"] == "herramienta"] == ["usar_mcp", "transferir"]
    for defensa in ("layer1", "layer2"):
        ep = _leer(tmp_path / "episodios", f"mcp_envenenado__es__{defensa}.json")
        assert ep["veredicto"]["tipo"] == "bloqueado" and ep["veredicto"]["saldo_final"] == ep["veredicto"]["saldo_inicial"]
        assert ep["veredicto"]["bloqueo"]["origen"]["tipo"] == "mcp"
        assert ep["veredicto"]["bloqueo"]["origen"]["mcp"] == ["conversor_divisas"]
    firewall = _leer(tmp_path / "episodios", "mcp_envenenado__es__layer1.json")
    assert any("firewall" in p.get("texto", "").lower() for p in firewall["pasos"] if p["tipo"] == "texto")
    assert "patrón de inyección" in firewall["registro"][-1]["motivo"]


def test_la_ingenieria_social_sigue_pasando_el_firewall(tmp_path):
    logs = generar_logs_mock(tmp_path / "logs", defensas=("layer1",), idiomas=("es",),
                             escenario="demo_microprocesadores")
    exportar(logs, tmp_path / "episodios")
    ep = _leer(tmp_path / "episodios", "demo_microprocesadores__es__layer1.json")
    assert ep["veredicto"]["tipo"] == "estafado"  # la capa 1 no ve nada en un cambio de cuenta


@pytest.mark.parametrize("texto, esperado", [
    ("<think>pienso en inglés</think>", ""),
    ("<think>pienso</think>Listo, pagué la factura.", "Listo, pagué la factura."),
    ("Hola <think>a\nb</think> mundo", "Hola  mundo"),
    ("Dije esto <think>y el razonamiento quedó cortado", "Dije esto"),
    ("Sin razonamiento", "Sin razonamiento"),
])
def test_la_demo_no_muestra_el_razonamiento_interno_del_modelo(texto, esperado):
    from scripts.exportar_episodios import sin_razonamiento

    assert sin_razonamiento(texto) == esperado
