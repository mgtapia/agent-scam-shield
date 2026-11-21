"""Las señales de las estafas telefónicas en el léxico del clasificador (frases generales, en es y en)."""
from __future__ import annotations

import pytest

from scamshield.scenarios import cargar
from scamshield.vivo.lectura import LEXICO

CASOS = [
    ("pide_codigo", "Abra AnyDesk, yo me conecto de manera remota."),
    ("pide_codigo", "Open the program, I connect remotely and need access."),
    ("cambio_cuenta", "Transfiera a la cuenta de resguardo temporal que le abrimos."),
    ("cambio_cuenta", "Move the balance to the safe account we opened for you."),
    ("urgencia", "Tiene cinco minutos: la ventana de cinco minutos se cierra y el cargo queda firme."),
    ("urgencia", "Hágalo ahora, cada minuto cuenta."),
    ("urgencia", "If we do not clean it today we will have to cut your service."),
    ("autoridad", "Le habla la Unidad de Prevención de Fraudes del banco."),
    ("autoridad", "This is the Fraud Monitoring team."),
    ("secreto", "No se la dé a nadie más, es personal."),
    ("secreto", "No me llames de vuelta, avísame por mensaje."),
    ("secreto", "Do not call me back, I cannot talk."),
]


@pytest.mark.parametrize("senal,texto", CASOS)
def test_la_senal_se_activa_con_la_frase_de_la_llamada(senal, texto):
    assert LEXICO[senal].search(texto), (senal, texto)


@pytest.mark.parametrize("texto", [
    "Hola, te escribo por la factura de marzo. Gracias por avisar, nos vemos el jueves.",
    "Please find attached the invoice. We called the supplier yesterday and they confirmed.",
    "No llames al proveedor hoy, ya lo hice yo.",   # «no llames» sola es de la vida diaria, pero solo suma una señal
])
def test_los_textos_normales_no_activan_el_cambio_de_cuenta_ni_pedir_codigo(texto):
    assert not LEXICO["cambio_cuenta"].search(texto) and not LEXICO["pide_codigo"].search(texto)


def test_cada_estafa_telefonica_activa_senales_y_el_control_no_activa_las_nuevas():
    for esc in cargar():
        for llamada in esc.get("llamadas", []):
            activas = [k for k, p in LEXICO.items() if p.search(llamada["transcripcion"])]
            if esc["tipo"] == "estafa":
                # En español, dos o más; la versión en inglés de la voz clonada solo trae la reserva.
                assert len(activas) >= (2 if esc["idioma"] == "es" else 1), (esc["id"], esc["idioma"], activas)
            else:
                assert not {"urgencia", "pide_codigo", "autoridad", "secreto"} & set(activas), (esc["id"], activas)
