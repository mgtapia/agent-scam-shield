"""Ataques al modo en vivo (bóveda y clasificador), con el motor real y sin API.

Cada ataque es una prueba. En verde, lo que Grifter resiste (por diseño o por un arreglo de este PR).
Con `xfail(strict=True)`, lo que hoy todavía funciona: si algún día se arregla, la prueba falla y
obliga a sacar la marca. La razón del `xfail` dice por qué sigue abierto.

Modelo de amenaza: el atacante controla el contenido de lo que le llega al dueño (remitente
suplantado, texto, cuentas) y, sin querer, las etiquetas que el dueño le pone a correos inocuos.
No controla las cuentas inscritas ni el encargo del dueño. La capa 2 no se toca aquí: lo que se
prueba es que, aunque la bóveda o el clasificador fallen, el pago sigue retenido.
"""
from __future__ import annotations

import dataclasses

import pytest

from scamshield.defenses.layer2 import politica_origen
from scamshield.vivo.boveda import MAXIMO_INDICADORES, TOPE_POR_REMITENTE, plantilla
from scamshield.vivo.clasificador import Clasificador
from scamshield.vivo.flujo import Flujo
from scamshield.vivo.motor import Motor


def _motor() -> Motor:
    reloj = iter(range(1, 10 ** 9))
    m = Motor(semilla=11, reloj=lambda: float(next(reloj)), flujo=Flujo(semilla=11))
    m.precalentar()
    return m


@pytest.fixture(scope="module")
def lectura() -> Motor:
    """Un motor ya entrenado, solo para leer: las pruebas que lo usan no lo modifican."""
    return _motor()


@pytest.fixture
def motor() -> Motor:
    return _motor()


def _estafa(m: Motor, clave: str = "proveedor_factura_cambio"):
    return next(c for c in m.flujo.episodio(clave=clave, idioma="es") if c.accion and c.etiqueta == "estafa")


def _legitimo(m: Motor, clave: str = "control_proveedor_factura"):
    return next(c for c in m.flujo.episodio(clave=clave, idioma="es") if c.etiqueta == "legitimo")


def _legitimo_generico(m: Motor):
    """Un correo legítimo con una redacción genérica que ningún escenario usa.

    No depende de qué episodios pasaron por el precalentamiento del motor, que son al azar y cambian cada vez que
    cambia el corpus: si uno de ellos ya era este correo, su plantilla figuraba como legítima y el envenenamiento
    que estas pruebas describen no podía entrar. La precondición queda escrita.
    """
    c = dataclasses.replace(
        _legitimo(m), cuerpo="Buenas tardes, le adjunto la boleta del servicio contratado por $150.000. Quedo atento.")
    assert plantilla(c.cuerpo) not in m.boveda.vistos_legitimos["plantilla"]
    return c


def _veredicto(m: Motor, c) -> dict:
    return m._veredicto(c, m._rasgos(c), m.boveda.revisar(c))


def _con_dominio_nuevo(m: Motor, dominio: str = "distribuidora-andina.cl"):
    """Una estafa suplantando a un proveedor real que la libreta no conoce, y un correo suyo legítimo."""
    assert not m.libreta.dominio_conocido(dominio)
    base = _estafa(m)
    estafa = dataclasses.replace(base, de=f"facturas@{dominio}", etiqueta="estafa")
    legitimo = dataclasses.replace(
        base, de=f"cobranza@{dominio}", asunto="Factura 2210", etiqueta="legitimo", accion=None,
        cuerpo="Hola, adjunto la factura 2210 del mes. Saludos.")
    return estafa, legitimo


def _de_tipo(aciertos, tipo: str) -> list:
    return [i for i in aciertos if i.tipo == tipo]


# --- Bóveda: envenenarla para provocar falsas alarmas ---------------------------------------------

def test_un_dominio_suplantado_deja_de_atajar_cuando_el_dueno_confirma_un_correo_legitimo(motor):
    estafa, legitimo = _con_dominio_nuevo(motor)
    motor.boveda.confirmar(estafa, 1.0)
    assert _de_tipo(motor.boveda.revisar(legitimo), "dominio")        # el envenenamiento entra
    motor.boveda.vio_legitimo(legitimo)
    assert not _de_tipo(motor.boveda.revisar(legitimo), "dominio")    # y el dueño lo deshace con un toque


