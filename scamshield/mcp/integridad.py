"""Integridad del escudo (#102): que nadie de adentro pueda apagar o debilitar Grifter en silencio.

El riesgo: quien controla la máquina (o un agente con una herramienta de archivos) edita `grifter.yaml`, inscribe la
cuenta del estafador o apaga la capa 2, y los pagos pasan sin aviso. Esto no lo impide, pero hace que **no pase sin
que el dueño se entere**:

- **Huella de la política.** Se calcula el hash de lo que decide qué se retiene (cuentas inscritas, datos del dueño,
  encargo, herramientas sensibles, capas encendidas y servidores de abajo) y se compara con la última que el dueño
  aprobó. Si cambió, Grifter retiene todo lo sensible y le manda al dueño el diff, hasta que aprueba o rechaza.
- **Primer arranque.** Sin una política aprobada todavía, la de ese arranque queda registrada como la inicial y el
  latido lo dice. Es la única vez que Grifter confía sin preguntar.
- **El diff no filtra secretos.** De los datos del dueño y de las credenciales de los servidores solo se dice qué
  cambió, nunca el valor.

El estado aprobado vive en un archivo aparte (`estado:` en `grifter.yaml`, por defecto `.grifter_aprobada.json` junto
al archivo). Si hay una clave (`GRIFTER_CLAVE_ESTADO`, que solo ve el proceso del proxy) el archivo va firmado con
HMAC: reescribirlo a mano sin la clave se nota. **Límite honesto:** quien tenga la máquina, la clave y el teléfono del
dueño puede todo. Lo que se logra es que no pase sin que el dueño se entere.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

log = logging.getLogger("grifter")

NOMBRE_ESTADO = ".grifter_aprobada.json"
ENTORNO_CLAVE = "GRIFTER_CLAVE_ESTADO"


def _h(valor: Any) -> str:
    """Un resumen corto de un valor secreto: sirve para notar que cambió, no para leerlo."""
    return hashlib.sha256(str(valor).encode("utf-8")).hexdigest()[:12]


def _cwd(config: Any, servidor: Any) -> str:
    """La carpeta del servidor, relativa a la del yaml: mover la carpeta entera no cambia la política."""
    if not servidor.cwd:
        return ""
    if config.ruta is not None:
        try:
            return Path(servidor.cwd).relative_to(Path(config.ruta).parent).as_posix()
        except ValueError:
            pass
    return Path(servidor.cwd).as_posix()


def politica_canonica(config: Any) -> dict[str, Any]:
    """Lo que decide qué retiene Grifter, en una forma estable y sin secretos en claro."""
    return {
        "cuentas_inscritas": {str(k): str(v) for k, v in sorted(config.cuentas_inscritas.items())},
        "datos_dueno": {str(k): _h(v) for k, v in sorted(config.datos_dueno.items())},
        "encargo": str(config.encargo or ""),
        "sensibles": {str(k): {"destino": r.destino, "que": r.que} for k, r in sorted(config.sensibles.items())},
        "capas": {str(k): bool(v) for k, v in sorted(config.capas.items())},
        "aprobadores": [{"nombre": a.nombre, "canal": a.canal} for a in config.aprobadores],
        "quorum": int(config.quorum),
        "umbral_doble": int(config.umbral_doble),
        "servidores": {s.nombre: {"comando": s.comando, "args": list(s.args), "cwd": _cwd(config, s),
                                  "env": {str(k): _h(v) for k, v in sorted(s.env.items())}}
                       for s in sorted(config.servidores, key=lambda s: s.nombre)},
        # #103: el mandato y las herramientas fijadas también son política. Solo si están, para que la huella
        # de una política sin ellos no cambie.
        **({"mandato": {str(k): v for k, v in sorted(getattr(config, "mandato", {}).items())}}
           if getattr(config, "mandato", None) else {}),
        **({"herramientas_fijadas": {str(k): str(v) for k, v in sorted(config.herramientas_fijadas.items())}}
           if getattr(config, "herramientas_fijadas", None) else {}),
    }


def huella(politica: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(politica, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def corta(h: str) -> str:
    return h[:12]


def diferencias(antes: Mapping[str, Any], despues: Mapping[str, Any]) -> list[str]:
    """El diff de dos políticas, en líneas que el dueño pueda leer en el celular. Sin valores secretos."""
    d: list[str] = []
    a, b = antes.get("cuentas_inscritas", {}), despues.get("cuentas_inscritas", {})
    for k in sorted(set(a) | set(b)):
        if k not in a:
            d.append(f"+ cuenta inscrita {k}: {b[k]}")
        elif k not in b:
            d.append(f"- cuenta inscrita {k}: {a[k]}")
        elif a[k] != b[k]:
            d.append(f"~ cuenta inscrita {k}: {a[k]} → {b[k]}")
    a, b = antes.get("datos_dueno", {}), despues.get("datos_dueno", {})
    for k in sorted(set(a) | set(b)):
        if k not in a:
            d.append(f"+ dato del dueño {k}")
        elif k not in b:
            d.append(f"- dato del dueño {k}")
        elif a[k] != b[k]:
            d.append(f"~ dato del dueño {k} cambió")
    if antes.get("encargo") != despues.get("encargo"):
        d.append("~ el encargo del dueño cambió")
    a, b = antes.get("sensibles", {}), despues.get("sensibles", {})
    for k in sorted(set(a) | set(b)):
        if k not in a:
            d.append(f"+ ahora se revisa {k}")
        elif k not in b:
            d.append(f"- YA NO SE REVISA {k}")
        elif a[k] != b[k]:
            d.append(f"~ cambió cómo se revisa {k}")
    a, b = antes.get("capas", {}), despues.get("capas", {})
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            estado = lambda v: "sin dato" if v is None else ("encendida" if v else "APAGADA")  # noqa: E731
            d.append(f"~ {k}: {estado(a.get(k))} → {estado(b.get(k))}")
    na = {x["nombre"]: x.get("canal", "") for x in antes.get("aprobadores", [])}
    nb = {x["nombre"]: x.get("canal", "") for x in despues.get("aprobadores", [])}
    for k in sorted(set(na) | set(nb)):
        if k not in na:
            d.append(f"+ aprobador nuevo {k}")
        elif k not in nb:
            d.append(f"- aprobador quitado {k}")
        elif na[k] != nb[k]:
            d.append(f"~ aprobador {k}: cambió su canal")
    if antes.get("quorum") != despues.get("quorum"):
        d.append(f"~ quórum: {antes.get('quorum')} → {despues.get('quorum')}")
    if antes.get("umbral_doble") != despues.get("umbral_doble"):
        d.append(f"~ umbral de doble autorización: {antes.get('umbral_doble')} → {despues.get('umbral_doble')}")
    a, b = antes.get("servidores", {}), despues.get("servidores", {})
    for k in sorted(set(a) | set(b)):
        if k not in a:
            d.append(f"+ servidor nuevo {k}: {b[k]['comando']} {' '.join(b[k]['args'])}".rstrip())
        elif k not in b:
            d.append(f"- servidor quitado {k}")
        elif a[k] != b[k]:
            que = [n for n in ("comando", "args", "cwd") if a[k][n] != b[k][n]]
            if a[k]["env"] != b[k]["env"]:
                que.append("credenciales")
            d.append(f"~ servidor {k}: cambió " + ", ".join(que))
    return d


@dataclass
class Cambio:
    """Lo que cambió respecto de la última política aprobada."""

    huella_anterior: str
    huella_nueva: str
    lineas: list[str] = field(default_factory=list)
    ilegible: str = ""   # si grifter.yaml no se pudo leer, por qué

    @property
    def texto(self) -> str:
        if self.ilegible:
            return f"grifter.yaml no se pudo leer ({self.ilegible})."
        return "\n".join(self.lineas) or "(la política cambió, sin diferencias que mostrar)"


@dataclass
class Estado:
    """La última política aprobada por el dueño."""

    huella: str
    politica: dict[str, Any]
    aprobada_en: str
    por: str


class IntegridadError(RuntimeError):
    pass


class Integridad:
    """Compara `grifter.yaml` con la última política aprobada y guarda las aprobaciones."""

    def __init__(self, ruta_config: Path, ruta_estado: Optional[Path] = None, cargar: Optional[Callable[[Path], Any]] = None,
                 clave: Optional[str] = None, reloj: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        if cargar is None:
            from .proxy import cargar_config as cargar
        self.ruta_config = Path(ruta_config)
        self.ruta_estado = Path(ruta_estado) if ruta_estado else self.ruta_config.parent / NOMBRE_ESTADO
        self._cargar, self._reloj = cargar, reloj
        self._clave = clave.encode("utf-8") if clave else None

    # --- Lo que dice el archivo hoy -----------------------------------------------------------------
    def leer_actual(self) -> tuple[Optional[Any], Optional[dict[str, Any]], str]:
        """(config, política, error): el archivo tal como está ahora. Si no se puede leer, falla cerrada."""
        try:
            config = self._cargar(self.ruta_config)
            return config, politica_canonica(config), ""
        except Exception as e:   # ilegible, borrado o con una forma rara: no se confía
            return None, None, type(e).__name__

    # --- Lo que aprobó el dueño ---------------------------------------------------------------------
    def _firma(self, cuerpo: Mapping[str, Any]) -> str:
        datos = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hmac.new(self._clave, datos, hashlib.sha256).hexdigest() if self._clave else ""

    def estado(self) -> Optional[Estado]:
        """La política aprobada, o None si todavía no hay (primer arranque). Un archivo roto o con firma mala
        lanza `IntegridadError`: no se confía en él."""
        if not self.ruta_estado.exists():
            return None
        try:
            crudo = json.loads(self.ruta_estado.read_text(encoding="utf-8"))
            cuerpo = {k: crudo[k] for k in ("huella", "politica", "aprobada_en", "por")}
        except (OSError, ValueError, KeyError) as e:
            raise IntegridadError(f"el registro de la política aprobada está dañado ({type(e).__name__})") from None
        if self._clave and not hmac.compare_digest(str(crudo.get("firma", "")), self._firma(cuerpo)):
            raise IntegridadError("la firma de la política aprobada no calza: alguien la tocó sin la clave")
        if huella(cuerpo["politica"]) != cuerpo["huella"]:
            raise IntegridadError("la huella guardada no calza con la política guardada")
        return Estado(**cuerpo)

    def aprobar(self, politica: dict[str, Any], por: str) -> Estado:
        cuerpo = {"huella": huella(politica), "politica": politica,
                  "aprobada_en": self._reloj().isoformat(timespec="seconds"), "por": por}
        self.ruta_estado.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta_estado.with_suffix(".tmp")
        temporal.write_text(json.dumps({**cuerpo, "firma": self._firma(cuerpo)}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        temporal.replace(self.ruta_estado)
        return Estado(**cuerpo)

    # --- La comparación -----------------------------------------------------------------------------
    def cambio(self) -> Optional[Cambio]:
        """None si la política de hoy es la aprobada; si no, qué cambió. Sin política aprobada no hay cambio:
        `arrancar` la registra como inicial. Un registro dañado o un archivo ilegible cuentan como cambio."""
        try:
            aprobada = self.estado()
        except IntegridadError as e:
            return Cambio("", "", ilegible=str(e))
        _, actual, error = self.leer_actual()
        if actual is None:
            return Cambio(aprobada.huella if aprobada else "", "", ilegible=error)
        if aprobada is None:
            return None
        nueva = huella(actual)
        if nueva == aprobada.huella:
            return None
        return Cambio(aprobada.huella, nueva, diferencias(aprobada.politica, actual))

    def arrancar(self) -> str:
        """Al arrancar: «inicial» si no había política aprobada (la deja registrada), «igual» o «cambio»."""
        try:
            aprobada = self.estado()
        except IntegridadError:
            return "cambio"
        if aprobada is None:
            _, actual, error = self.leer_actual()
            if actual is None:
                return "cambio"
            self.aprobar(actual, "primer arranque")
            return "inicial"
        return "cambio" if self.cambio() else "igual"
