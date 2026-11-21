"""Estafas desde infraestructura legítima (#127): el correo sale de una cuenta oficial y pasa SPF, DKIM y DMARC.

Un filtro de correo que mira el dominio del remitente falla aquí. La tesis de Grifter es la contraria: no confía en quién
manda sino en de dónde salió el valor, así que la cuenta que trae el correo sigue siendo contenido no confiable.
Las marcas son ficticias (Nube Austral, Pagos Andes, FirmaSegura): los escenarios no pueden nombrar marcas reales.
"""
from __future__ import annotations

import dataclasses

import pytest

from scamshield.defenses.layer2 import politica_origen
from scamshield.defenses.layer3 import confirmacion_beneficiario
from scamshield.env.tools import Herramientas
from scamshield.env.world import CORREO, World
from scamshield.evals.puntaje import puntuar
from scamshield.scenarios import cargar
from scamshield.vivo.flujo import dominio_de
from tests.test_ataques_modelo_vivo import _motor, _veredicto

ESCENARIOS = {(e["id"], e["idioma"]): e for e in cargar()}
IDIOMAS = ["es", "en"]
ESTAFAS = ["infra_dkim_citacion", "infra_cobro_con_nota", "infra_docs_comentario", "infra_calendario_pago",
           "infra_firma_cambio_cuenta"]
CONTROLES_CON_PAGO = ["control_infra_cobro_inscrito", "control_infra_doc_proveedor"]
CONTROL_ALERTA = "control_infra_alerta_seguridad"   # la alerta real de la cuenta oficial: no hay nada que pagar
CONTROLES = [*CONTROLES_CON_PAGO, CONTROL_ALERTA]
PASS = {"spf": "pass", "dkim": "pass", "dmarc": "pass"}


def _mundo(id_, idioma, defensas=()):
    esc = ESCENARIOS[(id_, idioma)]
    w = World.desde_escenario(esc)
    return esc, w, Herramientas(w, list(defensas))


def _hacer(h, accion):
    return getattr(h, accion["herramienta"])(**accion["args"])


# --- Los escenarios son lo que dicen ser ---

@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("id_", ESTAFAS + CONTROLES)
def test_el_remitente_es_legitimo_y_pasa_spf_dkim_y_dmarc(id_, idioma):
    esc = ESCENARIOS[(id_, idioma)]
    [correo] = esc["correos"]
    assert correo["autenticacion"] == PASS
    assert dominio_de(correo["de"]).endswith(("nubeaustral.cl", "pagosandes.cl", "firmasegura.cl"))   # la infraestructura


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_agente_ve_el_resultado_de_la_autenticacion_junto_al_remitente(idioma):
    _, w, h = _mundo("infra_dkim_citacion", idioma)
    texto = h.leer_correos()
    assert "Autenticación: SPF pass, DKIM pass, DMARC pass" in texto
    assert w.correos[0].autenticacion == PASS


def test_un_correo_sin_autenticacion_se_lee_como_siempre():
    _, w, h = _mundo("boleta_cambio_cuenta", "es")
    assert "Autenticación" not in h.leer_correos() and w.correos[0].autenticacion == {}


def test_el_mundo_guarda_y_recupera_la_autenticacion():
    _, w, _ = _mundo("infra_cobro_con_nota", "es")
    assert World.desde_dict(w.a_dict()).correos[0].autenticacion == PASS


# --- La prueba clave: con remitente legítimo, la capa 2 retiene igual ---

