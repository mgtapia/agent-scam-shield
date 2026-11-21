"""Doble autorización (#102): ninguna persona sola puede debilitar el escudo ni aprobar un pago grande.

Como en un banco para los montos grandes. Lo que necesita **quórum** (por defecto 2 personas distintas):

- un cambio de la política (cuenta inscrita nueva, apagar una capa, cambiar umbrales o la lista de aprobadores);
- un pago sobre `umbral_doble`, aunque la cuenta esté inscrita, y un pago que la capa 2 o 3 retuvo sobre ese umbral.

Reglas:
- **Quien inicia no aprueba** (maker-checker): si la solicitud trae un iniciador, su voto no cuenta.
- **Un solo «no» la rechaza**, y no pide código: rechazar siempre es seguro.
- **Vence** si no hay quórum en el plazo, y queda rechazada.
- **Cambiar la lista de aprobadores o el quórum** se aprueba con la lista *anterior*: nadie se agrega a sí mismo.
- **Cada voto a favor pide un segundo factor**: el código de un digipass de esa persona, de un solo uso y atado a la
  solicitud (id, monto, cuenta): sirve para esa solicitud y para ese voto, no para otra. Tres códigos malos bloquean a ese aprobador para esa operación.
- **Registro encadenado**: cada voto queda con quién, cuándo y por qué canal, con el hash del anterior; borrar o
  cambiar una línea rompe la cadena y se nota. El código nunca se guarda.

El código es un TOTP de RFC 6238 (HMAC-SHA1, 30 s, 6 dígitos) con la clave derivada de la semilla y del desafío de la
solicitud (estilo OCRA/PSD2: vinculación dinámica): un código sacado para otra operación no sirve para esta. Solo usa
`hmac` y `hashlib`. Las semillas viven fuera del repo (`GRIFTER_SEMILLAS`, ruta a un JSON `{nombre: base32}`).

Límite honesto: dos aprobadores con sus teléfonos y sus digipass, o un solo atacante que tenga ambos, puede todo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

PASO_S = 30
DIGITOS = 6
VENTANA = 1               # se acepta el paso anterior y el siguiente (relojes que no calzan)
MAX_FALLOS = 3
PLAZO_PAGO_S = 30 * 60
PLAZO_POLITICA_S = 24 * 3600
ENTORNO_SEMILLAS = "GRIFTER_SEMILLAS"

PENDIENTE, APROBADA, RECHAZADA, VENCIDA = "pendiente", "aprobada", "rechazada", "vencida"


# ---------------------------------------------------------------------------------------------
# TOTP (RFC 6238) y el digipass simulado
# ---------------------------------------------------------------------------------------------

def generar_semilla() -> str:
    """Una semilla nueva de 160 bits en base32, como la de un digipass."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _bytes(semilla: str) -> bytes:
    limpia = semilla.strip().replace(" ", "").upper()
    return base64.b32decode(limpia + "=" * (-len(limpia) % 8))


def hotp(clave: bytes, contador: int, digitos: int = DIGITOS, algoritmo: Any = hashlib.sha1) -> str:
    """HOTP de RFC 4226."""
    h = hmac.new(clave, struct.pack(">Q", contador), algoritmo).digest()
    corte = h[-1] & 0x0F
    numero = (struct.unpack(">I", h[corte:corte + 4])[0] & 0x7FFFFFFF) % (10 ** digitos)
    return str(numero).zfill(digitos)


