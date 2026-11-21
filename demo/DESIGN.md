# Diseño de la demo: consola de seguridad

Es una consola de un SOC, oscura y densa, con el amarillo neón de Platanus como único acento de marca. Se usa para **operar**: hay que reproducir un episodio, leer qué hizo el agente, responder la alerta y comparar resultados. Por eso, primero el dato y después la marca.

Los tokens viven como variables CSS en `:root` de `estilos.css`. El tema de ECharts (`graficos.js`) los lee con `getComputedStyle`, así que no tiene colores propios. Si un valor no está en esta página, no entra.

## Color

Son nueve colores y ninguno más. Cada semántico tiene un solo significado.

| Token | Valor | Uso |
|---|---|---|
| `--fondo` | `#0B0C0E` | Fondo de la página |
| `--superficie` | `#131519` | Paneles, carriles, capa de alerta y tooltips |
| `--borde` | `#262A31` | El único borde, siempre de 1 px. También la grilla de los gráficos |
| `--texto` | `#E8EAED` | Texto principal y datos |
| `--texto-2` | `#9198A1` | Etiquetas, ejes y datos secundarios |
| `--acento` | `#F0FF3D` | Marca, acción principal, foco y selección. También el trazo base del pulso |
| `--verde` | `#3DDC84` | Seguro, del dueño y pagado a una cuenta inscrita |
| `--rojo` | `#FF4D4F` | Cayó, estafa y pago a la cuenta de afuera |
| `--ambar` | `#FFB020` | Vino de afuera: correo, web o MCP que no es del dueño |

Reglas:

- El texto sobre `--acento` usa `--fondo`.
- Las transparencias de un token (`color-mix`) sirven solo para fondos de estado (selección, celda en hover). Nunca son un color nuevo.
- Los mapas de calor van en escala secuencial de `--superficie` a `--rojo`: más rojo es más estafa exitosa.
- Los radares usan un solo color de serie por figura: `--rojo` en «Sin defensa» y `--acento` en las demás.

## Tipografía

- **IBM Plex Sans** para la interfaz: etiquetas, botones y títulos.
- **IBM Plex Mono** para datos y registro: montos, cuentas, dominios, pasos del agente y números de los gráficos.
- Todo sale de Google Fonts.
- Hay dos pesos: 400 y 600.
- Los números van con `font-variant-numeric: tabular-nums`.

| Token | Tamaño / interlínea | Uso |
|---|---|---|
| `--t-1` | 12 / 16 | Ejes, tooltips, etiquetas de estado y metadatos |
| `--t-2` | 14 / 20 | Texto base: pasos, correos y controles |
| `--t-3` | 16 / 24 | Títulos de panel y nombres de carril |
| `--t-4` | 20 / 28 | Veredicto y monto de la alerta |
| `--t-5` | 24 / 32 | Nombre del producto en la barra |
| `--t-kpi` | 40 / 48 | Solo los KPI, que es el tamaño display |

## Forma

- `--radio: 0`. Las esquinas son rectas en todo: paneles, botones, celdas y tooltips. Hace juego con Material Symbols Sharp.
- `--linea: 1px solid var(--borde)`. Es el único borde. Los estados cambian el color de fondo o del texto, nunca el grosor del borde.
- No hay sombras, degradados ni brillos.

## Espaciado

Se usan múltiplos de 8 px: `--e-1` 8, `--e-2` 16, `--e-3` 24, `--e-4` 32 y `--e-6` 48. Los paneles se separan con un hueco de 1 px sobre `--borde` (la grilla se ve como una línea), así que los bordes quedan alineados de punta a punta.

## Íconos

- Solo **Material Symbols Sharp**, con `FILL 0`, `wght 300` y `GRAD 0`.
- Hay dos tamaños: `--i-1` 20 px (en línea con el texto) y `--i-2` 24 px (barra y alerta).
- No se usan emojis ni glifos Unicode como íconos.
- Íconos en uso: `shield`, `gpp_bad`, `gpp_good`, `mail`, `account_balance`, `payments`, `monitor_heart`, `play_arrow`, `restart_alt`, `smart_toy`, `person`, `block`, `check`, `close` y `language`.

## Composición

- La página tiene un solo nivel de contenedores. Panel, carril y celda de KPI son contenedores. Lo que va dentro son filas separadas por `--linea`, nunca tarjetas.
- La alerta del escudo es una capa propia, fija a la derecha, sobre la página. No es una tarjeta dentro de un carril.
- Orden de arriba a abajo:
  1. barra de control;
  2. franja de KPI;
  3. reproducción (bandeja y tres carriles);
  4. análisis (radares y mapas de calor).
- Desde 900 px, los tres carriles van lado a lado. Desde 1280 px, la bandeja va a la izquierda de los carriles.

## Texto

- No hay subtítulos ni descripciones. Solo hay datos y etiquetas cortas.
- Los carriles se llaman «Sin defensa», «Firewall» y «Escudo».
- El veredicto tiene de 1 a 3 palabras, más el dato.
- Lo que necesita explicación va en un tooltip (`data-ayuda`).
- Las personas tienen nombres de pila de fundadores de tecnología (Sam, Elon...).

## Movimiento

- Las transiciones duran 160 ms con `ease-out`, y solo para estados (hover, foco, apertura de la alerta).
- El pulso del agente es el único movimiento que dura: avanza con la reproducción.
- Con `prefers-reduced-motion`, las transiciones se apagan y el pulso se dibuja de una vez.

## Datos

- Los gráficos agregados leen `resultados.json`, o `resultados.js` si la página se abre como archivo. Ese archivo lo genera `scripts/exportar_resultados.py` desde los registros de Inspect.
- Una configuración sin datos se muestra como «Sin datos» y nunca como 0.
- Si la fuente es mockllm, la barra muestra «Datos de prueba».
