"""Pruebas del modo «Centro de operaciones» en vivo (scamshield/vivo). Sin red ni modelos."""
from __future__ import annotations

import pytest

from scamshield.defenses.layer2 import politica_origen
from scamshield.vivo.flujo import Flujo
from scamshield.vivo.motor import Motor

ESTADOS = {"leyendo", "pensando", "pagando", "esperando", "inactivo"}
CLASES = {"cuenta", "dominio", "urgencia", "codigo", "monto", "autoridad", "inyeccion"}
CAPAS = {"1", "2", "boveda", None}


@pytest.fixture(scope="module")
def flujo() -> Flujo:
    return Flujo(semilla=11)


def _motor(flujo: Flujo | None = None) -> Motor:
    reloj = iter(range(1, 10 ** 9))
    return Motor(semilla=11, reloj=lambda: float(next(reloj)), flujo=flujo or Flujo(semilla=11))


def _correr(motor: Motor, clave: str, idioma: str = "es") -> list[dict]:
    correos = motor.flujo.episodio(clave=clave, idioma=idioma)
    return [motor.publicar(ev) for _, ev in motor.episodio(correos)]


def _de_tipo(eventos: list[dict], tipo: str) -> list[dict]:
    return [e for e in eventos if e["tipo"] == tipo]


def test_estafa_confirmada_entra_a_la_boveda_y_el_siguiente_correo_sale_por_boveda():
    m = _motor()
    primera = _correr(m, "proveedor_factura_cambio")
    estafa = [e for e in _de_tipo(primera, "veredicto") if e["id"] == _de_tipo(primera, "accion")[0]["id"]][0]
    assert estafa["fuente"] != "boveda"
    entradas = {(e["indicador"]["tipo"], e["indicador"]["valor"]) for e in _de_tipo(primera, "boveda")}
    assert ("cuenta", "48-9917-3302") in entradas
    assert ("dominio", "molinosquilantu-cl.com") in entradas

    segunda = _correr(m, "proveedor_factura_cambio", idioma="en")
    accion = _de_tipo(segunda, "accion")[0]
    veredicto = [e for e in _de_tipo(segunda, "veredicto") if e["id"] == accion["id"]][0]
    assert veredicto["fuente"] == "boveda" and veredicto["capa"] == "boveda"
    assert veredicto["decision"] == "estafa"
    # El correo legítimo del mismo hilo (dominio real del proveedor) no lo ataja la bóveda.
    legitimo = [e for e in _de_tipo(segunda, "veredicto") if e["id"] != accion["id"]][0]
    assert legitimo["fuente"] != "boveda"
    # Verificación inmediata: el veredicto de bóveda llega antes que la lectura de ese correo.
    tipos = [e["tipo"] for e in segunda if e.get("id") == accion["id"]]
    assert tipos.index("veredicto") < tipos.index("lectura")
    assert m.foto()["bloqueos_por_capa"]["boveda"] == 1


def test_la_boveda_no_guarda_dominios_ni_cuentas_legitimas():
    m = _motor()
    _correr(m, "jefe_mismo_dominio")      # estafa desde el correo real del jefe
    _correr(m, "arriendo_falso")          # estafa desde un proveedor de correo genérico
    valores = {i["valor"] for i in m.boveda.lista()}
    assert "cobreaustral.cl" not in valores and "correo-mail.cl" not in valores
    control = _correr(m, "control_jefe_proveedor_inscrito")
    assert all(v["fuente"] != "boveda" for v in _de_tipo(control, "veredicto"))


def test_el_clasificador_mejora_su_recall_en_el_conjunto_apartado(flujo):
    m = _motor(flujo)
    apartado = m.clasificador.apartado
    assert sum(y for _, y in apartado) >= 10 and len(apartado) - sum(y for _, y in apartado) >= 10
    antes = m.clasificador.evaluar()
    assert antes["recall"] == 0.0
    vistos = set()
    for _ in range(80):
        for c in m.flujo.episodio():
            if m.flujo.es_evaluacion(c):
                continue
            vistos.add(c.unidad)
            m.clasificador.aprender(m._rasgos(c), int(c.etiqueta == "estafa"))
    despues = m.clasificador.evaluar()
    assert vistos.isdisjoint(m.flujo.claves_evaluacion)
    assert despues["recall"] > antes["recall"] + 0.3
    assert despues["falsas_alarmas"] < 0.2
    assert m.clasificador.version != "1.0.0"


