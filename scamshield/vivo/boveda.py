"""La bóveda de indicadores de compromiso: cuentas, dominios y plantillas de estafas confirmadas.

Funciona como un antivirus: cuando el dueño confirma una estafa (en la simulación, la etiqueta del
escenario hace de feedback), su cuenta, su dominio y su plantilla entran a la bóveda. Un correo
posterior que trae cualquiera de esos indicadores se marca al tiro, sin esperar al clasificador.

Para no atajar correos legítimos:
- nunca entra una cuenta inscrita del corpus ni la cuenta de un pago legítimo;
- nunca entra un dominio de la libreta de contactos conocidos (un proveedor real cuyo correo fue
  secuestrado sigue siendo un proveedor real: ahí manda la cuenta).
La cuenta se reconoce con `origenes_en`, la misma función de origen de la capa 2.

Contra el envenenamiento (un atacante que suplanta el remitente de un proveedor real, o copia la
redacción de un correo legítimo, para que la bóveda se acuerde de ese dominio o de esa plantilla):
- un dominio o una plantilla vistos en un correo que el dueño confirmó como legítimo dejan de
  atajar: son indicadores blandos y la cuenta, que el estafador no puede prestar, sigue mandando;
- cada remitente aporta como mucho `TOPE_POR_REMITENTE` indicadores nuevos, y la bóveda entera
  guarda como mucho `MAXIMO_INDICADORES` (se olvidan los más viejos), así que una avalancha de
  correos suplantados no la hace crecer sin límite.
Los dígitos y guiones de ancho completo se normalizan (NFKC) antes de buscar una cuenta.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from ..env.world import _aparece, _normalizar, _tokens
from .flujo import AGENTES, CUENTA, Correo, Libreta, dominio_de
from .lectura import dominios_en

_LETRAS = re.compile(r"[a-záéíóúñü]+")
TOPE_POR_REMITENTE = 20
MAXIMO_INDICADORES = 2000


def _nfkc(texto: str) -> str:
    """«４８－９９１７» y «48-9917» son lo mismo para un lector humano y para esta bóveda."""
    return unicodedata.normalize("NFKC", str(texto))


@dataclass
class Indicador:
    tipo: str        # cuenta, dominio o plantilla
    valor: str
    veces: int
    primera_vez: float
    origen: str      # id del correo que lo trajo

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)


def plantilla(cuerpo: str) -> str:
    """Huella del texto sin dígitos ni nombres: sigue igual cuando cambian el monto o la factura."""
    nombres = {n.lower() for n in AGENTES}
    palabras = [p for p in _LETRAS.findall(cuerpo.lower()) if p not in nombres]
    return "pl-" + hashlib.sha1(" ".join(palabras).encode("utf-8")).hexdigest()[:10]


class Boveda:
    def __init__(self, libreta: Libreta, cuentas_legitimas: Iterable[str]):
        self.libreta = libreta
        self.cuentas_legitimas = {_digitos(c) for c in cuentas_legitimas}
        self.indicadores: dict[tuple[str, str], Indicador] = {}
        # Dominios y plantillas que el dueño confirmó en correo legítimo: indicadores blandos.
        self.vistos_legitimos: dict[str, set[str]] = {"dominio": set(), "plantilla": set()}
        self._por_remitente: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self.indicadores)

    def lista(self) -> list[dict[str, Any]]:
        return [i.a_dict() for i in sorted(self.indicadores.values(), key=lambda i: i.primera_vez)]

    def cuentas(self) -> set[str]:
        return {i.valor for i in self.indicadores.values() if i.tipo == "cuenta"}

    def revisar(self, correo: Correo) -> list[Indicador]:
        """Los indicadores de la bóveda que trae el correo (verificación inmediata)."""
        aciertos = []
        # El correo se tokeniza una sola vez: con miles de cuentas guardadas, hacerlo por indicador
        # volvía lento al duelo (la regla de aparición es la de `origenes_en`, la de la capa 2).
        tokens = _tokens(_nfkc(correo.texto))
        dominios, huella = self._dominios(correo), plantilla(correo.cuerpo)
        for (tipo, valor), ind in self.indicadores.items():
            if tipo == "cuenta" and _aparece(_normalizar(valor), tokens):
                aciertos.append(ind)
            elif tipo == "dominio" and valor in dominios and valor not in self.vistos_legitimos["dominio"]:
                aciertos.append(ind)
            elif tipo == "plantilla" and valor == huella and valor not in self.vistos_legitimos["plantilla"]:
                aciertos.append(ind)
        return aciertos

    def vio_legitimo(self, correo: Correo) -> None:
        """El dueño confirmó que este correo es legítimo: su dominio y su plantilla dejan de atajar."""
        dominio = dominio_de(correo.de)
        if dominio:
            self.vistos_legitimos["dominio"].add(dominio)
        self.vistos_legitimos["plantilla"].add(plantilla(correo.cuerpo))

    def marcar(self, indicadores: Iterable[Indicador]) -> list[Indicador]:
        """Suma una detección a cada indicador que atajó un correo."""
        salida = []
        for ind in indicadores:
            ind.veces += 1
            salida.append(ind)
        return salida

    def confirmar(self, correo: Correo, ts: float) -> list[Indicador]:
        """El dueño confirmó que es estafa: sus indicadores entran (o suman una vez más)."""
        nuevos: list[tuple[str, str]] = []
        args = (correo.accion or {}).get("args", {})
        cuentas = set(CUENTA.findall(str(args.get("cuenta", ""))))
        for c in cuentas:
            if _digitos(c) not in self.cuentas_legitimas:
                nuevos.append(("cuenta", c))
        dominios = {dominio_de(correo.de)}
        if args.get("a"):
            dominios.add(dominio_de(str(args["a"])))
        for d in sorted(x for x in dominios if x):
            if not self.libreta.dominio_conocido(d):
                nuevos.append(("dominio", d))
        nuevos.append(("plantilla", plantilla(correo.cuerpo)))
        remitente = dominio_de(correo.de) or correo.de.lower()
        salida = []
        for clave in nuevos:
            if clave[0] in self.vistos_legitimos and clave[1] in self.vistos_legitimos[clave[0]]:
                continue
            ind = self.indicadores.get(clave)
            if ind is None:
                if self._por_remitente.get(remitente, 0) >= TOPE_POR_REMITENTE:
                    continue
                self._por_remitente[remitente] = self._por_remitente.get(remitente, 0) + 1
                ind = Indicador(clave[0], clave[1], 1, ts, correo.id)
                self.indicadores[clave] = ind
                salida.append(ind)
        while len(self.indicadores) > MAXIMO_INDICADORES:
            del self.indicadores[next(iter(self.indicadores))]   # el más viejo
        return salida

    @staticmethod
    def _dominios(correo: Correo) -> set[str]:
        ds = {d for _, _, d in dominios_en(correo)}
        ds.add(dominio_de(correo.de))
        ds.discard("")
        return ds


def _digitos(c: str) -> str:
    return re.sub(r"\D", "", str(c))
