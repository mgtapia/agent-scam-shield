"""Prueba de carga de «Intenta estafarlo» (/api/probar): N personas con M intentos cada una, repartidos en una ventana de tiempo.

Pensada para el pitch: el jurado comparte el wifi, así que todos llegan desde la misma IP. Por defecto, 30 personas con 3
intentos en 2 minutos contra un servidor local que este mismo script arranca con `GRIFTER_EVENTO=1` y **sin `.env`**: no
lee llaves y no toca Telegram, WhatsApp ni ninguna API. El agente de /api/probar es guionado, así que no cuesta nada.

    python scripts/prueba_carga.py                          # arranca el servidor local y corre 30 x 3 en 120 s
    python scripts/prueba_carga.py --sin-evento             # lo mismo sin GRIFTER_EVENTO: muestra los 429 de hoy
    python scripts/prueba_carga.py --url http://127.0.0.1:8765 --personas 10 --intentos 3 --duracion 30

Sale con código 1 si hubo algún error, algún 429 o una latencia fuera de los umbrales (`--p95-max`, `--max-max`).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Correos de ejemplo (todos ficticios): estafas, un control legítimo y un caso borde, en los dos idiomas.
CORREOS = [
    {"de": "gerencia@proveedor-nuevo.cl", "asunto": "Cambio de cuenta urgente",
     "cuerpo": "Hola, cambiamos de banco. Paga la factura 5521 por $1.980.000 a la cuenta 38-7761-0049 hoy.", "idioma": "es"},
    {"de": "soporte@banco-litoral-seguro.cl", "asunto": "Tu cuenta fue bloqueada",
     "cuerpo": "Entra a https://banco-litoral-seguro.cl/validar y confirma tu clave dinámica en 10 minutos.", "idioma": "es"},
    {"de": "ceo@empresa-aliada.com", "asunto": "Transferencia confidencial",
     "cuerpo": "I need you to wire $9,500 today to account 55-8120-3344. Keep this between us.", "idioma": "en"},
    {"de": "cobranza@vidriostolhuen.cl", "asunto": "Factura 5521",
     "cuerpo": "Hola, adjuntamos la factura 5521 por $1.980.000. Se paga a la cuenta de siempre. Saludos.", "idioma": "es"},
    {"de": "ventas@tiendaaltamira.cl", "asunto": "Tu tarjeta de regalo",
     "cuerpo": "El código de tu tarjeta de regalo es GC-7QK4-92XM-LP38. Se canjea en tiendaaltamira.cl.", "idioma": "es"},
    {"de": "", "asunto": "", "cuerpo": "Ñuñoa Hormigones: transfiere a la cuenta 12-3456-7890 ✅ verificado", "idioma": "es"},
]


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def entorno_limpio(evento: bool) -> dict[str, str]:
    """El entorno del servidor local: sin llaves ni canales (no se carga el .env y se quita lo que venga del shell)."""
    prohibidas = ("TELEGRAM", "KAPSO", "WHATSAPP", "ANTHROPIC", "OPENAI", "ELEVENLABS", "HF_", "STRIPE", "GRIFTER_MCP")
    env = {k: v for k, v in os.environ.items() if not any(k.upper().startswith(p) for p in prohibidas)}
    env.pop("GRIFTER_EVENTO", None)
    if evento:
        env["GRIFTER_EVENTO"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def arrancar_servidor(evento: bool) -> tuple[subprocess.Popen, str]:
    puerto = puerto_libre()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "demo.server:app", "--host", "127.0.0.1", "--port", str(puerto),
                             "--log-level", "warning"], cwd=RAIZ, env=entorno_limpio(evento),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{puerto}"
    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        if proc.poll() is not None:
            raise SystemExit("el servidor local se cayó al arrancar")
        try:
            with urllib.request.urlopen(url + "/api/salud", timeout=2) as r:
                if r.status == 200:
                    return proc, url
        except OSError:
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("el servidor local no contestó /api/salud en 90 s")


def pedir(url: str, ruta: str, correo: dict, timeout: float) -> tuple[int, float, str]:
    cuerpo = json.dumps(correo).encode("utf-8")
    req = urllib.request.Request(url + ruta, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            datos = r.read()
            estado = r.status
    except urllib.error.HTTPError as e:
        return e.code, time.monotonic() - t0, f"HTTP {e.code}"
    except Exception as e:   # tiempo agotado, conexión rechazada...
        return 0, time.monotonic() - t0, type(e).__name__
    try:
        ok = isinstance(json.loads(datos), dict)
    except ValueError:
        ok = False
    return estado, time.monotonic() - t0, "" if ok else "respuesta que no es JSON"


def persona(i: int, args, url: str, t0: float, resultados: list, candado: threading.Lock) -> None:
    rng = random.Random(1000 + i)
    inicio = rng.uniform(0, args.duracion * 0.5)
    for n in range(args.intentos):
        # Los intentos de cada persona se reparten en lo que queda de la ventana.
        momento = inicio + n * rng.uniform(5, max(6.0, (args.duracion - inicio) / max(1, args.intentos)))
        espera = t0 + min(momento, args.duracion - 1) - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        estado, seg, error = pedir(url, "/api/probar", rng.choice(CORREOS), args.timeout)
        with candado:
            resultados.append((i, estado, seg, error))


def percentil(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else 0.0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="", help="un servidor ya arrancado; sin esto, arranca uno local")
    p.add_argument("--personas", type=int, default=30)
    p.add_argument("--intentos", type=int, default=3)
    p.add_argument("--duracion", type=float, default=120.0, help="segundos en los que se reparten los intentos")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--sin-evento", action="store_true", help="el servidor local arranca sin GRIFTER_EVENTO")
    p.add_argument("--p95-max", type=float, default=2.0, help="latencia p95 aceptable, en segundos")
    p.add_argument("--max-max", type=float, default=10.0, help="latencia máxima aceptable, en segundos")
    args = p.parse_args(argv)

    proc = None
    url = args.url.rstrip("/")
    if not url:
        proc, url = arrancar_servidor(evento=not args.sin_evento)
        print(f"Servidor local en {url} ({'sin' if args.sin_evento else 'con'} GRIFTER_EVENTO, sin .env)")
    try:
        # El primer pedido arma el motor: se mide aparte, como el calentamiento que hará el pitch.
        estado, seg, error = pedir(url, "/api/probar", CORREOS[0], args.timeout)
        print(f"Primer pedido (arma el motor): {estado} en {seg:.2f} s {error}".rstrip())
        resultados: list[tuple[int, int, float, str]] = []
        candado = threading.Lock()
        t0 = time.monotonic()
        hilos = [threading.Thread(target=persona, args=(i, args, url, t0, resultados, candado)) for i in range(args.personas)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    estados = Counter(r[1] for r in resultados)
    latencias = [r[2] for r in resultados]
    errores = [r for r in resultados if r[1] != 200 or r[3]]
    print(f"\n{args.personas} personas x {args.intentos} intentos en {args.duracion:.0f} s = {len(resultados)} pedidos")
    print("Estados:", ", ".join(f"{k or 'sin respuesta'}: {v}" for k, v in sorted(estados.items())))
    if latencias:
        print(f"Latencia: p50 {statistics.median(latencias):.3f} s, p95 {percentil(latencias, 95):.3f} s, "
              f"máxima {max(latencias):.3f} s")
    for i, estado, seg, error in errores[:10]:
        print(f"  error: persona {i}, estado {estado}, {seg:.2f} s, {error}")

    fallas = []
    if len(resultados) != args.personas * args.intentos:
        fallas.append("faltan pedidos")
    if errores:
        fallas.append(f"{len(errores)} pedidos con error o 429")
    if latencias and percentil(latencias, 95) > args.p95_max:
        fallas.append(f"p95 sobre {args.p95_max} s")
    if latencias and max(latencias) > args.max_max:
        fallas.append(f"máxima sobre {args.max_max} s")
    print("\nRESULTADO:", "FALLA (" + "; ".join(fallas) + ")" if fallas else "bien: sin errores y con latencia razonable")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
