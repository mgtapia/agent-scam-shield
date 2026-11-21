"""Valida todos los escenarios: estructura, pares es/en, marcas ficticias y el guion de cada uno.

El guion es un agente sin LLM: lee todo lo que hay en el mundo y ejecuta la acción de la estafa
o la acción legítima que declara el YAML. Así cada escenario se prueba sin API y el resultado
esperado de la capa 2 queda escrito como dato en el escenario, no inferido por la prueba.
"""
from __future__ import annotations

import re

import pytest
import yaml

from scamshield.defenses.layer1 import PATRONES_INYECCION
from scamshield.defenses.layer2 import politica_origen
from scamshield.env.tools import Herramientas
from scamshield.env.world import World
from scamshield.evals.puntaje import puntuar
from scamshield.scenarios import cargar

ESCENARIOS = cargar()
POR_CLAVE = {(e["id"], e["idioma"]): e for e in ESCENARIOS}
ESTAFAS = [e for e in ESCENARIOS if e["tipo"] == "estafa"]
CONTROLES = [e for e in ESCENARIOS if e["tipo"] == "control"]

CLAVES_FRAUDBENCH = {
    "intent", "fraud_mechanism", "social_eng_tactics", "targeted_workflow_stage",
    "observable_evidence", "permitted_agent_actions", "prohibited_agent_actions",
    "correct_disposition", "control_pair_id",
}
# «familia» usa etiquetas propias, inspiradas en la taxonomía de ScamWorld (solo como referencia).
CLAVES_PROPIAS = {"dificultad", "familia"}
DIFICULTADES = {"burda", "media", "convincente"}
TAREAS = {"pagar", "transferir", "compartir", "ninguna"}

# Marcas e instituciones reales de Chile y globales que no pueden aparecer en un escenario.
# Se buscan como palabra completa. Se dejan fuera palabras comunes como «claro», «líder» o «visa».
MARCAS_REALES = [
    "BancoEstado", "Banco Estado", "Santander", "BCI", "Banco de Chile", "Itaú", "Itau",
    "Scotiabank", "Falabella", "Ripley", "Cencosud", "Jumbo", "Coopeuch", "BICE",
    "Chilexpress", "Correos de Chile", "Starken", "Blue Express", "Bluexpress",
    "SII", "Servicio de Impuestos Internos", "Tesorería General", "TGR", "ClaveÚnica",
    "Clave Única", "Registro Civil", "ChileAtiende", "Fonasa", "Carabineros", "PDI",
    "Enel", "CGE", "Metrogas", "Aguas Andinas", "Essbio", "Esval",
    "Autopista Central", "Costanera Norte", "Vespucio Sur", "Vespucio Norte",
    "Mercado Libre", "MercadoLibre", "Mercado Pago", "MACH", "Tenpo", "Copec", "Entel",
    "Movistar", "WOM", "VTR", "Servipag", "Khipu", "Webpay", "Transbank", "Previred",
    "Portal Inmobiliario", "Yapo", "LATAM", "JetSMART", "PedidosYa", "Rappi", "Uber",
    "WhatsApp", "Telegram", "Netflix", "Spotify", "Amazon", "Google", "Microsoft", "Apple",
    "PayPal", "Mastercard",
]


def _norm(texto) -> str:
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())


def _texto(esc) -> str:
    return yaml.safe_dump(esc, allow_unicode=True)


def _contenido_no_confiable(esc) -> str:
    partes = [f"{c['asunto']}\n{c['cuerpo']}" for c in esc.get("correos", [])]
    partes += list(esc.get("paginas", {}).values())
    partes += list(esc.get("mcp_herramientas", {}).values())
    return "\n".join(partes)


def _leer_todo(h: Herramientas) -> None:
    h.leer_correos()
    for url in h.w.paginas:
        h.abrir_web(url)
    for nombre in h.w.mcp_herramientas:
        h.usar_mcp(nombre)


def _ejecutar(h: Herramientas, accion: dict) -> str:
    return getattr(h, accion["herramienta"])(**accion["args"])


def _ids(escs):
    return [f"{e['id']}__{e['idioma']}" for e in escs]


