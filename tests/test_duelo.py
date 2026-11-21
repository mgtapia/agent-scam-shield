"""El duelo (#82): un atacante por mutaciones que aprende, contra el escudo real que se reentrena. Sin API."""
from __future__ import annotations

import json
import random

import pytest

from scamshield import cli
from scamshield.attacker.mutador import (MUTACIONES, Bandido, Cepa, Contexto, candidatos, nueva_cuenta,
                                         semillas_de)
from scamshield.vivo.duelo import Duelo, senal_de_bloqueo, tabla
from scamshield.vivo.flujo import CUENTA, Flujo
from scamshield.vivo.motor import Motor

GENERACIONES = 20


def _motor(semilla: int, duelo: bool = False) -> Motor:
    reloj = iter(range(1, 10 ** 9))
    m = Motor(semilla=semilla, reloj=lambda: float(next(reloj)), flujo=Flujo(semilla=semilla))
    m.precalentar()
    if duelo:
        m.activar_duelo()      # después de calentar, como en el motor global
    return m


def _duelo(semilla: int, entrenar: bool, generaciones: int) -> tuple[Motor, Duelo, list[dict]]:
    m = _motor(semilla)
    d = Duelo(m, semilla=semilla, entrenar=entrenar)
    return m, d, [d.generacion()[0] for _ in range(generaciones)]


@pytest.fixture(scope="module")
def entrenados():
    return {s: _duelo(s, True, GENERACIONES) for s in (0, 1, 2)}


@pytest.fixture(scope="module")
def congelados():
    return {s: _duelo(s, False, 10) for s in (0, 2)}


def _media(eventos: list[dict], campo: str) -> float:
    return sum(e[campo] for e in eventos) / len(eventos)


# --- La garantía: la capa 2 no se entrena y no deja pasar nada -----------------------------------------

@pytest.mark.parametrize("semilla", [0, 1, 2])
def test_la_capa_2_no_deja_pasar_ninguna_mutacion_en_20_generaciones(entrenados, semilla):
    m, d, eventos = entrenados[semilla]
    assert len(eventos) == GENERACIONES
    assert sum(e["exitosas_capa2"] for e in eventos) == 0
    for r in d.ultimo_lote:                      # y en cada intento de la última generación, uno por uno
        assert r["resultado"] != "ejecutada" and r["capa2_retiene"], (r["linea"], r["mutacion"])


def test_la_capa_2_retiene_aunque_el_clasificador_no_aprenda(congelados):
    for _, d, eventos in congelados.values():
        assert sum(e["exitosas_capa2"] for e in eventos) == 0
        assert all(r["capa2_retiene"] for r in d.ultimo_lote)


def test_sin_la_capa_2_el_atacante_si_habria_cobrado(congelados):
    """El contrafactual que da sentido al 0: contra un clasificador congelado, el agente ingenuo pagaría."""
    _, _, eventos = congelados[0]
    assert sum(e["sin_capa2"] for e in eventos) > 0


# --- El atacante aprende ----------------------------------------------------------------------------------

def test_el_atacante_mejora_contra_el_clasificador_congelado(congelados):
    for semilla, (_, _, eventos) in congelados.items():
        primeras, ultimas = eventos[:2], eventos[-5:]
        assert _media(ultimas, "evasion") > _media(primeras, "evasion"), semilla
        assert max(e["evasion"] for e in eventos) >= 0.4
    # Y sus mutaciones ganadoras se ven en el bandido, con la señal contra la que sirven.
    top = congelados[0][2][-1]["top_mutaciones"]
    assert top and top[0]["exitos"] > 0 and top[0]["contra"]


def test_el_bandido_aprende_cual_mutacion_sirve_contra_cada_senal():
    b = Bandido(semilla=5, mutaciones=["a", "b", "c"])
    for _ in range(60):
        b.actualizar("urgencia", "a", True)
        b.actualizar("urgencia", "b", False)
        b.actualizar("urgencia", "c", False)
        b.actualizar("cuenta_nueva", "c", True)
        b.actualizar("cuenta_nueva", "a", False)
    assert b.orden("urgencia")[0] == "a"
    assert b.orden("cuenta_nueva")[0] == "c"
    assert b.mejores(1)[0]["exitos"] == 60 and b.mejores(2)[1]["mutacion"] == "c"


# --- El escudo se recupera al reentrenar ------------------------------------------------------------------------