@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("id_", ESTAFAS)
def test_sin_defensa_cae_y_con_la_capa_2_no_aunque_el_correo_venga_firmado(id_, idioma):
    esc, w, h = _mundo(id_, idioma)
    h.leer_correos()
    for url in w.paginas:
        h.abrir_web(url)
    _hacer(h, esc["evaluacion"]["accion_estafa"])
    assert puntuar(w, esc)["cayo"]

    esc, w, h = _mundo(id_, idioma, [politica_origen])
    h.leer_correos()
    for url in w.paginas:
        h.abrir_web(url)
    assert "BLOQUEADA" in _hacer(h, esc["evaluacion"]["accion_estafa"])
    assert not puntuar(w, esc)["cayo"]


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("id_", ESTAFAS)
@pytest.mark.parametrize("remitente", ["no-reply@accounts.nubeaustral.cl", "servicio@pagosandes.cl", "jeff@alercesur.cl",
                                       "cualquiera@dominio-chueco.example"])
def test_la_retencion_no_depende_del_remitente_ni_de_su_autenticacion(id_, idioma, remitente):
    """El mismo correo desde cualquier remitente, con o sin SPF/DKIM/DMARC: la capa 2 decide igual."""
    esc = ESCENARIOS[(id_, idioma)]
    accion = esc["evaluacion"]["accion_estafa"]
    decisiones = set()
    for auth in (PASS, {"spf": "fail", "dkim": "fail", "dmarc": "fail"}, {}):
        w = World.desde_escenario(esc)
        w.correos = [dataclasses.replace(w.correos[0], de=remitente, autenticacion=dict(auth))]
        Herramientas(w).leer_correos()
        decisiones.add(politica_origen(w, accion["herramienta"], accion["args"]) is not None)
    assert decisiones == {True}


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("id_", CONTROLES_CON_PAGO)
def test_el_control_con_remitente_legitimo_y_la_cuenta_inscrita_pasa(id_, idioma):
    esc, w, h = _mundo(id_, idioma, [politica_origen, confirmacion_beneficiario])
    h.leer_correos()
    salida = _hacer(h, esc["evaluacion"]["accion_legitima"])
    r = puntuar(w, esc)
    assert "BLOQUEADA" not in salida and r["tarea_ok"] and not r["falsa_alarma"]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_alerta_legitima_de_la_cuenta_oficial_no_hace_confiable_al_remitente(idioma):
    """El mismo remitente de la citación falsa: lo que dice la alerta de verdad no autoriza ningún pago ni sale el código."""
    esc, w, h = _mundo(CONTROL_ALERTA, idioma, [politica_origen])
    h.leer_correos()
    assert esc["correos"][0]["de"] == ESCENARIOS[("infra_dkim_citacion", idioma)]["correos"][0]["de"]
    assert "BLOQUEADA" in h.pagar("Tesorería Judicial", "28-5530-1149", 289000, "Multa")
    assert "clave del dueño" in h.compartir_dato("318204", "no-reply@accounts.nubeaustral.cl")


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_capa_3_frena_ademas_las_que_dirigen_la_factura_a_otra_cuenta(idioma):
    for id_ in ("infra_docs_comentario", "infra_firma_cambio_cuenta"):
        esc, w, h = _mundo(id_, idioma, [confirmacion_beneficiario])
        h.leer_correos()
        assert "BLOQUEADA" in _hacer(h, esc["evaluacion"]["accion_estafa"]), id_


# --- El modo en vivo: ni el clasificador ni la bóveda aprenden que «el dominio de la infraestructura es seguro» ---

@pytest.fixture(scope="module")
def motor():
    return _motor()


def _estafa(m, clave):
    return next(c for c in m.flujo.episodio(clave=clave, idioma="es") if c.etiqueta == "estafa" and c.accion)


@pytest.mark.parametrize("clave", ESTAFAS)
def test_el_clasificador_no_la_da_por_segura_aunque_el_remitente_sea_conocido(motor, clave):
    """Aunque el remitente y su dominio estén en la libreta (como tras ver controles legítimos), la cuenta nueva delata."""
    c = _estafa(motor, clave)
    libreta = motor.libreta
    antes = (set(libreta.direcciones), set(libreta.dominios))
    try:
        libreta.direcciones.add(c.de.lower())
        libreta.dominios.add(dominio_de(c.de))
        v = _veredicto(motor, c)
    finally:
        libreta.direcciones, libreta.dominios = antes[0], antes[1]
    assert v["decision"] != "seguro", (clave, v["senales"])   # «estafa» o «sospechoso»: nunca pasa como seguro
    assert "cuenta_nueva" in {s["nombre"] for s in v["senales"]} or any(s["nombre"].startswith("boveda") for s in v["senales"])


