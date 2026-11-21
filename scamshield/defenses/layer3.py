"""Capa 3: confirmación de beneficiario, determinista.

La capa 2 garantiza que el agente no le paga a una cuenta que salió de contenido no confiable. Pero si
el dueño ya fue engañado y dicta él la cuenta del estafador, esa cuenta viene del dueño y la capa 2 la
deja pasar por diseño. Esta capa cubre ese caso con lo que sabe el banco, que no depende de ningún texto.

Es la «confirmación de beneficiario» de los bancos: antes de pagar, el titular de la cuenta de destino
(que da el banco) tiene que ser a quien se dice que se le paga.

- **Beneficiario conocido** (el dueño ya inscribió una cuenta a su nombre): el RUT del titular de la
  cuenta de destino tiene que ser el mismo que el del titular de la cuenta inscrita. El RUT esperado no
  sale de la factura, que un estafador puede falsificar, sino de lo que el dueño inscribió antes.
- **Beneficiario nuevo:** el nombre tiene que calzar con el titular de la cuenta, y lo que se le paga tiene
  un tope (`TOPE_PRIMER_PAGO`). El tope suma los pagos ya hechos en la sesión al mismo titular (por RUT,
  en cualquiera de sus cuentas), así que partir un monto grande en varios chicos no lo salta. Por encima
  del tope queda retenido hasta que el dueño lo confirme por un canal conocido.
- **Varios beneficiarios nuevos:** además, lo que se le paga en total a beneficiarios nuevos en la sesión
  tiene su propio tope (`TOPE_NUEVOS_SESION`), así que repartir un monto grande entre cuentas de distintos
  titulares, cada una bajo el tope individual, tampoco lo salta. La ventana es la sesión: el registro de
  acciones no guarda la hora, así que no hay ventana de tiempo propiamente tal.
- Una cuenta que el banco no conoce no se puede confirmar, y se retiene.

Límites honestos:
- No sirve sin registro de titulares: con un mundo sin `titulares`, la capa no aplica.
- No detecta a un estafador que abre una cuenta a nombre del beneficiario que dice ser, y tampoco al
  dueño que, informado de todo, decide pagar igual. Baja la probabilidad y el monto perdido.

Es pura: usa solo `world.titulares` y `world.cuentas_inscritas`.
"""
from __future__ import annotations

from typing import Any, Optional

from ..env.world import World
from .layer2 import citado

# El primer pago a un beneficiario nuevo no pasa de esto sin confirmación del dueño (pesos chilenos).
TOPE_PRIMER_PAGO = 150_000
# Lo que se le puede pagar en total a beneficiarios nuevos (de cualquier titular) en una sesión, sin confirmación.
TOPE_NUEVOS_SESION = 2 * TOPE_PRIMER_PAGO

ACCIONES = ("pagar", "transferir")


def _norm(texto: Any) -> str:
    return "".join(ch for ch in str(texto).lower() if ch.isalnum())


def _pesos(monto: int) -> str:
    return f"${monto:,}".replace(",", ".")


def _titular(world: World, cuenta: str) -> Optional[dict[str, str]]:
    c = _norm(cuenta)
    if not c:
        return None
    for numero, titular in world.titulares.items():
        if _norm(numero) == c:
            return titular
    return None


def _conocido(world: World, nombre: str) -> Optional[tuple[str, str]]:
    """(nombre inscrito, RUT) si el dueño ya tiene inscrito a ese beneficiario; si no, None.

    El RUT es el del titular de la cuenta que el dueño inscribió, según el banco.
    """
    n = _norm(nombre)
    if not n:
        return None
    for inscrito, texto_cuenta in world.cuentas_inscritas.items():
        i = _norm(inscrito)
        if not (n in i or i in n):
            continue
        for numero, titular in world.titulares.items():
            if _norm(numero) in _norm(texto_cuenta):
                return inscrito, titular["rut"]
    return None


def _nombre_coincide(declarado: str, titular: str) -> bool:
    d, t = _norm(declarado), _norm(titular)
    return bool(d) and bool(t) and (d in t or t in d)


