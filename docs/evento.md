# La demo pública el día del pitch

Tres cosas para que `https://grifter.onrender.com` no falle con el jurado adentro: el modo evento, la prueba de carga y el calentamiento.

## Modo evento (`GRIFTER_EVENTO=1`)

El jurado comparte el wifi y por lo tanto la IP. «Intenta estafarlo» (`/api/probar`) topa a 6 pedidos por minuto y 60 por hora por IP, y `/mcp` a 60 y 600, así que con 30 personas y 3 intentos cada una en 2 minutos, **85 de 90 pedidos reciben 429** (medido, ver abajo).

Con `GRIFTER_EVENTO=1` en el entorno del servicio:

| ruta | por IP por minuto | por IP por hora | global por hora |
|---|---|---|---|
| `/api/probar` | 6 → **120** | 60 → **1.200** | 600 (igual) |
| `/mcp` | 60 → **240** | 600 → **2.400** | 6.000 (igual) |

El **tope global no cambia**: un ataque repartido entre muchas IP sigue topado, y una sola IP que comparte medio auditorio también (600 pedidos por hora a `/api/probar` son más de 6 veces los 90 del pitch). Es una variable de entorno, no un parámetro del pedido: nadie de afuera la puede prender. `/api/salud` dice `"evento": true` cuando está activa, y `scripts/calentar.py` lo muestra.

**Cómo prenderlo:** en el panel de Render, Environment → `GRIFTER_EVENTO=1` (reinicia el servicio, así que se hace **antes** del calentamiento, no después). En `render.yaml` queda comentado: se decide el día. Para apagarlo, se borra la variable.

## Prueba de carga

```bash
python scripts/prueba_carga.py                    # 30 personas x 3 intentos en 120 s; arranca un servidor local con GRIFTER_EVENTO=1
python scripts/prueba_carga.py --sin-evento --duracion 30   # lo que pasa hoy con una IP compartida
```

El script arranca su propio servidor local, **sin `.env`** y sin las variables de llaves o canales del shell: no toca Telegram, WhatsApp ni ninguna API (el agente de `/api/probar` es guionado y no cuesta nada). Sale con 1 si hay un error, un 429 o una latencia sobre el umbral (`--p95-max` 2 s, `--max-max` 10 s).

Medido el 2026-11-21, en un laptop con Windows, servidor local:

| modo | pedidos | 200 | 429 | p50 | p95 | máxima |
|---|---|---|---|---|---|---|
| evento, 30 x 3 en 120 s | 90 | **90** | 0 | 0,016 s | 0,203 s | 0,281 s |
| normal, 30 x 3 en 30 s | 90 | 5 | **85** | 0,016 s | 0,500 s | 0,812 s |

El primer pedido tarda más (arma el motor: 3 a 4 s en el laptop). Por eso el calentamiento manda uno.

**Límite honesto:** se midió contra un servidor local. Render en el plan gratis tiene poca CPU y la red del auditorio no es la de un laptop: la latencia allá será mayor. La carga de `/mcp` no está en el script (el pitch usa `/api/probar`; `/mcp` se verifica con el calentamiento).

## Calentamiento, 5 minutos antes

El plan gratis de Render duerme el servicio tras ~15 minutos sin tráfico, y despertarlo toma ~50 s.

```bash
python scripts/calentar.py            # contra https://grifter.onrender.com
python scripts/calentar.py --mantener # y sigue pidiendo /api/salud cada 8 min para que no se duerma
```

Despierta el servicio con reintentos (hasta 180 s) y verifica, mostrando el tiempo de cada una:

1. `/api/salud`: contesta, con episodios, y dice si está en modo evento.
2. `/resultados.json`: existe y trae `bench`, `clasificador` y `duelo`.
3. `/mcp`: contesta el `initialize` (modo público).
4. `/api/probar`: un correo ficticio, que arma el motor para el primer intento del jurado.

Sale con 1 y dice cuál ruta falló. Solo hace GET, un `initialize` a `/mcp` y un POST de un correo ficticio: no manda nada a Telegram ni a ninguna API.

## Demo en vivo con WhatsApp

En el acto 1 del modo demo (`/#demo`), Marta toca «Pagar igual», aprueba con el código que le llega por correo (1 de 2) y falta Pablo, su hijo. Pablo lo hace el presentador: el pedido de aprobación le llega **de verdad** por WhatsApp (Kapso), con Aprobar y Rechazar y el mismo texto de la doble autorización. El teléfono del presentador se muestra en la pantalla grande con scrcpy.

**1. El día antes.** Desde el teléfono del presentador (el número de `KAPSO_OWNER_NUMBER`), escríbele «hola» al número de Grifter en las 24 h previas: WhatsApp solo deja mandar mensajes libres, como este pedido con botones, dentro de esa ventana.

