"""La política se verifica antes de abrir conexiones y rige también después de aprobar cambios."""
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack, asynccontextmanager
from types import SimpleNamespace

import mcp.types as types
import pytest
import yaml

from scamshield.mcp import proxy
from scamshield.mcp.integridad import Integridad, politica_canonica


CLAVE = "Cumbre-Alba-ficticia-2740"
OFICIAL = "banca.ejemplo.cl"
REVOCADO = "comprometido.ejemplo.cl"


def _escribir(ruta, transporte="stdio", **cambios):
    servidor = ({"comando": "proceso-ficticio", "args": []} if transporte == "stdio" else
                {"url": "https://mcp.ejemplo.cl/mcp", "headers": {"Authorization": "Bearer ficticio"}})
    datos = {"servidores": {"banco": servidor}, "registro": None, **cambios}
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    return proxy.cargar_config(ruta)


class Dueno:
    def __init__(self, respuesta=None):
        self.respuesta, self.pedidos = respuesta, []

    def pedir(self, cambio):
        self.pedidos.append(cambio)

    def estado(self):
        return self.respuesta


class SesionFalsa:
    def __init__(self, *args):
        self.llamadas = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def initialize(self):
        pass

    async def list_tools(self):
        return SimpleNamespace(tools=[types.Tool(name="leer_correo", description="Lectura ficticia", inputSchema={})])

    async def call_tool(self, nombre, args):
        self.llamadas.append((nombre, args))
        return types.CallToolResult(content=[types.TextContent(type="text", text="ok")])


def _transportes_falsos(monkeypatch):
    conexiones = []

    @asynccontextmanager
    async def stdio(parametros, **kwargs):
        conexiones.append(("stdio", parametros.command))
        yield object(), object()

    async def remoto(g, pila, servidor):
        conexiones.append(("http", servidor.url))
        await g._exponer(servidor.nombre, SesionFalsa())

    monkeypatch.setattr(proxy, "stdio_client", stdio)
    monkeypatch.setattr(proxy, "ClientSession", SesionFalsa)
    monkeypatch.setattr(proxy, "conectar_remoto", remoto)
    return conexiones


@pytest.mark.parametrize("transporte", ["stdio", "http"])
@pytest.mark.parametrize("situacion", ["ausente", "cambio", "firma_invalida"])
def test_no_abre_procesos_ni_envia_cabeceras_con_una_politica_sin_verificar(tmp_path, monkeypatch,
                                                                           transporte, situacion):
    conexiones = _transportes_falsos(monkeypatch)
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta, transporte)
    integridad = Integridad(ruta, clave="hmac-ficticio")
    if situacion != "ausente":
        integridad.aprobar(politica_canonica(config), "dueño")
        if situacion == "cambio":
            config = _escribir(ruta, transporte, encargo="Una política todavía no aprobada")
        else:
            estado = json.loads(integridad.ruta_estado.read_text(encoding="utf-8"))
            estado["firma"] = "firma-inventada"
            integridad.ruta_estado.write_text(json.dumps(estado), encoding="utf-8")
    g = proxy.Grifter(config, integridad=integridad, aprobador=Dueno())

    async def correr():
        async with AsyncExitStack() as pila:
            await g.conectar(pila)

    asyncio.run(correr())
    assert conexiones == []
    assert g.sesiones == {} and g.rutas == {} and g.herramientas == []


@pytest.mark.parametrize("transporte", ["stdio", "http"])
def test_aprobar_la_politica_permite_reintentar_la_conexion_sin_duplicar_servidores(tmp_path, monkeypatch, transporte):
    conexiones = _transportes_falsos(monkeypatch)
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta, transporte)
    integridad, dueno = Integridad(ruta), Dueno()
    g = proxy.Grifter(config, integridad=integridad, aprobador=dueno)

    async def correr():
        async with AsyncExitStack() as pila:
            await g.conectar(pila)
            assert conexiones == [] and integridad.estado() is None
            dueno.respuesta = True
            await g.conectar(pila)
            await g.conectar(pila)
            assert set(g.sesiones) == {"banco"}
            assert list(g.rutas) == ["leer_correo"]

    asyncio.run(correr())
    assert len(conexiones) == 1 and integridad.cambio() is None


