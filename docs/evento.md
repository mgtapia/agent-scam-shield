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
