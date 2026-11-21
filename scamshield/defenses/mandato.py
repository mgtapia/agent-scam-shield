"""El mandato del dueño: lo que aprobó, fijado, contra lo que de verdad se cobra (#103).

La capa 2 por origen protege a quién se le paga, no cuánto ni qué. Un servidor MCP de checkout puede
recibir el «sí» del dueño y después cobrar otra cosa: un cero de más, otro producto, ítems agregados al
carrito, otra moneda o un cobro mensual en vez de uno solo. Al aprobar, Grifter fija un *mandato* con el
producto, la cantidad, el monto máximo, la moneda, el beneficiario y si el cobro es único o recurrente.
Al ejecutar, compara los argumentos del pago, y la orden que devuelve el MCP, contra ese mandato.
Cualquier desvío se retiene y se le explica al dueño:

    aprobaste $412.000 CLP por 10.000 chip MX-3; el MCP pide $4.120.000

Sigue la idea de los *intent mandates* y *cart mandates* de AP2 (Agent Payments Protocol) y de Visa Trusted
Agent Protocol: lo que vale es lo que firmó el dueño, no lo que dice el comercio.

Aparte, la **fijación de herramientas** (como el *tool pinning* de mcp-scan): se guarda la huella (SHA-256)
de la descripción y del esquema de cada herramienta MCP aprobada. Si cambian (un *rug pull*: la herramienta
agrega un campo `cuenta_destino` con un valor por defecto, o reescribe su descripción), queda bloqueada hasta
que el dueño la revise.

Reglas:
- El mandato es opcional: sin mandato no se revisa nada y todo sigue igual que antes.
- Lo que el pago no dice no es un desvío (un `pagar` sin producto no se compara por producto), salvo el
  monto: un monto que no se entiende se retiene, y ante la duda se lee el mayor.
- El monto puede ser menor o igual al máximo; el resto de los campos tiene que ser igual.
- Cualquier cargo extra (seguro, propina, despacho express, comisión de plataforma) es un desvío.

Es pura: no conoce Inspect, el mundo simulado ni MCP.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ..env.world import origenes_en
from .layer2 import visible

PREFIJO = "Fuera del mandato del dueño"

# Nombres con que los servidores llaman a cada campo. Se buscan sin mayúsculas.
CLAVES_MONTO = ("monto", "amount", "total", "importe", "valor", "precio_total", "total_amount")
CLAVES_MONEDA = ("moneda", "currency", "divisa")
CLAVES_PRODUCTO = ("producto", "product", "sku", "articulo", "item")
CLAVES_CANTIDAD = ("cantidad", "quantity", "qty", "unidades")
CLAVES_RECURRENCIA = ("recurrencia", "recurrente", "recurring", "frecuencia", "frequency", "interval",
                      "intervalo", "billing", "modalidad")
CLAVES_CUENTA = ("cuenta", "cuenta_destino", "numero_cuenta", "account", "account_number", "iban")
CLAVES_EXTRAS = ("cargos_extra", "extras", "cargos", "add_ons", "addons", "items_extra", "fees")
CLAVES_LINEAS = ("items", "lineas", "line_items", "carrito", "cart")

UNICA = "unica"
_UNICA = {"", "unica", "unico", "una", "una vez", "pago unico", "cobro unico", "once", "one time", "onetime",
          "single", "none", "no", "false", "0"}
# La periodicidad en los dos idiomas, para que «monthly» y «mensual» sean lo mismo.
_PERIODOS = {"monthly": "mensual", "mensualmente": "mensual", "cada mes": "mensual", "month": "mensual",
             "yearly": "anual", "annual": "anual", "annually": "anual", "anualmente": "anual", "year": "anual",
             "weekly": "semanal", "week": "semanal", "recurring": "recurrente", "true": "recurrente",
             "si": "recurrente", "yes": "recurrente"}
_MONEDAS = {"clp": "CLP", "pesos": "CLP", "peso": "CLP", "pesos chilenos": "CLP", "clp$": "CLP",
            "usd": "USD", "us$": "USD", "dolares": "USD", "dolar": "USD", "dollars": "USD", "dollar": "USD",
            "eur": "EUR", "euros": "EUR", "euro": "EUR"}


@dataclass(frozen=True)
class Mandato:
    """Lo que el dueño aprobó. Todo campo vacío (o None) queda sin revisar, salvo el monto máximo."""

    monto_maximo: int
    moneda: str = "CLP"
    producto: str = ""
    cantidad: Optional[int] = None
    beneficiario: str = ""      # la cuenta a la que se aprobó pagar
    recurrencia: str = UNICA    # «unica» o la periodicidad aprobada («mensual», «anual»)

    @staticmethod
    def desde(datos: Any) -> Optional["Mandato"]:
        """Un mandato desde un diccionario (YAML o JSON), o None si no hay mandato."""
        if datos is None or isinstance(datos, Mandato):
            return datos
        if not datos:
            return None
        maximo = monto_de(datos.get("monto_maximo"))
        if maximo is None:
            raise ValueError("el mandato necesita un monto_maximo")
        cantidad = datos.get("cantidad")
        return Mandato(
            monto_maximo=maximo,
            moneda=_moneda(datos.get("moneda") or "CLP"),
            producto=str(datos.get("producto") or ""),
            cantidad=None if cantidad in (None, "") else monto_de(cantidad),
            beneficiario=str(datos.get("beneficiario") or ""),
            recurrencia=_recurrencia(datos.get("recurrencia")),
        )

    def resumen(self) -> str:
        """«$412.000 CLP por 10.000 chip MX-3»: lo que aprobó el dueño, en una línea."""
        texto = f"{pesos(self.monto_maximo)} {self.moneda}"
        if self.producto:
            cantidad = f"{_miles(self.cantidad)} " if self.cantidad is not None else ""
            texto += f" por {cantidad}{self.producto}"
        if self.recurrencia != UNICA:
            texto += f", cobro {self.recurrencia}"
        return texto


# ---------------------------------------------------------------------------------------------
# Comparar un pago o una orden con el mandato
# ---------------------------------------------------------------------------------------------

def desvios(mandato: Any, args: Mapping[str, Any], quien: str = "el pago") -> list[str]:
    """Cada diferencia entre lo que se pide y lo aprobado, ya redactada («el pago pide $4.120.000»).

    `args` son los argumentos de una llamada de pago o los campos de una orden. Lista vacía: calza.
    """
    m = Mandato.desde(mandato)
    if m is None:
        return []
    campos = {_clave(k): v for k, v in args.items()}
    salida: list[str] = []

    hay_monto, crudo = _buscar(campos, CLAVES_MONTO)
    monto = monto_de(crudo) if hay_monto else None
    if not hay_monto or monto is None:
        salida.append(f"{quien} no dice cuánto cobra, o no se entiende ({visible(crudo, 24)})" if hay_monto
                      else f"{quien} no dice cuánto cobra")
    elif monto > m.monto_maximo:
        salida.append(f"{quien} pide {pesos(monto)}")

    hay, moneda = _buscar(campos, CLAVES_MONEDA)
    if hay and _moneda(moneda) != m.moneda:
        salida.append(f"en {visible(moneda, 12)} y no en {m.moneda}")

    lineas = _lineas(campos)
    hay, producto = _buscar(campos, CLAVES_PRODUCTO)
    if not hay and len(lineas) == 1:
        hay, producto = _buscar(lineas[0], CLAVES_PRODUCTO)
    if m.producto and hay and _norm(producto) != _norm(m.producto):
        salida.append(f"otro producto: {visible(producto, 40)}")

    hay, cantidad = _buscar(campos, CLAVES_CANTIDAD)
    if not hay and len(lineas) == 1:
        hay, cantidad = _buscar(lineas[0], CLAVES_CANTIDAD)
    if m.cantidad is not None and hay and monto_de(cantidad) != m.cantidad:
        salida.append(f"otra cantidad: {visible(cantidad, 16)}")

    hay, recurrencia = _buscar(campos, CLAVES_RECURRENCIA)
    if hay and _recurrencia(recurrencia) != m.recurrencia:
        r = _recurrencia(recurrencia)
        salida.append("como pago único" if r == UNICA else f"como cobro {visible(r, 20)}")

    hay, cuenta = _buscar(campos, CLAVES_CUENTA)
    if m.beneficiario and hay and not origenes_en([("mandato", m.beneficiario)], str(cuenta)):
        salida.append(f"a la cuenta {visible(cuenta, 32)} y no a la {visible(m.beneficiario, 32)}")

    extras = [e for k in CLAVES_EXTRAS if k in campos for e in _lista(campos[k])]
    # Una línea del carrito que no es el producto aprobado también es un cargo que nadie aprobó.
    if m.producto and len(lineas) > 1:
        extras += [_texto_linea(l) for l in lineas
                   if _norm(_buscar(l, CLAVES_PRODUCTO)[1]) != _norm(m.producto)]
    if extras:
        salida.append("con cargos que no aprobaste: " + ", ".join(visible(e, 40) for e in extras[:4]))
    return salida


def motivo(mandato: Any, args: Mapping[str, Any], quien: str = "el pago") -> Optional[str]:
    """None si el pago calza con el mandato; si no, el motivo para el dueño, con la diferencia."""
    m = Mandato.desde(mandato)
    lista = desvios(m, args, quien) if m is not None else []
    if not lista:
        return None
    return f"{PREFIJO}: aprobaste {m.resumen()}; " + "; ".join(lista) + "."


def es_motivo_de_mandato(texto: Optional[str]) -> bool:
    return bool(texto) and str(texto).startswith(PREFIJO)


def parece_orden(datos: Any) -> bool:
    """El resultado de una herramienta trae una orden: un monto y algo más que la describa."""
    if not isinstance(datos, Mapping):
        return False
    campos = {_clave(k) for k in datos}
    describe = CLAVES_MONEDA + CLAVES_PRODUCTO + CLAVES_CANTIDAD + CLAVES_RECURRENCIA + CLAVES_LINEAS
    return bool(campos & set(CLAVES_MONTO)) and bool(campos & set(describe))


# ---------------------------------------------------------------------------------------------
# Fijación de herramientas
# ---------------------------------------------------------------------------------------------

def huella(descripcion: Optional[str], esquema: Any) -> str:
    """SHA-256 de la descripción y el esquema de una herramienta, en una forma canónica."""
    canon = json.dumps({"descripcion": descripcion or "", "esquema": esquema or {}}, sort_keys=True,
                       ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def revisar_fijacion(fijadas: Mapping[str, str], nombre: str, descripcion: Optional[str],
                     esquema: Any) -> Optional[str]:
    """None si la herramienta es la que se aprobó; si no, por qué queda bloqueada.

    Sin fijaciones (`fijadas` vacío) no hay nada que comparar. Con fijaciones, una herramienta que no está
    en la lista tampoco se aprobó.
    """
    if not fijadas:
        return None
    if nombre not in fijadas:
        return (f"la herramienta {visible(nombre, 40)} no está entre las aprobadas: queda bloqueada hasta "
                "que la revises.")
    if huella(descripcion, esquema) != str(fijadas[nombre]).strip().lower():
        return (f"la herramienta {visible(nombre, 40)} cambió su descripción o su esquema desde que la "
                "aprobaste: queda bloqueada hasta que la revises.")
    return None


# ---------------------------------------------------------------------------------------------
# Lectura de los campos
# ---------------------------------------------------------------------------------------------

def monto_de(valor: Any) -> Optional[int]:
    """El monto como entero, o None si no se entiende.

    «4.120.000», «4,120,000», «$4.120.000» y «4120000.00» son cuatro millones ciento veinte mil: solo se
    descartan uno o dos decimales al final, y ante la duda se lee el monto mayor.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return abs(int(valor)) if valor == valor else None
    texto = re.sub(r"[.,]\d{1,2}$", "", str(valor).strip())
    digitos = re.sub(r"\D", "", texto)
    return int(digitos) if digitos else None