def test_listar_herramientas_reintenta_la_conexion_despues_de_la_aprobacion_inicial(tmp_path, monkeypatch):
    conexiones = _transportes_falsos(monkeypatch)
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta, "http")
    integridad, dueno = Integridad(ruta), Dueno()
    g = proxy.Grifter(config, integridad=integridad, aprobador=dueno)
    servidor = g.servidor_mcp()
    listar = servidor.request_handlers[types.ListToolsRequest]

    async def correr():
        async with AsyncExitStack() as pila:
            await g.conectar(pila)
            inicial = await listar(types.ListToolsRequest(method="tools/list"))
            assert inicial.root.tools == [] and conexiones == []
            dueno.respuesta = True
            aprobadas = await listar(types.ListToolsRequest(method="tools/list"))
            assert [t.name for t in aprobadas.root.tools] == ["leer_correo"]

    asyncio.run(correr())
    assert len(conexiones) == 1


@pytest.mark.parametrize("transporte", ["stdio", "http"])
@pytest.mark.parametrize("clave", [None, "hmac-ficticio"])
@pytest.mark.parametrize("restauracion", ["antes_de_conectar", "despues_del_rechazo"])
@pytest.mark.parametrize("ataque", ["servidor", "reglas"])
def test_restaurar_el_yaml_no_autoriza_la_configuracion_alterada_en_memoria(
        tmp_path, monkeypatch, transporte, clave, restauracion, ataque):
    conexiones = _transportes_falsos(monkeypatch)
    ruta = tmp_path / "grifter.yaml"
    aprobada = _escribir(ruta, transporte)
    original = ruta.read_bytes()
    integridad = Integridad(ruta, clave=clave)
    integridad.aprobar(politica_canonica(aprobada), "dueño")
    estado_original = integridad.ruta_estado.read_bytes()
    cambios = ({"servidores": {"banco": {"comando": "proceso-rechazado", "args": []}}}
               if transporte == "stdio" else
               {"servidores": {"banco": {"url": "https://rechazado.ejemplo.cl/mcp",
                                          "headers": {"Authorization": "Bearer ficticio"}}}})
    if ataque == "reglas":
        cambios = {"capas": {"capa2": False}}
    alterada = _escribir(ruta, transporte, **cambios)
    dueno = Dueno(False)
    g = proxy.Grifter(alterada, integridad=integridad, aprobador=dueno)
    listar = g.servidor_mcp().request_handlers[types.ListToolsRequest]

    async def correr():
        async with AsyncExitStack() as pila:
            if restauracion == "despues_del_rechazo":
                await g.conectar(pila)
                assert conexiones == [] and len(dueno.pedidos) == 1
                assert g._rechazado is not None
            ruta.write_bytes(original)
            assert integridad.cambio() is None
            await g.conectar(pila)
            resultado = await listar(types.ListToolsRequest(method="tools/list"))
            assert conexiones == [] and resultado.root.tools == []
            assert g.sesiones == {} and g.rutas == {}
            assert "reinici" in (await g._politica_pendiente()).lower()
        # Reiniciar con el YAML restaurado sí abre únicamente el servidor aprobado.
        recuperado = proxy.Grifter(proxy.cargar_config(ruta), integridad=integridad, aprobador=dueno)
        async with AsyncExitStack() as pila:
            await recuperado.conectar(pila)
            assert list(recuperado.rutas) == ["leer_correo"]

    asyncio.run(correr())
    esperado = ("stdio", "proceso-ficticio") if transporte == "stdio" else ("http", "https://mcp.ejemplo.cl/mcp")
    assert conexiones == [esperado]
    assert integridad.ruta_estado.read_bytes() == estado_original


