"""El SDK de tres líneas: Grifter dentro de tu agente, sin proxy ni framework.

    from grifter import escudo
    herramientas = escudo(herramientas, cuentas_inscritas={"Silicio Austral": "Banco Litoral 33-7741-0092"},
                          encargo="Paga la factura de Silicio Austral", avisar=None)

`escudo` devuelve las mismas herramientas envueltas:

- Las que **leen contenido externo** (correo, web, MCP) anotan lo que devuelven como no confiable
  (origen `mcp`, igual que el proxy). Por defecto lo son todas las que no son sensibles; con
  `lectoras=[...]` solo las que nombres.
- Las **sensibles** (dinero o datos del dueño) pasan por la capa 2 y por la capa 3 antes de ejecutarse.
  Por defecto lo son `pagar`, `transferir`, `compartir_dato` y `responder` por nombre, y cualquier
  herramienta cuyos argumentos parezcan un pago (`cuenta`, `iban`, `monto` + `destinatario`...), igual
  que `regla_por_argumentos` del proxy. Con `sensibles={...}` se agregan o se cambian; una herramienta
  que nombres en `lectoras` nunca se detecta como sensible.
- Si una capa retiene, la función **no se ejecuta**: el modelo recibe un texto («Grifter retuvo el
  pago: ...») y, si se pasó `avisar(alerta)`, el dueño recibe la alerta. `avisar` devuelve True si el
  dueño aprueba; cualquier otra cosa, o que reviente, deja la llamada retenida (falla cerrada).

Reutiliza `Guardia` y `Grifter` de `scamshield.mcp.proxy`: la misma procedencia, la misma política y
el mismo tope de alertas contra el cansancio del dueño. Lo que escribe el agente en los argumentos
nunca vuelve confiable un valor.

Capa 3 (titular contra inscrita): solo actúa si pasas `titulares={cuenta: {"nombre": ..., "rut": ...}}`,
lo que sabe tu banco. Sin ese registro no hay contra qué confirmar y la capa no aplica.
"""
from __future__ import annotations

import functools
import inspect
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Union

from scamshield.defenses.layer2 import AccionSensible
from scamshield.defenses.layer3 import confirmacion_beneficiario
from scamshield.env.world import World
from scamshield.mcp.proxy import (
    ACCION_POR_DEFECTO,
    CLAVES_DESTINO,
    CLAVES_DINERO,
    SENSIBLES_POR_DEFECTO,
    Alerta,
    Config,
    Grifter,
    regla_por_argumentos,
)

log = logging.getLogger("grifter")

# Cómo se nombra al origen de lo leído en el aviso: «leer_correos de tu agente».
SERVIDOR = "tu agente"

Herramientas = Union[Iterable[Callable[..., Any]], Mapping[str, Callable[..., Any]]]
Avisar = Callable[[Alerta], Any]


def _a_regla(regla: Union[AccionSensible, str, Mapping[str, Any]]) -> AccionSensible:
    if isinstance(regla, AccionSensible):
        return regla
    if isinstance(regla, str):
        return AccionSensible(destino=regla, que="el destino")
    return AccionSensible(**dict(regla))


def _texto(resultado: Any) -> str:
    if isinstance(resultado, str):
        return resultado
    try:
        return json.dumps(resultado, ensure_ascii=False, default=str)
    except Exception:
        return str(resultado)


def _entero(valor: Any) -> int:
    """El monto en pesos. Si viene como texto, «1.500.000» y «1,500,000» son un millón y medio, no 1.

    Solo se descartan los decimales (uno o dos dígitos al final); ante la duda se lee el monto mayor,
    para que el tope del primer pago nunca vea menos de lo que se paga.
    """
    if valor is None or isinstance(valor, bool):
        return 0
    if isinstance(valor, (int, float)):
        return abs(int(valor))
    texto = re.sub(r"[.,]\d{1,2}$", "", str(valor).strip())
    digitos = re.sub(r"\D", "", texto)
    return int(digitos) if digitos else 0