# --- Cantidad y pares ---

@pytest.mark.parametrize("idioma", ["es", "en"])
def test_hay_15_estafas_y_5_controles_por_idioma(idioma):
    tipos = [e["tipo"] for e in ESCENARIOS if e["idioma"] == idioma]
    assert tipos.count("estafa") == 15
    assert tipos.count("control") == 5


def test_cada_escenario_tiene_su_par_en_el_otro_idioma():
    es = {e["id"] for e in ESCENARIOS if e["idioma"] == "es"}
    en = {e["id"] for e in ESCENARIOS if e["idioma"] == "en"}
    assert es == en


@pytest.mark.parametrize("esc", [e for e in ESCENARIOS if e["idioma"] == "es"], ids=lambda e: e["id"])
def test_el_par_es_en_mide_lo_mismo(esc):
    otro = POR_CLAVE[(esc["id"], "en")]
    assert esc["tipo"] == otro["tipo"]
    for clave in ("tarea", "cuenta_legitima", "cuenta_estafador", "monto", "dato_sensible",
                  "dato_legitimo", "capa2_estafa", "capa2_legitima"):
        assert esc["evaluacion"].get(clave) == otro["evaluacion"].get(clave), clave
    for clave in ("fraud_mechanism", "correct_disposition", "control_pair_id", "dificultad",
                  "dueno_ya_enganado"):
        assert esc["anotaciones"].get(clave) == otro["anotaciones"].get(clave), clave
    for parte in ("estafa", "legitima"):
        a, b = esc["evaluacion"].get(f"accion_{parte}"), otro["evaluacion"].get(f"accion_{parte}")
        assert (a is None) == (b is None)
        if a:
            assert a["herramienta"] == b["herramienta"]


# --- Estructura ---

@pytest.mark.parametrize("esc", ESCENARIOS, ids=_ids(ESCENARIOS))
def test_estructura(esc):
    assert esc["tipo"] in {"estafa", "control"}
    ev, an = esc["evaluacion"], esc["anotaciones"]
    assert ev["tarea"] in TAREAS
    if ev["tarea"] in ("pagar", "transferir"):
        assert ev["cuenta_legitima"] and ev["monto"]
    if ev["tarea"] == "compartir":
        assert ev["destinatario_legitimo"] and ev["dato_legitimo"]
    if ev["tarea"] != "ninguna":
        assert ev["accion_legitima"]["herramienta"]
        assert ev["capa2_legitima"] in {"bloquea", "deja_pasar"}
    if esc["tipo"] == "estafa":
        assert ev.get("cuenta_estafador") or ev.get("destinatario_estafador")
        assert ev["accion_estafa"]["herramienta"]
        assert ev["capa2_estafa"] in {"bloquea", "deja_pasar"}
        assert an["intent"] == "fraud"
    else:
        assert "accion_estafa" not in ev and not ev.get("cuenta_estafador")
        assert an["intent"] == "legitimate"
    faltan = (CLAVES_FRAUDBENCH | CLAVES_PROPIAS) - set(an)
    assert not faltan, faltan
    assert an["dificultad"] in DIFICULTADES
    assert isinstance(an["social_eng_tactics"], list)
    if an["control_pair_id"]:
        assert (an["control_pair_id"], esc["idioma"]) in POR_CLAVE


@pytest.mark.parametrize("esc", ESCENARIOS, ids=_ids(ESCENARIOS))
def test_cuentas_no_se_confunden(esc):
    """Cuentas de 8 dígitos o más, y ninguna contenida en otra: el rastreo es por subcadena."""
    ev = esc["evaluacion"]
    cuentas = [ev[c] for c in ("cuenta_legitima", "cuenta_estafador") if ev.get(c)]
    cuentas += list(esc.get("cuentas_inscritas", {}).values())
    for c in cuentas:
        assert sum(ch.isdigit() for ch in c) >= 8, c
    if ev.get("cuenta_legitima") and ev.get("cuenta_estafador"):
        a, b = _norm(ev["cuenta_legitima"]), _norm(ev["cuenta_estafador"])
        assert a not in b and b not in a


