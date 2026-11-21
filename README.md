# ¡Hola Platanus!

# Grifter

**Red-teaming y escudo para agentes de IA que pagan.**

**¿Caen los agentes de IA que pagan por nosotros en las estafas de siempre? ¿Caen más en español? ¿Las defensas actuales lo ven?**

Proyecto para la hackathon de Platanus, track **AI Security**, en la línea *Guardrails & adversarial robustness*.

> *English summary:* a benchmark of Chilean, Spanish-language social-engineering scams against payment-capable AI agents, with English counterparts, plus a layered defense: an open-source agent firewall as layer 1 and our provenance-based monitor as layer 2. We measure attack success by language, model and defense configuration, including against an adaptive attacker.

## La tesis
1. Los agentes ya pagan por las personas: Visa Intelligent Commerce, Mastercard Agent Pay, tarjetas dentro de ChatGPT.
2. Un estafador ya no necesita convencer a una persona: le basta con engañar a su agente. Una boleta falsa o un «cambio de cuenta del proveedor» no tienen nada técnico que detectar.
3. Los firewalls de agentes que existen, como Pipelock, mcp-watchdog o Snyk Agent Scan, buscan inyección técnica, herramientas MCP envenenadas y fuga de credenciales. Nuestra hipótesis es que no ven la ingeniería social.
4. Los benchmarks de estafas contra agentes (SEA, AgentPhishing, FraudBench) están en inglés. Para español y para estafas chilenas no hay números.

## Qué vamos a construir
- **Entorno simulado:** correo, web, banco y servidores MCP, con dinero y personas ficticias. Cada acción del agente queda registrada y se puntúa automáticamente.
- **Benchmark:** estafas chilenas adaptadas a agentes, en español chileno y en inglés. Por ejemplo: boleta falsa, cambio de cuenta del proveedor, falso ejecutivo que pide el código, tienda falsa, encomienda retenida, devolución de impuestos, multa de autopista o el «jefe» que pide una transferencia. Incluye episodios de control sin estafa para medir que el agente siga siendo útil.
- **Defensa en capas:**
  - **Capa 1:** un firewall abierto existente, para lo técnico.
  - **Capa 2, la nuestra:** rastrea el origen de cada dato. Si un destinatario, una cuenta o un monto viene de contenido no confiable (un correo, una web o un MCP), no llega a una acción de pago sin que el dueño lo confirme. La regla es determinista y no depende de que un LLM acierte. Se le suma un clasificador de señales de estafa.
- **Atacante adaptativo:** un LLM que reescribe cada estafa, ronda tras ronda, para evadir las defensas.
- **Eval reproducible** con [Inspect](https://inspect.aisi.org.uk/): 4 configuraciones de defensa (sin defensa, capa 1, capa 2 y las dos juntas) por modelo y por idioma.

## Estado
🚧 En construcción durante la hackathon. Las tareas están en los [Issues](../../issues) del repositorio.

## Cómo se va a correr
Requiere Python 3.12. Los comandos funcionarán cuando el código esté en el repositorio.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; en macOS o Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # completa tus llaves de API; .env nunca entra al repo
pytest                        # pruebas del entorno y de la política, sin llamar a ningún modelo
inspect eval scamshield/evals/task.py --model <proveedor/modelo> -T defense=none
inspect eval scamshield/evals/task.py --model <proveedor/modelo> -T defense=layer2
```

## Correr con proveedores gratis
La primera tabla se corre con Gemini y Groq, que tienen capa gratis. Claude y GPT se suman después, cuando lleguen los créditos.

```bash
pip install -e ".[dev,proveedores]"   # agrega google-genai y groq, que Inspect necesita
# En .env: GOOGLE_API_KEY, GROQ_API_KEY y/o HF_TOKEN (ver .env.example)
inspect eval scamshield/evals/task.py --model google/gemini-3.5-flash -T defense=layer2
inspect eval scamshield/evals/task.py --model groq/openai/gpt-oss-120b -T defense=layer2
inspect eval scamshield/evals/task.py --model hf-inference-providers/meta-llama/Llama-3.3-70B-Instruct -T defense=layer2
```

Para Hugging Face se usa `hf-inference-providers/`, que llama a la API de Inference Providers con `HF_TOKEN` y no necesita GPU. El proveedor `hf/` de Inspect, en cambio, corre el modelo en tu máquina con torch y transformers.

`scripts/correr_matriz.py` recorre las 4 configuraciones de defensa por cada modelo y cada idioma. Usa solo los proveedores con llave en `.env` y nunca imprime los valores. Los modelos por defecto de cada llave están en `MODELOS_POR_LLAVE`, al comienzo del archivo.

```bash
python scripts/correr_matriz.py --dry-run                        # muestra la matriz sin correr nada
python scripts/correr_matriz.py --defensas none,layer2 --idiomas es --limit 5
python scripts/correr_matriz.py --modelos groq/openai/gpt-oss-120b --max-connections 1
```

Los logs quedan en `logs/` y se abren con `inspect view`. Si no hay ninguna llave y no se pasa `--modelos`, el script termina con un error que dice qué variables definir.

## Estructura prevista
```
scamshield/
  env/        entorno simulado: mundo, herramientas y registro de acciones
  scenarios/  escenarios en YAML (es y en)
  defenses/   capa 1 (firewall abierto), capa 2 (origen de datos) y clasificador
  attacker/   generador adaptativo de variantes
  evals/      tarea de Inspect y puntaje
demo/         demo web
tests/        pruebas sin API
```

## Ética
- Todo es simulado: no hay dinero, personas ni sitios reales. Las marcas, nombres, cuentas y dominios de los escenarios son ficticios.
- El atacante se usa solo dentro del entorno de evaluación.
- Publicamos el dataset y la eval para que cualquiera pueda medir y endurecer sus agentes.

## Trabajo relacionado
- SEA: *Toward Safety-Aware AI Agents in Realistic Social Engineering Attack Scenarios* (arXiv 2611.10037).
- AgentPhishing: *A Benchmark of LLM Email Agents Under Adaptive Attack* (arXiv 2610.31404).
- FraudBench: *Stress-Testing Policy-Grounded Banking Agents Against Adaptive Fraud* (arXiv 2608.18136).
- AgentDojo: benchmark de inyección de prompts en agentes (ETH Zúrich).
- CaMeL: *Defeating Prompt Injections by Design* (Google DeepMind). De aquí viene la idea de separar los datos confiables de los no confiables.
- Firewalls abiertos: [Pipelock](https://github.com/luckyPipewrench/pipelock), [mcp-watchdog](https://pypi.org/project/mcp-watchdog), [Snyk Agent Scan](https://github.com/snyk/agent-scan).

## Equipo
Matías Tapia y Matías Ramírez, con Claude Code.

## Licencia
MIT.
