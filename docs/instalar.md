# Instalar Grifter

Elige lo que eres. Cada camino tiene a lo más cinco pasos.

| Quién eres | Qué haces | Tiempo |
|---|---|---|
| [Quiero verlo funcionar](#1-quiero-verlo-funcionar) | Abres una página | 1 min |
| [Uso ChatGPT](#2-uso-chatgpt) | Agregas un conector | 3 min |
| [Uso Claude Desktop o Claude Code](#3-uso-claude-desktop-o-claude-code) | Instalas Grifter en tu computador | 10 min |
| [Programo mi propio agente](#4-programo-mi-propio-agente) | Envuelves tus herramientas con tres líneas | 5 min |
| [Soy un banco, una billetera o un comercio](#5-soy-un-banco-una-billetera-o-un-comercio) | Pones Grifter delante de tus MCP | 1 día |
| [Investigo seguridad de agentes](#6-investigo-seguridad-de-agentes) | Corres el benchmark | 5 min |

En todos los casos, Grifter **no lee tu correo ni tu WhatsApp**. Se para entre el agente y sus herramientas: ve solo lo que el agente lee y revisa de dónde salió cada cuenta antes de pagar.

---

## 1. Quiero verlo funcionar
1. Abre **https://grifter.onrender.com**. Si tarda, es porque el servicio gratis estaba dormido.
2. En **Operaciones**, mira cómo los correos de estafa se frenan en vivo. En **Duelo**, el atacante que aprende contra el escudo que aprende.

No instalas nada. Los agentes y los correos son simulados; las defensas son las reales.

## 2. Uso ChatGPT
Por ahora conecta con una **tienda de juguete**, para ver a Grifter frenar un cobro desviado. Todavía no protege tus compras reales: eso necesita OAuth (ver la sección 5).

1. En ChatGPT web: **Settings → Apps → Advanced settings**, prende **Developer mode**.
2. Agrega un servidor MCP: nombre `Grifter`, URL `https://grifter.onrender.com/mcp`, autenticación **No authentication**.
3. En una conversación nueva, elige el conector y pide: «Compra 10 microprocesadores SA-3NM en la tienda de Silicio Austral y paga el checkout».
4. La tienda cambia la cuenta de cobro y Grifter retiene el pago. ChatGPT te muestra por qué.

## 3. Uso Claude Desktop o Claude Code
Necesitas Python 3.11 o más nuevo y Git.

1. Baja Grifter e instálalo:
   ```bash
   git clone https://github.com/mgtapia/grifter && cd grifter
   python -m venv .venv
   .venv\Scripts\activate          # Windows; en macOS o Linux: source .venv/bin/activate
   pip install -e .
   ```
2. Copia la configuración de ejemplo:
   ```bash
   cp scamshield/mcp/grifter.ejemplo.yaml grifter.yaml
   ```
   En `grifter.yaml` van tus **cuentas inscritas**, las únicas a las que el agente puede pagar sin preguntarte, y los servidores MCP que quieres proteger. El ejemplo ya trae un proveedor y un banco de prueba.
3. Conéctalo:
   - **Claude Code:** `claude mcp add grifter -- python -m scamshield.mcp.proxy --config grifter.yaml`
   - **Claude Desktop:** agrega a `claude_desktop_config.json` (en Windows, `%APPDATA%\Claude\`) el bloque de [mcp.md](mcp.md#claude-desktop) con tus rutas y reinicia la aplicación.
4. Pruébalo: «Paga la factura 8812 de Silicio Austral». El proveedor de prueba trae una cuenta cambiada, y Grifter retiene el pago.
5. **Opcional:** recibe las alertas en el celular. Pon `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en un archivo `.env` (ver `.env.example`). La alerta llega con botones para aprobar o bloquear.

## 4. Programo mi propio agente
Funciona con cualquier lista de funciones de Python, síncronas o `async`, sin framework ni proxy.

1. Instala:
   ```bash
   pip install "git+https://github.com/mgtapia/grifter"
   ```
2. Envuelve tus herramientas:
   ```python
   from grifter import escudo

   herramientas = escudo(herramientas,
                         cuentas_inscritas={"Silicio Austral": "Banco Litoral 33-7741-0092"},
                         encargo="Paga la factura de Silicio Austral",
                         avisar=None)   # o una función que le pregunte al dueño y devuelva True o False
   ```
3. Listo. Grifter clasifica cada herramienta:
   - las que **leen** (correo, web, MCP) marcan lo que devuelven como no confiable;
   - las que **pagan o comparten datos** se revisan antes de ejecutarse.

   Si Grifter retiene, la función no corre y el modelo recibe el porqué.

Ejemplos que corren sin llaves: [`examples/funciones_python.py`](../examples/funciones_python.py) y [`examples/anthropic_tool_use.py`](../examples/anthropic_tool_use.py) `--mock`. Con Stripe en modo prueba: [stripe-test-mode.md](stripe-test-mode.md). Las opciones están en el [README](../README.md#úsalo-en-tu-agente).

## 5. Soy un banco, una billetera o un comercio
Grifter va como un **proxy MCP remoto** delante de tus herramientas de pago. El agente del cliente se conecta a Grifter, y Grifter a tu MCP. Tus credenciales quedan en Grifter, nunca en el agente.

1. Instala como en la sección 3 y define en `grifter.yaml` tus MCP por URL (`servidores: {tienda: {url: ..., headers: ...}}`). Si tu MCP no responde, Grifter no expone sus herramientas: falla cerrado.
2. Carga las cuentas inscritas de cada cliente y los titulares (nombre y RUT) que ya conoces. Con eso se activa la confirmación de beneficiario (capa 3).
3. Activa la **doble autorización**: cambiar la política o apagar Grifter pide dos aprobadores, cada uno con su código de un solo uso (TOTP). Paso a paso en [mcp.md](mcp.md#doble-autorización-dos-personas-no-una).
4. Levántalo por HTTP:
   ```bash
   python -m scamshield.mcp.proxy --config grifter.yaml --http --puerto 8766
   ```
   Para la prueba basta un token de portador (`GRIFTER_MCP_TOKEN`). En producción va **OAuth 2.1**, como pide la especificación de MCP. Todavía no está hecho: es el próximo paso para conectar clientes reales.
5. Elige por dónde le llega la alerta al dueño: Telegram, WhatsApp (Kapso, [mcp.md](mcp.md#whatsapp-kapso-como-canal-del-dueño-116)) o tu propia aplicación, con el gancho `avisar`.

## 6. Investigo seguridad de agentes
```bash
git clone https://github.com/mgtapia/grifter && cd grifter
python -m venv .venv
.venv\Scripts\activate     # Windows; en macOS o Linux: source .venv/bin/activate
pip install -e ".[dev,demo]"
grifter bench          # el benchmark completo, sin llaves de API, en segundos
pytest                 # las pruebas, sin llamar a ningún modelo
```
Para correr con modelos reales (Anthropic, OpenAI, Gemini, Groq) y con el atacante adaptativo, mira el [README](../README.md#benchmark-en-un-comando).