@pytest.mark.xfail(strict=True, reason=(
    "El primer correo legítimo tras el envenenamiento todavía sale marcado por la bóveda con confianza "
    "0,99: sin autenticar al remitente (SPF/DKIM) no se distingue el dominio suplantado del real. "
    "El arreglo de este PR lo deshace en cuanto el dueño confirma uno, no antes."))
def test_el_primer_correo_legitimo_tras_envenenar_el_dominio_no_se_marca(motor):
    estafa, legitimo = _con_dominio_nuevo(motor)
    motor.boveda.confirmar(estafa, 1.0)
    assert not _de_tipo(motor.boveda.revisar(legitimo), "dominio")


def test_una_plantilla_copiada_de_un_correo_legitimo_deja_de_atajar_cuando_el_dueno_lo_confirma(motor):
    legitimo = _legitimo_generico(motor)
    copia = dataclasses.replace(_estafa(motor), cuerpo=legitimo.cuerpo.replace("$", "$9"), etiqueta="estafa")
    motor.boveda.confirmar(copia, 1.0)
    assert _de_tipo(motor.boveda.revisar(legitimo), "plantilla")      # la colisión envenena
    motor.boveda.vio_legitimo(legitimo)
    assert not _de_tipo(motor.boveda.revisar(legitimo), "plantilla")
    # Y una estafa nueva que copie esa redacción ya no puede volver a envenenarla.
    motor.boveda.confirmar(copia, 2.0)
    assert not _de_tipo(motor.boveda.revisar(legitimo), "plantilla")


@pytest.mark.xfail(strict=True, reason=(
    "Igual que con el dominio: antes de que el dueño confirme un correo legítimo con esa redacción, la "
    "plantilla copiada ataja el legítimo. Una plantilla genérica («adjunto la factura...») no se puede "
    "distinguir de la del estafador sin otra señal."))
def test_una_plantilla_copiada_no_ataja_el_primer_correo_legitimo(motor):
    legitimo = _legitimo_generico(motor)
    copia = dataclasses.replace(_estafa(motor), cuerpo=legitimo.cuerpo.replace("$", "$9"), etiqueta="estafa")
    motor.boveda.confirmar(copia, 1.0)
    assert not _de_tipo(motor.boveda.revisar(legitimo), "plantilla")


def test_la_boveda_nunca_aprende_una_cuenta_inscrita_aunque_el_correo_sea_una_estafa(motor):
    inscrita = sorted(motor.boveda.cuentas_legitimas)[0]
    formato = f"{inscrita[:2]}-{inscrita[2:6]}-{inscrita[6:]}"
    estafa = dataclasses.replace(
        _estafa(motor), etiqueta="estafa", accion={"herramienta": "pagar", "args": {"cuenta": formato, "monto": 1}})
    motor.boveda.confirmar(estafa, 1.0)
    assert formato not in motor.boveda.cuentas()


def test_la_boveda_nunca_aprende_el_dominio_de_un_contacto_conocido(motor):
    conocido = sorted(motor.libreta.direcciones)[0]
    dominio = conocido.split("@")[1]
    estafa = dataclasses.replace(_estafa(motor), de=conocido, etiqueta="estafa")   # hilo secuestrado
    motor.boveda.confirmar(estafa, 1.0)
    assert ("dominio", dominio) not in motor.boveda.indicadores


def test_lavar_el_dominio_con_un_correo_inocuo_no_libera_la_cuenta(motor):
    """Un atacante que consigue que el dueño confirme un correo suyo como legítimo apaga la señal del
    dominio, pero no la cuenta: esa es suya y no la puede prestar."""
    estafa, legitimo = _con_dominio_nuevo(motor)
    cuenta = estafa.accion["args"]["cuenta"]
    motor.boveda.confirmar(estafa, 1.0)
    motor.boveda.vio_legitimo(legitimo)
    de_nuevo = dataclasses.replace(estafa, cuerpo=f"Ahora paga a {cuenta}, gracias.")
    assert _de_tipo(motor.boveda.revisar(de_nuevo), "cuenta")


# --- Bóveda: sacar un indicador malo (evasión) y llenarla --------------------------------------------

