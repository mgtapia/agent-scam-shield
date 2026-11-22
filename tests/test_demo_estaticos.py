"""La interfaz y los episodios son públicos; las etiquetas y el código del servidor no."""
from __future__ import annotations

import json
import re
import shutil
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from demo import server


@pytest.fixture
def demo(tmp_path, monkeypatch):
    # Ejecuta las rutas reales contra una copia temporal, sin iniciar canales ni conexiones MCP.
    for nombre in server.ACTIVOS_PUBLICOS:
        origen = server.DEMO / nombre
        if origen.is_file():
            (tmp_path / nombre).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origen, tmp_path / nombre)
    shutil.copytree(server.DEMO / "episodios", tmp_path / "episodios")
    shutil.copytree(server.DEMO / "audio", tmp_path / "audio")
    for nombre in ("server.py", "telegram.py", "whatsapp.py", "__init__.py", "DESIGN.md",
                   ".env", "privado.js", "privado.json", "__pycache__/server.cpython-311.pyc"):
        ruta = tmp_path / nombre
        ruta.parent.mkdir(exist_ok=True)
        ruta.write_text("informacion-interna-de-la-demo", encoding="utf-8")
    monkeypatch.setattr(server, "ETIQUETAS", tmp_path / "etiquetas.jsonl")
    monkeypatch.setattr(server, "limite_etiquetas", server.limite_de("etiquetas", {}))   # una etiqueta por prueba: que el tope no se acumule
    for ruta in server.app.routes:
        if ruta.name in ("demo", "episodios", "audio"):
            directorio = tmp_path if ruta.name == "demo" else tmp_path / ruta.name
            monkeypatch.setattr(ruta.app, "directory", directorio)
            monkeypatch.setattr(ruta.app, "all_directories", [directorio])
    cliente = TestClient(server.app)
    etiqueta = {"eleccion": "no_pagar", "cuenta": "cuenta-privada-del-dueno", "destinatario": "alerta-privada-del-dueno"}
    assert cliente.post("/api/etiquetas", json=etiqueta).json() == {"ok": True}
    guardada = json.loads((tmp_path / "etiquetas.jsonl").read_text(encoding="utf-8"))
    assert guardada["cuenta"] == etiqueta["cuenta"] and guardada["destinatario"] == etiqueta["destinatario"] and guardada["recibida"]
    return cliente, tmp_path


@pytest.mark.parametrize("metodo", ["GET", "HEAD"])
@pytest.mark.parametrize("ruta", [
    "/etiquetas.jsonl", "/etiquetas.jsonl?download=1", "/%65tiquetas.jsonl",
    "/etiquetas%2ejsonl", "/%2e/etiquetas.jsonl", "/index.html/../etiquetas.jsonl",
    "/episodios/../etiquetas.jsonl", "/episodios/%2e%2e/etiquetas.jsonl",
    "/episodios%2f..%2fetiquetas.jsonl", "/episodios/%2e%2e%2fetiquetas.jsonl?download=1",
    "/%252e%252e/etiquetas.jsonl", "/%2fetiquetas.jsonl",
])
def test_el_historial_guardado_por_la_api_no_se_puede_descargar(demo, metodo, ruta):
    cliente, _ = demo
    respuesta = cliente.request(metodo, ruta)
    assert respuesta.status_code == 404
    assert "cuenta-privada" not in respuesta.text and "alerta-privada" not in respuesta.text


@pytest.mark.parametrize("metodo", ["GET", "HEAD"])
@pytest.mark.parametrize("ruta", [
    "/server.py", "/telegram.py", "/whatsapp.py", "/__init__.py", "/DESIGN.md", "/.env",
    "/privado.js", "/privado.json", "/__pycache__/server.cpython-311.pyc",
])
def test_los_archivos_internos_no_se_publican_aunque_existan(demo, metodo, ruta):
    cliente, _ = demo
    respuesta = cliente.request(metodo, ruta)
    assert respuesta.status_code == 404 and "informacion-interna" not in respuesta.text