@pytest.mark.parametrize("clave", ESTAFAS)
def test_conocer_al_remitente_no_le_resta_sospecha_a_la_estafa(motor, clave):
    """Con el remitente en la libreta (un servicio legítimo), la confianza de estafa no baja respecto de un remitente nuevo.

    Sin la señal `servicio_legitimo_con_pago`, el remitente conocido le quitaba `primer_contacto` a la estafa.
    """
    c = _estafa(motor, clave)
    desconocido = dataclasses.replace(c, de="soporte@dominio-cualquiera.example")
    libreta = motor.libreta
    antes = (set(libreta.direcciones), set(libreta.dominios))
    try:
        libreta.direcciones.discard(desconocido.de.lower())
        libreta.dominios.discard("dominio-cualquiera.example")
        p_desconocido = _veredicto(motor, desconocido)["confianza"]
        libreta.direcciones.add(c.de.lower())
        libreta.dominios.add(dominio_de(c.de))
        conocido = _veredicto(motor, c)
    finally:
        libreta.direcciones, libreta.dominios = antes
    assert conocido["confianza"] >= p_desconocido - 0.02, (clave, conocido["confianza"], p_desconocido)


def test_la_senal_solo_se_activa_con_remitente_conocido_y_cuenta_nueva(motor):
    from scamshield.vivo.clasificador import rasgos
    c = _estafa(motor, "infra_firma_cambio_cuenta")
    libreta = motor.libreta
    antes = (set(libreta.direcciones), set(libreta.dominios))
    try:
        libreta.direcciones.discard(c.de.lower()), libreta.dominios.discard(dominio_de(c.de))
        assert rasgos(c, libreta, motor.umbral_monto).senales["servicio_legitimo_con_pago"] == 0.0
        libreta.direcciones.add(c.de.lower())
        assert rasgos(c, libreta, motor.umbral_monto).senales["servicio_legitimo_con_pago"] == 1.0
    finally:
        libreta.direcciones, libreta.dominios = antes
    legitimo = next(x for x in motor.flujo.episodio(clave="control_infra_cobro_inscrito", idioma="es"))
    assert rasgos(legitimo, libreta, motor.umbral_monto).senales["servicio_legitimo_con_pago"] == 0.0   # la cuenta es la inscrita


def test_los_controles_de_infraestructura_se_dejan_pasar_y_su_dominio_queda_como_legitimo(motor):
    for clave in CONTROLES:
        for c in motor.flujo.episodio(clave=clave, idioma="es"):
            assert c.etiqueta == "legitimo" and c.origen == CORREO
            assert _veredicto(motor, c)["decision"] == "seguro"
            assert motor.libreta.conocido(c.de)


def test_la_boveda_no_guarda_el_dominio_de_la_infraestructura_de_una_estafa_confirmada():
    """Si el dueño confirma una estafa que salió de un dominio conocido, entra la cuenta, no el dominio del proveedor."""
    motor = _motor()   # uno propio: confirmar cambia la bóveda
    c = _estafa(motor, "infra_cobro_con_nota")
    assert motor.libreta.dominio_conocido(dominio_de(c.de))
    motor.boveda.confirmar(c, 1.0)
    guardados = {(i["tipo"], i["valor"]) for i in motor.boveda.lista()}   # los nuevos y los que ya estaban
    assert ("dominio", dominio_de(c.de)) not in guardados
    assert any(tipo == "cuenta" for tipo, _ in guardados)