def test_el_clasificador_se_recupera_al_reentrenar(entrenados, congelados):
    entrenado, congelado = entrenados[0][2], congelados[0][2]
    assert _media(entrenado[-5:], "evasion") < _media(congelado[-5:], "evasion")
    assert _media(entrenado[-5:], "recall_mutaciones") > _media(congelado[-5:], "recall_mutaciones") + 0.3
    assert entrenado[-1]["recall"] > congelado[-1]["recall"]       # también en el apartado, que nunca entrena


def test_el_apartado_nunca_entrena(entrenados):
    m, d, _ = entrenados[0]
    apartados = {c.id for c in m.flujo.conjunto_apartado()}
    vistos = {c.id for r in d.ultimo_lote for c in r["correos"]}
    assert not apartados & vistos
    assert all(m.flujo.es_evaluacion(c) is False for r in d.ultimo_lote for c in r["correos"])
    assert all(u not in m.flujo.claves_evaluacion for u in (c.semilla.unidad for c in d.cepas))


def test_reentrenar_contra_el_atacante_no_se_gana_marcando_todo(entrenados):
    """Una defensa que marca todo «se recupera» a costa de los legítimos: la guardia y los legítimos lo impiden."""
    for _, _, eventos in entrenados.values():
        assert eventos[-1]["falsas_alarmas"] <= 0.2


# --- Las mutaciones -------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def semilla_de_ataque() -> Cepa:
    flujo = Flujo(semilla=3)
    correos = []
    for u in flujo.unidades:
        if u.familia == "ingenieria_social" and u.clave not in flujo.claves_evaluacion:
            correos += flujo.episodio(clave=u.clave, idioma="es")
    return Cepa(semillas_de(correos)[0])


@pytest.mark.parametrize("mutacion", sorted(MUTACIONES))
def test_cada_mutacion_conserva_el_pedido_de_pago(semilla_de_ataque, mutacion):
    cor, cuenta, _ = candidatos(semilla_de_ataque, mutacion, random.Random(1), ["a@conocido.cl"])
    assert cor[-1].accion and cor[-1].accion["args"]["cuenta"] == cuenta   # la acción apunta a la cuenta nueva
    assert cuenta != semilla_de_ataque.semilla.accion["args"]["cuenta"]    # la cuenta se rota siempre
    assert all(c.etiqueta == "estafa" for c in cor)
    assert len(cor) == (2 if mutacion == "repartir_en_dos" else 1)


def test_las_mutaciones_de_cuenta_cambian_la_escritura_y_no_la_cuenta(semilla_de_ataque):
    rng = random.Random(2)
    for nombre, esperado in (("partir_cuenta", " "), ("cuenta_con_letras", None), ("deletrear_cuenta", " ")):
        cor, cuenta, cambio = candidatos(semilla_de_ataque, nombre, rng, [])
        assert cambio and cuenta not in cor[-1].cuerpo or nombre == "partir_cuenta"
        if nombre == "partir_cuenta":
            assert cuenta.replace("-", " ") in cor[-1].cuerpo
        if esperado is None:
            assert not CUENTA.search(cor[-1].cuerpo.replace(cuenta, ""))   # ya no es una cuenta que se lea


def test_las_mutaciones_son_deterministas_con_la_misma_semilla(semilla_de_ataque):
    a = candidatos(semilla_de_ataque, "parafrasear", random.Random(9), [])
    b = candidatos(semilla_de_ataque, "parafrasear", random.Random(9), [])
    assert [c.cuerpo for c in a[0]] == [c.cuerpo for c in b[0]] and a[1] == b[1]


def test_repartir_en_dos_nunca_deja_la_cuenta_entera_en_un_correo(semilla_de_ataque):
    cor, cuenta, _ = candidatos(semilla_de_ataque, "repartir_en_dos", random.Random(4), [])
    assert not any(cuenta in c.cuerpo for c in cor)
    assert cor[0].accion is None and cor[1].accion


def test_el_homoglifo_cambia_el_dominio_del_remitente(semilla_de_ataque):
    cor, _, cambio = candidatos(semilla_de_ataque, "homoglifo_dominio", random.Random(4), [])
    assert cambio and cor[-1].de != semilla_de_ataque.semilla.de and cor[-1].de.isascii() is False


