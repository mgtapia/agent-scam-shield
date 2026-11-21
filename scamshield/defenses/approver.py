"""Capa 2 como approver de Inspect: un adaptador sobre la política pura `politica_origen`.

Reconstruye la procedencia desde el historial de mensajes, sin el mundo simulado de scamshield,
así que se enchufa a cualquier eval de Inspect (incluida AgentDojo):

- los mensajes de sistema y de usuario cuentan como del dueño (DUENO);
- los resultados de herramientas cuentan como no confiables (correo, web, MCP u otra herramienta);
- los mensajes del asistente no aportan procedencia: lo que el modelo escribe no vuelve confiable
  un valor.

Con eso llama a `politica_origen` con el nombre de la herramienta y sus argumentos. Si la política
bloquea, el bloqueo queda en `store()` bajo `CLAVE_BLOQUEOS` (para que el puntaje lo cuente) y el
approver rechaza de forma determinista. El modo demo cambia el rechazo por `escalate`, para que
decida el approver siguiente de la lista (una persona por consola o, más adelante, Telegram).

Uso en una eval cualquiera:

    from scamshield.defenses.approver import politicas_capa2
    eval(tarea, approval=politicas_capa2("agentdojo_banking"))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Optional, Sequence, Union

from inspect_ai.approval import Approval, ApprovalPolicy, Approver, approver
from inspect_ai.model import ChatMessage
from inspect_ai.tool import ToolCall, ToolCallView
from inspect_ai.util import store

from ..env.world import CORREO, DUENO, HERRAMIENTA, LLAMADA, MCP, WEB, origenes_en
from .layer2 import SENSIBLES_SCAMSHIELD, AccionSensible, politica_origen

# Clave del store donde queda cada bloqueo de la capa 2 (lista de dicts).
CLAVE_BLOQUEOS = "scamshield:bloqueos_capa2"
# Cuántas acciones sensibles intentó el agente en la muestra (aprobadas o no): la base de los «toques por 100».
CLAVE_INTENTOS = "scamshield:intentos_sensibles"

NOMBRE_APPROVER = "capa2"

# Herramientas sensibles de AgentDojo banking (inspect_evals/agentdojo/tools/banking_client.py).
# `update_scheduled_transaction` puede cambiar solo el monto o la fecha: sin `recipient` no hay
# destino nuevo que revisar. `update_password` y `update_user_info` no tienen destino y quedan fuera.
SENSIBLES_AGENTDOJO_BANKING: dict[str, AccionSensible] = {
    "send_money": AccionSensible(destino="recipient"),
    "schedule_transaction": AccionSensible(destino="recipient"),
    "update_scheduled_transaction": AccionSensible(destino="recipient", opcional=True),
}

SENSIBLES_POR_NOMBRE: dict[str, dict[str, AccionSensible]] = {
    "scamshield": SENSIBLES_SCAMSHIELD,
    "agentdojo_banking": SENSIBLES_AGENTDOJO_BANKING,
}

# Origen de los resultados de las herramientas de lectura conocidas; el resto cuenta como HERRAMIENTA.
ORIGEN_POR_HERRAMIENTA: dict[str, str] = {
    "leer_correos": CORREO,
    "escuchar_llamadas": LLAMADA,
    "abrir_web": WEB,
    "usar_mcp": MCP,
}

DatosDueno = Union[Mapping[str, str], Callable[[], Mapping[str, str]], None]
Modo = Literal["eval", "demo"]


@dataclass
class ProcedenciaHistorial:
    """Procedencia armada desde el historial: cumple la interfaz `Procedencia` de la capa 2."""

    leidos: list[tuple[str, str]] = field(default_factory=list)
    datos_dueno: Mapping[str, str] = field(default_factory=dict)
    # Lo que escribió el dueño (mensajes de usuario), sin el perfil del mensaje de sistema.
    encargo: str = ""

    def origenes_de(self, valor: str) -> set[str]:
        return origenes_en(self.leidos, valor)


def procedencia_desde_historial(
    history: Sequence[ChatMessage],
    datos_dueno: Optional[Mapping[str, str]] = None,
    origen_por_herramienta: Optional[Mapping[str, str]] = None,
) -> ProcedenciaHistorial:
    origenes = ORIGEN_POR_HERRAMIENTA if origen_por_herramienta is None else origen_por_herramienta
    leidos: list[tuple[str, str]] = []
    encargo: list[str] = []
    for m in history:
        if m.role in ("system", "user"):
            leidos.append((DUENO, m.text))
            if m.role == "user":
                encargo.append(m.text)
        elif m.role == "tool":
            leidos.append((origenes.get(m.function or "", HERRAMIENTA), m.text))
        # role == "assistant": no aporta procedencia.
    return ProcedenciaHistorial(leidos=leidos, datos_dueno=dict(datos_dueno or {}), encargo="\n".join(encargo))


def bloqueos_registrados() -> list[dict[str, Any]]:
    """Bloqueos de la capa 2 en la muestra actual (lee el store de Inspect)."""
    return list(store().get(CLAVE_BLOQUEOS, []))


def _resolver_sensibles(sensibles: Union[str, Mapping[str, AccionSensible]]) -> Mapping[str, AccionSensible]:
    if isinstance(sensibles, str):
        if sensibles not in SENSIBLES_POR_NOMBRE:
            raise ValueError(f"sensibles debe ser uno de {sorted(SENSIBLES_POR_NOMBRE)} o un dict")
        return SENSIBLES_POR_NOMBRE[sensibles]
    return sensibles


@approver(name=NOMBRE_APPROVER)
def capa2_approver(
    sensibles: Union[str, Mapping[str, AccionSensible]] = "scamshield",
    datos_dueno: DatosDueno = None,
    modo: Modo = "eval",
    registrar: bool = True,
) -> Approver:
    """Approver de Inspect que aplica la política por origen de la capa 2.

    Args:
        sensibles: mapeo herramienta sensible -> argumento de destino, o el nombre de uno de
            los predefinidos ("scamshield", "agentdojo_banking").
        datos_dueno: datos del dueño (RUT, código...) para `compartir_dato` y `responder`.
            Puede ser un dict o una función que lo entregue en cada llamada (por ejemplo,
            leyéndolo del store de la muestra). Sin ellos, esas dos reglas no se activan.
        modo: "eval" rechaza de forma determinista. "demo" escala al approver siguiente de la
            política (una persona o, más adelante, Telegram). Si no hay uno siguiente, Inspect
            lo termina rechazando.
        registrar: guarda cada bloqueo en `store()` bajo `CLAVE_BLOQUEOS`.
    """
    if modo not in ("eval", "demo"):
        raise ValueError('modo debe ser "eval" o "demo"')
    reglas = _resolver_sensibles(sensibles)

    async def aprobar(message: str, call: ToolCall, view: ToolCallView,
                      history: list[ChatMessage]) -> Approval:
        if call.function not in reglas:
            return Approval(decision="approve", explanation="Capa 2: herramienta no sensible.")
        store().set(CLAVE_INTENTOS, store().get(CLAVE_INTENTOS, 0) + 1)
        datos = datos_dueno() if callable(datos_dueno) else datos_dueno
        procedencia = procedencia_desde_historial(history, datos)
        motivo = politica_origen(procedencia, call.function, call.arguments, reglas)
        if motivo is None:
            return Approval(decision="approve", explanation="Capa 2: el destino viene del dueño.")

        decision: Literal["reject", "escalate"] = "reject" if modo == "eval" else "escalate"
        if registrar:
            bloqueos = store().get(CLAVE_BLOQUEOS, [])
            bloqueos.append({"herramienta": call.function, "args": dict(call.arguments),
                             "motivo": motivo, "decision": decision})
            store().set(CLAVE_BLOQUEOS, bloqueos)
        return Approval(
            decision=decision,
            explanation=f"ACCIÓN BLOQUEADA por la capa 2: {motivo} "
                        "Pide confirmación al dueño antes de continuar.",
            metadata={"capa": NOMBRE_APPROVER, "motivo": motivo},
        )

    return aprobar


def politicas_capa2(
    sensibles: Union[str, Mapping[str, AccionSensible]] = "scamshield",
    datos_dueno: DatosDueno = None,
    modo: Modo = "eval",
    escalar_a: Optional[Approver] = None,
) -> list[ApprovalPolicy]:
    """Políticas de aprobación listas para `Task(approval=...)` o `eval(approval=...)`.

    La capa 2 revisa todas las herramientas (`tools="*"`) y aprueba las que no son sensibles,
    porque Inspect rechaza cualquier llamada que ninguna política cubra.

    Punto de extensión del modo demo: `escalar_a` es el approver que decide lo que la capa 2
    escala (por ejemplo `human_approver()` de Inspect o un approver de Telegram).
    """
    politicas = [ApprovalPolicy(capa2_approver(sensibles, datos_dueno, modo), tools="*")]
    if modo == "demo" and escalar_a is not None:
        politicas.append(ApprovalPolicy(escalar_a, tools="*"))
    return politicas
