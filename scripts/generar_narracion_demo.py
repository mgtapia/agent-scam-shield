"""Genera con ElevenLabs la voz que narra los actos 2 y 3 del modo demo (demo/demo.html).

El acto 1 tiene las voces de la llamada (abuela y nieto). Desde el acto 2 una narradora cuenta cada escena en una o
dos frases. Cada audio queda en `demo/audio/narracion_<escena>.mp3` con su ficha `.json`, que trae el texto, la voz,
el modelo, el aviso de voz sintética y **cuándo empieza cada palabra** (de `/with-timestamps`). Con esos tiempos se
fijan a mano las constantes de `demo/demo.js`, igual que `FRASES` en el acto 1: la demo no lee la ficha al correr.

Reglas (las mismas de `generar_audios_vishing.py`):
- Nunca se clona a nadie. Se usa una voz de la biblioteca compartida de ElevenLabs, publicada por su autor para
  texto a voz. El script le pregunta a la API su clase y se detiene si es `cloned` o `famous`.
- La llave sale de `ELEVENLABS_API_KEY` (entorno o `.env`); no se imprime ni se guarda.
- `--dry-run` imprime el plan y los caracteres sin red. Lo que ya existe no se rehace sin `--forzar`.
- Los números van escritos en palabras: así la voz los lee bien y los tiempos de cada palabra calzan.

Uso:
    python scripts/generar_narracion_demo.py --dry-run
    python scripts/generar_narracion_demo.py                         # genera lo que falte
    python scripts/generar_narracion_demo.py --solo correo --forzar
    python scripts/generar_narracion_demo.py --voz <id> --salida /tmp/muestras --solo correo   # probar otra voz
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.generar_audios_vishing import CATEGORIAS_PROHIBIDAS, Cliente, ErrorDeVoz, _cargar_llave  # noqa: E402

MODELO = "eleven_v3"            # admite etiquetas de emoción en inglés entre corchetes
FORMATO = "mp3_44100_64"        # mono, 64 kbps: lo justo para una voz proyectada
# «Ignacio - Natural Chilean, unhurried pace», voz profesional de la biblioteca compartida de ElevenLabs (es-CL):
# chilena, natural y clara. Se probaron también «Angela - Warm, Calm and Assured» (prblQcKOdF08ozhxP2mk) y «Catalina -
# Chilean Spanish» (6Gr4AVmTax1pMJO0lHRK): con ellas la narración dura 50 s o más y la demo pasa de los 110 s.
VOZ = "NDx3GTwfaeouBvRv4NrB"
NOMBRE_VOZ = "Ignacio - Natural Chilean, unhurried pace (biblioteca de ElevenLabs)"
ETIQUETA = re.compile(r"\[[^\]]*\]")

# Una pieza por escena. El texto es lo que se dice; las etiquetas entre corchetes son el tono para eleven_v3.
NARRACION = {
    # Acto 1: la entrada (sobre el timbre, antes de que conteste la abuela) y todo lo que pasa después de colgar.
    "entrada": "[warm] Marta le encargó a su agente contestar sus llamadas.",
    "autoriza": "[warm] El agente va a pagar. Sin Grifter, la plata se va. Con Grifter, queda retenido: la cuenta salió "
                "de una llamada. Marta insiste: ahora hacen falta dos aprobaciones. Ella aprueba con su código. "
                "Falta Pablo, su hijo… y Pablo rechaza. No se pagó nada.",
    # Acto 2: cada escena y su regla a pantalla completa.
    "correo": "[warm] Un falso banco pide el código del SMS. El agente lo iba a mandar… y Grifter lo frena.",
    "compra": "[warm] Aprobaste cuatrocientos doce mil y te cobran diez veces más. Grifter lo frena.",
    "cifras": "[warm] Lo medimos: ciento cincuenta estafas, pasan cero. Cinco mil doscientos ochenta intentos "
              "de un atacante que aprende: ninguno cruza.",
    "regla_correo": "[firm] La clave no sale sin el dueño.",
    "regla_compra": "[firm] Solo lo que aprobaste.",
    "cierre": "[calm] Tu agente puede creerle a cualquiera. Tu plata, no.",
    "marca": "[warm] Grifter: escudo para agentes que pagan.",
}
# Velocidad de la voz por escena (voice_settings.speed; 1 es la normal). Las escenas del acto 2 y las cifras van un
# poco más rápido para que la demo quepa en unos 85 s con voz de punta a punta; el cierre, a velocidad normal.
VELOCIDAD = {"entrada": 1.12, "autoriza": 1.12, "correo": 1.12, "compra": 1.12, "cifras": 1.12, "regla_correo": 1.0,
             "regla_compra": 1.0, "cierre": 1.0, "marca": 1.0}


def palabras(alineacion: dict[str, Any]) -> list[list[Any]]:
    """Cada palabra dicha con el segundo en que empieza, sin las etiquetas de tono. Sale de los caracteres de la
    respuesta (no del texto pedido), porque la API puede normalizar algo."""
    chars = alineacion["characters"]
    inicios = alineacion["character_start_times_seconds"]
    texto = "".join(chars)
    sin_etiquetas = ETIQUETA.sub(lambda m: " " * len(m.group()), texto)
    salida = []
    for m in re.finditer(r"\S+", sin_etiquetas):
        salida.append([m.group(), round(inicios[m.start()], 3)])
    return salida


def clase_de_voz(cliente: Cliente, voz_id: str) -> str:
    """La clase de la voz según la biblioteca compartida (professional, high_quality...). Se mira primero ahí porque
    una voz de biblioteca que ya se usó aparece también en la cuenta, pero con otra clase. Si no está en la
    biblioteca, vale la de la cuenta."""
    datos = json.loads(cliente._pedir("GET", "/v1/shared-voices", query="?page_size=100&language=es&accent=chilean"))
    for v in datos.get("voices", []):
        if v.get("voice_id") == voz_id:
            return str(v.get("category") or "")
    try:
        return cliente.categoria(voz_id)
    except ErrorDeVoz:
        return ""


def sintetizar(cliente: Cliente, voz_id: str, texto: str, modelo: str = MODELO,
               velocidad: float = 1.0) -> tuple[bytes, dict[str, Any]]:
    """El mp3 y la alineación por carácter (`/with-timestamps`)."""
    cuerpo: dict[str, Any] = {"text": texto, "model_id": modelo}
    if velocidad != 1.0:
        cuerpo["voice_settings"] = {"speed": velocidad}
    resp = json.loads(cliente._pedir("POST", f"/v1/text-to-speech/{voz_id}/with-timestamps",
                                     cuerpo, query=f"?output_format={FORMATO}"))
    return base64.b64decode(resp["audio_base64"]), resp["alignment"]


def generar(cliente: Cliente, ids: list[str], salida: Path, voz_id: str = VOZ, nombre_voz: str = NOMBRE_VOZ,
            modelo: str = MODELO, forzar: bool = False, imprimir: Callable[[str], None] = print) -> list[Path]:
    pendientes = [i for i in ids if forzar or not (salida / f"narracion_{i}.mp3").exists()]
    for i in set(ids) - set(pendientes):
        imprimir(f"ya existe, no se rehace: narracion_{i}.mp3")
    if not pendientes:
        return []
    clase = clase_de_voz(cliente, voz_id)
    if not clase or clase in CATEGORIAS_PROHIBIDAS:
        raise ErrorDeVoz(f"la voz {voz_id} es de clase «{clase or 'desconocida'}»: no se clona a nadie ni se usa "
                         "una voz que no se pueda verificar. Elige una voz de la biblioteca.")
    salida.mkdir(parents=True, exist_ok=True)
    hechos = []
    for i in pendientes:
        texto = NARRACION[i]
        velocidad = VELOCIDAD.get(i, 1.0)
        audio, alineacion = sintetizar(cliente, voz_id, texto, modelo, velocidad)
        destino = salida / f"narracion_{i}.mp3"
        destino.write_bytes(audio)
        dichas = palabras(alineacion)
        duracion = round(alineacion["character_end_times_seconds"][-1], 3)
        destino.with_suffix(".json").write_text(json.dumps({
            "escenario": f"demo_narracion_{i}", "idioma": "es", "origen": "narración", "texto": texto,
            "voz": nombre_voz, "voz_id": voz_id, "clase_de_voz": clase, "modelo": modelo, "formato": FORMATO, "velocidad": velocidad,
            "sintetica": True,
            "aviso": "Voz sintética de la biblioteca compartida de ElevenLabs, publicada por su autor para texto a voz. "
                     "No imita a nadie del proyecto ni a ninguna persona de la demo.",
            "caracteres": len(texto), "duracion_s": duracion, "palabras": dichas,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ritmo = len(ETIQUETA.sub("", texto).strip()) / duracion
        imprimir(f"listo: {destino.name} ({len(audio)} bytes; {duracion:.2f} s; {ritmo:.1f} caracteres por segundo)")
        hechos.append(destino)
    return hechos


def main(argv: Optional[list[str]] = None, entorno: Optional[dict[str, str]] = None, cliente: Optional[Cliente] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="Imprime el plan y los caracteres; no usa la llave ni la red.")
    ap.add_argument("--solo", help="Escenas a generar, separadas por coma: " + ", ".join(NARRACION))
    ap.add_argument("--salida", default=str(RAIZ / "demo" / "audio"), help="Carpeta de los audios. Por defecto demo/audio.")
    ap.add_argument("--voz", default=VOZ, help="Id de una voz de la biblioteca. Por defecto %(default)s.")
    ap.add_argument("--nombre-voz", default=None, help="Nombre de la voz para la ficha.")
    ap.add_argument("--modelo", default=MODELO, help="Modelo de ElevenLabs. Por defecto %(default)s.")
    ap.add_argument("--forzar", action="store_true", help="Rehace los audios que ya existen (gasta créditos otra vez).")
    args = ap.parse_args(argv)
    ids = [s.strip() for s in args.solo.split(",") if s.strip()] if args.solo else list(NARRACION)
    desconocidas = [i for i in ids if i not in NARRACION]
    if desconocidas:
        print(f"Escenas desconocidas: {', '.join(desconocidas)}")
        return 1
    total = sum(len(NARRACION[i]) for i in ids)
    print(f"Se generarían {len(ids)} audios con {args.modelo} y la voz {args.voz}: {total} caracteres.")
    for i in ids:
        print(f"  - narracion_{i}: {len(NARRACION[i])} caracteres")
    if args.dry_run:
        return 0
    if cliente is None:
        llave = _cargar_llave(dict(os.environ if entorno is None else entorno))
        if not llave:
            print("Falta ELEVENLABS_API_KEY (en .env). Con --dry-run se ve el plan sin llave.")
            return 1
        cliente = Cliente(llave)
    nombre = args.nombre_voz or (NOMBRE_VOZ if args.voz == VOZ else args.voz)
    try:
        generar(cliente, ids, Path(args.salida), args.voz, nombre, args.modelo, args.forzar)
    except ErrorDeVoz as e:
        print(f"Se detiene: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
