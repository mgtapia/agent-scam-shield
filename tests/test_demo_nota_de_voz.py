"""`scripts/demo_nota_de_voz.py`: la nota de voz llega por chat, la capa 2 retiene el pago y la alerta sale por WhatsApp.

Sin red: el envío de Kapso es una función de la prueba y nada lee `.env`.
"""
from __future__ import annotations

import re

import pytest

from demo import notificar as notif
from demo import whatsapp
from scripts import demo_nota_de_voz as demo


class Kapso:
    """Un Kapso de mentira: anota cada cuerpo que `CanalWhatsApp.enviar` iba a mandar."""

    def __init__(self):
        self.enviados: list[dict] = []

    def __call__(self, cuerpo):
        self.enviados.append(cuerpo)
        return {"messages": [{"id": "wamid.1"}]}


@pytest.fixture
def canal(monkeypatch):
    kapso = Kapso()
    c = whatsapp.CanalWhatsApp("LLAVE-SECRETA", "123", "+56 9 7777 8888", lambda etiqueta: None)
    monkeypatch.setattr(c, "enviar", kapso)
    monkeypatch.setattr(notif, "_CANALES", [])   # que ningún canal de otra prueba reciba la alerta
    c.kapso = kapso
    return c


@pytest.mark.parametrize("escenario", ["chat_hijo_numero_nuevo", "chat_jefe_nota_de_voz", "chat_contacto_secuestrado"])
def test_el_agente_recibe_la_nota_intenta_pagar_y_la_capa_2_lo_retiene(escenario):
    r = demo.episodio(demo.elegir(escenario))
    assert r["retenida"] and not r["cayo"]
    assert r["origenes"] == {"whatsapp"}                   # la cuenta venía en la nota de voz
    a = r["alerta"]
    assert a["escenario"] == escenario and a["cuenta"] and a["monto"] and "nota de voz" in a["dominio"]
    assert "whatsapp" in a["motivo"]


def test_sin_enviar_no_se_manda_nada(canal, capsys):
    r = demo.correr(canal=canal, imprimir=print)
    t = capsys.readouterr().out
    assert canal.kapso.enviados == [] and r["enviada"] == []
    assert "RETENIDO por la capa 2" in t and "Sin --enviar" in t and "Pagar a mi inscrita | No pagar | Pagar igual" in t


def test_con_enviar_la_alerta_llega_al_dueno_con_los_tres_botones(canal):
    r = demo.correr(enviar=True, canal=canal, imprimir=lambda s: None)
    assert r["enviada"] == ["whatsapp"]
    [msg] = canal.kapso.enviados
    assert msg["to"] == "56977778888" and msg["type"] == "interactive"
    botones = msg["interactive"]["action"]["buttons"]
    assert [b["reply"]["title"] for b in botones] == ["Pagar a mi inscrita", "No pagar", "Pagar igual"]
    texto = msg["interactive"]["body"]["text"]
    assert "Grifter retuvo un pago" in texto and "71-5520-3408" in texto and "$420.000" in texto and "nota de voz" in texto


def test_la_llave_no_aparece_en_lo_que_se_imprime_ni_se_manda(canal, capsys):
    demo.correr(enviar=True, canal=canal)
    assert "LLAVE-SECRETA" not in capsys.readouterr().out
    assert "LLAVE-SECRETA" not in str(canal.kapso.enviados)


