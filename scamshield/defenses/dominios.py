"""Credenciales atadas a su dominio oficial, como un gestor de contraseñas (#128).

Un agente que navega no «comparte» la clave: la **escribe en el formulario** de una página. Si esa página es un clon
(el banco clonado por SMS, un homoglifo con HTTPS válido, un anuncio patrocinado que lleva al clon), la clave sale igual.
Esta regla cierra ese hueco: toda herramienta que manda texto a la web (`escribir_formulario`, `enviar_formulario`, o
`abrir_web` con la clave en la dirección) se revisa, y si lo que sale es un dato del dueño atado a un dominio, el destino
tiene que ser **exactamente** ese dominio.

- El dueño declara, por cada dato, los dominios donde puede escribirse (`dominios`: `clave_banca: [banca.bancolitoral.cl]`).
  Un subdominio vale solo si está declarado.
- Una credencial (la que el nombre delata o la que el dueño declara) sin dominio declarado no sale a ninguna página.
- No cuentan como el dominio oficial: los homoglifos (`bancoIitoral.cl`, con i mayúscula en vez de ele), el punycode
  (`xn--...`), cualquier dominio con caracteres que no sean ASCII, los dominios parecidos y los subdominios no declarados.
- **El candado HTTPS no cuenta.** Un clon con certificado válido se retiene igual: la regla mira el dominio, no el
  certificado ni el texto de la página.
- Una dirección con trucos (`https://bancolitoral.cl@clon.cl`, barras invertidas, espacios o caracteres de control) se
  lee como lo que haría un navegador, y ante la duda no es el dominio oficial.

La alerta explica el porqué: «Tu agente intentó escribir la clave banca en bancolitoral-seguro.cl, no en
bancolitoral.cl».

Límite honesto: se revisa lo que el agente manda por estas herramientas. Un dato escrito en el camino de una dirección
sin parámetros, o dictado por otra vía (una llamada, un mensaje), lo cubren las otras reglas de la capa 2.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlsplit

from ..env.world import claves_de_credencial

HERRAMIENTAS_WEB = {"abrir_web", "escribir_formulario", "enviar_formulario"}

_HOST_VALIDO = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")
_URL = re.compile(r"(?:https?:)?//[^\s\"'<>]+", re.IGNORECASE)
_CLAVES_URL = ("url", "uri", "href", "link", "action", "destino", "sitio", "pagina", "site", "page")


def host_de(direccion: object) -> Optional[str]:
    """El host al que iría un navegador con esta dirección, en minúsculas; None si no se puede decir con certeza.

    Sin esquema (`bancolitoral.cl/login`) se lee igual. Con usuario (`https://bancolitoral.cl@clon.cl`) el host es lo
    que va después de la arroba. Una barra invertida, un espacio o un carácter de control hacen que navegadores y
    bibliotecas lean cosas distintas: ahí no se confía y se devuelve None.
    """
    texto = str(direccion or "").strip()
    if not texto or "\\" in texto or any(ord(c) < 33 or ord(c) == 127 for c in texto):
        return None
    if "://" not in texto and not texto.startswith("//"):
        texto = "//" + texto
    try:
        partes = urlsplit(texto)
        host = partes.hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.rstrip(".").lower() or None


def forma_visible(host: str) -> str:
    """El host tal como se vería escrito con letras ASCII: lo que no lo es, en punycode (`xn--`)."""
    if host.isascii():
        return host
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host.encode("ascii", "backslashreplace").decode("ascii")


def _normalizar_oficial(dominio: object) -> Optional[str]:
    host = host_de(dominio)
    return host if host and host.isascii() and _HOST_VALIDO.match(host) else None


def es_dominio_oficial(host: Optional[str], oficiales: Iterable[object]) -> bool:
    """El host es exactamente uno de los oficiales. Sin comodines, sin subdominios, sin homoglifos, sin punycode."""
    if not host or not host.isascii() or not _HOST_VALIDO.match(host):
        return False
    return host in {o for o in (_normalizar_oficial(d) for d in oficiales) if o}


def hosts_en(args: Mapping[str, Any], destino: Optional[str] = None) -> list[str]:
    """Los hosts a los que apuntan los argumentos de una llamada (la dirección o direcciones que lleva).

    Si `destino` nombra un argumento, vale ese. Si no, los argumentos con nombre de dirección (`url`, `href`...) y,
    si no hay ninguno, cualquier texto con esquema (`https://...`). Un host ilegible se anota como cadena vacía: no
    es el oficial.
    """
    candidatos: list[str] = []
    if destino and destino in args and args[destino] not in (None, ""):
        candidatos.append(str(args[destino]))
    else:
        for k, v in args.items():
            if str(k).lower() in _CLAVES_URL and isinstance(v, str) and v.strip():
                candidatos.append(v)
        if not candidatos:
            for texto in _textos(args):
                candidatos += [m.group(0) for m in _URL.finditer(texto)]
    vistos: list[str] = []
    for c in candidatos:
        h = host_de(c) or ""
        if h not in vistos:
            vistos.append(h)
    return vistos


def _textos(valor: Any) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, Mapping):
        return [t for k, v in valor.items() for t in [str(k), *_textos(v)]]
    if isinstance(valor, (list, tuple, set)):
        return [t for v in valor for t in _textos(v)]
    return [] if valor is None else [str(valor)]


def _esqueleto(host: str) -> str:
    """El host como lo lee el ojo: las letras que se confunden (i, l, 1, |, 0, o, rn y m) se igualan."""
    s = unicodedata.normalize("NFKD", forma_visible(host)).encode("ascii", "ignore").decode("ascii").lower()
    s = s.replace("rn", "m").replace("vv", "w")
    return "".join({"1": "l", "i": "l", "|": "l", "0": "o"}.get(c, c) for c in s)


def parece_al_oficial(host: str, oficial: str) -> bool:
    return (_esqueleto(host) == _esqueleto(oficial) or _esqueleto(oficial).split(".")[0] in _esqueleto(host)
            or difflib.SequenceMatcher(None, _esqueleto(host), _esqueleto(oficial)).ratio() >= 0.75)


def _legible(clave: str) -> str:
    return clave.replace("_", " ").strip()


def datos_llevados(procedencia: Any, args: Mapping[str, Any]) -> list[str]:
    """Las claves de `datos_dueno` atadas a un dominio (o credenciales) cuyo valor va en los argumentos."""
    from .layer2 import _norm, _variantes   # import tardío: layer2 importa este módulo

    datos = procedencia.datos_dueno
    dominios: Mapping[str, Iterable[object]] = getattr(procedencia, "dominios", None) or {}
    claves = claves_de_credencial(datos, getattr(procedencia, "credenciales", ())) | {k for k in dominios if k in datos}
    junto = " ".join(_textos(dict(args)))
    llevadas = []
    for clave in sorted(claves):
        valor = _norm(datos[clave])
        if len(valor) >= 4 and (valor in _norm(junto) or any(valor in v for v in _variantes(junto))):
            llevadas.append(clave)
    return llevadas


def revisar_web(procedencia: Any, herramienta: str, args: Mapping[str, Any],
                destino: Optional[str] = None) -> Optional[str]:
    """None si la llamada puede seguir; si no, el motivo de la retención.

    `procedencia` aporta `datos_dueno` y, opcionalmente, `dominios` (clave -> dominios oficiales), `credenciales` y
    `pagina_actual` (a dónde irían los datos si la llamada no trae dirección).
    """
    dominios: Mapping[str, Iterable[object]] = getattr(procedencia, "dominios", None) or {}
    llevadas = datos_llevados(procedencia, args)
    if not llevadas:
        return None
    hosts = hosts_en(args, destino)
    if not hosts:
        pagina = getattr(procedencia, "pagina_actual", None)
        hosts = [host_de(pagina) or ""] if pagina else [""]
    for clave in llevadas:
        oficiales = [str(d) for d in (dominios.get(clave) or [])]
        for host in hosts:
            if es_dominio_oficial(host, oficiales):
                continue
            return _motivo(clave, host, oficiales)
    return None


def _motivo(clave: str, host: str, oficiales: list[str]) -> str:
    que = _legible(clave)
    if not host:
        donde = "una página que no se pudo identificar"
    else:
        visible = forma_visible(host)
        donde = visible if visible == host else f"{visible} (con caracteres que no son ASCII)"
    validos = [o for o in (_normalizar_oficial(d) for d in oficiales) if o]
    if not validos:
        return (f"Tu agente intentó escribir {que} en {donde}, y no hay un dominio oficial declarado para ese dato: "
                "una credencial no sale a ninguna página sin él.")
    oficial = ", ".join(validos)
    parecido = ""
    if host and any(parece_al_oficial(host, o) for o in validos):
        parecido = " Se parece al oficial, pero no es el mismo."
    return f"Tu agente intentó escribir {que} en {donde}, no en {oficial}.{parecido}"