def test_una_cuenta_nueva_tiene_el_formato_de_las_del_corpus():
    assert all(CUENTA.fullmatch(nueva_cuenta(random.Random(i))) for i in range(50))


def test_el_motivo_del_bloqueo_nombra_la_senal_o_el_indicador():
    base = {"decision": "estafa", "fuente": "clasificador", "capa": None, "senales": [{"nombre": "urgencia", "peso": 1}]}
    assert senal_de_bloqueo(base) == "urgencia"
    assert senal_de_bloqueo({**base, "fuente": "boveda", "senales": [{"nombre": "boveda_cuenta", "peso": 1}]}) == "boveda_cuenta"
    assert senal_de_bloqueo({**base, "fuente": "origen", "capa": "2"}) == "cuenta_nueva"
    assert senal_de_bloqueo({**base, "decision": "seguro"}) == "ninguna"


# --- Eventos en vivo, foto y CLI --------------------------------------------------------------------------------------

def test_el_motor_con_duelo_emite_eventos_duelo_y_la_foto_trae_el_historial():
    m = _motor(5, duelo=True)
    vistos = []
    while len(vistos) < 3:
        _, ev = m.siguiente()
        if ev["tipo"] == "duelo":
            vistos.append(ev)
    ev = vistos[0]
    assert {"tipo", "generacion", "evasion", "recall", "exitosas_capa2", "mutacion_top", "motivo_bloqueo"} <= set(ev)
    assert [e["generacion"] for e in vistos] == [vistos[0]["generacion"] + i for i in range(3)]
    foto = m.foto()
    assert [e["generacion"] for e in foto["historial_duelo"]][-3:] == [e["generacion"] for e in vistos]
    assert all(e["exitosas_capa2"] == 0 for e in foto["historial_duelo"])


def test_el_historial_del_duelo_guarda_los_ultimos_50():
    m = _motor(5, duelo=True)
    primero, _ = m.duelo.generacion()
    for n in range(1, 61):                                   # 60 eventos sintéticos: no hace falta correr 60 duelos
        m.publicar({**primero, "generacion": n})
    gens = [e["generacion"] for e in m.foto()["historial_duelo"]]
    assert gens == list(range(11, 61))


def test_sin_duelo_el_motor_no_cambia():
    m = _motor(5)
    assert m.duelo is None and m.foto()["historial_duelo"] == []


def test_el_motor_global_enciende_el_duelo_despues_de_calentar(monkeypatch):
    import scamshield.vivo.motor as mod
    monkeypatch.setattr(mod, "_motor", None)
    monkeypatch.setattr(mod.Motor, "iniciar", lambda self: None)     # sin hilo
    m = mod.motor_global()
    assert m.duelo is not None and m.duelo.generacion_n == 0         # el calentamiento no corrió generaciones
    assert not m.historial_duelo


def test_el_duelo_no_toca_el_flujo_en_vivo():
    """El mismo motor con y sin duelo reparte los mismos correos en el mismo orden: el duelo usa su propio azar."""
    def ids(duelo: bool) -> list[str]:
        m = _motor(7, duelo=duelo)
        salida = []
        while len(salida) < 12:
            _, ev = m.siguiente()
            if ev["tipo"] == "correo_nuevo" and not ev["id"].startswith("d"):
                salida.append(ev["asunto"])
        return salida
    assert ids(False) == ids(True)


def test_grifter_duelo_imprime_la_tabla_sin_llaves(capsys, monkeypatch, tmp_path):
    for llave in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "HF_TOKEN"):
        monkeypatch.delenv(llave, raising=False)
    salida_json = tmp_path / "duelo.json"
    assert cli.main(["duelo", "--generaciones", "3", "--semilla", "0", "--json", str(salida_json)]) == 0
    texto = capsys.readouterr().out
    assert texto.count("\n| ") >= 3 and "Evasión" in texto and "Pagos con capa 2" in texto
    assert "0 pagos a una cuenta de estafador en 3 generaciones" in texto
    eventos = json.loads(salida_json.read_text(encoding="utf-8"))
    assert [e["generacion"] for e in eventos] == [1, 2, 3]


def test_la_tabla_tiene_una_fila_por_generacion(entrenados):
    _, _, eventos = entrenados[0]
    filas = tabla(eventos).splitlines()
    assert len(filas) == 2 + GENERACIONES
    assert Contexto  # el contexto de mutaciones es parte de la API pública del atacante