def test_sin_configuracion_de_kapso_avisa_y_no_falla(capsys, monkeypatch):
    for v in ("KAPSO_API_KEY", "KAPSO_PHONE_NUMBER_ID", "KAPSO_OWNER_NUMBER"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(demo, "_cargar_env", lambda: None)
    assert demo.main(["--enviar"]) == 2   # no se pudo mandar: el código de salida lo dice, el mensaje explica por qué
    t = capsys.readouterr().out
    assert "faltan KAPSO_API_KEY" in t and "--dry-run" in t


def test_un_escenario_sin_nota_de_voz_o_sin_pago_se_rechaza():
    with pytest.raises(SystemExit, match="nota de voz"):
        demo.elegir("chat_codigo_por_error")
    with pytest.raises(SystemExit, match="No existe"):
        demo.elegir("no_existe")
    with pytest.raises(SystemExit, match="nota de voz"):
        demo.elegir("vishing_familiar")


def test_indica_donde_va_el_audio_o_como_generarlo(capsys):
    demo.correr(imprimir=print)
    assert "generar_audios_vishing.py --notas-de-voz --solo chat_hijo_numero_nuevo" in capsys.readouterr().out


# --- El momento del pitch: cada paso con su hora y la latencia medida ---

class Reloj:
    """Un reloj que avanza `paso` segundos cada vez que se mira, para medir sin esperar."""

    def __init__(self, paso: float):
        self.t, self.paso = 0.0, paso

    def __call__(self) -> float:
        self.t += self.paso
        return self.t


def test_cada_paso_sale_con_su_hora_y_los_segundos_desde_que_llego_el_mensaje(canal):
    lineas: list[str] = []
    r = demo.correr(enviar=True, canal=canal, imprimir=lineas.append, reloj=Reloj(0.5), hora=lambda: 1_800_000_000.0)
    pasos = [ln for ln in lineas if ln.startswith("[")]
    assert all(re.match(r"\[\d\d:\d\d:\d\d\.\d{3}  \+ ?\d+\.\d\d s\] ", ln) for ln in pasos)
    assert "Llega por chat" in pasos[0] and "+ 0.00 s" in pasos[0]
    textos = [t for t, _ in r["pasos"]]
    assert [any(k in t for t in textos) for k in ("Llega", "lee el chat", "RETENIDO", "arma la alerta", "Se manda", "Kapso aceptó")] == [True] * 6
    assert [d for _, d in r["pasos"]] == sorted(d for _, d in r["pasos"])   # el tiempo solo avanza


def test_la_latencia_es_de_la_nota_a_que_kapso_acepta_y_se_compara_con_la_meta(canal):
    lineas: list[str] = []
    r = demo.correr(enviar=True, canal=canal, imprimir=lineas.append, reloj=Reloj(0.5))
    assert r["latencia"] == r["pasos"][-1][1] == pytest.approx(0.5 * (len(r["pasos"]) - 1))
    assert any("dentro de la meta" in ln and "menos de 5 s" in ln for ln in lineas)
    lento = demo.correr(enviar=True, canal=canal, imprimir=lineas.append, reloj=Reloj(1.0))
    assert lento["latencia"] >= demo.META_SEGUNDOS and any("SUPERA LA META" in ln for ln in lineas)


def test_el_ensayo_en_seco_corre_todos_los_pasos_sin_red_ni_llaves(capsys, monkeypatch):
    for v in ("KAPSO_API_KEY", "KAPSO_PHONE_NUMBER_ID", "KAPSO_OWNER_NUMBER"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(notif, "_CANALES", [])
    monkeypatch.setattr(demo, "_cargar_env", lambda: pytest.fail("el ensayo no lee .env"))
    assert demo.main(["--dry-run"]) == 0
    t = capsys.readouterr().out
    assert "SIMULADO" in t and "(simulado, sin red) POST a Kapso: mensaje interactivo con 3 botones" in t
    assert "Latencia" in t and "Kapso aceptó la alerta" in t


def test_si_el_envio_falla_lo_dice_con_el_respaldo_y_sale_con_2(canal, monkeypatch, capsys):
    def cae(cuerpo):
        raise whatsapp.ErrorWhatsApp("enviar: no se pudo hablar con Kapso (URLError)")

    monkeypatch.setattr(canal, "enviar", cae)
    r = demo.correr(enviar=True, canal=canal)
    t = capsys.readouterr().out
    assert r["enviada"] == [] and r["latencia"] is None and "no se pudo hablar con Kapso" in r["error"]
    assert "FALLÓ el envío" in t and "--dry-run" in t and "LLAVE-SECRETA" not in t


def test_la_alerta_del_demo_trae_el_titular_segun_el_banco_cuando_el_escenario_lo_tiene():
    r = demo.episodio(demo.elegir("chat_contacto_secuestrado"))
    assert r["alerta"]["titular"] == "Brian"
