"""Mapeo de los mecanismos de estafa a OWASP Top 10 for Agentic Applications y a MITRE ATLAS.

Cada escenario trae `anotaciones.fraud_mechanism`. Aquí cada mecanismo se asocia a una categoría de
OWASP y a una técnica de ATLAS. Los identificadores y los nombres salen de las listas oficiales, no se
inventaron. Donde no calzaba ninguna de verdad, o no se pudo verificar, la celda dice `por confirmar`.

Fuentes (consultadas el 2026-11-21):

- OWASP Top 10 for Agentic Applications for 2026 (OWASP GenAI Security Project, publicada el 9 de
  diciembre de 2025): https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
  Los diez identificadores y nombres se verificaron en el anuncio oficial
  (https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)
  y en la referencia de FINOS (https://air-governance-framework.finos.org/references/owasp-asi), que
  reproduce los títulos completos. El PDF oficial está detrás de un formulario y no se leyó: el
  calce de cada mecanismo con la descripción de la categoría es criterio nuestro y se marca
  «aproximado» cuando no es de primera mano.
- MITRE ATLAS, versión de datos 2026.10 (publicada el 2026-10-28, formato 6.1.0):
  https://atlas.mitre.org/techniques ; datos en
  https://github.com/mitre-atlas/atlas-data/releases/tag/v2026.10 (ATLAS-2026.10.yaml). Los
  identificadores y nombres de las técnicas usadas se leyeron de ese archivo.

Qué cubre ATLAS y qué no: ATLAS describe ataques a sistemas de IA. Aquí el blanco sí es un sistema de IA (el
agente que paga), pero el fraude en sí (una boleta falsa, un cambio de cuenta) no tiene una técnica propia. La
regla que se aplica a todos los mecanismos por igual es esta:

- el atacante se hace pasar por una persona, una empresa o un proveedor, o inventa una identidad creíble
  (jefe, proveedor, banco, tienda, arrendador): AML.T0073 Impersonation, calce aproximado;
- el atacante pide un código o credenciales por un mensaje electrónico (OTP, clave): AML.T0052 Phishing,
  calce aproximado;
- el atacante deja instrucciones en lo que el agente lee (página, correo): AML.T0051.001, calce exacto;
- el atacante envenena la descripción de una herramienta MCP: AML.T0011.002, calce exacto;
- el dueño ya fue engañado y dicta la cuenta: `por confirmar` (el engaño está en la persona, no en el agente).

La técnica «Financial Harm» (AML.T0048.000) describe el daño, no el cómo, y serviría para todos por igual,
así que no se usa.

Los nombres de OWASP no coinciden del todo entre las dos fuentes oficiales: el anuncio dice «Tool Misuse»,
«Identity & Privilege Abuse» y «Unexpected Code Execution», y la referencia de FINOS dice «Tool Misuse and
Exploitation», «Identity and Privilege Abuse» y «Unexpected Code Execution (RCE)». Se usan los títulos
completos de FINOS. Los de las categorías que el mapeo cita (ASI01 y ASI04) son iguales en las dos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

POR_CONFIRMAR = "por confirmar"
NO_APLICA = "n/a"

FUENTE_OWASP = {
    "nombre": "OWASP Top 10 for Agentic Applications for 2026",
    "url": "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/",
    "publicada": "2025-12-09",
}
FUENTE_ATLAS = {
    "nombre": "MITRE ATLAS",
    "url": "https://atlas.mitre.org/techniques",
    "datos": "https://github.com/mitre-atlas/atlas-data/releases/tag/v2026.10",
    "version": "2026.10",
    "publicada": "2026-10-28",
}

# Los diez, tal como se publican. Se usan para validar que el mapeo no cite un identificador que no existe.
OWASP_AGENTICO = {
    "ASI01": "Agent Goal Hijack",
    "ASI02": "Tool Misuse and Exploitation",
    "ASI03": "Identity and Privilege Abuse",
    "ASI04": "Agentic Supply Chain Vulnerabilities",
    "ASI05": "Unexpected Code Execution (RCE)",
    "ASI06": "Memory & Context Poisoning",
    "ASI07": "Insecure Inter-Agent Communication",
    "ASI08": "Cascading Failures",
    "ASI09": "Human-Agent Trust Exploitation",
    "ASI10": "Rogue Agents",
}

# Solo las técnicas que el mapeo usa, con el nombre exacto de ATLAS 2026.10.
ATLAS_TECNICAS = {
    "AML.T0011.002": "User Execution: Poisoned AI Agent Tool",
    "AML.T0051.001": "LLM Prompt Injection: Indirect",
    "AML.T0052": "Phishing",
    "AML.T0073": "Impersonation",
}

EXACTO = "exacto"
APROXIMADO = "aproximado"


@dataclass(frozen=True)
class Entrada:
    owasp: str
    atlas: str
    owasp_calce: str = EXACTO
    atlas_calce: str = EXACTO
    nota: str = ""


_ASI01_APROX = ("Un contenido no confiable (correo, web) cambia lo que decide el agente, sin instrucciones "
                "explícitas para él: ASI01 describe el efecto y no la forma, y la alternativa es ASI02. ")

# Para las categorías de OWASP, la inyección y el MCP envenenado calzan de forma exacta; el resto es ingeniería
# social que llega por un canal no confiable y cambia la decisión del agente, y calza de forma aproximada con ASI01.
MAPEO: dict[str, Entrada] = {
    "indirect_prompt_injection": Entrada("ASI01", "AML.T0051.001",
                                         nota="Una página o un correo trae instrucciones para el agente."),
    # ASI04 cita de forma explícita los componentes MCP envenenados en tiempo de ejecución.
    "tool_poisoning": Entrada("ASI04", "AML.T0011.002",
                              nota="La descripción de una herramienta MCP trae las instrucciones."),
    # Suplantación: AML.T0073 incluye autoridades, colegas, proveedores de servicios y personas inventadas.
    "ceo_fraud": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO, _ASI01_APROX + "Se hace pasar por el jefe."),
    "business_email_compromise": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                         _ASI01_APROX + "Se hace pasar por el proveedor."),
    "payee_account_change": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                    _ASI01_APROX + "Un supuesto aviso del proveedor cambia la cuenta."),
    "fake_invoice": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                            _ASI01_APROX + "Un cobro de un proveedor inventado."),
    "safe_account": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                            _ASI01_APROX + "Se hace pasar por el banco o por soporte."),
    "fake_fine": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                         _ASI01_APROX + "Se hace pasar por una autoridad."),
    "delivery_fee": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                            _ASI01_APROX + "Se hace pasar por una empresa de envíos."),
    "fake_shop": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                         _ASI01_APROX + "Una tienda inventada."),
    "rental_advance_fee": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                  _ASI01_APROX + "Un arrendador inventado."),
    "investment_fraud": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                _ASI01_APROX + "Un asesor de inversión inventado."),
    "family_impersonation": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                    _ASI01_APROX + "Se hace pasar por un familiar."),
    # Estafas que evolucionaron con IA (issue #86). Misma regla que el resto: el atacante inventa una identidad
    # creíble y llega por un canal no confiable. Lo que cambia es la táctica (video falso, sitio generado, otro
    # agente), no el mecanismo que mide el mapeo.
    "deepfake_endorsement": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                    _ASI01_APROX + "Un video falso de una autoridad respalda una plataforma de inversión."),
    "advance_fee_loan": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                _ASI01_APROX + "Una financiera inventada cobra una comisión antes de prestar."),
    "regulator_impersonation": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                       _ASI01_APROX + "Se hace pasar por el regulador del mercado."),
    "fake_support_site": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                 _ASI01_APROX + "Un sitio generado con IA se hace pasar por el soporte del banco."),
    "qr_payment_redirect": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                   _ASI01_APROX + "Un QR o un enlace de la factura lleva a otra cuenta."),
    # ASI07 (Insecure Inter-Agent Communication) es la alternativa para el agente vendedor, pero el mapeo aplica
    # una sola regla a todas las suplantaciones, y aquí el atacante también se hace pasar por el proveedor.
    "agent_to_agent_fraud": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                                    _ASI01_APROX + "Un agente vendedor cambia la cuenta a mitad de la negociación; "
                                    "la alternativa es ASI07."),
    "task_scam": Entrada("ASI01", "AML.T0073", APROXIMADO, APROXIMADO,
                         _ASI01_APROX + "Una oferta de trabajo por tareas cobra por «desbloquear» comisiones."),
    # Pedir un código o credenciales por un mensaje: phishing.
    "otp_phishing": Entrada("ASI01", "AML.T0052", APROXIMADO, APROXIMADO,
                            _ASI01_APROX + "Busca que el agente entregue un código de un solo uso."),
    "credential_phishing": Entrada("ASI01", "AML.T0052", APROXIMADO, APROXIMADO,
                                   _ASI01_APROX + "Busca que el agente entregue datos o credenciales del dueño."),
    # Los controles no son un ataque.
    "none": Entrada(NO_APLICA, NO_APLICA, nota="Control: no hay ataque."),
}

# Cuando el dueño ya cayó, el agente obedece a su dueño de verdad y el engañado es la persona. ASI09 es
# el caso inverso (una persona que confía de más en el agente), así que ninguna categoría calza.
ENGANADO = Entrada(POR_CONFIRMAR, POR_CONFIRMAR, nota=(
    "El dueño ya fue engañado y dicta la cuenta: el engaño está en la persona, no en el contenido que lee "
    "el agente. ASI09 (Human-Agent Trust Exploitation) es el caso inverso."))


def mecanismo_de(esc: dict[str, Any]) -> str:
    return esc["anotaciones"]["fraud_mechanism"]


def clasificar(esc: dict[str, Any]) -> Entrada:
    """La entrada de OWASP y ATLAS de un escenario (el mecanismo, salvo cuando el dueño ya fue engañado)."""
    if esc["anotaciones"].get("dueno_ya_enganado"):
        return ENGANADO
    return MAPEO[mecanismo_de(esc)]


def celda(identificador: str, calce: str) -> str:
    """El identificador para una tabla, con `*` si el calce es aproximado."""
    if identificador in (POR_CONFIRMAR, NO_APLICA):
        return identificador
    return identificador + ("*" if calce == APROXIMADO else "")


def nombre(identificador: str) -> str:
    return OWASP_AGENTICO.get(identificador) or ATLAS_TECNICAS.get(identificador) or identificador
