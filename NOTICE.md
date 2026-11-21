# Atribuciones

Grifter se publica con licencia MIT. Reutiliza ideas, estructura o código de estos proyectos abiertos, cuyas licencias se respetan:

| Proyecto | Licencia | Qué tomamos |
|---|---|---|
| [inspect_evals / agentdojo](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/agentdojo). Copyright (c) 2024 UK AI Security Institute. Port de [AgentDojo](https://github.com/ethz-spylab/agentdojo) (ETH Zürich, MIT) | MIT | La estructura de la tarea de Inspect: un solver que arma el mundo en el store, herramientas sobre ese store y un puntaje con seguridad y utilidad separadas. `scripts/agentdojo_banking.py` corre su tarea `agentdojo` (banking) como dependencia opcional y adapta su `ground_truth_agent` para que el approver vea la conversación completa |
| [FraudBench](https://github.com/leanmcp/fraudbench). Copyright (c) 2025 Sierra Research | MIT | El formato de anotación de las tareas: mecanismo de fraude, tácticas de ingeniería social, evidencia observable y acciones permitidas y prohibidas |
| [PAIR / JailbreakingLLMs](https://github.com/patrickrchao/JailbreakingLLMs). Copyright (c) 2023 PAIR Team | MIT | El formato del atacante iterativo (mejora y nuevo intento en JSON), adaptado a estafas |
| [SpaPhish](https://data.mendeley.com/datasets/hz2d6gz7pc) | CC BY 4.0 | Correos de phishing en español para calibrar el clasificador. No se incluyen en el repo: se descargan con un script |
| [Pipelock](https://github.com/pipelab-org/pipelock). Copyright 2026 Joshua Waldrep | Apache-2.0 (núcleo). Los binarios oficiales incluyen además código ELv2 de `enterprise/` | Capa 1: el firewall se usa como un proceso aparte (su API `/api/v1/scan` y `pipelock mcp scan`), sin copiar su código ni redistribuir su binario. `scamshield/defenses/pipelock.py` es un cliente propio. Probado con v3.8.0 |
| [ScamWorld](https://github.com/wuyoscar/scamworld-bench) | Código Apache-2.0; datos CC BY-NC 4.0 | Solo su taxonomía de estafas, como referencia. No copiamos sus datos |

Los textos de licencia completos están en cada repositorio de origen. Si un archivo de este repo copia código de alguno de ellos, lo dice en su encabezado.

## Skills de Claude Code de terceros

Las carpetas de `.claude/skills/` son copias de skills de otros proyectos, fijadas a un commit exacto. Cada carpeta trae su archivo de licencia; si el original la tenía solo en la raíz del repo, copiamos ese archivo dentro de la carpeta. No agregamos encabezados a los archivos copiados: el `SKILL.md` tiene que empezar con su frontmatter (`---`) para que Claude Code lo cargue, y los scripts quedan tal cual. La atribución de cada archivo es la licencia de su carpeta más esta tabla.

| Repositorio | Licencia | Commit | Skills |
|---|---|---|---|
| [UKGovernmentBEIS/inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals/tree/c2d3d5e1335c07fb8032bcfc7869e9437e635c4c/.claude/skills). Copyright (c) 2024 UK AI Security Institute | MIT (`LICENSE` de la raíz, copiado en cada carpeta) | `c2d3d5e1335c07fb8032bcfc7869e9437e635c4c` | `create-eval`, `eval-validity-review` |
| [anthropics/skills](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills), de Anthropic | Apache-2.0 (`LICENSE.txt` propio de cada carpeta; en ese repo la licencia va por carpeta) | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` | `webapp-testing`, `frontend-design` |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/ec59a29a03d5c40f73ab40878df04860bc00e876/skills). Copyright (c) 2025 K-Dense Inc. | MIT (`LICENSE.md` de la raíz, copiado en cada carpeta) | `ec59a29a03d5c40f73ab40878df04860bc00e876` | `matplotlib`, `scientific-visualization` |

Notas:
- El frontmatter de `matplotlib/SKILL.md` dice `license:` con un enlace a la licencia de Matplotlib. Esa es la licencia de la biblioteca, no la de la skill: la skill está bajo la MIT de K-Dense.
- `verify-scoring-change` de inspect_evals no se copió: uno de sus pasos lee el `.env` del checkout, y este proyecto no lee `.env`.
- Único cambio respecto del original: en `matplotlib` y `scientific-visualization` quitamos la línea `allowed-tools` del frontmatter, que pre-aprobaba Bash mientras la skill está activa.