@pytest.mark.parametrize("escritura", [
    "48-9917-3302", "48 9917 3302", "4899173302", "48.9917.3302", "48–9917–3302", "48-9917-​3302",
    "４８－９９１７－３３０２",
])
def test_la_boveda_reconoce_la_cuenta_aunque_cambie_la_escritura(motor, escritura):
    base = _estafa(motor)
    cuenta = "48-9917-3302"
    motor.boveda.confirmar(dataclasses.replace(
        base, etiqueta="estafa", accion={"herramienta": "pagar", "args": {"cuenta": cuenta, "monto": 1}}), 1.0)
    otro = dataclasses.replace(base, de="x@otro.cl", cuerpo=f"Paga a {escritura} hoy.")
    assert _de_tipo(motor.boveda.revisar(otro), "cuenta")


def test_un_remitente_no_llena_la_boveda(motor):
    antes = len(motor.boveda)
    base = _estafa(motor)
    for i in range(200):
        cuenta = f"{i % 90 + 10:02d}-{i:04d}-{i:04d}"
        motor.boveda.confirmar(dataclasses.replace(
            base, de=f"a{i}@relleno.cl", cuerpo=f"texto {'x' * (i % 11)} {cuenta}", etiqueta="estafa",
            accion={"herramienta": "pagar", "args": {"cuenta": cuenta, "monto": 1}}), 10.0 + i)
    assert len(motor.boveda) - antes <= TOPE_POR_REMITENTE


def test_miles_de_remitentes_suplantados_no_hacen_crecer_la_boveda_sin_limite(motor):
    base = _estafa(motor)
    for i in range(MAXIMO_INDICADORES + 500):
        cuenta = f"{i % 90 + 10:02d}-{i % 10000:04d}-{i % 9973:04d}"
        motor.boveda.confirmar(dataclasses.replace(
            base, de=f"a{i}@dom{i}.cl", cuerpo=f"x{'a' * (i % 7)} {cuenta} {i}", etiqueta="estafa",
            accion={"herramienta": "pagar", "args": {"cuenta": cuenta, "monto": 1}}), 10.0 + i)
    assert len(motor.boveda) <= MAXIMO_INDICADORES


# --- Clasificador: evadirlo ---------------------------------------------------------------------------

def _neutro(m: Motor, cuenta: str):
    """Una estafa sin lenguaje de estafa, desde un remitente conocido (hilo secuestrado o suplantado)."""
    conocido = sorted(m.libreta.direcciones)[0]
    cuerpo = ("Hola, te escribo por la factura del mes. Para el pago usa estos datos de transferencia: "
              f"Banco Litoral cta vista {cuenta}. Gracias, quedo atento.")
    return dataclasses.replace(_estafa(m), de=conocido, asunto="Factura del mes", cuerpo=cuerpo)


@pytest.mark.parametrize("cuenta", ["48-9917-3302", "48 9917 3302", "4899173302", "４８－９９１７－３３０２"])
def test_cambiar_la_escritura_de_la_cuenta_no_hace_que_la_estafa_salga_segura(lectura, cuenta):
    assert _veredicto(lectura, _neutro(lectura, cuenta))["decision"] != "seguro"


@pytest.mark.xfail(strict=True, reason=(
    "Evasión abierta: una cuenta con una letra en vez de un dígito, escrita en palabras o partida en dos "
    "mensajes no la reconoce `cuenta_nueva`, y sin otras señales el clasificador la ve «segura». "
    "Lo que sí frena el pago es la capa 2 (siguiente prueba), no el veredicto."))
@pytest.mark.parametrize("cuenta", [
    "48-9917-33O2", "cuarenta y ocho, nueve nueve uno siete, tres tres cero dos", "48-9917 y en otro mensaje 3302",
])
def test_una_cuenta_disfrazada_no_hace_que_la_estafa_salga_segura(lectura, cuenta):
    assert _veredicto(lectura, _neutro(lectura, cuenta))["decision"] != "seguro"


