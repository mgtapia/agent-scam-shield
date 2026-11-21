"""Despierta la demo pública (Render, plan gratis) y comprueba lo que se va a mostrar, 5 minutos antes del pitch.

El plan gratis duerme el servicio tras ~15 minutos sin tráfico y despertarlo toma ~50 s. Este script lo despierta con reintentos y
después verifica, en orden:

  1. /api/salud        el servicio contesta, con episodios (y dice si está en modo evento, GRIFTER_EVENTO=1)
  2. /resultados.json  la página de Resultados tiene su JSON y sus secciones
  3. /mcp              Grifter como conector MCP remoto contesta el `initialize` (modo público)
  4. /api/probar       un correo de prueba (arma el motor la primera vez: es lo que tarda en el primer intento del jurado)

    python scripts/calentar.py                                   # contra https://grifter.onrender.com
    python scripts/calentar.py --url http://127.0.0.1:8765       # contra un servidor local
    python scripts/calentar.py --mantener                        # y sigue avisando cada 8 min para que no se duerma

Solo hace GET a /api/salud y /resultados.json, un POST `initialize` a /mcp y un POST a /api/probar con un correo ficticio. No
manda nada a Telegram ni a ninguna API. Sale con código 1 si algo crítico falla, con la lista de lo que falló.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

URL_POR_DEFECTO = "https://grifter.onrender.com"
CABECERAS_MCP = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INICIO_MCP = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "calentar", "version": "0"}}}
CORREO_DE_PRUEBA = {"de": "cobranza@proveedor-ejemplo.cl", "asunto": "Factura 5521",
                    "cuerpo": "Hola, adjuntamos la factura 5521. Se paga a la cuenta de siempre. Saludos.", "idioma": "es"}
SECCIONES_RESULTADOS = ("bench", "clasificador", "duelo")


def pedir(url: str, metodo: str = "GET", cuerpo: dict | None = None, cabeceras: dict | None = None,
          timeout: float = 90.0) -> tuple[int, bytes, float]:
    """(estado, cuerpo, segundos). Estado 0 si no hubo respuesta (el servicio todavía duerme o la red falló)."""
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    cab = {"Content-Type": "application/json", **(cabeceras or {})} if cuerpo is not None else dict(cabeceras or {})
    req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.monotonic() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.monotonic() - t0
    except Exception:
        return 0, b"", time.monotonic() - t0


def despertar(base: str, espera_max: float, reintento: float = 5.0) -> tuple[bool, float]:
    """Pide /api/salud hasta que conteste 200. (despertó, segundos que tomó)."""
    t0 = time.monotonic()
    intento = 0
    while True:
        intento += 1
        estado, _, seg = pedir(base + "/api/salud", timeout=min(90.0, max(5.0, espera_max)))
        total = time.monotonic() - t0
        if estado == 200:
            print(f"  despertó en {total:.1f} s (intento {intento})")
            return True, total
        print(f"  intento {intento}: {'sin respuesta' if estado == 0 else f'HTTP {estado}'} a los {seg:.1f} s; sigue durmiendo...")
        if total + reintento >= espera_max:
            return False, total
        time.sleep(reintento)


def verificar(base: str, probar: bool = True) -> list[tuple[str, bool, str]]:
    """Cada comprobación: (nombre, crítica y falló = False, detalle). Devuelve (nombre, ok, detalle)."""
    filas: list[tuple[str, bool, str]] = []

    estado, cuerpo, seg = pedir(base + "/api/salud")
    try:
        salud = json.loads(cuerpo)
    except ValueError:
        salud = {}
    ok = estado == 200 and salud.get("ok") is True and salud.get("episodios", 0) > 0
    modo = "modo evento" if salud.get("evento") else "modo normal (tope por IP de siempre)"
    filas.append(("/api/salud", ok, f"HTTP {estado}, {salud.get('episodios', '?')} episodios, {modo}, {seg:.2f} s"))

    estado, cuerpo, seg = pedir(base + "/resultados.json")
    try:
        res = json.loads(cuerpo)
    except ValueError:
        res = None
    faltan = [s for s in SECCIONES_RESULTADOS if not isinstance(res, dict) or s not in res]
    filas.append(("/resultados.json", estado == 200 and isinstance(res, dict) and not faltan,
                  f"HTTP {estado}, {len(cuerpo) // 1024} KB, {seg:.2f} s" + (f", faltan secciones: {faltan}" if faltan else "")))

    estado, cuerpo, seg = pedir(base + "/mcp", "POST", INICIO_MCP, CABECERAS_MCP)
    texto = cuerpo.decode("utf-8", errors="replace")
    ok = estado == 200 and ("grifter" in texto.lower() or "serverinfo" in texto.lower())
    detalle = {404: "apagado: falta GRIFTER_MCP_PUBLICO=1 o el token", 401: "pide token (no está en modo público)"}.get(
        estado, f"HTTP {estado}")
    filas.append(("/mcp", ok, f"{detalle}, {seg:.2f} s" if not ok else f"initialize contestó, {seg:.2f} s"))

    if probar:
        estado, cuerpo, seg = pedir(base + "/api/probar", "POST", CORREO_DE_PRUEBA)
        try:
            ok = estado == 200 and isinstance(json.loads(cuerpo), dict)
        except ValueError:
            ok = False
        detalle = f"HTTP {estado}, {seg:.2f} s" + (" (arma el motor la primera vez)" if ok and seg > 1.5 else "")
        if estado == 429:
            detalle += " (el tope por IP: prende GRIFTER_EVENTO=1)"
        filas.append(("/api/probar", ok, detalle))
    return filas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL_POR_DEFECTO)
    p.add_argument("--espera", type=float, default=180.0, help="segundos máximos para que despierte")
    p.add_argument("--sin-probar", action="store_true", help="no manda el correo de prueba a /api/probar")
    p.add_argument("--mantener", action="store_true", help="después de verificar, sigue pidiendo /api/salud cada 8 min")
    args = p.parse_args(argv)
    base = args.url.rstrip("/")

    print(f"Despertando {base} ...")
    despierto, _ = despertar(base, args.espera)
    if not despierto:
        print(f"\nFALLA: {base} no despertó en {args.espera:.0f} s. Mira el panel de Render (despliegue y registros).")
        return 1

    print("\nVerificando:")
    filas = verificar(base, probar=not args.sin_probar)
    for nombre, ok, detalle in filas:
        print(f"  [{'ok' if ok else 'FALLA'}] {nombre}: {detalle}")
    malas = [n for n, ok, _ in filas if not ok]
    print("\nRESULTADO:", f"FALLA ({', '.join(malas)})" if malas else "todo listo para el pitch")

    if args.mantener and not malas:
        print("Sigo pidiendo /api/salud cada 8 minutos para que no se duerma (Ctrl+C para parar).")
        try:
            while True:
                time.sleep(8 * 60)
                estado, _, seg = pedir(base + "/api/salud")
                print(f"  {time.strftime('%H:%M:%S')} /api/salud: HTTP {estado} en {seg:.2f} s")
        except KeyboardInterrupt:
            pass
    return 1 if malas else 0


if __name__ == "__main__":
    sys.exit(main())
