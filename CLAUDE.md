# CLAUDE.md: Grifter (github.com/mgtapia/grifter; el módulo de Python sigue siendo `scamshield`)

Proyecto para la hackathon de Platanus (36 h, track AI Security). Es un benchmark de estafas chilenas contra agentes de IA que pagan, más una defensa en capas. La tesis y el alcance están en `README.md`; las tareas, en los Issues y en el tablero «Hackathon Platanus» de GitHub.

## Reglas
- **Idioma:** todo en español (código, commits, PR, issues y docs), salvo nombres de APIs externas. Se responde de tú.
- **Llaves:** las llaves de API van solo en `.env`, que escribe Matías. No se leen, no se imprimen y nunca entran al repo. Antes de cada push se revisa que no haya secretos.
- **Nada real:** todo es ficticio, sin dinero, marcas ni sitios reales. El atacante se usa solo dentro de la eval.
- **Nombres de personas** (dueños, familiares, jefes, ejecutivos y personajes de la demo): nombres de pila de gente famosa de tecnología, idealmente fundadores (Sam, Elon, Jensen, Mark, Larry, Sergey, Reed, Melanie, Whitney, Daniela, Anne...). Sin apellidos, fotos ni empresas reales. Lo decidió Matías.
- **Licencias:** lo que se copia de otro proyecto queda atribuido en `NOTICE.md` y en el encabezado del archivo. No se copian datos con licencia NC (como ScamWorld) ni código GPL.
- **Git:** una rama y un PR por issue, con `Closes #n` y los archivos agregados por nombre. Nunca `push --force` a `main`.

## Cómo se verifica
```bash
.venv/Scripts/python -m pytest -q        # sin API: el entorno, la política y la tarea con mockllm
.venv/Scripts/inspect eval scamshield/evals/task.py --model <proveedor/modelo> -T defense=layer2
```
Nada se da por listo sin `pytest` en verde. Si cambias el puntaje, agrega una prueba que lo cubra.

## Mapa
- `scamshield/env/`: el mundo simulado y sus herramientas. Cada texto leído guarda su origen.
- `scamshield/defenses/`:
  - `layer1`: firewall técnico; hoy son reglas de referencia y va a ser Pipelock;
  - `layer2`: política por origen del valor, determinista.
- `scamshield/evals/`: `task.py` (la tarea de Inspect, con estructura de agentdojo) y `puntaje.py`.
- `scamshield/scenarios/{es,en}/`: un YAML por escenario. Cada estafa tiene su par en el otro idioma.
