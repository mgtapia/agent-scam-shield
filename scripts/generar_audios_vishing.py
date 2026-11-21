"""Genera con ElevenLabs el audio de las llamadas de estafa (#117) para la demo y el pitch.

Qué se genera: la transcripción de cada llamada de los escenarios `vishing_*` y del control telefónico, en español,
con una voz sintética de la biblioteca de ElevenLabs. Con `--notas-de-voz` suma también las notas de voz de los
escenarios de chat. Los audios quedan en `demo/audio/<escenario>.mp3`, cada uno con su ficha `<escenario>.json` que
dice que la voz es sintética.

Reglas:
- **Nunca se clona la voz de una persona real.** Antes de gastar nada, el script le pregunta a la API qué clase de voz
  es cada una y se detiene si es `cloned` (clonada) o `famous` (de una persona conocida). La «voz clonada del jefe» de
  los escenarios se simula con una voz de biblioteca.
- **El costo se imprime antes de gastarlo.** `--dry-run` solo imprime el plan y los créditos estimados, sin llave y sin
  red. Con una llamada real, `--tope-caracteres` (por defecto 12.000) corta antes de pasarse.
- **La llave** sale de `ELEVENLABS_API_KEY`, en `.env`. No se imprime ni se guarda en las fichas.
- Lo que ya está generado no se vuelve a generar (cuesta créditos): `--forzar` lo rehace.

Los créditos son los de ElevenLabs: 1 por carácter con `eleven_multilingual_v2` y la mitad con los modelos `flash` y
`turbo`. Cuánto es eso en dinero depende del plan; `--usd-por-mil` lo convierte si pasas el precio de tu plan.

Uso:
    python scripts/generar_audios_vishing.py --dry-run
    python scripts/generar_audios_vishing.py --notas-de-voz --dry-run
    python scripts/generar_audios_vishing.py                       # genera lo que falte
    python scripts/generar_audios_vishing.py --solo vishing_familiar --forzar
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

URL_BASE = "https://api.elevenlabs.io"
MODELO = "eleven_multilingual_v2"
FORMATO = "mp3_44100_128"
TOPE_CARACTERES = 12_000
# Voces premade de la biblioteca de ElevenLabs. Si no están en tu cuenta, pasa otras con --voz-femenina/--voz-masculina
# o con ELEVENLABS_VOZ_FEMENINA y ELEVENLABS_VOZ_MASCULINA.
VOCES = {"femenina": "21m00Tcm4TlvDq8ikWAM", "masculina": "pNInz6obpgDQGcFmaJgB"}
# Clases de voz que el script se niega a usar: una persona real, con o sin su permiso.
CATEGORIAS_PROHIBIDAS = {"cloned", "famous"}
# La voz de cada personaje (todos ficticios). Lo que no está aquí usa la masculina.
VOZ_DE = {
    "vishing_clave_dinamica": "femenina",      # Daniela, de Seguridad del banco
    "vishing_soporte_tecnico": "femenina",     # Melanie, de soporte técnico
    "vishing_familiar": "masculina",           # Mark
    "vishing_cuenta_segura": "masculina",      # Reed
    "vishing_jefe_voz_clonada": "masculina",   # Steve
    "control_llamada_proveedor_inscrito": "masculina",   # Jeff
    "chat_hijo_numero_nuevo": "masculina",
    "chat_jefe_nota_de_voz": "masculina",
    "control_chat_gerente_proveedor_inscrito": "masculina",
}
PREFIJO = re.compile(r"^\s*\[[^\]]*\]\s*")   # «[Buzón de voz, 52 segundos] » y sus notas de la transcripción


class ErrorDeVoz(RuntimeError):
    pass


@dataclass
class Pieza:
    escenario: str
    texto: str          # lo que se dice, sin el encabezado entre corchetes
    voz: str            # «femenina» o «masculina»
    origen: str         # «llamada» o «nota de voz»

    @property
    def caracteres(self) -> int:
        return len(self.texto)


def limpiar(transcripcion: str) -> str:
    """Lo que se dice: la transcripción sin el encabezado «[Buzón de voz, 41 segundos]» ni los saltos de línea."""
    return " ".join(PREFIJO.sub("", str(transcripcion)).split())


def reunir(escenarios: list[dict[str, Any]], notas_de_voz: bool = False, solo: Optional[set[str]] = None) -> list[Pieza]:
    """Una pieza por llamada de los escenarios telefónicos (y por nota de voz de chat si se pide), solo en español."""
    piezas = []
    for esc in escenarios:
        if esc.get("idioma") != "es":
            continue
        id_ = esc["id"]
        if solo is not None and id_ not in solo:
            continue
        voz = VOZ_DE.get(id_, "masculina")
        if id_.startswith(("vishing_", "control_llamada")):
            piezas += [Pieza(id_, limpiar(l["transcripcion"]), voz, "llamada") for l in esc.get("llamadas", [])[:1]]
        if notas_de_voz:
            for m in esc.get("chat", []):
                for a in m.get("adjuntos", []):
                    if a.get("tipo") == "nota_de_voz":
                        piezas.append(Pieza(id_, limpiar(a["texto"]), voz, "nota de voz"))
    return piezas


def creditos(piezas: list[Pieza], modelo: str = MODELO) -> float:
    """Créditos de ElevenLabs: 1 por carácter, la mitad con los modelos flash y turbo."""
    factor = 0.5 if re.search(r"flash|turbo", modelo) else 1.0
    return sum(p.caracteres for p in piezas) * factor


def plan(piezas: list[Pieza], modelo: str, voces: dict[str, str], usd_por_mil: Optional[float]) -> str:
    lineas = [f"Se generarían {len(piezas)} audios con el modelo {modelo}:"]
    for p in piezas:
        lineas.append(f"  - {p.escenario} ({p.origen}, voz {p.voz} {voces[p.voz]}): {p.caracteres} caracteres")
    total = sum(p.caracteres for p in piezas)
    linea = f"Total: {total} caracteres, ~{creditos(piezas, modelo):,.0f} créditos de ElevenLabs."
    if usd_por_mil is not None:
        linea += f" A US${usd_por_mil:g} por mil caracteres: ~US${total * usd_por_mil / 1000:.2f}."
    lineas.append(linea.replace(",", "."))
    return "\n".join(lineas)


# --- La API ------------------------------------------------------------------------------------------------

Transporte = Callable[[str, str, dict[str, str], Optional[bytes]], tuple[int, bytes]]


def transporte_http(metodo: str, url: str, cabeceras: dict[str, str], cuerpo: Optional[bytes]) -> tuple[int, bytes]:
    pedido = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class Cliente:
    """Lo mínimo de la API de ElevenLabs: la clase de una voz y la síntesis de un texto. El transporte se inyecta."""

    def __init__(self, llave: str, transporte: Transporte = transporte_http, url_base: str = URL_BASE):
        self._llave, self._t, self.url_base = llave, transporte, url_base.rstrip("/")

    def _pedir(self, metodo: str, ruta: str, cuerpo: Optional[dict] = None, query: str = "") -> bytes:
        cabeceras = {"xi-api-key": self._llave, "Accept": "*/*"}
        datos = None
        if cuerpo is not None:
            cabeceras["Content-Type"] = "application/json"
            datos = json.dumps(cuerpo).encode("utf-8")
        estado, resp = self._t(metodo, f"{self.url_base}{ruta}{query}", cabeceras, datos)
        if estado != 200:
            # El cuerpo del error puede traer detalle útil; nunca la llave, que solo va en la cabecera.
            raise ErrorDeVoz(f"ElevenLabs respondió {estado} en {metodo} {ruta}: {resp[:300].decode('utf-8', 'replace')}")
        return resp

    def categoria(self, voz_id: str) -> str:
        """La clase de voz según la API: premade, generated, professional, cloned, famous..."""
        datos = json.loads(self._pedir("GET", f"/v1/voices/{voz_id}"))
        return str(datos.get("category") or "")

    def sintetizar(self, voz_id: str, texto: str, modelo: str = MODELO) -> bytes:
        return self._pedir("POST", f"/v1/text-to-speech/{voz_id}", {"text": texto, "model_id": modelo},
                           query=f"?output_format={FORMATO}")


def verificar_voces(cliente: Cliente, voces: dict[str, str], usadas: set[str]) -> dict[str, str]:
    """La clase de cada voz que se va a usar; se detiene ante una voz clonada o de una persona conocida."""
    categorias = {}
    for nombre in sorted(usadas):
        categoria = cliente.categoria(voces[nombre])
        if not categoria or categoria in CATEGORIAS_PROHIBIDAS:
            raise ErrorDeVoz(f"la voz {nombre} ({voces[nombre]}) es de clase «{categoria or 'desconocida'}»: no se clona "
                             "a una persona real ni se usa una voz que no se pueda verificar. Elige una voz de la biblioteca.")
        categorias[nombre] = categoria
    return categorias


def generar(piezas: list[Pieza], cliente: Cliente, voces: dict[str, str], salida: Path, modelo: str = MODELO,
            forzar: bool = False, imprimir: Callable[[str], None] = print) -> list[Path]:
    """Sintetiza cada pieza y guarda el mp3 y su ficha. Devuelve los mp3 que escribió."""
    pendientes = []
    for p in piezas:
        destino = salida / f"{p.escenario}{'' if p.origen == 'llamada' else '_nota'}.mp3"
        if destino.exists() and not forzar:
            imprimir(f"ya existe, no se rehace: {destino.name}")
            continue
        pendientes.append((p, destino))
    if not pendientes:
        return []
    categorias = verificar_voces(cliente, voces, {p.voz for p, _ in pendientes})
    salida.mkdir(parents=True, exist_ok=True)
    hechos = []
    for p, destino in pendientes:
        audio = cliente.sintetizar(voces[p.voz], p.texto, modelo)
        destino.write_bytes(audio)
        destino.with_suffix(".json").write_text(json.dumps({
            "escenario": p.escenario, "idioma": "es", "origen": p.origen, "texto": p.texto,
            "voz": p.voz, "voz_id": voces[p.voz], "clase_de_voz": categorias[p.voz], "modelo": modelo,
            "sintetica": True,
            "aviso": "Voz sintética de la biblioteca de ElevenLabs. No es la voz de ninguna persona real.",
            "caracteres": p.caracteres}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        imprimir(f"listo: {destino.name} ({len(audio):,} bytes)".replace(",", "."))
        hechos.append(destino)
    return hechos


# --- La línea de comandos ----------------------------------------------------------------------------------

def _cargar_llave(entorno: dict[str, str]) -> str:
    """ELEVENLABS_API_KEY del entorno o de `.env` (sin imprimirla). Si el checkout es un worktree, busca el principal."""
    if not entorno.get("ELEVENLABS_API_KEY"):
        from dotenv import dotenv_values

        for ruta in (RAIZ / ".env", RAIZ.parent / ".env"):
            if ruta.is_file():
                valor = dotenv_values(ruta).get("ELEVENLABS_API_KEY")
                if valor:
                    return valor
    return entorno.get("ELEVENLABS_API_KEY", "")


def main(argv: Optional[list[str]] = None, entorno: Optional[dict[str, str]] = None, cliente: Optional[Cliente] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="Imprime el plan y el costo estimado; no usa la llave ni la red.")
    ap.add_argument("--notas-de-voz", action="store_true", help="Suma las notas de voz de los escenarios de chat.")
    ap.add_argument("--solo", help="Escenarios a generar, separados por coma (por defecto, todos los telefónicos).")
    ap.add_argument("--salida", default=str(RAIZ / "demo" / "audio"), help="Carpeta de los audios. Por defecto demo/audio.")
    ap.add_argument("--modelo", default=MODELO, help="Modelo de ElevenLabs. Por defecto %(default)s.")
    ap.add_argument("--voz-femenina", help="Id de una voz de biblioteca para los personajes femeninos.")
    ap.add_argument("--voz-masculina", help="Id de una voz de biblioteca para los personajes masculinos.")
    ap.add_argument("--tope-caracteres", type=int, default=TOPE_CARACTERES, help="Se detiene si el plan pasa de esto. %(default)s.")
    ap.add_argument("--usd-por-mil", type=float, help="Precio de tu plan por mil caracteres, para estimar en dólares.")
    ap.add_argument("--forzar", action="store_true", help="Rehace los audios que ya existen (gasta créditos otra vez).")
    args = ap.parse_args(argv)
    entorno = dict(os.environ if entorno is None else entorno)

    from scamshield.scenarios import cargar

    voces = {"femenina": args.voz_femenina or entorno.get("ELEVENLABS_VOZ_FEMENINA") or VOCES["femenina"],
             "masculina": args.voz_masculina or entorno.get("ELEVENLABS_VOZ_MASCULINA") or VOCES["masculina"]}
    solo = {s.strip() for s in args.solo.split(",") if s.strip()} if args.solo else None
    piezas = reunir(cargar(("es",)), args.notas_de_voz, solo)
    if not piezas:
        print("No hay nada que generar con esos filtros.")
        return 1
    print(plan(piezas, args.modelo, voces, args.usd_por_mil))
    gasto = creditos(piezas, args.modelo)
    if args.dry_run:
        return 0
    if sum(p.caracteres for p in piezas) > args.tope_caracteres:
        print(f"Se detiene: el plan pasa del tope de {args.tope_caracteres} caracteres. Sube --tope-caracteres o usa --solo.")
        return 1
    llave = _cargar_llave(entorno)
    if cliente is None:
        if not llave:
            print("Falta ELEVENLABS_API_KEY (en .env). Con --dry-run se ve el costo sin llave.")
            return 1
        cliente = Cliente(llave)
    try:
        hechos = generar(piezas, cliente, voces, Path(args.salida), args.modelo, args.forzar)
    except ErrorDeVoz as e:
        print(f"Se detiene: {e}")
        return 1
    print(f"Generados {len(hechos)} audios en {args.salida} (hasta ~{gasto:,.0f} créditos).".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
