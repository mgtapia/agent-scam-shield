"""scripts/calentar.py: despierta la demo y verifica /api/salud, /resultados.json, /mcp y /api/probar. Con un servidor falso en 127.0.0.1."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts import calentar


class Falso(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *, dormido: int = 0, mcp: int = 200, resultados: dict | None = None, evento: bool = False, probar: int = 200):
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.dormido, self.mcp, self.evento, self.probar = dormido, mcp, evento, probar
        self.resultados = {"bench": {}, "clasificador": {}, "duelo": {}} if resultados is None else resultados
        self.pedidos: list[tuple[str, str]] = []


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _responder(self, estado: int, cuerpo: object) -> None:
        datos = (cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode("utf-8"))
        self.send_response(estado)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _atender(self, metodo: str) -> None:
        s = self.server
        s.pedidos.append((metodo, self.path))
        largo = int(self.headers.get("Content-Length") or 0)
        if largo:
            self.rfile.read(largo)
        if self.path == "/api/salud" and s.dormido > 0:
            s.dormido -= 1
            return self._responder(503, {"detail": "despertando"})
        if self.path == "/api/salud":
            return self._responder(200, {"ok": True, "episodios": 12, "evento": s.evento})
        if self.path == "/resultados.json":
            return self._responder(200, s.resultados)
        if self.path == "/mcp":
            return self._responder(s.mcp, {"result": {"serverInfo": {"name": "grifter"}}} if s.mcp == 200 else {"detail": "x"})
        if self.path == "/api/probar":
            return self._responder(s.probar, {"veredicto": "estafa"} if s.probar == 200 else {"detail": "tope"})
        self._responder(404, {})

    def do_GET(self):
        self._atender("GET")

    def do_POST(self):
        self._atender("POST")


@pytest.fixture
def servir():
    servidores = []

    def _servir(**kw) -> tuple[Falso, str]:
        s = Falso(**kw)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        servidores.append(s)
        return s, f"http://127.0.0.1:{s.server_address[1]}"

    yield _servir
    for s in servidores:
        s.shutdown()
        s.server_close()


def test_todo_listo_devuelve_cero_y_verifica_las_cuatro_rutas(servir, capsys):
    s, url = servir(evento=True)
    assert calentar.main(["--url", url]) == 0
    assert {p for _, p in s.pedidos} == {"/api/salud", "/resultados.json", "/mcp", "/api/probar"}
    salida = capsys.readouterr().out
    assert "todo listo para el pitch" in salida and "modo evento" in salida


def test_despierta_con_reintentos_aunque_conteste_503_al_principio(servir):
    s, url = servir(dormido=3)
    despierto, _ = calentar.despertar(url, espera_max=30, reintento=0.01)
    assert despierto
    assert [p for _, p in s.pedidos].count("/api/salud") == 4


def test_si_no_despierta_a_tiempo_falla_con_un_mensaje(servir, capsys):
    _, url = servir(dormido=10_000)
    assert calentar.main(["--url", url, "--espera", "0.2"]) == 1
    assert "no despertó" in capsys.readouterr().out


def test_un_puerto_cerrado_no_despierta():
    despierto, _ = calentar.despertar("http://127.0.0.1:9", espera_max=0.1, reintento=0.01)
    assert not despierto


@pytest.mark.parametrize("falla,nombre", [
    ({"mcp": 404}, "/mcp"), ({"mcp": 401}, "/mcp"), ({"probar": 429}, "/api/probar"),
    ({"resultados": {"bench": {}}}, "/resultados.json"),
])
def test_dice_cual_ruta_fallo(servir, capsys, falla, nombre):
    _, url = servir(**falla)
    assert calentar.main(["--url", url]) == 1
    salida = capsys.readouterr().out
    assert f"[FALLA] {nombre}" in salida and f"FALLA ({nombre})" in salida


def test_el_429_sugiere_el_modo_evento(servir, capsys):
    _, url = servir(probar=429)
    calentar.main(["--url", url])
    assert "GRIFTER_EVENTO=1" in capsys.readouterr().out


def test_sin_probar_no_toca_api_probar(servir):
    s, url = servir()
    assert calentar.main(["--url", url, "--sin-probar"]) == 0
    assert "/api/probar" not in {p for _, p in s.pedidos}