def pesos(monto: int) -> str:
    return "$" + _miles(monto)


def _miles(n: Optional[int]) -> str:
    return f"{n:,}".replace(",", ".") if n is not None else ""


def _clave(k: Any) -> str:
    return _sin_tildes(str(k)).strip().lower()


def _buscar(campos: Mapping[str, Any], claves: tuple[str, ...]) -> tuple[bool, Any]:
    for c in claves:
        if c in campos and campos[c] not in (None, ""):
            return True, campos[c]
    return False, None


def _lineas(campos: Mapping[str, Any]) -> list[dict[str, Any]]:
    for c in CLAVES_LINEAS:
        if isinstance(campos.get(c), list):
            return [{_clave(k): v for k, v in l.items()} if isinstance(l, Mapping) else {"producto": l}
                    for l in campos[c]]
    return []


def _texto_linea(linea: Mapping[str, Any]) -> str:
    _, producto = _buscar(linea, CLAVES_PRODUCTO)
    _, monto = _buscar(linea, CLAVES_MONTO + ("precio", "price"))
    return f"{producto or 'ítem'}" + (f" {monto}" if monto not in (None, "") else "")


def _lista(valor: Any) -> list[str]:
    if valor in (None, "", False):
        return []
    if isinstance(valor, (list, tuple)):
        return [_texto_linea(v) if isinstance(v, Mapping) else str(v) for v in valor if v not in (None, "")]
    if isinstance(valor, Mapping):
        return [_texto_linea(valor)]
    return [str(valor)]


def _moneda(valor: Any) -> str:
    texto = _sin_tildes(str(valor)).strip().lower()
    return _MONEDAS.get(texto, texto.upper())


def _recurrencia(valor: Any) -> str:
    if valor is True:
        return "recurrente"
    texto = re.sub(r"[_\-]+", " ", _sin_tildes(str(valor if valor is not None else ""))).strip().lower()
    return UNICA if texto in _UNICA else _PERIODOS.get(texto, texto)


def _norm(texto: Any) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", str(texto)).lower() if ch.isalnum())


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
