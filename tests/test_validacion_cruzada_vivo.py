"""La validación cruzada del clasificador en línea: los pliegues y que nada apartado se entrene. Sin API."""
from __future__ import annotations

import pytest

from scamshield.vivo.flujo import Flujo
from scripts.validacion_cruzada_vivo import METRICAS, colados_por, correr, resumir


def test_los_tres_pliegues_son_disjuntos_y_cubren_un_tercio_cada_uno():
    apartados = [Flujo(semilla=1, pliegue=p).claves_evaluacion for p in (0, 1, 2)]
    assert not (apartados[0] & apartados[1]) and not (apartados[0] & apartados[2]) and not (apartados[1] & apartados[2])
    total = len(Flujo(semilla=1).unidades)
    assert sum(len(a) for a in apartados) == total  # entre los tres, todos los escenarios


def test_el_pliegue_por_defecto_es_el_que_ya_usaba_el_motor():
    assert Flujo(semilla=3).claves_evaluacion == Flujo(semilla=3, pliegue=1).claves_evaluacion


def test_un_pliegue_invalido_se_rechaza():
    with pytest.raises(ValueError):
        Flujo(pliegue=3)


def test_una_corrida_entrena_sin_tocar_lo_apartado_y_mejora():
    fila = correr(pliegue=0, semilla=1, episodios=60)
    assert fila["recall_antes"] == 0.0 and fila["recall"] > 0.3
    assert fila["escenarios_apartados"] >= 9 and fila["evaluado_en"] >= 30


def test_el_resumen_da_media_y_rango():
    r = resumir([{"recall": 0.5, "precision": 1.0, "falsas_alarmas": 0.0},
                 {"recall": 1.0, "precision": 0.8, "falsas_alarmas": 0.2}])
    assert set(r) == set(METRICAS) and r["recall"] == {"media": 0.75, "min": 0.5, "max": 1.0}


# --- Apartar por familia: las variantes de una misma historia no se separan ---

ESPIAS = "espia_industrial_"


def test_apartando_por_escenario_las_variantes_de_una_historia_se_reparten_entre_pliegues():
    """Es la fuga que hay que evitar: una variante entrena y otra evalúa, con las mismas palabras."""
    en_pliegues = [
        {u.clave for u in Flujo(semilla=1, pliegue=p).unidades if u.clave.startswith(ESPIAS)} &
        Flujo(semilla=1, pliegue=p).claves_evaluacion for p in (0, 1, 2)]
    assert sum(1 for e in en_pliegues if e) > 1   # las tres variantes caen en pliegues distintos


def test_apartando_por_familia_las_variantes_se_apartan_juntas():
    for p in (0, 1, 2):
        f = Flujo(semilla=1, pliegue=p, agrupar="familia")
        espias = {u.clave for u in f.unidades if u.clave.startswith(ESPIAS)}
        assert len(espias) == 3
        assert espias <= f.claves_evaluacion or not (espias & f.claves_evaluacion), p
    assert any({u.clave for u in Flujo(semilla=1, pliegue=p, agrupar="familia").unidades
                if u.clave.startswith(ESPIAS)} <= Flujo(semilla=1, pliegue=p, agrupar="familia").claves_evaluacion
               for p in (0, 1, 2))   # y en algún pliegue las tres están apartadas


def test_por_familia_los_pliegues_siguen_siendo_disjuntos_y_cubren_todo():
    apartados = [Flujo(semilla=1, pliegue=p, agrupar="familia").claves_evaluacion for p in (0, 1, 2)]
    assert not (apartados[0] & apartados[1]) and not (apartados[0] & apartados[2]) and not (apartados[1] & apartados[2])
    assert set().union(*apartados) == {u.clave for u in Flujo(semilla=1).unidades}


def test_por_defecto_se_aparta_por_escenario_como_siempre():
    assert Flujo(semilla=3).claves_evaluacion == Flujo(semilla=3, agrupar="escenario").claves_evaluacion


def test_un_agrupar_invalido_se_rechaza():
    with pytest.raises(ValueError, match="agrupar"):
        Flujo(agrupar="barrio")


def test_una_corrida_por_familia_entrena_sin_tocar_lo_apartado():
    fila = correr(pliegue=0, semilla=1, episodios=60, agrupar="familia")
    assert fila["recall_antes"] == 0.0 and fila["recall"] > 0.3


# --- Qué se coló: por familia y por canal, sumando las corridas ---

def test_colados_por_familia_cuenta_correos_y_corridas():
    filas = [
        {"apartadas": [{"escenario": "a", "familia": "jefe", "canal": "correo", "n": 3},
                       {"escenario": "b", "familia": "jefe", "canal": "whatsapp", "n": 3},
                       {"escenario": "c", "familia": "banco", "canal": "llamada", "n": 3}],
         "colados": [{"escenario": "b", "familia": "jefe", "canal": "whatsapp", "n": 2}]},
        {"apartadas": [{"escenario": "a", "familia": "jefe", "canal": "correo", "n": 3}], "colados": []},
    ]
    fam = colados_por(filas, "familia")
    assert fam["jefe"] == {"colados": 2, "correos": 9, "corridas": 2, "corridas_con_colados": 1,
                           "escenarios": ["b"], "tasa": 0.222}
    assert fam["banco"]["colados"] == 0 and fam["banco"]["corridas"] == 1
    assert list(fam) == ["jefe", "banco"]   # primero lo que más se cuela
    canal = colados_por(filas, "canal")
    assert canal["whatsapp"]["colados"] == 2 and canal["correo"]["correos"] == 6


def test_una_corrida_trae_lo_apartado_y_lo_colado_por_familia():
    fila = correr(pliegue=0, semilla=1, episodios=20, agrupar="familia")
    apartadas = sum(a["n"] for a in fila["apartadas"])
    coladas = sum(c["n"] for c in fila["colados"])
    assert apartadas and round((apartadas - coladas) / apartadas, 3) == fila["recall"]
    assert {c["familia"] for c in fila["colados"]} <= {a["familia"] for a in fila["apartadas"]}
