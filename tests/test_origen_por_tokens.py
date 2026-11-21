"""La capa 2 no se engaña con un pedazo de un valor confiable (bug encontrado en la vuelta de mejoras)."""
import pytest

from scamshield.env.world import origenes_en

LEIDOS = [
    ("confiable", "Luz del Valle: 00-4417-2208"),
    ("dueno", "Paga la boleta de $48.290"),
    ("correo", "Nueva cuenta: 77-0193-5520. Escríbenos a cobranza@luzdelvalle-pagos.cl"),
]


@pytest.mark.parametrize("valor, esperado", [
    ("17-2208", set()),              # pedazo de la cuenta inscrita: antes pasaba como confiable
    ("4417", set()),
    ("4829", set()),                 # pedazo del monto del encargo
    ("luzdelvalle-pagos.cl", set()), # pedazo de un correo
    ("00-4417-2208", {"confiable"}),
    ("0044172208", {"confiable"}),
    ("00 4417 2208", {"confiable"}),
    ("77-0193-5520", {"correo"}),
    ("cobranza@luzdelvalle-pagos.cl", {"correo"}),
    ("48.290", {"dueno"}),
])
def test_solo_cuenta_el_valor_completo(valor, esperado):
    assert origenes_en(LEIDOS, valor) == esperado