class _Escudo:
    def __init__(self, *, cuentas_inscritas: Optional[Mapping[str, str]], encargo: str,
                 avisar: Optional[Avisar], datos_dueno: Optional[Mapping[str, str]],
                 titulares: Optional[Mapping[str, Mapping[str, str]]],
                 lectoras: Optional[Iterable[str]],
                 sensibles: Optional[Mapping[str, Union[AccionSensible, str, Mapping[str, Any]]]],
                 registro: Optional[Union[str, Path]]):
        declaradas = {**SENSIBLES_POR_DEFECTO}
        for nombre, regla in (sensibles or {}).items():
            declaradas[str(nombre)] = _a_regla(regla)
        self.config = Config(
            cuentas_inscritas={str(k): str(v) for k, v in (cuentas_inscritas or {}).items()},
            datos_dueno={str(k): str(v) for k, v in (datos_dueno or {}).items()},
            encargo=str(encargo or ""),
            sensibles=declaradas,
            acciones=dict(ACCION_POR_DEFECTO),
            registro=Path(registro) if registro else None,
        )
        self.declaradas = set(declaradas)
        self.lectoras = None if lectoras is None else {str(n) for n in lectoras}
        self.avisar = avisar
        self.grifter = Grifter(self.config)  # sin conectar: solo la guardia, el tope y el registro
        self.guardia = self.grifter.guardia
        self.mundo: Optional[World] = None
        if titulares:
            self.mundo = World(encargo=self.config.encargo, cuentas_inscritas=self.config.cuentas_inscritas,
                               titulares={str(k): dict(v) for k, v in titulares.items()})

    # --- clasificación ---------------------------------------------------------------------
    def _es_lectora(self, nombre: str) -> bool:
        if self.lectoras is not None:
            return nombre in self.lectoras
        return nombre not in self.config.sensibles

    def _clasificar(self, nombre: str, args: Mapping[str, Any]) -> bool:
        """True si la llamada es sensible. Una herramienta no declarada con argumentos de pago lo es."""
        if nombre not in self.declaradas and not (self.lectoras and nombre in self.lectoras):
            regla = regla_por_argumentos(args)
            if regla is not None:
                self.config.sensibles[nombre] = regla
                self.config.acciones[nombre] = "el pago"
            else:
                self.config.sensibles.pop(nombre, None)  # una detección anterior con otros argumentos
        return nombre in self.config.sensibles

    # --- revisión --------------------------------------------------------------------------
    def _revisar(self, nombre: str, args: Mapping[str, Any]) -> Optional[Alerta]:
        alerta = self.guardia.revisar(nombre, args, SERVIDOR)  # capa 2
        if alerta is not None:
            return alerta
        return self._capa3(nombre, args)

    def _capa3(self, nombre: str, args: Mapping[str, Any]) -> Optional[Alerta]:
        regla = self.config.sensibles[nombre]
        if self.mundo is None or regla.dato is not None or regla.mensaje is not None:
            return None  # sin registro de titulares, o no es un pago
        cuenta, destinatario, monto = self._datos_de_pago(regla, args)
        motivo = confirmacion_beneficiario(
            self.mundo, "pagar", {"cuenta": cuenta, "destinatario": destinatario, "monto": _entero(monto)})
        if motivo is None:
            return None
        accion = self.config.acciones.get(nombre, f"la llamada a {nombre}")
        mensaje = (f"Grifter retuvo {accion}: {motivo} Confírmala con el dueño por un canal conocido "
                   "antes de reintentar.")
        return Alerta(herramienta=nombre, servidor=SERVIDOR, args=dict(args), valor=str(cuenta),
                      motivo=motivo, mensaje=mensaje, fuentes=[])

    @staticmethod
    def _datos_de_pago(regla: AccionSensible, args: Mapping[str, Any]) -> tuple[Any, Any, Any]:
        cuenta = args.get(regla.destino, "")
        minusculas = {str(k).lower(): k for k in args}
        destinatario = next((args[minusculas[c]] for c in CLAVES_DESTINO
                             if c in minusculas and minusculas[c] != regla.destino), "")
        monto = next((args[minusculas[c]] for c in CLAVES_DINERO if c in minusculas), 0)
        return cuenta, destinatario, monto

    def _evaluar(self, nombre: str, args: Mapping[str, Any]) -> tuple[Optional[str], Optional[Alerta]]:
        """(texto de retención, None) si no se puede seguir; (None, alerta) si hay que preguntar;
        (None, None) si la llamada puede seguir. Falla cerrada si algo revienta."""
        try:
            alerta = self._revisar(nombre, args)
            if alerta is None:
                self._registrar("permitido", herramienta=nombre, servidor=SERVIDOR, args=dict(args))
                return None, None
            if self.grifter._inundado():
                self._registrar("retenido_sin_preguntar", alerta=alerta)
                return (alerta.mensaje + " Hay demasiadas alertas seguidas: Grifter retiene todo "
                        "sin preguntar por unos minutos."), None
            if self.avisar is None:
                self._registrar("retenido", alerta=alerta)
                return alerta.mensaje, None
            return None, alerta
        except Exception as e:
            log.exception("error al revisar %s", nombre)
            return self._falla(nombre, "revisarla", e), None

    def _falla(self, nombre: str, que: str, e: Exception) -> str:
        try:
            self._registrar("error_de_revision", herramienta=nombre, servidor=SERVIDOR, error=type(e).__name__)
        except Exception:
            pass
        return (f"Grifter retuvo la llamada a {nombre}: no pudo {que} ({type(e).__name__}). "
                "Por seguridad no se ejecuta.")

    def _veredicto(self, alerta: Alerta, aprobada: Any) -> Optional[str]:
        """None si el dueño aprobó; si no, el texto de retención. Solo True aprueba: «no», 1 o una lista
        no son el toque del dueño."""
        if aprobada is True:
            self._registrar("aprobado_por_dueno", alerta=alerta)
            return None
        self._registrar("retenido", alerta=alerta)
        return alerta.mensaje + " El dueño no la aprobó."

    def _preguntar(self, nombre: str, alerta: Alerta) -> Optional[str]:
        try:
            aprobada = self.avisar(alerta)
            if inspect.isawaitable(aprobada):
                if inspect.iscoroutine(aprobada):
                    aprobada.close()
                raise TypeError("avisar es async y la herramienta es síncrona")
            return self._veredicto(alerta, aprobada)
        except Exception as e:
            log.exception("error al avisar al dueño sobre %s", nombre)
            return self._falla(nombre, "avisar al dueño", e)

    async def _preguntar_async(self, nombre: str, alerta: Alerta) -> Optional[str]:
        try:
            aprobada = self.avisar(alerta)
            if inspect.isawaitable(aprobada):
                aprobada = await aprobada
            return self._veredicto(alerta, aprobada)
        except Exception as e:
            log.exception("error al avisar al dueño sobre %s", nombre)
            return self._falla(nombre, "avisar al dueño", e)

    def _registrar(self, evento: str, alerta: Optional[Alerta] = None, **datos: Any) -> None:
        self.grifter._registrar(evento, alerta=alerta, **datos)

    def _anotar(self, nombre: str, resultado: Any) -> None:
        if self._es_lectora(nombre):
            self.guardia.anotar_resultado(SERVIDOR, nombre, _texto(resultado))

    def _anotar_pago(self, nombre: str, args: Mapping[str, Any]) -> None:
        """Un pago que sí se ejecutó queda en el registro de la capa 3, que suma lo pagado a cada titular."""
        regla = self.config.sensibles.get(nombre)
        if self.mundo is None or regla is None or regla.dato is not None or regla.mensaje is not None:
            return
        cuenta, _, monto = self._datos_de_pago(regla, args)
        self.mundo.registrar("pagar", {"cuenta": str(cuenta), "monto": _entero(monto)}, "ejecutada")

    # --- envoltura -------------------------------------------------------------------------
    def envolver(self, nombre: str, funcion: Callable[..., Any]) -> Callable[..., Any]:
        try:
            firma: Optional[inspect.Signature] = inspect.signature(funcion)
        except (TypeError, ValueError):
            firma = None

        def argumentos(a: tuple, kw: dict) -> dict[str, Any]:
            if firma is not None:
                try:
                    return dict(firma.bind(*a, **kw).arguments)
                except TypeError:
                    pass
            return dict(kw)

        if inspect.iscoroutinefunction(funcion):
            @functools.wraps(funcion)
            async def envuelta(*a: Any, **kw: Any) -> Any:
                args = argumentos(a, kw)
                retenido, alerta = self._decidir(nombre, args)
                if alerta is not None:
                    retenido = await self._preguntar_async(nombre, alerta)
                if retenido is not None:
                    return retenido
                resultado = await funcion(*a, **kw)
                self._anotar(nombre, resultado)
                self._anotar_pago(nombre, args)
                return resultado
        else:
            @functools.wraps(funcion)
            def envuelta(*a: Any, **kw: Any) -> Any:
                args = argumentos(a, kw)
                retenido, alerta = self._decidir(nombre, args)
                if alerta is not None:
                    retenido = self._preguntar(nombre, alerta)
                if retenido is not None:
                    return retenido
                resultado = funcion(*a, **kw)
                self._anotar(nombre, resultado)
                self._anotar_pago(nombre, args)
                return resultado

        envuelta.__grifter__ = True  # type: ignore[attr-defined]
        return envuelta

    def _decidir(self, nombre: str, args: Mapping[str, Any]) -> tuple[Optional[str], Optional[Alerta]]:
        try:
            sensible = self._clasificar(nombre, args)
        except Exception as e:
            return self._falla(nombre, "revisarla", e), None
        if not sensible:
            return None, None
        return self._evaluar(nombre, args)