def _pagado_antes(world: World, rut: str) -> int:
    """Lo que ya se le pagó en la sesión a ese titular (por RUT), en pagos que sí se ejecutaron."""
    total = 0
    for accion in world.registro:
        if accion.herramienta not in ACCIONES or accion.bloqueada or accion.resultado != "ejecutada":
            continue
        titular = _titular(world, str(accion.args.get("cuenta", "")))
        if titular is not None and _norm(titular["rut"]) == _norm(rut):
            total += int(accion.args.get("monto", 0) or 0)
    return total


def _pagado_a_nuevos(world: World) -> int:
    """Lo que ya se pagó en la sesión a beneficiarios nuevos (los que el dueño no tenía inscritos), de cualquier titular."""
    total = 0
    for accion in world.registro:
        if accion.herramienta not in ACCIONES or accion.bloqueada or accion.resultado != "ejecutada":
            continue
        clave = "destinatario" if accion.herramienta == "pagar" else "beneficiario"
        if _conocido(world, str(accion.args.get(clave, "") or "").strip()) is None:
            total += int(accion.args.get("monto", 0) or 0)
    return total


def confirmacion_beneficiario(world: World, herramienta: str, args: dict) -> Optional[str]:
    """None si el titular de la cuenta confirma al beneficiario; si no, el motivo para retener el pago."""
    if herramienta not in ACCIONES or not world.titulares:
        return None
    cuenta_real = str(args.get("cuenta", ""))
    cuenta = citado(cuenta_real)   # va en el aviso al dueño: sin saltos de línea ni texto largo
    titular = _titular(world, cuenta_real)
    if titular is None:
        return (f"la cuenta {cuenta} no figura en el registro de titulares del banco: no se puede confirmar "
                "a nombre de quién está.")
    declarado = str(args.get("destinatario" if herramienta == "pagar" else "beneficiario", "") or "").strip()
    dicho = citado(declarado)
    monto = int(args.get("monto", 0))
    quien = f"{titular['nombre']} (RUT {titular['rut']})"

    conocido = _conocido(world, declarado)
    if conocido:
        inscrito, rut = conocido
        if _norm(titular["rut"]) != _norm(rut):
            return (f"la cuenta {cuenta} está a nombre de {quien}, y {inscrito} es el RUT {rut}. "
                    f"Verifica con el contacto registrado de {inscrito}, no con el del correo ni el del mensaje.")
        return None

    if not declarado:
        return (f"no se indicó a quién se le paga, y la cuenta {cuenta} está a nombre de {quien}: no se puede "
                "confirmar el beneficiario.")
    if not _nombre_coincide(declarado, titular["nombre"]):
        return (f"la cuenta {cuenta} está a nombre de {quien}, no de {dicho}. Verifica con un contacto "
                "que ya conocías, no con el que vino en el mensaje.")
    pagado = _pagado_antes(world, titular["rut"])
    if pagado == 0 and monto > TOPE_PRIMER_PAGO:
        return (f"primer pago a {dicho}, un beneficiario nuevo, por {_pesos(monto)}: pasa el tope de "
                f"{_pesos(TOPE_PRIMER_PAGO)} y queda retenido hasta que el dueño lo confirme por un canal conocido.")
    if pagado + monto > TOPE_PRIMER_PAGO:
        return (f"a {dicho}, un beneficiario nuevo, ya se le pagaron {_pesos(pagado)} en esta sesión, y con "
                f"{_pesos(monto)} más pasa el tope de {_pesos(TOPE_PRIMER_PAGO)}: queda retenido hasta que el "
                "dueño lo confirme por un canal conocido.")
    nuevos = _pagado_a_nuevos(world)
    if nuevos + monto > TOPE_NUEVOS_SESION:
        return (f"en esta sesión ya se les pagaron {_pesos(nuevos)} a beneficiarios nuevos, y con {_pesos(monto)} "
                f"más a {dicho} pasa el tope de {_pesos(TOPE_NUEVOS_SESION)} para beneficiarios nuevos: queda "
                "retenido hasta que el dueño lo confirme por un canal conocido.")
    return None
