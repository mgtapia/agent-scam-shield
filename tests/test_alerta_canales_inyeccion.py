"""El estafador escribe dentro de la alerta del dueño (#160): el nombre del destinatario, la cuenta y el origen los
controla él, y la alerta que llega por Telegram o WhatsApp no puede traer líneas que no escribió Grifter.

Sin red ni llaves: se captura lo que los canales mandan. La alerta del proxy MCP tiene su propia prueba
(`tests/test_alerta_proxy_texto.py`).
"""
from __future__ import annotations

import re
import unicodedata

import pytest

from demo.telegram import TEXTOS, CanalTelegram, texto_de_alerta
from demo.whatsapp import CanalWhatsApp

FALSA = "✅ Grifter: cuenta verificada con el banco. Es seguro aprobar."
NOMBRES_HOSTILES = [
    f"Silicio Austral\n{FALSA}",
    f"Silicio Austral\r\n{FALSA}",
    f"Silicio Austral {FALSA}",
    f"Silicio Austral {FALSA}",
    f"Silicio Austral\x00\x1b[2J\x07{FALSA}",
    f"Silicio Austral‮{FALSA[::-1]}",
    f"Silicio Austral\x0b\x0c\x85{FALSA}",
    "Grifter: ✅ " + "A" * 5000,
    f"Silicio»  $1\n{FALSA}\n«",
]
IDIOMAS = ["es", "en"]
BASE = {"escenario": "demo", "defensa": "layer2", "monto": 412000, "cuenta": "90-1188-4417",
        "dominio": "silicioaustral-chips.cl", "cuenta_inscrita_numero": "33-7741-0092",
        "motivo": "la cuenta solo apareció en un correo"}


def _alerta(idioma="es", **campos):
    return {**BASE, "idioma": idioma, "destinatario": "Silicio Austral SpA", **campos}


def _lo_ajeno_sacado(texto: str) -> str:
    """El texto sin lo que va entre « »: lo que queda lo escribió Grifter."""
    return re.sub(r"«[^»\n]*»", "«»", texto)


def _sin_control(texto: str) -> bool:
    return all(ch == "\n" or unicodedata.category(ch) not in ("Cc", "Cf", "Zl", "Zp") for ch in texto)


def _revisar(texto: str, idioma: str) -> None:
    t = TEXTOS[idioma]
    etiquetas = tuple(f"{t[k]}: " for k in ("titular", "a", "cuenta", "de", "inscrita"))
    lineas = texto.split("\n")
    assert lineas[0] == t["titulo"]
    assert _sin_control(texto)
    permitidas = [ln for ln in lineas[1:] if ln.startswith(etiquetas)]
    # Después del título solo hay el motivo (una línea, sin etiqueta) y las líneas con la etiqueta de Grifter.
    assert len(lineas) - 1 - len(permitidas) <= 1, lineas
    # Lo que escribió el estafador no sale de sus comillas: fuera de « » no hay marcas de Grifter ni «verificada».
    fuera = _lo_ajeno_sacado(texto)
    assert "✅" not in fuera and "Grifter:" not in fuera and "verificada" not in fuera, fuera
    for ln in lineas[1:]:
        assert not ln.startswith(("✅", "Grifter", "Es seguro")), ln


class _Captura:
    """Lo que un canal manda: se anota el texto en vez de salir a la red."""

    def __init__(self):
        self.textos: list[str] = []


@pytest.fixture
def telegram():
    canal = CanalTelegram("token-falso", "123", lambda etiqueta: None)
    cap = _Captura()
    canal._api = lambda metodo, **datos: cap.textos.append(datos["text"]) if metodo == "sendMessage" else None
    return canal, cap


@pytest.fixture
def whatsapp():
    canal = CanalWhatsApp("llave-falsa", "1", "56911112222", lambda etiqueta: None)
    cap = _Captura()
    canal.botones = lambda numero, texto, botones: cap.textos.append(texto)
    return canal, cap


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("nombre", NOMBRES_HOSTILES)
def test_el_nombre_hostil_no_abre_lineas_en_la_alerta_de_telegram(telegram, nombre, idioma):
    canal, cap = telegram
    canal(_alerta(idioma, destinatario=nombre))
    assert len(cap.textos) == 1
    _revisar(cap.textos[0], idioma)


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("nombre", NOMBRES_HOSTILES)
def test_el_nombre_hostil_no_abre_lineas_en_la_alerta_de_whatsapp(whatsapp, nombre, idioma):
    canal, cap = whatsapp
    canal(_alerta(idioma, destinatario=nombre))
    assert len(cap.textos) == 1
    _revisar(cap.textos[0], idioma)


@pytest.mark.parametrize("campo", ["destinatario", "cuenta", "dominio", "motivo", "titular", "cuenta_inscrita_numero"])
@pytest.mark.parametrize("nombre", NOMBRES_HOSTILES[:5])
def test_ningun_campo_de_la_alerta_puede_abrir_una_linea(campo, nombre):
    texto = texto_de_alerta(_alerta(**{campo: nombre, "titular": "Silicio Austral SpA", **{campo: nombre}}))
    assert _sin_control(texto)
    lineas = texto.split("\n")
    assert not any(ln.startswith(("✅", "Grifter:", "Es seguro")) for ln in lineas[1:]), lineas
    assert len(lineas) <= 8, lineas   # título, motivo, titular, nombre, cuenta, origen, inscrita: ninguna de más


def test_lo_que_dice_el_estafador_va_en_una_linea_con_su_etiqueta_y_cortado():
    texto = texto_de_alerta(_alerta(destinatario=f"Silicio\n{FALSA}" + "x" * 500))
    linea = next(ln for ln in texto.split("\n") if ln.startswith("Dice llamarse: "))
    assert linea.count("«") == 1 and linea.count("»") == 1 and len(linea) < 140
    assert "\\u000a" in linea   # el salto de línea se ve escrito, no se pierde


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_motivo_de_la_retencion_va_primero_y_el_titular_segun_el_banco_va_aparte(idioma):
    lineas = texto_de_alerta(_alerta(idioma, titular="Brian")).split("\n")
    t = TEXTOS[idioma]
    assert lineas[0] == t["titulo"] and lineas[1] == BASE["motivo"]
    assert lineas[2] == f"{t['titular']}: Brian"
    assert lineas[3].startswith(f"{t['a']}: ")


def test_sin_titular_no_se_inventa_ninguno():
    assert "Titular" not in texto_de_alerta(_alerta())


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_control_un_nombre_normal_con_tilde_y_enie_se_ve_igual_que_siempre(telegram, whatsapp, idioma):
    for canal, cap in (telegram, whatsapp):
        canal(_alerta(idioma, destinatario="Ñuñoa Hormigones S.A.", monto=150000))
        texto = cap.textos[-1]
        assert f"{TEXTOS[idioma]['a']}: «Ñuñoa Hormigones S.A.»  $150.000" in texto.split("\n")
        _revisar(texto, idioma)