def escudo(herramientas: Herramientas, cuentas_inscritas: Optional[Mapping[str, str]] = None,
           encargo: str = "", avisar: Optional[Avisar] = None, *,
           datos_dueno: Optional[Mapping[str, str]] = None,
           titulares: Optional[Mapping[str, Mapping[str, str]]] = None,
           lectoras: Optional[Iterable[str]] = None,
           sensibles: Optional[Mapping[str, Union[AccionSensible, str, Mapping[str, Any]]]] = None,
           registro: Optional[Union[str, Path]] = None) -> Union[list[Callable[..., Any]], dict[str, Callable[..., Any]]]:
    """Envuelve las herramientas de tu agente con Grifter. Devuelve una lista o un dict, como la recibió.

    Args:
        herramientas: lista de funciones (el nombre es `__name__`) o dict nombre -> función. Las
            funciones pueden ser síncronas o `async`.
        cuentas_inscritas: lo que el dueño inscribió, `{"Silicio Austral": "Banco Litoral 33-7741-0092"}`.
            Es lo único confiable además del encargo.
        encargo: el texto que escribió el dueño. Un valor que aparece ahí también es confiable.
        avisar: `avisar(alerta) -> bool`; recibe la `Alerta` de lo retenido y devuelve True si el dueño
            aprueba. Sin `avisar`, o si no devuelve True, la llamada queda retenida.
        datos_dueno: datos del dueño que no deben salir a extraños (RUT, clave, código...).
        titulares: lo que sabe el banco, `{cuenta: {"nombre": ..., "rut": ...}}`, para la capa 3.
        lectoras: nombres de las herramientas que leen contenido externo. Por defecto, todas las
            que no son sensibles.
        sensibles: herramientas de dinero o datos a agregar o cambiar, `{nombre: AccionSensible | "argumento"}`.
        registro: ruta de un JSONL con cada llamada sensible (permitida, retenida o aprobada).
    """
    interno = _Escudo(cuentas_inscritas=cuentas_inscritas, encargo=encargo, avisar=avisar,
                      datos_dueno=datos_dueno, titulares=titulares, lectoras=lectoras,
                      sensibles=sensibles, registro=registro)
    if isinstance(herramientas, Mapping):
        return {str(n): interno.envolver(str(n), f) for n, f in herramientas.items()}
    return [interno.envolver(f.__name__, f) for f in herramientas]


__all__ = ["Alerta", "AccionSensible", "escudo"]
