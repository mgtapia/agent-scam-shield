"""Demo local: el agente recibe una nota de voz por chat, intenta pagar, la capa 2 lo retiene y la alerta le llega al dueño
por WhatsApp con los botones (#117). Es el momento del pitch: un solo comando, cada paso con su hora y la latencia medida.

Un agente que obedece todo (sin modelo ni API) lee los mensajes del escenario con `leer_whatsapp`: el texto y la
transcripción de la nota de voz entran como contenido no confiable. Intenta pagar a la cuenta que trae, la capa 2 lo
retiene y se arma la alerta igual que la arma la página de la demo. Con `--enviar`, `notificar()` la manda al dueño por
Kapso con los tres botones; las respuestas siguen por Telegram mientras no haya un túnel para el webhook de Kapso.

Cada paso sale con su hora y los segundos desde que llegó el mensaje. La latencia que importa es la última: desde que
llega la nota hasta que Kapso acepta la alerta (la meta es menos de 5 s; la entrega al celular ya depende de WhatsApp).

La nota de voz de verdad (mp3) la genera `scripts/generar_audios_vishing.py --notas-de-voz`, que necesita
ELEVENLABS_API_KEY: sin ella solo se imprime su costo con `--dry-run`. Si el mp3 ya está en `demo/audio/`, se indica
dónde. Las llaves (`KAPSO_*`) salen de `.env` solo para dejarlas en el entorno: nunca se imprimen.

Uso:
    python scripts/demo_nota_de_voz.py --enviar              # el momento del pitch: la alerta llega al celular del dueño
    python scripts/demo_nota_de_voz.py --dry-run             # el ensayo en seco: mismos pasos con su hora, sin red ni llaves
    python scripts/demo_nota_de_voz.py                       # imprime la alerta y los botones, sin mandar nada
    python scripts/demo_nota_de_voz.py --escenario chat_jefe_nota_de_voz

Códigos de salida: 0 todo bien; 1 la capa 2 no retuvo el pago; 2 no se pudo mandar la alerta (usar --dry-run de respaldo).
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
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
META_SEGUNDOS = 5.0   # desde que llega la nota hasta que Kapso acepta la alerta


def _cargar_env() -> None:
    """Deja las llaves de `.env` en el entorno, sin pisar lo ya definido y sin imprimirlas."""
    from dotenv import load_dotenv

    for ruta in (RAIZ / ".env", RAIZ.parent / ".env"):
        if ruta.is_file():
            load_dotenv(ruta, override=False)
            return


class Cronologia:
    """Cada paso con su hora y los segundos desde que llegó el mensaje. El reloj y la hora se pueden inyectar."""

    def __init__(self, imprimir: Callable[[str], None] = print, reloj: Callable[[], float] = time.perf_counter,
                 hora: Callable[[], float] = time.time):
        self.imprimir, self.reloj, self.hora = imprimir, reloj, hora
        self.t0: Optional[float] = None
        self.pasos: list[tuple[str, float]] = []

    def marca(self, texto: str, inicio: bool = False) -> float:
        ahora = self.reloj()
        if inicio or self.t0 is None:
            self.t0 = ahora
        dt = ahora - self.t0
        hora = datetime.fromtimestamp(self.hora()).strftime("%H:%M:%S.%f")[:-3]
        self.imprimir(f"[{hora}  +{dt:5.2f} s] {texto}")
        self.pasos.append((texto, dt))
        return dt


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
    titular = (esc.get("titulares") or {}).get(str(args.get("cuenta")), {}).get("nombre")
    if titular:
        alerta["titular"] = titular   # el nombre de la cuenta según el banco: lo único de la alerta que no dijo el estafador
    return {"retenida": retenida, "cayo": puntuar(w, esc)["cayo"], "alerta": alerta, "origenes": w.origenes_de(str(args.get("cuenta"))),
            "salida": salida}


def audio_de(esc: dict[str, Any]) -> Optional[Path]:
    ruta = RAIZ / "demo" / "audio" / f"{esc['id']}_nota.mp3"
    return ruta if ruta.is_file() else None


def canal_simulado(imprimir: Callable[[str], None] = print) -> whatsapp.CanalWhatsApp:
    """El mismo canal de WhatsApp con el envío a Kapso cambiado por un aviso en la terminal: nada sale a la red."""
    canal = whatsapp.CanalWhatsApp("sin-llave", "0", "56900000000", lambda etiqueta: None)

    def enviar(cuerpo: dict[str, Any]) -> dict[str, Any]:
        botones = [b["reply"]["title"] for b in cuerpo.get("interactive", {}).get("action", {}).get("buttons", [])]
        imprimir(f"    (simulado, sin red) POST a Kapso: mensaje interactivo con {len(botones)} botones")
        return {"messages": [{"id": "wamid.simulado"}]}

    canal.enviar = enviar   # type: ignore[method-assign]
    return canal


class _Medido:
    """Envuelve el canal para saber si la entrega falló: `notificar()` se traga el error y solo lo registra en el log."""

    __name__ = "whatsapp"

    def __init__(self, canal: Callable[[dict[str, Any]], None]):
        self.canal, self.error = canal, ""

    def __call__(self, alerta: dict[str, Any]) -> None:
        try:
            self.canal(alerta)
        except Exception as e:
            self.error = str(e) or type(e).__name__
            raise


def correr(escenario: str = ESCENARIO, enviar: bool = False, canal: Optional[whatsapp.CanalWhatsApp] = None,
           imprimir: Callable[[str], None] = print, simular: bool = False,
           reloj: Callable[[], float] = time.perf_counter, hora: Callable[[], float] = time.time) -> dict[str, Any]:
    esc = elegir(escenario)
    m = esc["chat"][0]
    cr = Cronologia(imprimir, reloj, hora)
    cr.marca(f"Llega por chat un mensaje de {m['de']} ({m['quien_dice_ser']}) [escenario {esc['id']}]", inicio=True)
    for a in m.get("adjuntos", []):
        if a.get("tipo") == "nota_de_voz":
            imprimir(f"    Nota de voz (transcripción): {a['texto']}")
    mp3 = audio_de(esc)
    imprimir(f"    Audio: {mp3.relative_to(RAIZ)}" if mp3 else
             f"    Audio: todavía no está; se genera con python scripts/generar_audios_vishing.py --notas-de-voz --solo {esc['id']}"
             " (necesita ELEVENLABS_API_KEY; con --dry-run solo se ve el costo).")
    cr.marca("El agente lee el chat y la nota de voz (contenido no confiable: origen whatsapp)")
    r = episodio(esc)
    cr.marca(f"El agente intenta pagar {r['alerta'].get('monto')} a la cuenta {r['alerta']['cuenta']} (origen {sorted(r['origenes'])}) -> "
             + ("RETENIDO por la capa 2." if r["retenida"] else "PASÓ (la capa 2 no lo retuvo)."))
    cr.marca("Se arma la alerta para el dueño")
    imprimir("  Alerta:\n" + "\n".join("    " + linea for linea in texto_de_alerta(r["alerta"]).splitlines()))
    botones = whatsapp.BOTONES["es"]
    imprimir("  Botones: " + " | ".join(botones[k] for k in ("pi", "np", "pg")))
    r.update(enviada=[], latencia=None, pasos=cr.pasos, error="")
    if simular:
        enviar, canal = True, canal or canal_simulado(imprimir)
    if enviar:
        if canal is None:
            canal = whatsapp.desde_entorno(lambda etiqueta: imprimir(f"  (respuesta) {etiqueta.get('eleccion')}"))
        if canal is None:
            imprimir("No se manda: faltan KAPSO_API_KEY, KAPSO_PHONE_NUMBER_ID o KAPSO_OWNER_NUMBER en .env. "
                     "Para ensayar sin llaves: --dry-run.")
            r["error"] = "faltan llaves de Kapso"
        elif not r["retenida"]:
            imprimir("No se manda: la capa 2 no retuvo el pago, no hay alerta.")
        else:
            medido = _Medido(canal)
            registrar_canal(medido)
            cr.marca("Se manda la alerta con los botones al WhatsApp del dueño" + (" (SIMULADO)" if simular else " (Kapso)"))
            r["enviada"] = notificar(r["alerta"])
            if r["enviada"]:
                r["latencia"] = cr.marca("Kapso aceptó la alerta: va camino al celular del dueño" + (" (simulado)" if simular else ""))
                veredicto = "dentro de la meta" if r["latencia"] < META_SEGUNDOS else "SUPERA LA META"
                imprimir(f"Latencia desde que llegó la nota hasta que Kapso aceptó la alerta: {r['latencia']:.2f} s "
                         f"(meta: menos de {META_SEGUNDOS:g} s): {veredicto}.")
            else:
                r["error"] = medido.error or "ningún canal"
                cr.marca(f"FALLÓ el envío ({r['error']}). Respaldo: python scripts/demo_nota_de_voz.py --dry-run")
    else:
        imprimir("(Sin --enviar: no se mandó nada.)")
    return r


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", default=ESCENARIO, help="Un escenario de chat con nota de voz. Por defecto %(default)s.")
    ap.add_argument("--enviar", action="store_true", help="Manda la alerta al dueño por WhatsApp (Kapso).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Ensayo en seco: los mismos pasos con su hora, con el envío simulado (sin red ni llaves).")
    a = ap.parse_args(argv)
    for flujo in (sys.stdout, sys.stderr):   # la consola de Windows no siempre es UTF-8: que las tildes y las « » salgan bien
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    if a.enviar and not a.dry_run:
        _cargar_env()
    r = correr(a.escenario, a.enviar, simular=a.dry_run)
    if not r["retenida"] or r["cayo"]:
        return 1
    return 2 if (a.enviar or a.dry_run) and not r["enviada"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