@pytest.mark.parametrize("cuenta", [
    "48-9917-3302", "48 9917 3302", "４８－９９１７－３３０２", "48-9917-33O2",
    "cuarenta y ocho, nueve nueve uno siete, tres tres cero dos",
])
def test_aunque_el_clasificador_diga_seguro_la_capa_2_retiene_el_pago(lectura, cuenta):
    """La garantía real: lo que aprende el clasificador solo sube la sospecha, no libera ningún pago."""
    ev = _neutro(lectura, cuenta)
    motivo = politica_origen(ev.mundo(), ev.accion["herramienta"], ev.accion["args"])
    assert motivo                                  # la cuenta no sale del dueño, se escriba como se escriba
    accion = lectura._accion(ev, _veredicto(lectura, ev))
    assert accion["resultado"] == "retenida" and accion["capa"] == "2"


# --- Clasificador: envenenar lo que aprende -------------------------------------------------------------

def _envenenar(m: Motor, c, veces: int = 60) -> None:
    """Correos inocuos con el mismo lenguaje de la estafa, que el dueño etiqueta «legítimo»."""
    inocuo = m._rasgos(dataclasses.replace(c, etiqueta="legitimo"))
    for _ in range(veces):
        m.clasificador.aprender(inocuo, 0)


@pytest.mark.xfail(strict=True, reason=(
    "Envenenamiento dirigido abierto: 60 correos inocuos con la redacción exacta de una estafa, que el "
    "dueño etiqueta legítimos, bajan su probabilidad de 0,99 a 0,006. La guardia de deriva mira un "
    "conjunto apartado que no incluye esa familia, así que no lo ve. Falta proveniencia de etiquetas."))
def test_envenenar_con_correos_inocuos_no_baja_la_probabilidad_de_una_estafa(motor):
    c = _estafa(motor)
    _envenenar(motor, c)
    assert motor.clasificador.probabilidad(motor._rasgos(c)) >= Clasificador.UMBRAL


def test_aun_envenenado_el_clasificador_la_estafa_con_cuenta_nueva_no_sale_segura(motor):
    c = _estafa(motor)
    _envenenar(motor, c)
    v = _veredicto(motor, c)
    assert v["decision"] != "seguro"                      # `cuenta_nueva` es un piso duro, no aprendido
    accion = motor._accion(c, v)
    assert accion["resultado"] == "retenida"              # y la capa 2 retiene igual


def test_la_guardia_de_deriva_acota_el_envenenamiento_general(motor):
    """Con las estafas apartadas etiquetadas «legítimo», una versión que pierde demasiado se revierte."""
    cl = motor.clasificador
    positivos = [r for r, y in cl.apartado if y]
    assert positivos
    for i in range(120):
        cl.aprender(positivos[i % len(positivos)], 0)
        if cl.ejemplos % cl.cada == 0:
            assert cl.p_medio_estafas() >= cl.mejor_p_estafas - cl.DERIVA_MAX - 1e-9
    assert cl.revertidas >= 1


# --- Falsas alarmas: que un correo legítimo salga «estafa» -------------------------------------------------

def test_agregar_urgencia_a_un_correo_legitimo_conocido_no_lo_marca(lectura):
    legitimo = _legitimo(lectura)
    urgente = dataclasses.replace(legitimo, cuerpo=legitimo.cuerpo + " Es urgente, vence hoy.")
    assert _veredicto(lectura, legitimo)["decision"] == "seguro"
    assert _veredicto(lectura, urgente)["decision"] == "seguro"


def test_la_unica_falsa_alarma_de_los_controles_es_la_documentada(lectura):
    """Las falsas alarmas conocidas de los controles, cada una con su razón.

    - `control_gasfiter_cuenta_nueva`: un pago legítimo cuya cuenta llega solo por correo (ver scenarios/README).
    - `control_chat_codigo_del_banco`: el aviso legítimo del banco dice «vence en 5 minutos» y «nunca lo compartas», y
      esas palabras encienden `urgencia` y `secreto` por sí solas. Con el calentamiento actual (la semilla 11 termina en
      una versión con varias reversiones de la guardia de deriva) el clasificador todavía no aprendió a restarles peso. La capa 2 igual deja pasar el mensaje: es una alerta de más, no un bloqueo.
    """
    marcados = set()
    for u in lectura.flujo.unidades:
        if u.familia != "control":
            continue
        for c in lectura.flujo.episodio(clave=u.clave, idioma="es"):
            if c.etiqueta == "legitimo" and _veredicto(lectura, c)["decision"] != "seguro":
                marcados.add(u.clave)
    assert marcados == {"control_gasfiter_cuenta_nueva", "control_chat_codigo_del_banco"}
