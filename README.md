# Grifter

**Escudo para agentes de IA que pagan.** Grifter revisa el origen de los datos antes de que un agente mueva dinero o comparta credenciales. Si el destino no se puede verificar, pide confirmación al dueño.

<img src="project-logo.png" alt="Escudo de Grifter" width="120" />

[Demo en vivo](https://grifter.onrender.com) · [Descripción del proyecto](project-description.md) · [Guía completa](GUIA.md)

## Pruébalo

Requiere Python 3.11 o superior. El benchmark y las pruebas funcionan sin llaves de API.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,demo]"
grifter bench
python -m demo.server
```

Abre la demo local en <http://127.0.0.1:8765>. En Windows, activa el entorno con `.venv\Scripts\activate`.

## Qué incluye

- **Defensa en capas:** firewall técnico, política determinista de origen de los datos y verificación del titular de la cuenta.
- **Integración:** [SDK Python](examples/funciones_python.py) y [proxy MCP](docs/mcp.md) para poner el escudo delante de un agente.
- **Evaluación reproducible:** estafas simuladas en español chileno e inglés, atacante adaptativo y resultados con sus [fuentes y límites](docs/cifras.md).
- **Demo web:** operaciones en vivo, episodios de evaluación y resultados.

Para instalarlo según tu caso, sigue [docs/instalar.md](docs/instalar.md). Para verificar el proyecto, ejecuta `pytest -q`.

## Equipo y hackathon

**team-40 · Platanus Hack 26: Santiago ft. Buk · Track AI Security**

[Matías Tapia](https://github.com/mgtapia) y [Matías Ramírez](https://github.com/maramir6).

El despliegue permanece conectado al [repositorio de desarrollo](https://github.com/mgtapia/grifter). El repositorio de la hackathon consulta su `main` cada cinco minutos y se actualiza automáticamente; los detalles están en [docs/sincronizacion.md](docs/sincronizacion.md).

Todo el benchmark usa escenarios ficticios. Licencia [MIT](LICENSE); atribuciones en [NOTICE.md](NOTICE.md).
