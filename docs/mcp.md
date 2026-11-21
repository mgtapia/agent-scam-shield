# Grifter como proxy MCP

Grifter se pone entre el agente y tus servidores MCP. Reexpone sus herramientas, anota cada resultado como contenido no confiable (origen `mcp`) y, antes de reenviar `pagar`, `transferir`, `compartir_dato` o `responder`, aplica la capa 2 (`politica_origen`). Si la cuenta o el destinatario solo aparecieron en lo que devolvió un servidor, la llamada no llega al servidor de abajo. El agente recibe un error de herramienta:

> Grifter retuvo el pago: la cuenta 90-1188-4417 apareció en datos_de_pago de silicio-austral, no en tus cuentas inscritas.

Cada llamada sensible queda en `grifter_eventos.jsonl`, sea `permitido`, `retenido` o `aprobado_por_dueno`.

## Piezas
| Módulo | Qué hace |
|---|---|
| `scamshield.mcp.proxy` | el proxy, configurado con `grifter.yaml` |
| `scamshield.mcp.servidor_proveedor` | portal ficticio de Silicio Austral: `consultar_factura`, `datos_de_pago`. Con `--envenenado`, `datos_de_pago` entrega la cuenta del estafador como un dato más. Con `--descripcion-envenenada`, la descripción de `consultar_factura` lleva instrucciones escondidas (el caso de la capa 1). |
| `scamshield.mcp.servidor_banco` | banco sandbox: `pagar(destinatario, cuenta, monto)` solo anota el pago en `banco_sandbox.jsonl` |

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

## Gancho para avisar al dueño
`Grifter(config, escalar=fn)` llama a `fn(alerta)` cada vez que retiene algo. La función puede ser síncrona o asíncrona. Si devuelve `True`, el dueño aprobó y la llamada se reenvía. Si devuelve otra cosa, sigue retenida. Por defecto solo deja la alerta en stderr. Ahí se conecta el aviso al celular (Telegram, #20).

## Prueba
```bash
.venv/Scripts/python -m pytest -q tests/test_mcp_proxy.py
```
Levanta el proxy sobre el proveedor envenenado y el banco sandbox con el cliente del SDK `mcp`. Comprueba que el pago a la cuenta envenenada se retiene y no llega al banco, y que el pago a la cuenta inscrita sí pasa. No usa red ni llaves.