def test_pago_a_una_cuenta_que_viene_de_un_correo_lo_retiene_la_capa_2():
    m = _motor()
    eventos = _correr(m, "proveedor_factura_cambio")
    accion = _de_tipo(eventos, "accion")[0]
    assert accion["herramienta"] == "pagar" and accion["args"]["cuenta"] == "48-9917-3302"
    assert accion["resultado"] == "retenida" and accion["capa"] == "2"
    assert accion["motivo"].startswith("Capa 2:")
    assert m.foto()["bloqueos_por_capa"]["2"] == 1


def test_un_control_a_la_cuenta_inscrita_se_ejecuta():
    m = _motor()
    accion = _de_tipo(_correr(m, "control_proveedor_factura"), "accion")[0]
    assert accion["resultado"] == "ejecutada" and accion["capa"] is None


@pytest.mark.parametrize("clave", ["inyeccion_web", "mcp_envenenado", "sint_inyeccion_correo",
                                   "sint_fuga_secretos"])
def test_un_ataque_tecnico_lo_detiene_la_capa_1(clave):
    m = _motor()
    eventos = _correr(m, clave)
    accion = _de_tipo(eventos, "accion")[0]
    assert accion["resultado"] == "retenida" and accion["capa"] == "1"
    veredicto = [e for e in _de_tipo(eventos, "veredicto") if e["id"] == accion["id"]][0]
    assert veredicto["familia"] == "tecnico" and veredicto["capa"] == "1"
    lectura = [e for e in _de_tipo(eventos, "lectura") if e["id"] == accion["id"]][0]
    assert any(t["clase"] == "inyeccion" for t in lectura["tramos"])


def test_la_fuga_de_secretos_solo_la_ve_la_capa_1():
    m = _motor()
    correo = m.flujo.episodio(clave="sint_fuga_secretos", idioma="es")[0]
    assert politica_origen(correo.mundo(), correo.accion["herramienta"], correo.accion["args"]) is None


def test_los_eventos_cumplen_el_esquema_del_contrato():
    m = _motor()
    eventos = m.avanzar(900)
    cuerpos: dict[str, str] = {}
    vistos = set()
    for e in eventos:
        t = e["tipo"]
        vistos.add(t)
        assert isinstance(e["ts"], float)
        if t == "agente_estado":
            assert e["agente"] in {"Elon", "Sam", "Jensen", "Whitney"}
            assert e["estado"] in ESTADOS and isinstance(e["tarea"], str)
        elif t == "correo_nuevo":
            assert e["id"].startswith("m-") and len(e["id"]) == 8
            assert {"agente", "de", "asunto", "cuerpo"} <= e.keys()
            cuerpos[e["id"]] = e["cuerpo"]
        elif t == "lectura":
            for tr in e["tramos"]:
                assert tr["clase"] in CLASES and 0.0 <= tr["riesgo"] <= 1.0 and tr["nota"]
                assert cuerpos[e["id"]][tr["inicio"]:tr["fin"]] == tr["texto"]
        elif t == "veredicto":
            assert e["decision"] in {"seguro", "sospechoso", "estafa"}
            assert 0.0 <= e["confianza"] <= 1.0
            assert e["fuente"] in {"boveda", "origen", "clasificador"}
            assert e["capa"] in CAPAS
            assert e["familia"] in {"ingenieria_social", "tecnico", "legitimo"}
            assert all({"nombre", "peso"} == s.keys() for s in e["senales"])
            assert e["version_modelo"].startswith("1.0.")
        elif t == "accion":
            assert e["resultado"] in {"ejecutada", "retenida", "escalada"}
            assert e["capa"] in CAPAS and e["motivo"] and isinstance(e["args"], dict)
        elif t == "boveda":
            i = e["indicador"]
            assert i["tipo"] in {"cuenta", "dominio", "plantilla"}
            assert {"valor", "veces", "primera_vez", "origen"} <= i.keys()
        elif t == "modelo":
            assert {"version", "ejemplos", "precision", "recall", "falsas_alarmas", "evaluado_en",
                    "cambios"} <= e.keys()
            for c in e["cambios"]:
                assert {"senal", "peso_antes", "peso_despues"} == c.keys()
        else:
            raise AssertionError(f"tipo desconocido: {t}")
    assert vistos == {"agente_estado", "correo_nuevo", "lectura", "veredicto", "accion", "boveda",
                      "modelo"}
    foto = m.foto()
    assert len(foto["correos"]) <= 50 and set(foto["bloqueos_por_capa"]) == {"1", "2", "boveda"}
    assert {"boveda", "modelo", "agentes", "correos"} <= foto.keys()


