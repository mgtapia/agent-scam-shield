"""Demo local: el agente recibe una nota de voz por chat, intenta pagar, la capa 2 lo retiene y la alerta le llega al dueño
por WhatsApp con los botones (#117).

Un agente que obedece todo (sin modelo ni API) lee los mensajes del escenario con `leer_whatsapp`: el texto y la
transcripción de la nota de voz entran como contenido no confiable. Intenta pagar a la cuenta que trae, la capa 2 lo
retiene y se arma la alerta igual que la arma la página de la demo. Con `--enviar`, `notificar()` la manda al dueño por
Kapso con los tres botones; las respuestas siguen por Telegram mientras no haya un túnel para el webhook de Kapso.

La nota de voz de verdad (mp3) la genera `scripts/generar_audios_vishing.py --notas-de-voz`, que necesita
ELEVENLABS_API_KEY: sin ella solo se imprime su costo con `--dry-run`. Si el mp3 ya está en `demo/audio/`, se indica
dónde. Las llaves (`KAPSO_*`) salen de `.env` solo para dejarlas en el entorno: nunca se imprimen.

Uso:
    python scripts/demo_nota_de_voz.py                       # imprime la alerta y los botones, sin mandar nada
    python scripts/demo_nota_de_voz.py --escenario chat_jefe_nota_de_voz
    python scripts/demo_nota_de_voz.py --enviar              # además la manda al dueño por WhatsApp (Kapso)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from demo import whatsapp  # noqa: E402
from demo.notificar import notificar, registrar_canal  # noqa: E402
from demo.telegram import texto_de_alerta  # noqa: E402
from scamshield.defenses.layer2 import politica_origen  # noqa: E402
from scamshield.env.tools import Herramientas  # noqa: E402
from scamshield.env.world import WHATSAPP, World  # noqa: E402
from scamshield.evals.puntaje import puntuar  # noqa: E402
from scamshield.scenarios import cargar  # noqa: E402

ESCENARIO = "chat_hijo_numero_nuevo"
CUENTA = re.compile(r"\d{2}-\d{4}-\d{4}")


def _cargar_env() -> None:
    """Deja las llaves de `.env` en el entorno, sin pisar lo ya definido y sin imprimirlas."""
    from dotenv import load_dotenv

    for ruta in (RAIZ / ".env", RAIZ.parent / ".env"):
        if ruta.is_file():
            load_dotenv(ruta, override=False)
            return


def elegir(escenario: str, idioma: str = "es") -> dict[str, Any]:
    for esc in cargar((idioma,)):
        if esc["id"] == escenario:
            if not esc.get("chat") or not any(a.get("tipo") == "nota_de_voz" for m in esc["chat"] for a in m.get("adjuntos", [])):
                raise SystemExit(f"{escenario} no trae una nota de voz por chat.")
            if "accion_estafa" not in esc["evaluacion"]:
                raise SystemExit(f"{escenario} no es una estafa con un pago.")
            return esc
    raise SystemExit(f"No existe el escenario {escenario} en {idioma}.")


def episodio(esc: dict[str, Any]) -> dict[str, Any]:
    """El agente ingenuo lee el chat e intenta pagar con la capa 2 puesta. Devuelve lo que pasó y la alerta."""
    w = World.desde_escenario(esc)
    h = Herramientas(w, [politica_origen])
    h.leer_whatsapp()
    accion = esc["evaluacion"]["accion_estafa"]
    args = accion["args"]
    salida = getattr(h, accion["herramienta"])(**args)
    retenida = "BLOQUEADA" in salida
    motivo = next((a.motivo for a in reversed(w.registro) if a.bloqueada), "")
    mensaje = w.chat[0]
    inscrita = next(iter(esc.get("cuentas_inscritas", {}).items()), ("", ""))
    numero_inscrita = CUENTA.search(inscrita[1])
    alerta = {
        "escenario": esc["id"], "idioma": esc["idioma"], "defensa": "layer2",
        "destinatario": args.get("beneficiario") or args.get("destinatario", ""), "monto": args.get("monto"),
        "cuenta": args.get("cuenta"), "dominio": f"WhatsApp de {mensaje.de} (nota de voz)", "correos": [],
        "cuenta_inscrita": bool(inscrita[0]), "cuenta_inscrita_numero": numero_inscrita.group(0) if numero_inscrita else "",
        "nombre_inscrita": inscrita[0], "motivo": motivo,
    }
    return {"retenida": retenida, "cayo": puntuar(w, esc)["cayo"], "alerta": alerta, "origenes": w.origenes_de(str(args.get("cuenta"))),
            "salida": salida}


def audio_de(esc: dict[str, Any]) -> Optional[Path]:
    ruta = RAIZ / "demo" / "audio" / f"{esc['id']}_nota.mp3"
    return ruta if ruta.is_file() else None


def correr(escenario: str = ESCENARIO, enviar: bool = False, canal: Optional[whatsapp.CanalWhatsApp] = None,
           imprimir: Callable[[str], None] = print) -> dict[str, Any]:
    esc = elegir(escenario)
    r = episodio(esc)
    m = esc["chat"][0]
    imprimir(f"Escenario {esc['id']}: llega un mensaje de {m['de']} ({m['quien_dice_ser']}).")
    for a in m.get("adjuntos", []):
        if a.get("tipo") == "nota_de_voz":
            imprimir(f"  Nota de voz (transcripción): {a['texto']}")
    mp3 = audio_de(esc)
    imprimir(f"  Audio: {mp3.relative_to(RAIZ)}" if mp3 else
             f"  Audio: todavía no está; se genera con python scripts/generar_audios_vishing.py --notas-de-voz --solo {esc['id']}"
             " (necesita ELEVENLABS_API_KEY; con --dry-run solo se ve el costo).")
    imprimir(f"El agente intenta pagar a {r['alerta']['cuenta']}: origen {sorted(r['origenes'])} -> "
             + ("RETENIDO por la capa 2." if r["retenida"] else "PASÓ (la capa 2 no lo retuvo)."))
    imprimir("Alerta al dueño:\n" + "\n".join("  " + linea for linea in texto_de_alerta(r["alerta"]).splitlines()))
    botones = whatsapp.BOTONES["es"]
    imprimir("  Botones: " + " | ".join(botones[k] for k in ("pi", "np", "pg")))
    r["enviada"] = []
    if enviar:
        if canal is None:
            canal = whatsapp.desde_entorno(lambda etiqueta: imprimir(f"  (respuesta) {etiqueta.get('eleccion')}"))
        if canal is None:
            imprimir("No se manda: faltan KAPSO_API_KEY, KAPSO_PHONE_NUMBER_ID o KAPSO_OWNER_NUMBER en .env.")
        elif not r["retenida"]:
            imprimir("No se manda: la capa 2 no retuvo el pago, no hay alerta.")
        else:
            registrar_canal(canal)
            r["enviada"] = notificar(r["alerta"])
            imprimir(f"Alerta mandada por: {', '.join(r['enviada']) or 'ningún canal (falló el envío)'}.")
    else:
        imprimir("(Sin --enviar: no se mandó nada.)")
    return r


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", default=ESCENARIO, help="Un escenario de chat con nota de voz. Por defecto %(default)s.")
    ap.add_argument("--enviar", action="store_true", help="Manda la alerta al dueño por WhatsApp (Kapso).")
    a = ap.parse_args(argv)
    if a.enviar:
        _cargar_env()
    r = correr(a.escenario, a.enviar)
    return 0 if r["retenida"] and not r["cayo"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
