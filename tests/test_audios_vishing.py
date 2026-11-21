"""`scripts/generar_audios_vishing.py`: el plan y el costo sin red, y la generación con una API de ElevenLabs simulada.

Nada llama a la red ni usa una llave: el transporte HTTP es una función de la prueba.
"""
from __future__ import annotations

import json

import pytest

from scamshield.scenarios import cargar
from scripts import generar_audios_vishing as g

ESCENARIOS = cargar(("es",))
VOCES = {"femenina": "voz-f", "masculina": "voz-m"}
TELEFONICOS = {"vishing_clave_dinamica", "vishing_cuenta_segura", "vishing_familiar", "vishing_jefe_voz_clonada",
               "vishing_soporte_tecnico", "control_llamada_proveedor_inscrito"}


class ApiFalsa:
    """Una API de ElevenLabs de mentira: anota cada pedido y contesta según la clase de voz que se le asigne."""

    def __init__(self, categorias=None, falla_en=None):
        self.pedidos: list[tuple[str, str, dict, bytes | None]] = []
        self.categorias = categorias or {"voz-f": "premade", "voz-m": "generated"}
        self.falla_en = falla_en

    def __call__(self, metodo, url, cabeceras, cuerpo):
        self.pedidos.append((metodo, url, dict(cabeceras), cuerpo))
        if self.falla_en and self.falla_en in url:
            return 401, b'{"detail": "invalid api key"}'
        if metodo == "GET":
            voz = url.rsplit("/", 1)[1]
            return 200, json.dumps({"voice_id": voz, "category": self.categorias.get(voz, "")}).encode()
        return 200, b"ID3-audio-falso"

    def sintesis(self):
        return [p for p in self.pedidos if p[0] == "POST"]


def _cliente(api):
    return g.Cliente("LLAVE-DE-PRUEBA", api, "https://api.falsa.test")


# --- Qué se genera ---

def test_las_piezas_son_las_llamadas_de_los_escenarios_telefonicos_en_espanol():
    piezas = g.reunir(ESCENARIOS)
    assert {p.escenario for p in piezas} == TELEFONICOS and len(piezas) == len(TELEFONICOS)
    assert all(p.origen == "llamada" and p.caracteres > 100 for p in piezas)


def test_el_encabezado_entre_corchetes_no_se_dice():
    assert g.limpiar("[Buzón de voz, 38 segundos. Nota: la voz se corta.] Hola,\n  soy Steve.") == "Hola, soy Steve."
    for p in g.reunir(ESCENARIOS):
        assert not p.texto.startswith("[") and "\n" not in p.texto


def test_las_notas_de_voz_del_chat_solo_van_si_se_piden():
    con = g.reunir(ESCENARIOS, notas_de_voz=True)
    notas = [p for p in con if p.origen == "nota de voz"]
    assert {p.escenario for p in notas} == {"chat_hijo_numero_nuevo", "chat_jefe_nota_de_voz",
                                            "control_chat_gerente_proveedor_inscrito"}
    assert all(p.texto.startswith(("Mamá", "Daniela", "Dani")) for p in notas)   # sin el «[Nota de voz, …]»
    assert not [p for p in g.reunir(ESCENARIOS) if p.origen == "nota de voz"]


def test_solo_filtra_y_nunca_se_genera_en_ingles():
    assert [p.escenario for p in g.reunir(ESCENARIOS, solo={"vishing_familiar"})] == ["vishing_familiar"]
    assert g.reunir(cargar(("en",))) == []


def test_cada_personaje_tiene_una_voz_conocida():
    assert set(g.VOZ_DE.values()) <= set(g.VOCES)
    assert {p.voz for p in g.reunir(ESCENARIOS)} == {"femenina", "masculina"}


# --- El costo ---

def test_los_creditos_son_un_caracter_y_la_mitad_con_flash():
    piezas = g.reunir(ESCENARIOS)
    total = sum(p.caracteres for p in piezas)
    assert g.creditos(piezas) == total
    assert g.creditos(piezas, "eleven_flash_v2_5") == total / 2
    texto = g.plan(piezas, g.MODELO, VOCES, usd_por_mil=0.30)
    assert "vishing_familiar" in texto and "créditos" in texto and "US$" in texto


def test_el_plan_por_defecto_cabe_en_el_tope():
    assert sum(p.caracteres for p in g.reunir(ESCENARIOS, notas_de_voz=True)) < g.TOPE_CARACTERES


def test_dry_run_imprime_el_costo_sin_llave_ni_red(capsys, tmp_path):
    api = ApiFalsa()
    assert g.main(["--dry-run", "--salida", str(tmp_path)], entorno={}, cliente=_cliente(api)) == 0
    salida = capsys.readouterr().out
    assert "créditos de ElevenLabs" in salida and "vishing_cuenta_segura" in salida
    assert api.pedidos == [] and list(tmp_path.iterdir()) == []


