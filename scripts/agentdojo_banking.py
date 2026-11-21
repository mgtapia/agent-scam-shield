"""Corre AgentDojo banking (inspect_evals) con y sin la capa 2 como approver, y arma la tabla.

La tarea es `inspect_evals/agentdojo` con `workspace=banking` (MIT, UK AISI; port de AgentDojo de
ETH Zürich, MIT; ver NOTICE.md). Se corren cuatro evals:

    defensa      x  ataque
    sin_defensa     con_ataque  (with_injections=True: utilidad bajo ataque y éxito del ataque)
    capa2           sin_ataque  (with_injections=False: utilidad sin ataque; mide los falsos positivos)

En AgentDojo, `security` vale C cuando el ataque LOGRÓ su objetivo, así que en la tabla se reporta
como «éxito del ataque» (ASR) y la seguridad es 1 - ASR.

Uso (con llaves en .env; no se llama a ningún modelo con --dry-run ni con --agente guionado):

    python scripts/agentdojo_banking.py --dry-run
    python scripts/agentdojo_banking.py --model openai/gpt-4o-mini
    python scripts/agentdojo_banking.py --agente guionado        # sin modelo: ejecuta el ground truth
    python scripts/agentdojo_banking.py --solo-tabla --log-dir logs/agentdojo_banking

Requiere el extra opcional: pip install -e ".[agentdojo]" (instala inspect-evals[agentdojo]).
inspect_evals se importa solo al correr, no al cargar este módulo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DEFENSAS = ("sin_defensa", "capa2")
ATAQUES = {"con_ataque": True, "sin_ataque": False}
LOG_DIR = "logs/agentdojo_banking"
MODELO_GUIONADO = "mockllm/model"


def _lista_ids(texto: str | None) -> list[int] | None:
    if not texto:
        return None
    return [int(x) for x in texto.split(",") if x.strip()]


def plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Las evals que se van a correr, sin importar inspect_evals."""
    corridas = []
    for defensa in DEFENSAS:
        for ataque, con_inyecciones in ATAQUES.items():
            corridas.append({
                "nombre": f"{defensa}__{ataque}",
                "defensa": defensa,
                "ataque": ataque,
                "task_args": {
                    "workspace": "banking",
                    "with_sandbox_tasks": "no",
                    "with_injections": con_inyecciones,
                    "user_task_ids": _lista_ids(args.user_tasks),
                    "injection_task_ids": _lista_ids(args.injection_tasks),
                },
                "approval": 'politicas_capa2("agentdojo_banking")' if defensa == "capa2" else None,
                "agente": args.agente,
                "modelo": MODELO_GUIONADO if args.agente == "guionado" else args.model,
                "log_dir": str(Path(args.log_dir) / f"{defensa}__{ataque}"),
            })
    return corridas


def _agente_guionado():
    """Ejecuta las llamadas del ground truth de AgentDojo pasando por la aprobación de Inspect.

    Adaptado de inspect_evals/agentdojo/agents/ground_truth_agent.py (MIT, UK AISI): el original
    llama a `execute_tools` solo con el último mensaje, así que un approver no vería el pedido del
    usuario ni los resultados anteriores. Aquí se le pasa la conversación completa.
    """
    from inspect_ai.model import ChatCompletionChoice, ChatMessageAssistant, ModelOutput, execute_tools
    from inspect_ai.solver import Generate, TaskState, solver

    @solver
    def agente_guionado():
        async def solve(state: TaskState, generate: Generate) -> TaskState:
            tarea = state.metadata.get("injection_task") or state.metadata["user_task"]
            for llamada in tarea.ground_truth(state.metadata["pre_environment"]):
                state.messages.append(ChatMessageAssistant(
                    content=f"Llamada del ground truth: {llamada.function}", tool_calls=[llamada]))
                resultado = await execute_tools(state.messages, state.tools)
                state.messages.extend(resultado.messages)
            salida = getattr(tarea, "GROUND_TRUTH_OUTPUT", "") or "Listo."
            final = ChatMessageAssistant(content=salida)
            state.messages.append(final)
            state.output = ModelOutput(model="guionado", choices=[ChatCompletionChoice(message=final)])
            return state
        return solve

    return agente_guionado()


def correr(corridas: list[dict[str, Any]], limit: int | None) -> None:
    try:
        from inspect_evals.agentdojo import agentdojo
    except ImportError as e:
        sys.exit(f"Falta inspect_evals con AgentDojo ({e}). Instala: pip install -e \".[agentdojo]\"")
    from inspect_ai import eval as inspect_eval
    from inspect_ai import task_with

    from scamshield.defenses.approver import politicas_capa2

    for c in corridas:
        tarea = agentdojo(**c["task_args"])
        cambios: dict[str, Any] = {
            "approval": politicas_capa2("agentdojo_banking") if c["defensa"] == "capa2" else None,
            "name": f"agentdojo_banking__{c['nombre']}",
            "metadata": {**(tarea.metadata or {}), "defensa": c["defensa"], "ataque": c["ataque"],
                         "agente": c["agente"]},
        }
        if c["agente"] == "guionado":
            cambios["solver"] = _agente_guionado()
        tarea = task_with(tarea, **cambios)
        print(f"== {c['nombre']} ({c['modelo']}) -> {c['log_dir']}")
        inspect_eval(tarea, model=c["modelo"], log_dir=c["log_dir"], limit=limit, display="plain")