def test_rutas_del_servidor():
    from fastapi.testclient import TestClient

    import demo.server as servidor
    import scamshield.vivo.motor as motor

    motor._motor = _motor()   # no arranca el hilo con la semilla del reloj
    motor._motor._hilo = object()
    cliente = TestClient(servidor.app)
    estado = cliente.get("/api/vivo/estado").json()
    assert estado["simulacion"] == "Simulación · motor real"
    assert estado["bloqueos_por_capa"] == {"1": 0, "2": 0, "boveda": 0}
    assert cliente.post("/api/vivo/control", json={"accion": "velocidad", "valor": 4}).json()["velocidad"] == 4
    assert cliente.post("/api/vivo/control", json={"accion": "pausa"}).json()["pausa"] is True
    assert cliente.post("/api/vivo/control", json={"accion": "velocidad", "valor": 3}).status_code == 422
    assert cliente.get("/api/salud").json()["ok"] is True
    cors = cliente.get("/api/vivo/estado", headers={"Origin": "http://127.0.0.1:8769"})
    assert cors.headers["access-control-allow-origin"] == "http://127.0.0.1:8769"
    ajeno = cliente.get("/api/vivo/estado", headers={"Origin": "https://ejemplo.cl"})
    assert "access-control-allow-origin" not in ajeno.headers
    assert cliente.post("/api/vivo/control", json={"accion": "idioma", "valor": "en"}).json()["idioma"] == "en"
    motor._motor = None


def test_el_flujo_sale_en_espanol_por_defecto_y_el_ingles_se_pide():
    m = _motor()
    idiomas = {c.escenario["idioma"] for _ in range(40) for c in m.flujo.episodio()}
    assert idiomas == {"es"}
    m.control("idioma", "en")
    assert {c.escenario["idioma"] for _ in range(20) for c in m.flujo.episodio()} == {"en"}
    with pytest.raises(ValueError):
        m.control("idioma", "fr")


def test_el_precalentamiento_deja_modelo_boveda_e_historial():
    ahora = [1_000_000.0]
    m = Motor(semilla=11, reloj=lambda: ahora[0], flujo=Flujo(semilla=11))
    vistos = m.precalentar(correos=40)
    foto = m.foto()
    assert vistos >= 40 and foto["totales"]["correos"] == vistos
    assert foto["modelo"]["version"] != "1.0.0" and foto["modelo"]["ejemplos"] > 0
    assert len(foto["boveda"]) > 0
    assert foto["historial_modelo"][0]["version"] == "1.0.0"
    assert foto["historial_modelo"][-1] == foto["modelo"]
    assert foto["historial_bloqueos"] and set(foto["historial_bloqueos"][-1]) == {"ts", "1", "2", "boveda"}
    # Los ts quedan en el pasado reciente y en orden, nunca en el futuro.
    ts = [e["ts"] for _, e in m.eventos_desde(0)]
    assert ts == sorted(ts) and ts[-1] <= ahora[0] and ts[0] < ahora[0] - 60