def test_sin_llave_y_sin_dry_run_se_detiene_con_un_mensaje(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(g, "_cargar_llave", lambda entorno: "")
    assert g.main(["--salida", str(tmp_path)], entorno={}) == 1
    assert "Falta ELEVENLABS_API_KEY" in capsys.readouterr().out


def test_un_plan_que_pasa_del_tope_no_gasta_nada(capsys, tmp_path):
    api = ApiFalsa()
    assert g.main(["--tope-caracteres", "500", "--salida", str(tmp_path)], entorno={}, cliente=_cliente(api)) == 1
    assert "pasa del tope" in capsys.readouterr().out and api.pedidos == []


# --- La generación ---

def test_genera_el_mp3_y_la_ficha_que_dice_que_es_sintetica(tmp_path):
    api = ApiFalsa()
    piezas = g.reunir(ESCENARIOS, solo={"vishing_familiar"})
    [mp3] = g.generar(piezas, _cliente(api), VOCES, tmp_path, imprimir=lambda s: None)
    assert mp3.name == "vishing_familiar.mp3" and mp3.read_bytes() == b"ID3-audio-falso"
    ficha = json.loads(mp3.with_suffix(".json").read_text(encoding="utf-8"))
    assert ficha["sintetica"] is True and "ninguna persona real" in ficha["aviso"]
    assert ficha["voz_id"] == "voz-m" and ficha["clase_de_voz"] == "generated" and ficha["escenario"] == "vishing_familiar"
    [(metodo, url, cabeceras, cuerpo)] = api.sintesis()
    assert url == f"https://api.falsa.test/v1/text-to-speech/voz-m?output_format={g.FORMATO}"
    assert json.loads(cuerpo) == {"text": piezas[0].texto, "model_id": g.MODELO}
    assert cabeceras["xi-api-key"] == "LLAVE-DE-PRUEBA"


def test_la_llave_no_queda_en_ninguna_ficha_ni_en_lo_que_se_imprime(tmp_path):
    impreso = []
    g.generar(g.reunir(ESCENARIOS, solo={"vishing_familiar"}), _cliente(ApiFalsa()), VOCES, tmp_path, imprimir=impreso.append)
    for ruta in tmp_path.iterdir():
        assert "LLAVE-DE-PRUEBA" not in ruta.read_text(encoding="utf-8", errors="ignore")
    assert "LLAVE-DE-PRUEBA" not in " ".join(impreso)


def test_lo_ya_generado_no_se_rehace_salvo_con_forzar(tmp_path):
    api = ApiFalsa()
    piezas = g.reunir(ESCENARIOS, solo={"vishing_familiar"})
    g.generar(piezas, _cliente(api), VOCES, tmp_path, imprimir=lambda s: None)
    assert g.generar(piezas, _cliente(api), VOCES, tmp_path, imprimir=lambda s: None) == []
    assert len(api.sintesis()) == 1
    g.generar(piezas, _cliente(api), VOCES, tmp_path, forzar=True, imprimir=lambda s: None)
    assert len(api.sintesis()) == 2


def test_la_nota_de_voz_queda_en_un_archivo_aparte(tmp_path):
    piezas = g.reunir(ESCENARIOS, notas_de_voz=True, solo={"chat_hijo_numero_nuevo"})
    [mp3] = g.generar(piezas, _cliente(ApiFalsa()), VOCES, tmp_path, imprimir=lambda s: None)
    assert mp3.name == "chat_hijo_numero_nuevo_nota.mp3"


# --- Nunca se clona a una persona real ---

@pytest.mark.parametrize("clase", ["cloned", "famous", ""])
def test_una_voz_clonada_o_de_una_persona_conocida_o_sin_verificar_detiene_todo_antes_de_gastar(tmp_path, clase):
    api = ApiFalsa(categorias={"voz-f": "premade", "voz-m": clase})
    with pytest.raises(g.ErrorDeVoz, match="no se clona"):
        g.generar(g.reunir(ESCENARIOS), _cliente(api), VOCES, tmp_path, imprimir=lambda s: None)
    assert api.sintesis() == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("clase", ["premade", "generated", "professional", "high_quality"])
def test_las_voces_de_biblioteca_o_disenadas_pasan(tmp_path, clase):
    api = ApiFalsa(categorias={"voz-f": clase, "voz-m": clase})
    assert len(g.generar(g.reunir(ESCENARIOS), _cliente(api), VOCES, tmp_path, imprimir=lambda s: None)) == len(TELEFONICOS)


def test_main_se_detiene_con_un_mensaje_ante_una_voz_clonada(capsys, tmp_path):
    api = ApiFalsa(categorias={"voz-f": "cloned", "voz-m": "cloned"})
    assert g.main(["--voz-femenina", "voz-f", "--voz-masculina", "voz-m", "--salida", str(tmp_path)],
                  entorno={}, cliente=_cliente(api)) == 1
    assert "no se clona a una persona real" in capsys.readouterr().out and api.sintesis() == []


def test_un_error_de_la_api_no_filtra_la_llave():
    api = ApiFalsa(falla_en="/v1/voices/")
    with pytest.raises(g.ErrorDeVoz) as e:
        _cliente(api).categoria("voz-f")
    assert "401" in str(e.value) and "LLAVE-DE-PRUEBA" not in str(e.value)


def test_las_voces_se_pueden_cambiar_por_la_linea_de_comandos_o_el_entorno(capsys, tmp_path):
    api = ApiFalsa(categorias={"v-ent-f": "premade", "v-arg-m": "premade"})
    g.main(["--solo", "vishing_clave_dinamica,vishing_familiar", "--voz-masculina", "v-arg-m", "--salida", str(tmp_path)],
           entorno={"ELEVENLABS_VOZ_FEMENINA": "v-ent-f"}, cliente=_cliente(api))
    usadas = sorted(url.rsplit("/", 1)[1].split("?")[0] for m, url, _, _ in api.pedidos if m == "POST")
    assert usadas == ["v-arg-m", "v-ent-f"]