def test_aprobar_antes_de_conectar_aplica_toda_la_configuracion_autorizada(tmp_path, monkeypatch):
    conexiones = _transportes_falsos(monkeypatch)
    ruta = tmp_path / "grifter.yaml"
    inicial = _escribir(ruta)
    integridad = Integridad(ruta, clave="hmac-ficticio")
    integridad.aprobar(politica_canonica(inicial), "dueño")
    g = proxy.Grifter(inicial, integridad=integridad, aprobador=Dueno(True))
    autorizada = _escribir(ruta, "http", semillas="privado/semillas.json",
                           registro_aprobaciones="privado/aprobaciones.jsonl", estado="privado/estado.json",
                           dominios_oficiales={"clave_banca": [OFICIAL]})

    async def correr():
        async with AsyncExitStack() as pila:
            await g.conectar(pila)
            assert list(g.rutas) == ["leer_correo"]
            assert not g._reinicio_necesario

    asyncio.run(correr())
    assert conexiones == [("http", "https://mcp.ejemplo.cl/mcp")]
    assert politica_canonica(g.config) == politica_canonica(autorizada) == integridad.estado().politica
    assert g.guardia.dominios == autorizada.dominios


def test_revocar_un_dominio_aprobado_se_aplica_a_la_guardia_y_a_la_siguiente_llamada(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    datos = {"datos_dueno": {"clave_banca": CLAVE},
             "dominios_oficiales": {"clave_banca": [OFICIAL, REVOCADO]}}
    config = _escribir(ruta, **datos)
    integridad, dueno = Integridad(ruta), Dueno()
    integridad.aprobar(politica_canonica(config), "dueño")
    g = proxy.Grifter(config, integridad=integridad, aprobador=dueno, escalar=lambda alerta: False)
    sesion = SesionFalsa()
    g.sesiones["banco"] = sesion
    g.rutas["enviar_formulario"] = ("banco", "enviar_formulario")
    argumentos = {"url": f"https://{REVOCADO}/login", "campos": {"clave": CLAVE}}
    assert not asyncio.run(g.llamar("enviar_formulario", argumentos)).isError
    assert len(sesion.llamadas) == 1
    datos["dominios_oficiales"] = {"clave_banca": [OFICIAL]}
    _escribir(ruta, **datos)
    assert asyncio.run(g.llamar("enviar_formulario", argumentos)).isError
    dueno.respuesta = True
    retenida = asyncio.run(g.llamar("enviar_formulario", argumentos))
    assert retenida.isError and len(sesion.llamadas) == 1
    assert integridad.cambio() is None
    assert g.config.dominios == g.guardia.dominios == {"clave_banca": [OFICIAL]}


def test_aprobar_un_cambio_de_servidores_no_reutiliza_las_conexiones_anteriores(tmp_path):
    ruta = tmp_path / "grifter.yaml"
    config = _escribir(ruta, "http")
    integridad, dueno = Integridad(ruta), Dueno()
    integridad.aprobar(politica_canonica(config), "dueño")
    g = proxy.Grifter(config, integridad=integridad, aprobador=dueno)
    anterior = SesionFalsa()
    g.sesiones["banco"] = anterior
    g.rutas["leer_correo"] = ("banco", "leer_correo")
    assert not asyncio.run(g.llamar("leer_correo", {})).isError
    _escribir(ruta, "http", servidores={"nuevo": {"url": "https://nuevo.ejemplo.cl/mcp"}})
    assert asyncio.run(g.llamar("leer_correo", {})).isError
    dueno.respuesta = True
    for _ in range(2):
        retenida = asyncio.run(g.llamar("leer_correo", {}))
        assert retenida.isError and "reinici" in retenida.content[0].text.lower()
    assert len(anterior.llamadas) == 1 and integridad.cambio() is None
