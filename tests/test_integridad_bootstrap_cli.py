"""El primer visto bueno viene del dueño; el YAML pendiente no elige quién puede aprobarlo."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import mcp.types as types
import pytest
import yaml

from scamshield.mcp import alerta_telegram, proxy
from scamshield.mcp.integridad import Integridad, politica_canonica


CUENTA = "11-1111-1111"
APROBADORES = [{"nombre": "Sam", "canal": "111"}, {"nombre": "Reed", "canal": "222"}]


def _escribir(ruta, **cambios):
    datos = {"cuentas_inscritas": {"Proveedor": CUENTA}, "registro": None,
             "aprobadores": APROBADORES, "quorum": 2, "semillas": "credenciales/anteriores.json", **cambios}
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    return proxy.cargar_config(ruta)


class Dueno:
    def __init__(self, respuesta=None):
        self.respuesta, self.pedidos = respuesta, []

    def pedir(self, cambio):
        self.pedidos.append(cambio)

    def estado(self):
        return self.respuesta


class QuorumFalso:
    def __init__(self):
        self.aprobador = Dueno()
        self.reconfiguraciones = []

    def aprobador_de_politica(self):
        return self.aprobador

    def reconfigurar(self, politica):
        self.reconfiguraciones.append(politica)


class ModuloFalso:
    def __init__(self):
        self.configuraciones, self.quorums, self.estados = [], [], []

    def quorum_desde_entorno(self, config, integridad, canal, entorno):
        # Crear el canal de quórum equivale a cargar sus semillas: solo debe ocurrir con política aprobada.
        estado = integridad.estado()
        assert estado is not None
        self.configuraciones.append(config)
        self.estados.append(estado.politica)
        quorum = QuorumFalso()
        self.quorums.append(quorum)
        return quorum


class BancoFalso:
    def __init__(self):
        self.llamadas = []

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, args))
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")])


def _montar(config, integridad, dueno, modulo):
    crear_quorum = lambda: proxy._quorum_aprobado(config, integridad, modulo, object(), {})
    g = proxy.Grifter(config, escalar=lambda alerta: False, integridad=integridad, aprobador=dueno,
                      quorum=crear_quorum(), crear_quorum=crear_quorum)
    banco = BancoFalso()
    g.sesiones["banco"] = banco
    g.rutas["pagar"] = ("banco", "pagar")
    return g, banco


def _pagar(g):
    return asyncio.run(g.llamar("pagar", {"cuenta": CUENTA, "monto": 1000}))


@pytest.mark.parametrize("clave", [None, "clave-hmac-ficticia"])
def test_sin_estado_no_se_cargan_aprobadores_ni_semillas_del_yaml(tmp_path, clave, monkeypatch):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta, aprobadores=[{"nombre": "Mallory", "canal": "333"}], quorum=1,
                       semillas="semillas-del-atacante.json")
    integridad = Integridad(ruta, clave=clave)
    modulo = ModuloFalso()
    leer = Path.read_text

    def sin_semillas(archivo, *a, **kw):
        assert archivo != config.semillas, "no se pueden abrir semillas de una política no aprobada"
        return leer(archivo, *a, **kw)

    monkeypatch.setattr(Path, "read_text", sin_semillas)
    assert proxy._quorum_aprobado(config, integridad, modulo, object(), {}) is None
    assert modulo.configuraciones == [] and not integridad.ruta_estado.exists()


def test_un_estado_con_firma_mala_no_habilita_el_quorum_del_yaml(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    integridad.aprobar(politica_canonica(config), "dueño")
    estado = json.loads(integridad.ruta_estado.read_text(encoding="utf-8"))
    estado["firma"] = "firma-inventada"
    integridad.ruta_estado.write_text(json.dumps(estado), encoding="utf-8")
    modulo = ModuloFalso()
    assert proxy._quorum_aprobado(config, integridad, modulo, object(), {}) is None
    assert modulo.configuraciones == []


@pytest.mark.parametrize("nueva_lista", [[], [{"nombre": "Mallory", "canal": "333"}]])
def test_el_quorum_y_las_semillas_salen_de_la_politica_aprobada_aunque_el_yaml_los_cambie(tmp_path, nueva_lista):
    ruta = tmp_path / "grifter.yaml"
    aprobada = _escribir(ruta)
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    integridad.aprobar(politica_canonica(aprobada), "dueño")
    pendiente = _escribir(ruta, aprobadores=nueva_lista, quorum=1, semillas="credenciales/mallory.json")
    antes = asdict(pendiente)
    modulo = ModuloFalso()
    quorum = proxy._quorum_aprobado(pendiente, integridad, modulo, object(), {})
    assert quorum is modulo.quorums[0]
    recibida = modulo.configuraciones[0]
    assert recibida is not pendiente and asdict(pendiente) == antes
    assert recibida.aprobadores == aprobada.aprobadores and recibida.quorum == 2
    assert recibida.semillas == tmp_path / "credenciales" / "anteriores.json"


@pytest.mark.parametrize("ruta_aprobada", [None, "auditoria/aprobaciones.jsonl"], ids=["defecto", "explicita"])
@pytest.mark.parametrize("cambio", [{"registro_aprobaciones": "mallory/aprobaciones.jsonl"},
                                    {"registro_aprobaciones": None}, {}], ids=["cambiado", "nulo", "quitado"])
def test_el_registro_de_aprobaciones_sale_de_la_politica_aprobada_aunque_el_yaml_lo_cambie(tmp_path,
                                                                                       ruta_aprobada, cambio):
    ruta = tmp_path / "grifter.yaml"
    aprobada = _escribir(ruta, **({"registro_aprobaciones": ruta_aprobada} if ruta_aprobada else {}))
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    integridad.aprobar(politica_canonica(aprobada), "dueño")
    pendiente = _escribir(ruta, **cambio)
    antes = asdict(pendiente)
    modulo = ModuloFalso()

    quorum = proxy._quorum_aprobado(pendiente, integridad, modulo, object(), {})

    assert quorum is modulo.quorums[0]
    recibida = modulo.configuraciones[0]
    assert recibida is not pendiente and asdict(pendiente) == antes
    assert recibida.registro_aprobaciones == tmp_path / (ruta_aprobada or "grifter_aprobaciones.jsonl")


def test_una_lista_aprobada_vacia_no_se_sustituye_por_aprobadores_nuevos_del_yaml(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta, aprobadores=[])
    integridad = Integridad(ruta)
    integridad.aprobar(politica_canonica(config), "dueño")
    pendiente = _escribir(ruta, aprobadores=[{"nombre": "Mallory", "canal": "333"}], quorum=1)
    modulo = ModuloFalso()
    assert proxy._quorum_aprobado(pendiente, integridad, modulo, object(), {}) is None
    assert modulo.configuraciones == []


def test_el_dueno_aprueba_la_primera_politica_y_el_siguiente_cambio_necesita_quorum(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    dueno, modulo = Dueno(True), ModuloFalso()
    g, banco = _montar(config, integridad, dueno, modulo)
    assert modulo.quorums == []
    asyncio.run(g.arrancar())
    assert integridad.estado().por == "dueño" and len(dueno.pedidos) == 1
    assert len(modulo.quorums) == 1 and g.quorum is modulo.quorums[0]
    assert not _pagar(g).isError and len(banco.llamadas) == 1
    _escribir(ruta, encargo="Paga otra factura del proveedor")
    assert _pagar(g).isError and len(banco.llamadas) == 1
    assert len(dueno.pedidos) == 1 and dueno.respuesta is True
    anterior = modulo.quorums[0]
    assert len(anterior.aprobador.pedidos) == 1
    anterior.aprobador.respuesta = True
    assert not _pagar(g).isError and len(banco.llamadas) == 2
    assert len(modulo.quorums) == 2 and g.quorum is modulo.quorums[-1]


def test_rechazar_la_primera_politica_no_crea_estado_ni_carga_quorum(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    dueno, modulo = Dueno(False), ModuloFalso()
    g, banco = _montar(config, integridad, dueno, modulo)
    assert asyncio.run(g.arrancar()) == "cambio"
    assert _pagar(g).isError and banco.llamadas == []
    assert not integridad.ruta_estado.exists() and modulo.quorums == []


def test_un_yaml_sin_aprobar_no_puede_ocultar_una_fuga_quitando_la_herramienta_sensible(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    clave = "Clave-ficticia-2740"
    config = _escribir(ruta, datos_dueno={"clave": clave},
                       sensibles={"pagar": {"destino": "cuenta", "que": "la cuenta"}})
    integridad = Integridad(ruta)
    g, banco = _montar(config, integridad, Dueno(), ModuloFalso())
    g.rutas["responder"] = ("banco", "responder")
    assert "responder" not in config.sensibles
    asyncio.run(g.arrancar())
    resultado = asyncio.run(g.llamar("responder", {"a": "contacto", "mensaje": clave}))
    assert resultado.isError and banco.llamadas == []
    assert integridad.estado() is None and not integridad.ruta_estado.exists()


def test_una_lectura_espera_la_aprobacion_inicial_antes_de_confiar_en_las_reglas_del_yaml(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta)
    dueno, modulo = Dueno(), ModuloFalso()
    g, banco = _montar(config, integridad, dueno, modulo)
    g.rutas["leer_correo"] = ("banco", "leer_correo")
    asyncio.run(g.arrancar())
    resultado = asyncio.run(g.llamar("leer_correo", {}))
    assert resultado.isError and banco.llamadas == []
    assert integridad.estado() is None and modulo.quorums == []
    dueno.respuesta = True
    assert not asyncio.run(g.llamar("leer_correo", {})).isError
    assert banco.llamadas == [("leer_correo", {})]
    assert integridad.estado().por == "dueño" and len(dueno.pedidos) == 1
    _escribir(ruta, encargo="Una política nueva necesita otra aprobación")
    assert asyncio.run(g.llamar("leer_correo", {})).isError
    assert banco.llamadas == [("leer_correo", {})]
    modulo.quorums[0].aprobador.respuesta = True
    assert not asyncio.run(g.llamar("leer_correo", {})).isError
    assert banco.llamadas == [("leer_correo", {}), ("leer_correo", {})]


def test_las_semillas_nuevas_se_cargan_solo_despues_de_aprobar_con_las_anteriores(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    integridad.aprobar(politica_canonica(config), "dueño")
    modulo = ModuloFalso()
    g, banco = _montar(config, integridad, Dueno(True), modulo)
    anterior = modulo.quorums[0]
    _escribir(ruta, semillas="credenciales/nuevas.json")
    assert _pagar(g).isError and banco.llamadas == []
    assert len(modulo.configuraciones) == 1
    assert modulo.configuraciones[0].semillas == tmp_path / "credenciales" / "anteriores.json"
    g._pagos[("pagar", CUENTA, 1000)] = "solicitud-del-quorum-anterior"
    anterior.aprobador.respuesta = True
    assert not _pagar(g).isError
    assert len(modulo.configuraciones) == 2
    assert modulo.configuraciones[-1].semillas == tmp_path / "credenciales" / "nuevas.json"
    assert modulo.estados[-1]["semillas"] == "credenciales/nuevas.json"
    assert g._pagos == {}


def test_quitar_los_aprobadores_necesita_el_quorum_previo_y_luego_vuelve_al_dueno(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta)
    integridad.aprobar(politica_canonica(config), "dueño")
    dueno, modulo = Dueno(False), ModuloFalso()
    g, banco = _montar(config, integridad, dueno, modulo)
    anterior = modulo.quorums[0]
    _escribir(ruta, aprobadores=[])
    assert _pagar(g).isError and len(anterior.aprobador.pedidos) == 1 and dueno.pedidos == []
    anterior.aprobador.respuesta = True
    assert not _pagar(g).isError and g.quorum is None and g.aprobador is dueno
    _escribir(ruta, aprobadores=[], encargo="Una nueva operación")
    assert _pagar(g).isError and len(dueno.pedidos) == 1 and len(banco.llamadas) == 1


@pytest.mark.parametrize("preaprobada", [False, True])
def test_un_fallo_al_cargar_el_quorum_retiene_hasta_recuperarlo_con_la_politica_ya_aprobada(tmp_path, preaprobada):
    class ModuloConFallo(ModuloFalso):
        def __init__(self):
            super().__init__()
            self.fallar, self.intentos = False, []

        def quorum_desde_entorno(self, config, integridad, canal, entorno):
            estado = integridad.estado()
            assert estado is not None and estado.por == "dueño"
            self.intentos.append(estado.politica)
            if self.fallar:
                raise OSError("las semillas aprobadas todavía no están disponibles")
            return super().quorum_desde_entorno(config, integridad, canal, entorno)

    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    integridad = Integridad(ruta, clave="clave-hmac-ficticia")
    if preaprobada:
        integridad.aprobar(politica_canonica(config), "dueño")
    modulo = ModuloConFallo()
    g, banco = _montar(config, integridad, Dueno(True), modulo)
    if preaprobada:
        _escribir(ruta, semillas="credenciales/nuevas.json")
        g.quorum.aprobador.respuesta = True
    inicio_fallos = len(modulo.intentos)
    modulo.fallar = True
    asyncio.run(g.arrancar())
    aprobada = integridad.estado().politica
    assert aprobada == politica_canonica(proxy.cargar_config(ruta))
    assert integridad.cambio() is None
    for _ in range(2):
        assert _pagar(g).isError
    assert banco.llamadas == [] and len(modulo.intentos) > inicio_fallos
    assert all(p == aprobada for p in modulo.intentos[inicio_fallos:])
    modulo.fallar = False
    assert not _pagar(g).isError and len(banco.llamadas) == 1
    assert g.quorum is modulo.quorums[-1]
    # La aprobación anterior (del dueño o del quórum viejo) no autoriza un cambio nuevo.
    _escribir(ruta, semillas=aprobada["semillas"], encargo="Otra política necesita otro visto bueno")
    assert _pagar(g).isError and len(banco.llamadas) == 1


@pytest.mark.parametrize("preaprobada", [False, True])
def test_cli_entrega_dueno_y_factory_a_correr_sin_usar_quorum_no_aprobado(tmp_path, monkeypatch, preaprobada):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta)
    if preaprobada:
        Integridad(ruta).aprobar(politica_canonica(config), "dueño")
    dueno, modulo, recibidos = Dueno(), ModuloFalso(), []
    canal = object()
    monkeypatch.setenv("GRIFTER_CANAL", "telegram")
    monkeypatch.delenv("GRIFTER_CLAVE_ESTADO", raising=False)
    monkeypatch.setattr(alerta_telegram, "ganchos_desde_entorno", lambda entorno: SimpleNamespace(
        escalar=lambda alerta: False, aprobador=dueno, latido=None, canal=canal))
    monkeypatch.setattr(alerta_telegram, "quorum_desde_entorno", modulo.quorum_desde_entorno)

    async def correr(config, escalar, integridad, aprobador, latido, quorum, crear_quorum):
        recibidos.append((integridad, aprobador, quorum, crear_quorum))

    monkeypatch.setattr(proxy, "correr", correr)
    proxy.main(["--config", str(ruta)])
    assert len(recibidos) == 1
    integridad, aprobador, quorum, factory = recibidos[0]
    assert aprobador is dueno and callable(factory)
    if preaprobada:
        assert quorum is modulo.quorums[0]
    else:
        assert quorum is None and modulo.quorums == [] and factory() is None
        assert not integridad.ruta_estado.exists()