# --- Tabla desde los logs ---

def _ultimo_log(directorio: Path):
    from inspect_ai.log import list_eval_logs, read_eval_log

    logs = sorted(list_eval_logs(str(directorio)), key=lambda i: i.mtime or 0)
    return read_eval_log(logs[-1]) if logs else None


def _resumen(log) -> dict[str, Any]:
    utilidad, exito_ataque, bloqueos = [], [], 0
    utiles: dict[str, bool] = {}
    for s in log.samples or []:
        if not s.scores:
            continue
        valor = next(iter(s.scores.values())).value
        if "utility" in valor:
            utilidad.append(valor["utility"] == "C")
            utiles[str(s.id)] = valor["utility"] == "C"
        if "security" in valor:
            exito_ataque.append(valor["security"] == "C")
        bloqueos += sum(1 for e in s.events
                        if e.event == "approval" and e.approver == "capa2" and e.decision == "reject")

    def tasa(xs: list[bool]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    return {"n": len(log.samples or []), "utilidad": tasa(utilidad), "asr": tasa(exito_ataque),
            "bloqueos": bloqueos, "utiles": utiles}


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f} %"


def tabla(log_dir: str) -> str:
    raiz = Path(log_dir)
    res: dict[tuple[str, str], dict[str, Any]] = {}
    for defensa in DEFENSAS:
        for ataque in ATAQUES:
            log = _ultimo_log(raiz / f"{defensa}__{ataque}")
            if log is not None:
                res[(defensa, ataque)] = _resumen(log)

    filas = ["| Defensa | Utilidad sin ataque | Utilidad con ataque | Éxito del ataque (ASR) "
             "| Seguridad (1 - ASR) | Rechazos de la capa 2 | Muestras |",
             "|---|---|---|---|---|---|---|"]
    for defensa in DEFENSAS:
        sin = res.get((defensa, "sin_ataque"), {})
        con = res.get((defensa, "con_ataque"), {})
        asr = con.get("asr")
        filas.append(
            f"| {defensa} | {_pct(sin.get('utilidad'))} | {_pct(con.get('utilidad'))} | {_pct(asr)} "
            f"| {_pct(None if asr is None else 1 - asr)} "
            f"| {sin.get('bloqueos', 0) + con.get('bloqueos', 0)} "
            f"| {sin.get('n', 0)} + {con.get('n', 0)} |")

    # Tareas legítimas que la capa 2 frena: útiles sin defensa y no útiles con la capa 2, sin ataque.
    base = res.get(("sin_defensa", "sin_ataque"), {}).get("utiles", {})
    capa2 = res.get(("capa2", "sin_ataque"), {}).get("utiles", {})
    frenadas = sorted(k for k, ok in base.items() if ok and capa2.get(k) is False)
    salida = "\n".join(filas)
    salida += "\n\nTareas legítimas que la capa 2 frena (sin ataque): " + (", ".join(frenadas) or "ninguna")
    return salida


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--model", default=None, help="modelo de Inspect, por ejemplo openai/gpt-4o-mini")
    p.add_argument("--agente", choices=["modelo", "guionado"], default="modelo",
                   help="modelo: el agente por defecto de AgentDojo; guionado: ejecuta el ground truth sin modelo")
    p.add_argument("--log-dir", default=LOG_DIR)
    p.add_argument("--limit", type=int, default=None, help="máximo de muestras por eval")
    p.add_argument("--user-tasks", default=None, help="ids de tareas de usuario, por ejemplo 0,5,10")
    p.add_argument("--injection-tasks", default=None, help="ids de tareas de inyección, por ejemplo 0,7")
    p.add_argument("--dry-run", action="store_true", help="muestra qué correría, sin importar inspect_evals")
    p.add_argument("--solo-tabla", action="store_true", help="no corre nada: arma la tabla desde --log-dir")
    args = p.parse_args(argv)

    if not args.solo_tabla and args.agente == "modelo" and not args.model and not args.dry_run:
        p.error("falta --model (o usa --agente guionado para correr sin modelo)")

    corridas = plan(args)
    if args.dry_run:
        for c in corridas:
            print(f"{c['nombre']}: inspect_evals/agentdojo {c['task_args']} approval={c['approval']} "
                  f"agente={c['agente']} modelo={c['modelo']} log_dir={c['log_dir']}")
        return
    if not args.solo_tabla:
        correr(corridas, args.limit)
    texto = tabla(args.log_dir)
    print(texto)
    Path(args.log_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.log_dir) / "tabla.md").write_text(texto + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
