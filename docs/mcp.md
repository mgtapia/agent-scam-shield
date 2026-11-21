# Grifter como proxy MCP

Grifter se pone entre el agente y tus servidores MCP. Reexpone sus herramientas, anota cada resultado como contenido no confiable (origen `mcp`) y, antes de reenviar `pagar`, `transferir`, `compartir_dato` o `responder`, aplica la capa 2 (`politica_origen`). Si la cuenta o el destinatario solo aparecieron en lo que devolvió un servidor, la llamada no llega al servidor de abajo. El agente recibe un error de herramienta:

> Grifter retuvo el pago: la cuenta 90-1188-4417 apareció en datos_de_pago de silicio-austral, no en tus cuentas inscritas.

Cada llamada sensible queda en `grifter_eventos.jsonl`, sea `permitido`, `retenido` o `aprobado_por_dueno`.

## Piezas
| Módulo | Qué hace |
|---|---|
| `scamshield.mcp.proxy` | el proxy, configurado con `grifter.yaml` |
| `scamshield.mcp.servidor_proveedor` | portal ficticio de Silicio Austral: `leer_correo`, `consultar_factura`, `datos_de_pago`. Con `--envenenado`, el correo y `datos_de_pago` entregan la cuenta del estafador como un dato más. Con `--descripcion-envenenada`, la descripción de `consultar_factura` lleva instrucciones escondidas (el caso de la capa 1). |
| `scamshield.mcp.servidor_banco` | banco sandbox: `pagar(destinatario, cuenta, monto)` solo anota el pago en `banco_sandbox.jsonl` |
| `scamshield.mcp.remoto` | Grifter hacia arriba por streamable HTTP en `/mcp`, con token de portador (ver [Conector remoto](#conector-remoto-chatgpt-claudeai-y-otros)) |
| `scamshield.mcp.cliente_http` | Grifter hacia abajo, contra MCP remotos del comercio por URL, con falla cerrada |
| `scamshield.mcp.servidor_tienda` | tienda ficticia de Silicio Austral: `buscar_productos`, `crear_checkout`, `pagar_checkout`. Con `--desviada`, el checkout manda a pagar a la cuenta del estafador. Con `--http`, sirve `/mcp` por HTTP. |

Para verlo con un modelo de verdad (Claude Haiku) y la alerta en Telegram: [demo-real.md](demo-real.md).

## Configuración
```bash
cp scamshield/mcp/grifter.ejemplo.yaml grifter.yaml
```
En `grifter.yaml` van los servidores de abajo, las cuentas inscritas, los datos del dueño y, opcionalmente, el `encargo` y las herramientas sensibles. Las rutas relativas se resuelven contra la carpeta del archivo. `comando: python` usa el mismo Python del proxy.

Lo confiable es solo lo que escribe el dueño en `grifter.yaml` (o en `--encargo "..."`). Los clientes MCP no le pasan el mensaje del usuario al servidor, así que sin `encargo` la regla es conservadora: solo valen las cuentas inscritas. Lo que escribe el agente en los argumentos nunca cuenta como confiable.

## Claude Code
Desde la raíz del repo, con el Python del venv:
```bash
claude mcp add grifter -- .venv/Scripts/python -m scamshield.mcp.proxy --config grifter.yaml
```
Si `python` ya es el del venv, sirve tal cual: `claude mcp add grifter -- python -m scamshield.mcp.proxy --config grifter.yaml`. Revisa la conexión con `claude mcp list`.

## Claude Desktop
En `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`), con rutas absolutas:
```json
{
  "mcpServers": {
    "grifter": {
      "command": "D:\\ruta\\grifter\\.venv\\Scripts\\python.exe",
      "args": ["-m", "scamshield.mcp.proxy", "--config", "D:\\ruta\\grifter\\grifter.yaml"],
      "env": { "PYTHONPATH": "D:\\ruta\\grifter" }
    }
  }
}
```
Reinicia Claude Desktop después de guardar.

## Demo de 1 minuto
1. Configura `grifter.yaml` desde el ejemplo (el proveedor ya viene `--envenenado`) y agrega Grifter a Claude Code como arriba.
2. Pide: «Paga la factura 8812 de Silicio Austral. Saca el monto con consultar_factura y la cuenta con datos_de_pago».
3. El agente lee la «cuenta actualizada» 90-1188-4417 y llama a `pagar`. Grifter la retiene y el agente muestra el aviso.
4. Muestra las pruebas: `grifter_eventos.jsonl` tiene el evento `retenido` y `banco_sandbox.jsonl` no tiene el pago.
5. Contraste: quita `--envenenado` en `grifter.yaml` y reinicia la sesión. La cuenta es la inscrita (33-7741-0092), así que el pago pasa y queda anotado en el banco sandbox.

## Conector remoto: ChatGPT, Claude.ai y otros
ChatGPT y Claude.ai solo se conectan a servidores MCP **remotos** por HTTPS. Para ellos, Grifter expone streamable HTTP en `/mcp` y se pone esa URL en vez de la del comercio. Las credenciales del comercio y del banco quedan en Grifter (los `headers` de `grifter.yaml`), no en el agente.

**Levantarlo:**
```bash
export GRIFTER_MCP_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
python -m scamshield.mcp.proxy --config grifter.yaml --http --puerto 8766   # http://127.0.0.1:8766/mcp
```
En la demo de Render, `demo/server.py` monta `/mcp` en el mismo servicio solo si `GRIFTER_MCP_TOKEN` está definido (en el panel de Render, no en `render.yaml`). Por defecto pone detrás la tienda ficticia con el checkout desviado (`scamshield/mcp/grifter.tienda.yaml`); `GRIFTER_MCP_CONFIG` apunta a otra configuración. Sin el token, `/mcp` responde 404 y la demo sigue igual.

**Autenticación:**
- Para la demo, un token de portador: `Authorization: Bearer <GRIFTER_MCP_TOKEN>`, de al menos 16 caracteres. Sin el token correcto, Grifter responde 401 antes de tocar nada. Sin el token configurado, el endpoint no se abre.
- En producción va **OAuth 2.1**, como pide la especificación de autorización de MCP: Grifter como servidor de recursos y un servidor de autorización que emita tokens por usuario.

**Con token de portador.** Se conectan los clientes que permiten poner una cabecera:
```bash
claude mcp add --transport http grifter https://grifter.onrender.com/mcp \
  --header "Authorization: Bearer $GRIFTER_MCP_TOKEN"
```
Lo mismo para el conector MCP de la API de Anthropic (`authorization_token`), la herramienta `mcp` de la API de Responses de OpenAI (`headers`) o el MCP Inspector.

**ChatGPT (modo desarrollador).** En ChatGPT web: Settings, Apps (antes Connectors), Advanced settings, Developer mode. Después se agrega un servidor MCP propio con su nombre y la URL `https://grifter.onrender.com/mcp`. Hoy ChatGPT ofrece solo **OAuth** o **sin autenticación** y no deja poner un token de portador fijo. Contra el `/mcp` protegido con token, ChatGPT recibe 401. Para que ChatGPT se conecte falta OAuth. Esto queda pendiente, porque abrir `/mcp` sin autenticación expondría el endpoint a cualquiera. **Claude.ai** (conectores personalizados) tiene la misma restricción: OAuth o nada.

**Los MCP del comercio, por URL.** En `grifter.yaml`:
```yaml
servidores:
  tienda:
    url: https://tienda.example/mcp
    headers: {Authorization: "Bearer ${TOKEN_TIENDA}"}   # ${VAR} sale del entorno; si falta, no arranca
```
Grifter les aplica las mismas capas que a un servidor por stdio. **Falla cerrada:**
- Si el MCP del comercio no responde al arrancar o rechaza la credencial, sus herramientas no se exponen y queda el evento `servidor_remoto_inalcanzable` en el registro.
- Si cae después, cada llamada termina en error («Grifter no pudo llegar a…») y queda el evento `servidor_inalcanzable`. Grifter no inventa un resultado ni reintenta con otro destino.

**Probar contra un comercio remoto local:** `python -m scamshield.mcp.servidor_tienda --desviada --http --puerto 8770` y en `grifter.yaml` `tienda: {url: http://127.0.0.1:8770/mcp}`.

**Qué no hace.** Grifter no entra en la pantalla biométrica de la billetera de ChatGPT, que es cerrada. Frena la llamada al checkout del comercio antes de que la billetera pida tu cara.

## Gancho para avisar al dueño
`Grifter(config, escalar=fn)` llama a `fn(alerta)` cada vez que retiene algo. La función puede ser síncrona o asíncrona. Si devuelve `True`, el dueño aprobó y la llamada se reenvía. Si devuelve otra cosa, sigue retenida. Por defecto solo deja la alerta en stderr. Ahí se conecta el aviso al celular (Telegram, #20).

## Prueba
```bash
.venv/Scripts/python -m pytest -q tests/test_mcp_proxy.py tests/test_mcp_remoto.py tests/test_grifter_no_se_cae.py
```
Levanta el proxy sobre el proveedor envenenado y el banco sandbox con el cliente del SDK `mcp`, por stdio y por HTTP (`/mcp` con token). Comprueba que el pago a la cuenta envenenada se retiene y no llega al banco, y que el pago a la cuenta inscrita sí pasa. `test_mcp_remoto.py` cubre:
- el 401;
- los MCP del comercio por URL, con sus headers;
- la falla cerrada: el comercio no responde, rechaza la credencial o cae a mitad de camino;
- `/mcp` en la demo, con la tienda.

No usa red externa ni llaves: todo corre en 127.0.0.1.
