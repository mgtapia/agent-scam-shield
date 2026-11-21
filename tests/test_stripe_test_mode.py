"""`examples/stripe_test_mode.py` con un cliente HTTP falso: sin red, sin llaves y sin llamar a Stripe."""
from __future__ import annotations

import base64
import importlib.util
import json
import urllib.parse
from pathlib import Path

import pytest

from grifter import escudo

RAIZ = Path(__file__).resolve().parents[1]
LLAVE = "sk_test_llave_de_las_pruebas"


def _cargar():
    spec = importlib.util.spec_from_file_location("stripe_test_mode", RAIZ / "examples" / "stripe_test_mode.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ej = _cargar()


class HttpFalso:
    """Registra cada llamada y responde como Stripe: un PaymentIntent por cada POST."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []
        self.intents: dict[str, dict] = {}

    def __call__(self, metodo, url, cuerpo, cabeceras):
        datos = {k: v[0] for k, v in urllib.parse.parse_qs((cuerpo or b"").decode()).items()}
        self.llamadas.append({"metodo": metodo, "url": url, "datos": datos, "cabeceras": cabeceras})
        ruta = url.removeprefix("https://api.stripe.com")
        metadata = {k[9:-1]: v for k, v in datos.items() if k.startswith("metadata[")}
        if ruta == "/v1/payment_intents":
            id_ = f"pi_{len(self.intents) + 1}"
            estado = "succeeded" if datos["confirm"] == "true" else "requires_confirmation"
            self.intents[id_] = {"id": id_, "status": estado, "metadata": metadata}
            return 200, dict(self.intents[id_])
        id_ = ruta.split("/")[3]
        if ruta.endswith("/confirm"):
            self.intents[id_]["status"] = "succeeded"
        else:
            self.intents[id_]["metadata"].update(metadata)
        return 200, dict(self.intents[id_])


def _agente(http, decide=None):
    pagos = ej.PagosStripe(ej.ClienteStripe(LLAVE, http), decide=decide)
    herramientas = escudo({"leer_correos": pagos.leer_correos, "pagar": pagos.pagar},
                          cuentas_inscritas=ej.CUENTAS, encargo=ej.ENCARGO, avisar=pagos.avisar)
    return pagos, herramientas


def setup_function(_):
    ej.PAGOS.clear()


def test_el_pago_legitimo_se_crea_y_se_confirma():
    http = HttpFalso()
    _, h = _agente(http)
    h["leer_correos"]()
    texto = h["pagar"](ej.INSCRITA, 412_000, "Silicio Austral")
    assert "succeeded" in texto
    assert len(http.llamadas) == 1
    llamada = http.llamadas[0]
    assert llamada["metodo"] == "POST" and llamada["url"] == "https://api.stripe.com/v1/payment_intents"
    d = llamada["datos"]
    assert d["confirm"] == "true"
    assert d["payment_method"] == "pm_card_visa"
    assert d["amount"] == "412000" and d["currency"] == "clp"
    assert d["metadata[cuenta_destino]"] == ej.INSCRITA
    assert d["metadata[beneficiario]"] == "Silicio Austral"
    assert http.intents["pi_1"]["status"] == "succeeded"
    assert ej.PAGOS == [{"cuenta": ej.INSCRITA, "monto": 412_000, "stripe": "pi_1"}]


def test_la_estafa_queda_sin_confirmar_y_con_la_metadata():
    http = HttpFalso()
    _, h = _agente(http)
    h["leer_correos"]()
    texto = h["pagar"](ej.ESTAFA, 412_000, "Silicio Austral")
    assert texto.startswith("Grifter retuvo el pago")
    assert len(http.llamadas) == 1   # solo la creación: nunca se confirmó
    d = http.llamadas[0]["datos"]
    assert d["confirm"] == "false"
    assert d["metadata[grifter]"] == "retenido"
    assert ej.ESTAFA in d["metadata[motivo]"] and "no confiable" in d["metadata[motivo]"]
    assert d["metadata[cuenta_destino]"] == ej.ESTAFA
    assert d["metadata[beneficiario]"] == "Silicio Austral"
    assert http.intents["pi_1"]["status"] == "requires_confirmation"
    assert ej.PAGOS == []
    assert not any(c["url"].endswith("/confirm") for c in http.llamadas)


def test_si_el_dueno_aprueba_se_confirma_el_mismo_pago_retenido():
    http = HttpFalso()
    _, h = _agente(http, decide=lambda alerta: True)
    h["leer_correos"]()
    texto = h["pagar"](ej.ESTAFA, 412_000, "Silicio Austral")
    assert "succeeded" in texto
    assert len(http.intents) == 1   # no se cobró dos veces: se confirmó el retenido
    assert http.intents["pi_1"]["status"] == "succeeded"
    assert http.intents["pi_1"]["metadata"]["grifter"] == "aprobado_por_dueno"
    assert http.llamadas[-1]["url"].endswith("/v1/payment_intents/pi_1/confirm")
    assert ej.PAGOS[0]["stripe"] == "pi_1"


def test_si_el_dueno_no_aprueba_queda_retenido():
    http = HttpFalso()
    _, h = _agente(http, decide=lambda alerta: False)
    h["leer_correos"]()
    h["pagar"](ej.ESTAFA, 412_000, "Silicio Austral")
    assert http.intents["pi_1"]["status"] == "requires_confirmation"
    assert ej.PAGOS == []


def test_reintentar_lo_retenido_no_crea_otro_payment_intent():
    http = HttpFalso()
    _, h = _agente(http)
    h["leer_correos"]()
    h["pagar"](ej.ESTAFA, 412_000, "Silicio Austral")
    h["pagar"](ej.ESTAFA, 412_000, "Silicio Austral")
    assert len(http.intents) == 1


@pytest.mark.parametrize("llave", ["sk_live_abc123", "rk_live_abc", "pk_test_abc", "", None, "  "])
def test_una_llave_que_no_es_de_prueba_se_rechaza_antes_de_llamar(llave):
    http = HttpFalso()
    with pytest.raises(ValueError) as e:
        ej.ClienteStripe(llave, http)
    assert "sk_live_abc123" not in str(e.value)   # nunca se imprime la llave
    assert http.llamadas == []


def test_main_con_una_llave_live_en_el_entorno_no_llama_a_nadie(monkeypatch):
    monkeypatch.setenv("STRIPE_TEST_KEY", "sk_live_abc123")
    monkeypatch.setattr(ej, "_cargar_env", lambda: None)
    http = HttpFalso()
    with pytest.raises(ValueError):
        ej.main(["--modelo-falso"], http=http)
    assert http.llamadas == []


def test_la_llave_va_en_la_autenticacion_basica_y_no_en_la_url():
    http = HttpFalso()
    ej.ClienteStripe(LLAVE, http).crear_pago("1", 1000, "x", confirmar=True)
    llamada = http.llamadas[0]
    assert base64.b64decode(llamada["cabeceras"]["Authorization"].split()[1]).decode() == f"{LLAVE}:"
    assert LLAVE not in llamada["url"]


def test_un_error_de_stripe_no_muestra_la_llave():
    def http(metodo, url, cuerpo, cabeceras):
        return 401, {"error": {"message": "Invalid API Key provided"}}

    with pytest.raises(ej.ErrorStripe) as e:
        ej.ClienteStripe(LLAVE, http).crear_pago("1", 1000, "x", confirmar=True)
    assert LLAVE not in str(e.value)


def test_mock_funciona_sin_llave_ni_red(monkeypatch, capsys):
    monkeypatch.delenv("STRIPE_TEST_KEY", raising=False)
    salida = ej.main(["--mock"])
    assert [p["cuenta"] for p in salida["pagos_cobrados"]] == [ej.INSCRITA]
    assert len(salida["retenidos"]) == 1
    retenido = next(i for i in salida["intentos"] if i["id"] == salida["retenidos"][0])
    assert retenido["metadata"]["grifter"] == "retenido"
    assert "Pagos cobrados" in capsys.readouterr().out


def test_mock_con_aprobacion_cobra_los_dos(monkeypatch):
    monkeypatch.delenv("STRIPE_TEST_KEY", raising=False)
    salida = ej.main(["--mock", "--aprobar"])
    assert [p["cuenta"] for p in salida["pagos_cobrados"]] == [ej.INSCRITA, ej.ESTAFA]
    assert salida["retenidos"] == []


def test_el_ejemplo_no_depende_del_paquete_stripe():
    codigo = (RAIZ / "examples" / "stripe_test_mode.py").read_text(encoding="utf-8")
    assert "import stripe" not in codigo and "from stripe" not in codigo
    assert "stripe" not in (RAIZ / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert json.dumps(ej.ESQUEMAS)   # los esquemas son serializables
