"""Modo evento (GRIFTER_EVENTO=1): el jurado comparte una IP; sube el tope por IP y no el global."""
from __future__ import annotations

import pytest

from demo.limite import TOPES, TOPES_EVENTO_POR_IP, LimitePorIP, limite_de, modo_evento


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _con_reloj(limite: LimitePorIP, reloj: Reloj) -> LimitePorIP:
    limite.reloj = reloj
    return limite


@pytest.mark.parametrize("valor,esperado", [("1", True), (" 1 ", True), ("0", False), ("", False), ("true", False), ("yes", False)])
def test_solo_el_uno_prende_el_modo_evento(valor, esperado):
    assert modo_evento({"GRIFTER_EVENTO": valor}) is esperado
    assert modo_evento({}) is False


def test_sin_el_modo_los_topes_son_los_de_siempre():
    for ruta, (minuto, hora, glob) in TOPES.items():
        lim = limite_de(ruta, {})
        assert (lim.por_minuto, lim.por_hora, lim.global_por_hora) == (minuto, hora, glob)
    assert (limite_de("probar", {}).por_minuto, limite_de("mcp", {}).por_minuto) == (6, 60)


def test_el_modo_evento_sube_el_tope_por_ip_y_deja_el_global_igual():
    for ruta in TOPES:
        normal, evento = limite_de(ruta, {}), limite_de(ruta, {"GRIFTER_EVENTO": "1"})
        assert evento.por_minuto > normal.por_minuto and evento.por_hora > normal.por_hora
        assert (evento.por_minuto, evento.por_hora) == TOPES_EVENTO_POR_IP[ruta]
        assert evento.global_por_hora == normal.global_por_hora   # el tope global no se toca


def test_treinta_personas_con_tres_intentos_en_dos_minutos_desde_una_ip():
    """El jurado en el mismo wifi: 90 pedidos desde una dirección en 2 minutos."""
    def correr(entorno):
        reloj = Reloj()
        lim = _con_reloj(limite_de("probar", entorno), reloj)
        permitidos = 0
        for intento in range(3):
            for persona in range(30):
                reloj.t = 1000.0 + (intento * 30 + persona) * (120 / 90)
                permitidos += lim.permitir("203.0.113.7")[0]
        return permitidos

    assert correr({}) < 20                          # hoy: el jurado se topa a los pocos intentos
    assert correr({"GRIFTER_EVENTO": "1"}) == 90    # modo evento: nadie recibe un 429


def test_en_modo_evento_una_sola_ip_sigue_topada_por_el_global():
    reloj = Reloj()
    lim = _con_reloj(limite_de("probar", {"GRIFTER_EVENTO": "1"}), reloj)
    ok = 0
    for i in range(2000):
        reloj.t = 1000.0 + i * 1.5   # 40 por minuto durante unos 50 minutos: bajo el tope por IP, sobre el global
        ok += lim.permitir("203.0.113.7")[0]
    assert ok == TOPES["probar"][2]   # el global (600 por hora) corta aunque la IP esté bajo su propio tope


def test_en_modo_evento_un_ataque_desde_una_ip_se_corta_por_minuto():
    reloj = Reloj()
    lim = _con_reloj(limite_de("probar", {"GRIFTER_EVENTO": "1"}), reloj)
    resultados = [lim.permitir("198.51.100.9")[0] for _ in range(500)]   # todos en el mismo instante
    assert sum(resultados) == TOPES_EVENTO_POR_IP["probar"][0]


def test_la_salud_dice_si_esta_en_modo_evento(monkeypatch):
    from fastapi.testclient import TestClient

    import demo.server as servidor

    monkeypatch.setenv("GRIFTER_EVENTO", "1")
    assert TestClient(servidor.app).get("/api/salud").json()["evento"] is True
    monkeypatch.delenv("GRIFTER_EVENTO")
    assert TestClient(servidor.app).get("/api/salud").json()["evento"] is False