def totp(clave: bytes, t: float, paso: int = PASO_S, digitos: int = DIGITOS, algoritmo: Any = hashlib.sha1) -> str:
    """TOTP de RFC 6238 sobre la clave tal cual (sin vincular a ninguna operación)."""
    return hotp(clave, int(t // paso), digitos, algoritmo)


def desafio(id_: str, monto: Any = "", cuenta: Any = "") -> str:
    """El texto al que se ata el código: la solicitud, el monto y la cuenta."""
    return f"{id_}|{monto}|{cuenta}"


def clave_vinculada(semilla: str, desafio_: str) -> bytes:
    """La clave del TOTP de una operación: derivada de la semilla y del desafío (vinculación dinámica)."""
    return hmac.new(_bytes(semilla), b"grifter-ocra|" + desafio_.encode("utf-8"), hashlib.sha256).digest()


def digipass(semilla: str, desafio_: str, t: Optional[float] = None) -> str:
    """El digipass simulado: el código que mostraría el dispositivo del aprobador para esta operación."""
    return totp(clave_vinculada(semilla, desafio_), time.time() if t is None else t)


def contador_valido(semilla: str, desafio_: str, codigo: str, t: float) -> Optional[int]:
    """El contador TOTP con el que calza el código (ventana de ±1 paso), o None. Comparación de tiempo constante."""
    clave = clave_vinculada(semilla, desafio_)
    base = int(t // PASO_S)
    for c in range(base - VENTANA, base + VENTANA + 1):
        if hmac.compare_digest(hotp(clave, c), str(codigo).strip()):
            return c
    return None


def cargar_semillas(ruta: Optional[str] = None, entorno: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Las semillas de los aprobadores: un JSON `{nombre: base32}` fuera del repo. Vacío si no hay ruta."""
    import os

    entorno = os.environ if entorno is None else entorno
    ruta = ruta or entorno.get(ENTORNO_SEMILLAS, "")
    if not ruta:
        return {}
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in datos.items()}


# ---------------------------------------------------------------------------------------------
# Registro encadenado con hash
# ---------------------------------------------------------------------------------------------

GENESIS = "0" * 64


class RegistroEncadenado:
    """JSONL donde cada línea lleva el hash de la anterior: quitar o cambiar una rompe la cadena."""

    def __init__(self, ruta: Optional[Path]):
        self.ruta = Path(ruta) if ruta else None

    def _lineas(self) -> list[dict[str, Any]]:
        if self.ruta is None or not self.ruta.exists():
            return []
        return [json.loads(l) for l in self.ruta.read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def _hash(previo: str, cuerpo: Mapping[str, Any]) -> str:
        return hashlib.sha256((previo + json.dumps(cuerpo, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()

    def agregar(self, cuerpo: Mapping[str, Any]) -> None:
        if self.ruta is None:
            return
        lineas = self._lineas()
        previo = lineas[-1]["hash"] if lineas else GENESIS
        cuerpo = dict(cuerpo)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**cuerpo, "previo": previo, "hash": self._hash(previo, cuerpo)}, ensure_ascii=False) + "\n")

    def verificar(self) -> Optional[int]:
        """None si la cadena está entera; si no, el número (desde 1) de la primera línea que no calza."""
        previo = GENESIS
        for n, linea in enumerate(self._lineas(), 1):
            cuerpo = {k: v for k, v in linea.items() if k not in ("previo", "hash")}
            if linea.get("previo") != previo or linea.get("hash") != self._hash(previo, cuerpo):
                return n
            previo = linea["hash"]
        return None

    def lineas(self) -> list[dict[str, Any]]:
        return self._lineas()


# ---------------------------------------------------------------------------------------------
# Aprobadores y solicitudes
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Aprobador:
    nombre: str
    canal: str = ""   # el chat de Telegram de esa persona


@dataclass
class Solicitud:
    id: str
    tipo: str                      # «politica» o «pago»
    detalle: str                   # lo que se aprueba, en una o dos líneas legibles
    desafio: str                   # lo que ata el código
    creada: float
    vence: float
    aprobadores: tuple[str, ...]   # quiénes pueden votar (la lista vigente cuando se abrió)
    quorum: int
    iniciador: Optional[str] = None
    votos: dict[str, bool] = field(default_factory=dict)
    fallos: dict[str, int] = field(default_factory=dict)
    estado: str = PENDIENTE

    @property
    def a_favor(self) -> int:
        return sum(1 for v in self.votos.values() if v)


@dataclass
class Resultado:
    """Lo que pasó con un voto: `ok` si se registró, y el mensaje para el aprobador."""

    ok: bool
    mensaje: str
    estado: str


class Aprobaciones:
    """Las solicitudes pendientes y la regla del quórum. No sabe de Telegram: recibe votos y dice el resultado."""

    def __init__(self, aprobadores: list[Aprobador], quorum: int = 2, semillas: Optional[Mapping[str, str]] = None,
                 registro: Optional[RegistroEncadenado] = None, reloj: Callable[[], float] = time.time,
                 max_fallos: int = MAX_FALLOS):
        nombres = [a.nombre for a in aprobadores]
        if len(set(nombres)) != len(nombres):
            raise ValueError("hay aprobadores repetidos")
        if quorum < 1 or quorum > len(aprobadores):
            raise ValueError("el quórum tiene que ser al menos 1 y no mayor que los aprobadores")
        self.aprobadores = {a.nombre: a for a in aprobadores}
        self.quorum, self.semillas = quorum, dict(semillas or {})
        self.registro, self.reloj, self.max_fallos = registro or RegistroEncadenado(None), reloj, max_fallos
        self.solicitudes: dict[str, Solicitud] = {}

    # --- Abrir y consultar ---------------------------------------------------------------------------
    def abrir(self, tipo: str, detalle: str, monto: Any = "", cuenta: Any = "", iniciador: Optional[str] = None,
              plazo_s: Optional[float] = None, canal: str = "") -> Solicitud:
        id_ = secrets.token_hex(4)
        ahora = self.reloj()
        plazo = plazo_s if plazo_s is not None else (PLAZO_POLITICA_S if tipo == "politica" else PLAZO_PAGO_S)
        s = Solicitud(id=id_, tipo=tipo, detalle=detalle, desafio=desafio(id_, monto, cuenta), creada=ahora,
                      vence=ahora + plazo, aprobadores=tuple(self.aprobadores), quorum=self.quorum, iniciador=iniciador)
        self.solicitudes[id_] = s
        self._anotar(s, "abierta", None, canal, f"{tipo}: {detalle}")
        return s

    def estado(self, id_: str) -> str:
        """El estado de la solicitud; si venció sin quórum, pasa a vencida (rechazada)."""
        s = self.solicitudes.get(id_)
        if s is None:
            return RECHAZADA
        if s.estado == PENDIENTE and self.reloj() >= s.vence:
            s.estado = VENCIDA
            self._anotar(s, "vencida", None, "", f"sin quórum ({s.a_favor} de {s.quorum})")
        return s.estado

    def progreso(self, id_: str) -> str:
        s = self.solicitudes[id_]
        return f"{s.a_favor} de {s.quorum} aprobaciones"

    # --- Votar -----------------------------------------------------------------------------------------
    def votar(self, id_: str, nombre: str, aprobar: bool, codigo: str = "", canal: str = "") -> Resultado:
        s = self.solicitudes.get(id_)
        if s is None:
            return Resultado(False, "Esa solicitud no existe.", RECHAZADA)
        if self.estado(id_) != PENDIENTE:
            return Resultado(False, f"La solicitud ya está {s.estado}.", s.estado)
        if nombre not in s.aprobadores:
            self._anotar(s, "voto_ignorado", nombre, canal, "no es aprobador")
            return Resultado(False, "No eres aprobador de esta solicitud.", s.estado)
        if nombre in s.votos:
            return Resultado(False, "Ya votaste esta solicitud.", s.estado)
        if not aprobar:   # un solo «no» la rechaza, sin código
            s.votos[nombre] = False
            s.estado = RECHAZADA
            self._anotar(s, "rechazo", nombre, canal, "")
            return Resultado(True, "Rechazaste la solicitud: queda rechazada.", s.estado)
        if nombre == s.iniciador:
            self._anotar(s, "voto_ignorado", nombre, canal, "quien inició no aprueba")
            return Resultado(False, "Tú iniciaste esto: lo tiene que aprobar otra persona.", s.estado)
        if s.fallos.get(nombre, 0) >= self.max_fallos:
            return Resultado(False, "Demasiados códigos malos: quedaste bloqueado para esta operación.", s.estado)
        semilla = self.semillas.get(nombre)
        contador = contador_valido(semilla, s.desafio, codigo, self.reloj()) if semilla else None
        if contador is None:
            s.fallos[nombre] = s.fallos.get(nombre, 0) + 1
            restantes = self.max_fallos - s.fallos[nombre]
            self._anotar(s, "codigo_malo", nombre, canal, f"intento {s.fallos[nombre]} de {self.max_fallos}")
            return Resultado(False, "Código incorrecto, vencido o ya usado."
                             + (f" Te quedan {restantes}." if restantes > 0 else " Quedaste bloqueado para esta operación."),
                             s.estado)
        s.votos[nombre] = True
        if s.a_favor >= s.quorum:
            s.estado = APROBADA
            self._anotar(s, "aprobacion", nombre, canal, f"quórum {s.a_favor} de {s.quorum}: aprobada")
            return Resultado(True, "Listo: se completó el quórum, queda aprobada.", s.estado)
        self._anotar(s, "aprobacion", nombre, canal, f"{s.a_favor} de {s.quorum}")
        return Resultado(True, f"Registrado: {s.a_favor} de {s.quorum} aprobaciones.", s.estado)

    def consumir(self, id_: str) -> bool:
        """Marca una solicitud aprobada como usada. Un pago aprobado sale una sola vez."""
        s = self.solicitudes.get(id_)
        if s is None or self.estado(id_) != APROBADA:
            return False
        del self.solicitudes[id_]
        return True

    def _anotar(self, s: Solicitud, evento: str, quien: Optional[str], canal: str, nota: str) -> None:
        self.registro.agregar({"ts": datetime.fromtimestamp(self.reloj(), timezone.utc).isoformat(timespec="seconds"),
                               "evento": evento, "solicitud": s.id, "tipo": s.tipo, "quien": quien, "canal": canal,
                               "nota": nota})


def aprobadores_de(politica: Mapping[str, Any]) -> tuple[list[Aprobador], int]:
    """Los aprobadores y el quórum de una política canónica (la aprobada, no la nueva)."""
    lista = [Aprobador(a["nombre"], a.get("canal", "")) for a in politica.get("aprobadores", [])]
    return lista, int(politica.get("quorum", 1) or 1)


class AprobadorQuorum:
    """El gancho `aprobador` del proxy cuando hay aprobadores: un cambio de política necesita el quórum.

    Los aprobadores son los de la política *aprobada* (no los del archivo nuevo): así cambiar la lista o el quórum
    se aprueba con la lista anterior, y nadie se agrega a sí mismo.
    """

    def __init__(self, quorum: Any):
        self.quorum, self._id = quorum, ""

    def pedir(self, cambio: Any) -> None:
        s = self.quorum.aprobaciones.abrir("politica", cambio.texto, "", cambio.huella_nueva[:12])
        self._id = s.id
        self.quorum.notificar(s)

    def estado(self) -> Optional[bool]:
        if not self._id:
            return None
        self.quorum.sondear()
        estado = self.quorum.aprobaciones.estado(self._id)
        if estado == APROBADA:
            return True
        return None if estado == PENDIENTE else False


def main(argv: Optional[list[str]] = None) -> int:
    """Digipass simulado para la demo: crea semillas y saca el código de una solicitud.

        python -m scamshield.mcp.aprobaciones semillas Sam Reed --salida ../fuera-del-repo/semillas.json
        python -m scamshield.mcp.aprobaciones codigo --nombre Sam --id 3fa91c07 --monto 8000000 --cuenta 90-1188-4417
    """
    import argparse
    import os

    p = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="orden", required=True)
    s1 = sub.add_parser("semillas", help="crea una semilla por aprobador y las guarda fuera del repo")
    s1.add_argument("nombres", nargs="+")
    s1.add_argument("--salida", type=Path, required=True)
    s2 = sub.add_parser("codigo", help="el código del digipass de una persona para una solicitud")
    s2.add_argument("--nombre", required=True)
    s2.add_argument("--id", required=True, dest="id_")
    s2.add_argument("--monto", default="")
    s2.add_argument("--cuenta", default="")
    s2.add_argument("--semillas", default=os.environ.get(ENTORNO_SEMILLAS, ""))
    a = p.parse_args(argv)
    if a.orden == "semillas":
        if a.salida.exists():
            print(f"{a.salida} ya existe: no se pisa.")
            return 2
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(json.dumps({n: generar_semilla() for n in a.nombres}, indent=1), encoding="utf-8")
        print(f"Semillas de {', '.join(a.nombres)} en {a.salida}. Que no entren al repo.")
        return 0
    semillas = cargar_semillas(a.semillas or None)
    if a.nombre not in semillas:
        print(f"No hay semilla para {a.nombre}.")
        return 2
    print(digipass(semillas[a.nombre], desafio(a.id_, a.monto, a.cuenta)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
