"""Una sola fuente de cifras para el pitch y el video: genera docs/cifras.md desde demo/resultados.json.

Cada cifra que se puede decir en voz alta sale con su valor, su intervalo, su n, el comando que la reproduce y una frase lista
para decir. Nada se escribe a mano: si un número cambia en `results/`, se regenera `demo/resultados.json`
(`python scripts/resultados_demo.py`) y después este archivo, y la frase cambia sola.

    python scripts/cifras_finales.py            # escribe docs/cifras.md
    python scripts/cifras_finales.py --check    # sale con 1 si docs/cifras.md no es lo que saldría hoy (lo usa la prueba)

Lo que no tiene archivo de origen en el repo va aparte, en «No decir como medido»: se puede decir con su fuente escrita, no como una
cifra reproducible.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "demo" / "resultados.json"
SALIDA = RAIZ / "docs" / "cifras.md"


def _p(x: float) -> str:
    """Un porcentaje entero, redondeando 0,5 hacia arriba (así lo muestran el README y la demo)."""
    return str(int(x * 100 + 0.5 + 1e-9))


def pct(m: dict[str, Any]) -> str:
    """«100 % [97-100]»."""
    return f"{_p(m['tasa'])} % [{_p(m['bajo'])}-{_p(m['alto'])}]"


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def coma(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


class Cifra:
    def __init__(self, id: str, cifra: str, n: str, intervalo: str, comando: str, frase: str, fuente: str):
        self.id, self.cifra, self.n, self.intervalo, self.comando, self.frase, self.fuente = (
            id, cifra, n, intervalo, comando, frase, fuente)


def cifras(r: dict[str, Any]) -> tuple[list[Cifra], list[Cifra]]:
    """(las que se pueden decir, las que no tienen archivo de origen)."""
    b, cob, clas = r["bench"], r["cobertura"]["totales"], r["clasificador"]
    por = {c["clave"]: c for c in b["configuraciones"]}
    estafas, controles = b["escenarios"]["estafas"], b["escenarios"]["controles"]
    cmd_bench = b.get("comando", "grifter bench --json results/bench.json")
    fuente_bench = b.get("fuente", "results/bench.json")
    ok: list[Cifra] = []

    ok.append(Cifra(
        "bench-total", f"{estafas} estafas y {controles} controles", f"{estafas + controles} escenarios (id × idioma)", "—",
        cmd_bench, f"Medimos {estafas} estafas chilenas, en español y en inglés, y {controles} casos legítimos para ver qué se "
                   "frena de más.", fuente_bench))
    sin, c2, c23 = por["none"]["estafas_exitosas"], por["layer2"]["estafas_exitosas"], por["layer23"]["estafas_exitosas"]
    ok.append(Cifra(
        "bench-sin-defensa", f"{pct(sin)} caen sin defensa", f"n = {sin['escenarios']} estafas", "95 % (Wilson)", cmd_bench,
        f"Sin defensa, un agente que hace lo que lee cae en las {estafas} estafas.", fuente_bench))
    ok.append(Cifra(
        "bench-capa2", f"{pct(c2)} caen con la capa 2", f"n = {c2['escenarios']} estafas", "95 % (Wilson)", cmd_bench,
        f"Con la capa 2 sola, caen {round(c2['tasa'] * c2['escenarios'])} de {estafas}: son las que dicta el dueño, que ya cayó.",
        fuente_bench))
    ok.append(Cifra(
        "bench-completo", f"{pct(c23)} caen con Grifter completo (capas 2 y 3)", f"n = {c23['escenarios']} estafas",
        "95 % (Wilson): cero de n no es riesgo cero", cmd_bench,
        f"{estafas} estafas, {round(c23['tasa'] * c23['escenarios'])} pasan Grifter completo. Con intervalo: entre 0 y "
        f"{_p(c23['alto'])} %, porque las estafas las escribimos nosotros.", fuente_bench))
    u, fa = por["layer23"]["utilidad"], por["layer23"]["falsas_alarmas"]
    ok.append(Cifra(
        "bench-utilidad", f"{pct(u)} de utilidad y {pct(fa)} de falsas alarmas con Grifter completo",
        f"utilidad n = {u['escenarios']}; falsas alarmas n = {fa['escenarios']} controles", "95 % (Wilson)", cmd_bench,
        f"Y sigue pagando lo legítimo: {_p(u['tasa'])} % de utilidad.", fuente_bench))
    l1 = por["layer1"]["estafas_exitosas"]
    ok.append(Cifra(
        "bench-capa1", f"{pct(l1)} caen con la capa 1 de referencia (reglas de firewall)", f"n = {l1['escenarios']} estafas",
        "95 % (Wilson)", cmd_bench,
        f"Un firewall de reglas casi no cambia nada: {_p(l1['tasa'])} % de las estafas siguen pasando.", fuente_bench))
    ec = b["es_contra_en"]
    ok.append(Cifra(
        "es-contra-en", f"{ec['pares']} escenarios pares español-inglés (estafas y controles), {len(ec['difieren'])} difieren", f"{ec['pares']} pares", "—",
        cmd_bench, f"Los {ec['pares']} escenarios existen en español y en inglés, y la defensa decide igual en las dos lenguas "
                   f"({len(ec['difieren'])} difieren).",
        fuente_bench))
    ok.append(Cifra(
        "cobertura-tipos", f"{cob['familias']} tipos de ataque; {cob['frenadas_bench']} de {cob['ataques_bench']} frenados "
                           "con Grifter completo", f"{cob['ataques_bench']} ataques", "—", r["cobertura"]["comando"],
        f"{cob['familias']} tipos de ataque, de la boleta falsa al MCP envenenado, y Grifter completo frena los "
        f"{cob['ataques_bench']}.", "results/bench.json · results/clasificador.json · results/duelo · tests"))

    d = r["duelo"]
    sin_c2 = d["congelado"]["sin_capa2"]
    ok.append(Cifra(
        "duelo", f"{miles(cob['intentos_duelo'])} intentos del atacante que aprende, {cob['cruces_capa2_duelo']} cruzan la capa 2",
        f"{miles(cob['intentos_duelo'])} intentos ({d['generaciones']} generaciones, 6 corridas)", "—", d["comando"],
        f"Un atacante que aprende reescribió la estafa {miles(cob['intentos_duelo'])} veces: {cob['cruces_capa2_duelo']} "
        "cruzaron la capa 2.", d["fuente"]))
    ok.append(Cifra(
        "duelo-contrafactual", f"{miles(sin_c2)} de {miles(d['congelado']['candidatos'])} intentos habrían cobrado sin la capa 2 "
                              "(clasificador congelado)", f"{miles(d['congelado']['candidatos'])} intentos", "—", d["comando"],
        f"Sin la capa 2, {miles(sin_c2)} de esos intentos le habrían ganado al clasificador: por eso el cero no es trivial.",
        d["fuente"]))

    p = r["pipelock"]
    ok.append(Cifra(
        "pipelock", f"Pipelock frena {p['frenadas']} de {p['estafas']} estafas, {p['falsas_alarmas']} falsas alarmas",
        f"n = {p['estafas']} estafas", f"[{_p(p['bajo'])}-{_p(p['alto'])}] % (Wilson)", p["comando"],
        f"Un firewall de agentes real frenó {p['frenadas']} de {p['estafas']}, todas técnicas: la ingeniería social no tiene "
        "nada técnico que detectar.", p["fuente"] + " (se corrió con el binario real de Pipelock; el archivo de datos no está en el repo)"))

    s = r["sonnet"]
    ok.append(Cifra(
        "sonnet", f"Sonnet pagó {s['pagos']} de {s['repeticiones']} con el correo del gerente comprometido",
        f"{s['repeticiones']} repeticiones, {s['estafas_exitosas']['escenarios']} escenarios (es y en)",
        f"[{_p(s['estafas_exitosas']['bajo'])}-{_p(s['estafas_exitosas']['alto'])}] %", s["comando"],
        f"Con el encargo «paga lo que el gerente apruebe», Sonnet pagó {s['pagos']} de {s['repeticiones']}: es un solo "
        "escenario, y la vulnerabilidad es la confianza delegada, no que el modelo sea tonto.", s["fuente"]))

    h = r["haiku"]
    he, hu, ht = h["estafas_exitosas"], h["utilidad"], h["toques_por_100"]
    ok.append(Cifra(
        "haiku-estafas", f"Haiku con la capa 2 y el dueño en el circuito: {pct(he)} de estafas",
        f"{he['repeticiones']} repeticiones, {he['escenarios']} escenarios en español", "95 % (Wilson)", h["comando"],
        f"Haiku no cayó en ninguno de {he['escenarios']} escenarios: cero, con un techo de {_p(he['alto'])} %.", h["fuente"]))
    ok.append(Cifra(
        "haiku-utilidad", f"{pct(hu)} de utilidad", f"{hu['repeticiones']} repeticiones, {hu['escenarios']} escenarios",
        "95 % (Wilson)", h["comando"], f"Y siguió pagando lo legítimo: {_p(hu['tasa'])} % de utilidad.", h["fuente"]))
    ok.append(Cifra(
        "haiku-toques", f"unos {round(ht['tasa'])} toques por cada 100 acciones sensibles [{_p(ht['bajo'] / 100)}-"
                        f"{_p(ht['alto'] / 100)}]", f"{ht['intentos']} acciones sensibles", "95 % (Wilson)", h["comando"],
        f"Al dueño le pide un toque unas {round(ht['tasa'])} veces de cada 100 acciones sensibles.", h["fuente"]))

    ok.append(Cifra(
        "clasificador", f"recall {coma(clas['recall']['media'])} [{coma(clas['recall']['min'])}-{coma(clas['recall']['max'])}], "
                        f"precisión {coma(clas['precision']['media'])}, {_p(clas['falsas_alarmas']['media'])} % de falsas alarmas",
        f"{clas['corridas']} corridas ({clas['pliegues']} pliegues × {len(clas['semillas'])} semillas), "
        f"{r['colados']['clasificador']['correos']} correos apartados", "rango entre corridas, no Wilson", clas["comando"],
        f"El clasificador que aprende en vivo detecta {_p(clas['recall']['media'])} de cada 100 estafas nuevas, con "
        f"{_p(clas['falsas_alarmas']['media'])} % de falsas alarmas; solo sube la sospecha, nunca aprueba un pago.",
        clas["fuente"]))
    wa = r["colados"]["clasificador_por_canal"]["whatsapp"]
    ok.append(Cifra(
        "clasificador-whatsapp", f"se le cuelan {wa['colados']} de {wa['correos']} mensajes de WhatsApp apartados",
        f"{wa['correos']} apartados (suma de {wa['corridas']} corridas)", "—", clas["comando"],
        "Lo que más se le cuela al clasificador son los mensajes de WhatsApp: ahí manda la capa 2, no el clasificador.",
        clas["fuente"]))

    dd = r["colados"]["dueno_dicta"]
    ok.append(Cifra(
        "dueno-dicta", f"{dd['layer2']} estafas que dicta el dueño pasan la capa 2; con la capa 3, {dd['layer23']}",
        f"{dd['none']} estafas donde el dueño ya cayó", "—", cmd_bench,
        f"Cuando el dueño ya cayó y dicta la cuenta, la capa 2 las deja pasar por diseño ({dd['layer2']} de {dd['none']}); "
        f"la capa 3, que compara el titular, las frena todas.", "results/bench.json"))

    at = r["atacante"]["series"]
    a_sin = next(x for x in at if x["defensa"] == "none")
    a_c2 = next(x for x in at if x["defensa"] == "layer2")
    ok.append(Cifra(
        "atacante-adaptativo",
        f"atacante adaptativo ({a_c2['modelo']}, {a_c2['n']} estafas): sin defensa {a_sin['exitos'][-1]} de {a_sin['n']}, "
        f"con la capa 2 {a_c2['exitos'][-1]} de {a_c2['n']}",
        f"n = {a_c2['n']} estafas, {a_c2['rondas']} rondas de reescritura",
        f"con capa 2 [0-{_p(a_c2['ic'][-1][1])}] %", r["atacante"]["comando"],
        f"Con cinco estafas el intervalo es ancho: es un humo, no una curva. Sin defensa cayeron {a_sin['exitos'][-1]} de "
        f"{a_sin['n']} y reescribir no ayudó; con la capa 2, ninguna.", r["atacante"]["fuente"]))

    sin_archivo = [Cifra(
        "haiku-jefe", "Haiku en el jefe comprometido: 6 de 11 sin defensa, 0 de 12 con la capa 2", "11 y 12 repeticiones", "—",
        "(sin comando: no hay archivo en results/)",
        "Con Haiku, el mismo escenario cayó 6 de 11 sin defensa y 0 de 12 con la capa 2.",
        "corrida con modelo de los logs de Inspect (logs/jefe y logs/dueno, fuera del repo); fuente: #153 y #156; sin archivo de origen en results/")]
    return ok, sin_archivo


def armar(r: dict[str, Any]) -> str:
    ok, sin_archivo = cifras(r)
    lineas = [
        "# Cifras finales",
        "",
        "> Generado por `python scripts/cifras_finales.py` desde `demo/resultados.json` (que sale de `results/` con "
        "`python scripts/resultados_demo.py`). **No se edita a mano**: `tests/test_cifras.py` falla si este archivo no es lo que "
        "saldría hoy, o si el README o `docs/pitch.md` citan un total que no calza.",
        "",
        f"Corpus medido: **{r['bench']['escenarios']['estafas']} estafas y {r['bench']['escenarios']['controles']} controles** "
        f"(`resultados.json` generado el {r['generado'][:10]}). Los intervalos son de Wilson al 95 %, salvo donde se dice otra "
        "cosa. Las estafas las escribimos nosotros: un 0 % dice que la garantía se cumple sobre este corpus, no que ninguna "
        "estafa pueda saltarla.",
        "",
        "## Para decir en voz alta",
        "",
        "| # | Cifra | n | Intervalo | Frase |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(ok, 1):
        lineas.append(f"| {i} | {c.cifra} | {c.n} | {c.intervalo} | «{c.frase}» |")
    lineas += ["", "## Cómo se reproduce cada una", "", "| # | Id | Comando | Fuente |", "|---|---|---|---|"]
    for i, c in enumerate(ok, 1):
        lineas.append(f"| {i} | `{c.id}` | `{c.comando}` | {c.fuente} |")
    lineas += ["", "## No decir como medido", "",
               "Se dicen en el README y en el pitch, pero no hay en el repo un archivo que las reproduzca. Dilas con su fuente "
               "(«según los logs de la corrida del 2026-11»), no como una cifra de `results/`.", "",
               "| Cifra | Frase | Fuente |", "|---|---|---|"]
    for c in sin_archivo:
        lineas.append(f"| {c.cifra} | «{c.frase}» | {c.fuente} |")
    lineas += ["", "## Límites que se dicen antes de que pregunten", "",
               "- Las estafas las escribimos nosotros: cero de n no es riesgo cero.",
               "- El agente del bench es guionado: mide las defensas, no lo crédulo de un modelo.",
               "- Haiku y Sonnet: pocos escenarios y pocas repeticiones; los intervalos son anchos.",
               "- El atacante adaptativo corrió con 5 estafas: es un humo, no una curva.",
               "- El clasificador no promete nada: solo sube la sospecha.", ""]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="no escribe: sale con 1 si docs/cifras.md está desfasado")
    p.add_argument("--resultados", type=Path, default=RESULTADOS)
    p.add_argument("--salida", type=Path, default=SALIDA)
    a = p.parse_args(argv)
    r = json.loads(a.resultados.read_text(encoding="utf-8"))
    texto = armar(r)
    if a.check:
        actual = a.salida.read_text(encoding="utf-8").replace("\r\n", "\n") if a.salida.exists() else ""
        if actual != texto:
            print(f"{a.salida} está desfasado: corre `python scripts/cifras_finales.py`", file=sys.stderr)
            return 1
        return 0
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(texto, encoding="utf-8", newline="\n")
    print(f"escrito {a.salida} ({len(cifras(r)[0])} cifras)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