@pytest.mark.parametrize("esc", ESTAFAS, ids=_ids(ESTAFAS))
def test_el_destino_del_estafador_no_viene_del_dueno(esc):
    """Salvo cuando el dueño ya fue engañado, el destino de la estafa no sale del encargo."""
    ev = esc["evaluacion"]
    destino = _norm(ev.get("cuenta_estafador") or ev["destinatario_estafador"])
    del_dueno = _norm(esc["encargo"]) + _norm(esc.get("cuentas_inscritas")) + _norm(esc.get("datos_dueno"))
    enganado = esc["anotaciones"].get("dueno_ya_enganado", False)
    assert (destino in del_dueno) == enganado
    assert (ev["capa2_estafa"] == "deja_pasar") == enganado


# --- Nada real ---

@pytest.mark.parametrize("esc", ESCENARIOS, ids=_ids(ESCENARIOS))
def test_sin_marcas_reales(esc):
    texto = _texto(esc)
    for marca in MARCAS_REALES:
        assert not re.search(rf"(?<!\w){re.escape(marca)}(?!\w)", texto, flags=re.IGNORECASE), marca


@pytest.mark.parametrize("esc", CONTROLES, ids=_ids(CONTROLES))
def test_los_controles_no_parecen_inyeccion(esc):
    texto = _contenido_no_confiable(esc)
    for patron in PATRONES_INYECCION:
        assert not re.search(patron, texto, flags=re.IGNORECASE), patron


# --- El guion de cada escenario ---

@pytest.mark.parametrize("esc", ESTAFAS, ids=_ids(ESTAFAS))
def test_sin_defensa_la_estafa_funciona(esc):
    w = World.desde_escenario(esc)
    h = Herramientas(w)
    _leer_todo(h)
    _ejecutar(h, esc["evaluacion"]["accion_estafa"])
    assert puntuar(w, esc)["cayo"]


@pytest.mark.parametrize("esc", ESTAFAS, ids=_ids(ESTAFAS))
def test_capa2_frente_a_la_estafa(esc):
    w = World.desde_escenario(esc)
    h = Herramientas(w, [politica_origen])
    _leer_todo(h)
    salida = _ejecutar(h, esc["evaluacion"]["accion_estafa"])
    r = puntuar(w, esc)
    if esc["evaluacion"]["capa2_estafa"] == "bloquea":
        assert "BLOQUEADA" in salida and not r["cayo"]
    else:
        assert "BLOQUEADA" not in salida and r["cayo"]


CON_ACCION_LEGITIMA = [e for e in ESCENARIOS if e["evaluacion"]["tarea"] != "ninguna"]


@pytest.mark.parametrize("esc", CON_ACCION_LEGITIMA, ids=_ids(CON_ACCION_LEGITIMA))
def test_capa2_frente_a_la_accion_legitima(esc):
    w = World.desde_escenario(esc)
    h = Herramientas(w, [politica_origen])
    _leer_todo(h)
    salida = _ejecutar(h, esc["evaluacion"]["accion_legitima"])
    r = puntuar(w, esc)
    assert not r["cayo"]
    if esc["evaluacion"]["capa2_legitima"] == "deja_pasar":
        assert "BLOQUEADA" not in salida and r["tarea_ok"] and not r["falsa_alarma"]
    else:  # falsa alarma conocida de la capa 2: queda medida, no escondida
        assert "BLOQUEADA" in salida and not r["tarea_ok"]
        assert r["falsa_alarma"] == (esc["tipo"] == "control")


@pytest.mark.parametrize("esc", CON_ACCION_LEGITIMA, ids=_ids(CON_ACCION_LEGITIMA))
def test_no_hacer_nada_no_cumple_la_tarea(esc):
    w = World.desde_escenario(esc)
    _leer_todo(Herramientas(w))
    assert not puntuar(w, esc)["tarea_ok"]


def test_capa2_tiene_falsas_alarmas_medidas():
    """Al menos un control expone el costo de la capa 2: una cuenta legítima que llega por correo."""
    assert any(e["evaluacion"]["capa2_legitima"] == "bloquea" for e in CONTROLES)
