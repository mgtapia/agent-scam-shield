"""Capa 3: confirmación de beneficiario, determinista.

La capa 2 garantiza que el agente no le paga a una cuenta que salió de contenido no confiable. Pero si
el dueño ya fue engañado y dicta él la cuenta del estafador, esa cuenta viene del dueño y la capa 2 la
deja pasar por diseño. Esta capa cubre ese caso con lo que sabe el banco, que no depende de ningún texto.

Es la «confirmación de beneficiario» de los bancos: antes de pagar, el titular de la cuenta de destino
(que da el banco) tiene que ser a quien se dice que se le paga.

- **Beneficiario conocido** (el dueño ya inscribió una cuenta a su nombre): el RUT del titular de la
  cuenta de destino tiene que ser el mismo que el del titular de la cuenta inscrita. El RUT esperado no
  sale de la factura, que un estafador puede falsificar, sino de lo que el dueño inscribió antes.
- **Beneficiario nuevo:** el nombre tiene que calzar con el titular de la cuenta, y el primer pago tiene
  un tope (`TOPE_PRIMER_PAGO`). Por encima del tope queda retenido hasta que el dueño lo confirme por
  un canal conocido.
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

# El primer pago a un beneficiario nuevo no pasa de esto sin confirmación del dueño (pesos chilenos).
TOPE_PRIMER_PAGO = 150_000

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


def confirmacion_beneficiario(world: World, herramienta: str, args: dict) -> Optional[str]:
    """None si el titular de la cuenta confirma al beneficiario; si no, el motivo para retener el pago."""
    if herramienta not in ACCIONES or not world.titulares:
        return None
    cuenta = str(args.get("cuenta", ""))
    titular = _titular(world, cuenta)
    if titular is None:
        return (f"la cuenta {cuenta} no figura en el registro de titulares del banco: no se puede confirmar "
                "a nombre de quién está.")
    declarado = str(args.get("destinatario" if herramienta == "pagar" else "beneficiario", "") or "").strip()
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
        return (f"la cuenta {cuenta} está a nombre de {quien}, no de {declarado}. Verifica con un contacto "
                "que ya conocías, no con el que vino en el mensaje.")
    if monto > TOPE_PRIMER_PAGO:
        return (f"primer pago a {declarado}, un beneficiario nuevo, por {_pesos(monto)}: pasa el tope de "
                f"{_pesos(TOPE_PRIMER_PAGO)} y queda retenido hasta que el dueño lo confirme por un canal conocido.")
    return None