**2. El servidor local**, en el notebook del pitch. Toma las llaves de Kapso de `.env`; si corre desde un worktree, también busca el `.env` del repo principal:

```bash
GRIFTER_DEMO_WHATSAPP=1 python -m demo.server --puerto 8765
```

- Sin `GRIFTER_DEMO_WHATSAPP=1`, la ruta `POST /api/demo/alerta-en-vivo` da 404. En Render está apagada salvo el día del pitch, que se prende en el panel (ver el punto 5); aun así, sin la clave de un solo uso nadie puede hacer sonar el teléfono.
- **Pide una clave de un solo uso.** El servidor la genera al arrancar y la imprime en la consola («Clave de un solo uso de este arranque: …»).
  - Va en la URL, y la barra de direcciones se proyecta y queda en el historial y en el log de acceso. Por eso nunca es una clave fija: muere al reiniciar el servidor.
  - `GRIFTER_DEMO_CLAVE` ya no se usa. Si está en `.env`, el servidor avisa que la ignora.
  - Después de una exposición, reinicia el servidor y usa la clave nueva.
- **Tope a las claves malas:** después de 5 en un minuto, la ruta responde 429 hasta que pase el minuto, aunque llegue la buena.
- **Un pedido cada 30 s como máximo.** Si Kapso no acepta el envío (502) o faltan las llaves (503), el intento no gasta los 30 s y se puede reintentar de inmediato.
- Las llaves de Kapso nunca aparecen en la respuesta ni en los registros.

**3. La URL**, en Chrome a pantalla completa (F11), y Espacio para arrancar:

```
http://127.0.0.1:8765/demo.html?whatsapp=1&clave=LA_CLAVE_DE_ESTE_ARRANQUE
```

Copia la clave de la consola justo antes de subir al escenario. Si reinicias el servidor, la URL vieja deja de servir.

La demo llama a Kapso una sola vez por corrida, a los 45 s, y no espera la respuesta: si Kapso falla o tarda, la demo sigue con el teléfono dibujado.

**4. El teléfono en la pantalla grande:** con el Android conectado por USB y la depuración USB activada, `scrcpy --window-title Pablo --stay-awake` duplica la pantalla en una ventana que se pone al lado de la demo.

**5. El rechazo de Pablo.** La demo se detiene hasta 7 s esperando que el presentador toque «Rechazar» en su WhatsApp (si no llega, sigue con el rechazo simulado), con la narradora callada justo antes de «rechaza». Cuando llega, el log de la izquierda dice «Pablo rechazó desde su WhatsApp · 2,4 s», con la latencia medida.
- **Respaldo:** si el WhatsApp no llega, la tecla **S** sigue con el rechazo simulado. Si el envío falla (sin llaves o Kapso no lo acepta), la demo no espera.
- Con `?espera=N` el máximo de la pausa pasa a N s.
- Para que el toque llegue, Kapso tiene que poder llamar al servidor. **El webhook en Kapso**, en el número de WhatsApp, Webhooks: la URL `https://<servidor>/api/whatsapp/webhook`, el evento `whatsapp.message.received` y el secreto, que es el mismo `KAPSO_WEBHOOK_SECRET` del entorno. El servidor revisa la firma HMAC de cada entrega (ver `docs/mcp.md`) y solo cuenta el botón del número de `KAPSO_OWNER_NUMBER` sobre el pedido recién enviado.
  - **En local:** un túnel público, por ejemplo `cloudflared tunnel --url http://127.0.0.1:8765`, y en Kapso la URL `https://….trycloudflare.com/api/whatsapp/webhook`.
  - **En Render:** no hace falta túnel. En el panel de Render, Environment: `GRIFTER_DEMO_WHATSAPP=1`, `KAPSO_API_KEY`, `KAPSO_PHONE_NUMBER_ID`, `KAPSO_OWNER_NUMBER` y `KAPSO_WEBHOOK_SECRET`. En Kapso, la URL `https://grifter.onrender.com/api/whatsapp/webhook`. La clave de un solo uso sale en los logs de Render al arrancar; el plan gratis duerme el servicio y cada arranque cambia la clave, así que se copia de los logs justo antes de presentar.

  La página se entera consultando `GET /api/demo/alerta-en-vivo/estado`, que devuelve solo el estado y la latencia, con la clave en una cabecera.

**Ensayo:** cada prueba le llega de verdad al teléfono. Sin `?whatsapp=1`, la demo corre igual y no manda nada, y con `?t=48` se ve el cuadro fijo, siempre en modo simulado.