@pytest.mark.parametrize("metodo", ["GET", "HEAD"])
@pytest.mark.parametrize("ruta,activo", [("/", "index.html"), ("/index.html", "index.html"), ("/app.js", "app.js")])
@pytest.mark.parametrize("destino", ["etiquetas.jsonl", "privado.js", "privado.json"])
def test_un_enlace_con_nombre_publico_no_publica_su_destino_privado(demo, metodo, ruta, activo, destino):
    cliente, raiz = demo
    (raiz / activo).unlink()
    (raiz / activo).symlink_to(raiz / destino)
    respuesta = cliente.request(metodo, ruta)
    assert respuesta.status_code == 404
    assert "cuenta-privada" not in respuesta.text and "informacion-interna" not in respuesta.text


class _Referencias(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rutas = set()

    def handle_starttag(self, tag, attrs):
        for clave, valor in attrs:
            if clave in ("src", "href") and valor and not valor.startswith(("http:", "https:", "#")):
                self.rutas.add("/" + valor.lstrip("/"))


def test_la_pagina_y_todos_sus_activos_siguen_accesibles(demo):
    cliente, raiz = demo
    pagina = cliente.get("/")
    assert pagina.status_code == 200 and pagina.text == (raiz / "index.html").read_text(encoding="utf-8")
    referencias = _Referencias()
    referencias.feed(pagina.text)
    for ruta in referencias.rutas | {"/index.html", "/resultados.json"}:
        respuesta = cliente.get(ruta + "?version=1")
        assert respuesta.status_code == 200, ruta
        assert respuesta.content == (raiz / ruta.lstrip("/")).read_bytes()
        cabecera = cliente.head(ruta)
        assert cabecera.status_code == 200 and cabecera.content == b""


def test_el_modo_demo_del_pitch_y_sus_activos_son_publicos(demo):
    # /#demo redirige a demo.html (la secuencia automática del video): sus activos no pueden quedar en 404.
    cliente, raiz = demo
    assert {"demo.html", "demo.css", "demo.js"} <= server.ACTIVOS_PUBLICOS
    if not (raiz / "demo.html").is_file():
        pytest.skip("demo.html todavía no está en esta rama")
    referencias = _Referencias()
    referencias.feed((raiz / "demo.html").read_text(encoding="utf-8"))
    # demo.js arma el teléfono y la llamada después de cargar: sus imágenes y audios tampoco pueden dar 404.
    desde_js = {"/" + r for r in re.findall(r"[\"'`]((?:img|audio)/[\w./-]+\.(?:svg|png|jpg|webp|mp3))", (raiz / "demo.js").read_text(encoding="utf-8"))}
    assert {"/img/nieto.svg", "/img/pablo.jpg", "/img/marca.png", "/audio/cuento_del_tio_nieto.mp3"} <= desde_js
    for ruta in referencias.rutas | desde_js | {"/demo.html"}:
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 200, ruta
        assert respuesta.content == (raiz / ruta.lstrip("/")).read_bytes()


def test_la_demo_dinamica_y_sus_activos_son_publicos(demo):
    # La versión B del modo demo (dinamica.html): la página, su CSS y su JS, y las fotos y los audios que arma dinamica.js.
    cliente, raiz = demo
    assert {"dinamica.html", "dinamica.css", "dinamica.js"} <= server.ACTIVOS_PUBLICOS
    referencias = _Referencias()
    referencias.feed((raiz / "dinamica.html").read_text(encoding="utf-8"))
    assert {"/dinamica.css", "/dinamica.js", "/estilos.css"} <= referencias.rutas
    desde_js = {"/" + r for r in re.findall(r"[\"'`]((?:img|audio)/[\w./-]+\.(?:svg|png|jpg|webp|mp3))", (raiz / "dinamica.js").read_text(encoding="utf-8"))}
    narracion = {r for r in desde_js if r.startswith("/audio/dinamica_")}
    assert len(narracion) == 18 and {"/audio/cuento_del_tio_nieto.mp3", "/img/nieto.jpg", "/img/abuela.jpg", "/img/pablo.jpg", "/img/marca.png"} <= desde_js
    for ruta in referencias.rutas | desde_js | {"/dinamica.html"}:
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 200, ruta
        assert respuesta.content == (raiz / ruta.lstrip("/")).read_bytes()
    # Cada narración tiene su ficha, que dice que la voz es sintética.
    for ruta in narracion:
        ficha = json.loads((raiz / ruta.lstrip("/")).with_suffix(".json").read_text(encoding="utf-8"))
        assert ficha["sintetica"] is True and ficha["voz_id"] and ficha["modelo"] == "eleven_v3" and ficha["aviso"]


def test_la_demo_en_grafo_y_sus_activos_son_publicos(demo):
    # La versión C del modo demo (grafo.html): la página, su CSS y su JS, y las fotos y los audios que arma grafo.js.
    cliente, raiz = demo
    assert {"grafo.html", "grafo.css", "grafo.js"} <= server.ACTIVOS_PUBLICOS
    referencias = _Referencias()
    referencias.feed((raiz / "grafo.html").read_text(encoding="utf-8"))
    assert {"/grafo.css", "/grafo.js", "/estilos.css"} <= referencias.rutas
    desde_js = {"/" + r for r in re.findall(r"[\"'`]((?:img|audio)/[\w./-]+\.(?:svg|png|jpg|webp|mp3))", (raiz / "grafo.js").read_text(encoding="utf-8"))}
    narracion = {r for r in desde_js if r.startswith("/audio/grafo_")}
    assert len(narracion) == 16 and {"/audio/cuento_del_tio_nieto.mp3", "/audio/cuento_del_tio_abuela_tomas.mp3", "/img/nieto.jpg", "/img/abuela.jpg", "/img/pablo.jpg", "/img/marca.png"} <= desde_js
    # La versión C no depende de los mp3 de la versión B: los que reusa están copiados con nombre propio.
    assert not any(r.startswith("/audio/dinamica_") for r in desde_js)
    for ruta in referencias.rutas | desde_js | {"/grafo.html"}:
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 200, ruta
        assert respuesta.content == (raiz / ruta.lstrip("/")).read_bytes()
    # Cada narración tiene su ficha, que dice que la voz es sintética y trae los tiempos por palabra.
    for ruta in narracion:
        ficha = json.loads((raiz / ruta.lstrip("/")).with_suffix(".json").read_text(encoding="utf-8"))
        assert ficha["sintetica"] is True and ficha["voz_id"] and ficha["modelo"] == "eleven_v3" and ficha["aviso"]
        assert ficha["duracion_s"] > 0 and len(ficha["inicios_de_palabra_s"]) == len(ficha["texto"].split())


def test_todos_los_episodios_exportados_siguen_publicos(demo):
    cliente, raiz = demo
    for archivo in (raiz / "episodios").iterdir():
        if archivo.is_file():
            ruta = "/episodios/" + archivo.name
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200 and respuesta.content == archivo.read_bytes(), ruta
            assert cliente.head(ruta).status_code == 200, ruta


def test_los_episodios_no_permiten_enlaces_a_archivos_fuera_de_su_carpeta(demo):
    cliente, raiz = demo
    (raiz / "episodios" / "fuga.json").symlink_to(raiz / "etiquetas.jsonl")
    for metodo in ("GET", "HEAD"):
        assert cliente.request(metodo, "/episodios/fuga.json").status_code == 404


def test_los_audios_y_sus_fichas_siguen_publicos(demo):
    cliente, raiz = demo
    archivos = list((raiz / "audio").iterdir())
    assert any(a.suffix == ".mp3" for a in archivos) and any(a.suffix == ".json" for a in archivos)
    for archivo in archivos:
        if archivo.is_file():
            ruta = "/audio/" + archivo.name
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200 and respuesta.content == archivo.read_bytes(), ruta
            assert cliente.head(ruta).status_code == 200, ruta


def test_los_audios_no_permiten_atravesar_a_las_etiquetas(demo):
    cliente, _ = demo
    for ruta in ("/audio/../etiquetas.jsonl", "/audio/%2e%2e/etiquetas.jsonl",
                 "/audio/%2e%2e%2fetiquetas.jsonl?download=1"):
        for metodo in ("GET", "HEAD"):
            assert cliente.request(metodo, ruta).status_code == 404


def test_los_audios_no_permiten_enlaces_fuera_de_su_carpeta(demo):
    cliente, raiz = demo
    (raiz / "audio" / "fuga.mp3").symlink_to(raiz / "etiquetas.jsonl")
    for metodo in ("GET", "HEAD"):
        assert cliente.request(metodo, "/audio/fuga.mp3").status_code == 404
