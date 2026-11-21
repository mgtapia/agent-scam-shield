# Diseño de la demo de Grifter

Grifter es una consola de seguridad sobria, en la línea del modo oscuro de Linear, Vercel, Datadog o Stripe. El 90 % de la pantalla es escala de grises fría, y el color aparece solo cuando lleva significado. La página se usa para **operar**: reproducir un episodio, leer qué hizo el agente, responder la alerta y comparar resultados. Por eso, primero el dato.

Los tokens viven como variables CSS en `:root` de `estilos.css`. El monitor ECG y el tema de ECharts (`graficos.js`) los leen con `getComputedStyle` y no tienen colores propios. Si un valor no está en esta página, no entra.

## Color

Son nueve colores y ninguno más. Cada elemento lleva a lo sumo un color semántico, y nunca hay color de marca.

| Token | Valor | Uso |
|---|---|---|
| `--fondo` | `#09090B` | Fondo de la página |
| `--superficie` | `#111113` | Bloques: franja, carriles, correos, KPI y gráficos |
| `--borde` | `#27272A` | El único borde, siempre de 1 px. También la retícula de los gráficos y el hover |
| `--texto` | `#FAFAFA` | Texto principal, datos y botón principal (texto oscuro sobre claro) |
| `--texto-2` | `#A1A1AA` | Etiquetas, ejes y datos secundarios |
| `--texto-3` | `#71717A` | Trazo base del ECG, íconos de paso y deshabilitados |
| `--rojo` | `#F87171` | «Cayó», el pago al estafador, el pico de riesgo y el estado de alerta |
| `--verde` | `#4ADE80` | Solo «Bloqueado»: el veredicto, el paso bloqueado y el tramo del ECG cortado por el escudo |
| `--ambar` | `#FBBF24` | Solo la etiqueta «externo»: un valor que salió de un correo, la web o un MCP |

Reglas:

- Las cuentas inscritas van en texto normal, con la etiqueta neutra «inscrita».
- Los KPI van en blanco. El delta va en gris con una flecha, y en rojo o verde solo si empeora o mejora.
- Los mapas de calor usan una escala secuencial de `--superficie` a `--rojo`: más rojo es más estafa exitosa.
- Los radares son grises, y pasan a rojo solo si alguna táctica tiene éxito.
- No hay brillo, degradados, sombras de color ni scanlines, salvo el estado de alerta (ver abajo).

## Tipografía

- **IBM Plex Sans** para la interfaz.
- **IBM Plex Mono** para datos y registro: montos, cuentas, dominios, pasos del agente y números de los gráficos.
- Las dos salen de Google Fonts.
- Hay dos pesos: 400 y 600.
- Los números van con `tabular-nums`.

| Token | Tamaño / interlínea | Uso |
|---|---|---|
| `--t-1` | 12 / 16 | Ejes, tooltips, etiquetas, pasos de herramienta y metadatos |
| `--t-2` | 14 / 20 | Texto base, títulos de bloque y controles |
| `--t-3` | 16 / 24 | Nombres de carril y títulos de capa |
| `--t-4` | 20 / 28 | Veredicto y monto de la franja |
| `--t-5` | 24 / 32 | Logotipo y monto de la alerta |
| `--t-kpi` | 40 / 48 | Solo los KPI, que es el tamaño display |

## Forma

- `--radio: 0`. Las esquinas son rectas en todo. Hace juego con Material Symbols Sharp.
- `--linea: 1px solid var(--borde)` es el único borde. El hover cambia el fondo (`--borde`), nunca el borde. El foco es un contorno de 1 px en `--texto`.
- La pestaña activa se subraya con 1 px en `--texto`.

## Espaciado y grilla

- Los espacios son múltiplos de 8: `--e-1` 8, `--e-2` 16, `--e-3` 24, `--e-4` 32 y `--e-6` 48.
- Cada vista es una grilla de 12 columnas, con 24 px de margen fijo y 16 px de separación. Todos los bloques se alinean a esas columnas.

## Íconos

- Solo **Material Symbols Sharp**, con `FILL 0`, `wght 300` y `GRAD 0`.
- Hay dos tamaños: `--i-1` 20 px (en línea) y `--i-2` 24 px (logotipo y capas).
- No se usan emojis ni glifos Unicode como íconos.

## Arquitectura

La barra tiene el logotipo «Grifter» a la izquierda, las pestañas al centro y los controles de la vista a la derecha. Cada vista tiene un solo propósito.

- **En vivo:**
  - una franja con el escenario: dueño, tarea en una línea, monto y cuenta inscrita;
  - los tres carriles («Sin defensa», «Firewall», «Escudo»), cada uno con ECG, pasos y veredicto;
  - la lista de correos, de una línea por correo. El cuerpo se abre en un panel lateral, y ahí solo se resalta la cuenta que usó el agente.
  - La alerta del escudo es una capa propia sobre el carril, debajo de su ECG.
- **Resultados:**
  - KPI (estafas exitosas, utilidad, falsas alarmas y brecha entre ES y EN);
  - un radar por configuración;
  - los mapas de calor táctica × defensa y modelo × idioma. Un clic en una celda abre ese episodio en En vivo.
- **Pruébalo:** solo el esqueleto de «Intenta estafarlo» (#21).

Hay un solo nivel de contenedores. Dentro de un bloque solo hay filas separadas por `--linea`, nunca tarjetas.

## Texto

- No hay subtítulos, descripciones ni párrafos. Solo hay datos y etiquetas cortas.
- El veredicto tiene de 1 a 3 palabras, más el dato.
- Lo que necesita explicación va en un tooltip (`data-ayuda`).
- Las personas tienen nombres de pila de fundadores de tecnología (Sam, Elon...).

## Movimiento

- Las transiciones duran 160 ms con `ease-out`, y solo para estados.
- **Monitor ECG:**
  - es un canvas por carril, con un solo `requestAnimationFrame` para todos;
  - corre siempre de derecha a izquierda, con un latido base en `--texto-3` y un barrido vertical de escaneo;
  - un paso con un valor externo sube la línea; un intento de pago externo dispara un pico en `--rojo`, y si el pago pasó, la línea queda alterada en rojo;
  - si el escudo bloquea, la línea se corta a un verde estable.
- **Estado de alerta:** es la única excepción a «sin glow».
  - Cuando un carril intenta pagar a una cuenta externa o entra la alerta del escudo, toda la ventana muestra un borde `--rojo` (2 px más un resplandor interior al 45 %).
  - El borde parpadea en opacidad entre 1 y 0,35, con un ciclo de 1,2 s.
  - Se apaga cuando el dueño responde o cuando se reinicia el episodio.
- **Con `prefers-reduced-motion`:**
  - no hay transiciones ni loop;
  - el ECG se dibuja una vez por evento;
  - el borde de alerta queda fijo, sin parpadeo.

## Datos

- Los gráficos de Resultados leen `resultados.json`, o `resultados.js` si la página se abre como archivo. Ese archivo lo genera `scripts/exportar_resultados.py` desde los registros de Inspect.
- Una configuración sin datos se muestra como «—» y «Sin datos», nunca como 0.
- Si la fuente es mockllm, la barra muestra «Datos de prueba».
- El escenario que abre En vivo está en `ESCENARIO_POR_DEFECTO`, en `app.js`. `?escenario=` en la URL manda sobre esa constante.
