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
- En Operaciones, el rojo marca el veredicto «Estafa», los tramos de riesgo alto (0,6 o más) y una acción de ataque que pasó. El verde marca la acción retenida, que es el mismo «Bloqueado». «Seguro» y «Sospechoso» van en blanco y se distinguen por el ícono.
- Las capas de defensa son tres grises: Firewall en `--texto`, Escudo en `--texto-2` y Bóveda en `--texto-3`. En la barra por familia, una acción legítima que se ejecutó va en `--borde`.
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

La barra tiene el logotipo «Grifter» a la izquierda, las pestañas justo después y los controles de la vista a la derecha. Bajo 1440 px las pestañas van sin ícono, para que las cinco quepan sin tocar los controles de Episodios. Las pestañas no cambian de lugar entre vistas: cada vista trae otros controles, y si estuvieran centradas saltarían al cambiar de pestaña. Cada vista tiene un solo propósito.

- **Operaciones** (primera pestaña): el centro de operaciones en vivo, alimentado por `/api/vivo`.
  - Arriba va una fila de agentes con su estado, su tarea y su cola. El agente cuyo correo está en Lectura se subraya como la pestaña activa.
  - Al medio van Entrada (un correo por fila, el más nuevo arriba), Lectura (el correo activo, sus tramos y el veredicto con señales y acción) y Registro (todos los eventos en mono, el más nuevo abajo).
  - Abajo van Defensa en capas (contadores y una barra apilada por familia), Bóveda (los indicadores, como una cuarentena) y Modelo (versión, métricas, curva y pesos).
  - En Defensa en capas, los contadores son los de `bloqueos_por_capa` del motor: Firewall y Escudo cuentan acciones retenidas, y Bóveda, veredictos atajados por la bóveda. Cada número va por su lado: no suman lo mismo que las barras.
  - La barra por familia lleva un desenlace por correo, al terminar su lectura: la capa que retuvo la acción, la bóveda si ninguna capa la retuvo, o «ejecutada».
  - El correo escrito en Pruébalo entra al flujo marcado con la etiqueta neutra «Juez» en lugar del agente. Su cuerpo se desplaza dentro de Lectura como cualquier otro.
  - Desde 1600 px de ancho y 900 de alto, todo cabe en una pantalla. Más bajo o más angosto, las filas pasan a alto fijo y la página se desplaza. Bajo 1600 px, Registro baja a la fila de Bóveda y Modelo ocupa el ancho.
  - Cada bloque recorta su contenido y desplaza lo suyo. En Lectura, el cuerpo y la lista de tramos ceden alto y el veredicto con la acción queda siempre visible abajo. Del veredicto se muestran las tres señales de más peso y un «+n».
  - El sello de la barra dice «Simulación · motor real» con el motor, y «Simulación · emisor local» con el respaldo. Al lado va la pausa.
- **Un solo estado para todas las pestañas:** el idioma ES/EN y la velocidad 1x/2x/4x. La velocidad se ve en Operaciones y en Episodios, y mueve a la vez el flujo del motor y la reproducción del episodio.
- **Episodios** (`#vivo`): episodios exportados de Inspect, en tres carriles. Un carril corrido con mockllm lleva la etiqueta «Datos de prueba».
  - Al entrar, abre el escenario de la estafa más reciente que vio Operaciones y que tenga episodio exportado, con la etiqueta «Visto en Operaciones».
  - Si se llega desde Operaciones, arranca a reproducir sola, salvo con `prefers-reduced-motion`. Desde otra pestaña espera a «Reproducir».
  - Elegir otro escenario en el selector manda sobre eso.
  - una franja con el escenario: dueño, tarea en una línea, monto y cuenta inscrita;
  - los tres carriles («Sin defensa», «Firewall», «Escudo»), cada uno con ECG, pasos y veredicto;
  - la lista de correos, de una línea por correo. El cuerpo se abre en un panel lateral, y ahí solo se resalta la cuenta que usó el agente.
  - La alerta del escudo es una capa propia sobre el carril, debajo de su ECG.
- **Resultados:** los números de la tabla «Resultados» del README, cada uno con su intervalo.
  - «Agente que hace todo lo que lee» (`grifter bench`): una fila por configuración. Las estafas exitosas llevan una barra en `--rojo`, con la tasa en sólido y el intervalo al 95 % en rojo al 35 %. Las tres configuraciones del README van en blanco, y las otras dos (firewall de referencia y beneficiario solo) en `--texto-2`.
  - «Modelos y firewall reales»: una fila por medición (Pipelock, Sonnet, Haiku y el clasificador), con el número en `--t-4` y su intervalo al lado. Para el clasificador va el rango entre corridas, y se dice que es un rango.
  - «Atacante adaptativo»: las estafas exitosas acumuladas por ronda, una línea gris por defensa, distinta por trazo y con su nombre al final. Pasa a rojo solo si una estafa le ganó a esa defensa. Si no hay curva con rondas, va un estado vacío que dice qué falta y con qué comando se regenera.
  - La fuente y el comando de cada número van en la ayuda (`data-ayuda`). Un número sin archivo de origen lleva la etiqueta «sin archivo».
- **Duelo** (#82): un hacker que aprende de cómo lo bloqueamos, contra el escudo que se reentrena con él. Es una vista propia, no un bloque de Operaciones: Operaciones ya llena una pantalla y el duelo cuenta otra historia, que en el proyector necesita espacio.
  - Arriba va la franja: la generación, la evasión del hacker en `--rojo`, el recall del escudo en blanco, cada uno con su cambio contra la generación anterior, y las estafas exitosas con la capa 2 en `--verde`, que se mantienen en 0.
  - Al medio van las curvas por generación: evasión en rojo, recall en blanco y «con capa 2» en verde punteado, plana en 0, cada una con su nombre al final. Al lado, lo que aprende el hacker: sus tres mutaciones más útiles (la primera en rojo) y el motivo del último bloqueo, con el conteo por señal.
  - Abajo, una fila por generación, la más nueva arriba.
  - Los eventos `duelo` llegan por el flujo de `/api/vivo`: Operaciones se los pasa al Duelo y anota cada generación en su registro. `/api/vivo/estado` trae `historial_duelo`. Sin eventos, la vista dice que el duelo no corre en el motor y cómo verlo con el emisor local (`?sim`).
  - El duelo es parte del flujo en vivo: lleva el sello, la pausa y la velocidad de Operaciones.
- **Pruébalo:** «Intenta estafarlo» (#21), conectado a `POST /api/probar`.
  - A la izquierda va el formulario, con el encargo del dueño y su cuenta inscrita arriba para que el juez sepa a qué apunta. A la derecha va el resultado.
  - El resultado lleva el veredicto («Frenada» en verde, «Pasó» en rojo o «Sin acción» en gris), la acción que intentó el agente y una fila por capa con su resultado («Retenida» o «Ejecutada», como en Operaciones) y su motivo. La fila del escudo completo no repite el motivo: dice qué partes la frenan.
  - Debajo va el texto del juez con los tramos de la lectura resaltados, como en Operaciones. El cuerpo largo se desplaza por dentro.
  - Los errores 413, 429 y de red van en una línea roja junto al botón, nunca en un `alert()`.
  - El correo del juez solo se evalúa: no entrena el clasificador ni entra a la bóveda.

Hay un solo nivel de contenedores. Dentro de un bloque solo hay filas separadas por `--linea`, nunca tarjetas.

## Texto

- No hay subtítulos, descripciones ni párrafos. Solo hay datos y etiquetas cortas.
- El veredicto tiene de 1 a 3 palabras, más el dato.
- Lo que necesita explicación va en un tooltip (`data-ayuda`).
- Las personas tienen nombres de pila de fundadores de tecnología (Sam, Elon...).

## Movimiento

- Las transiciones duran 160 ms con `ease-out`, y solo para estados.
- `--dur-dato` (480 ms) es solo para un dato que cambia por un evento: una fila que entra, un contador que sube o un peso que cambia. El dato destella una vez con fondo `--borde`.
- **En Operaciones nada se mueve en loop.** Todo movimiento responde a un evento del flujo:
  - `correo_nuevo` hace entrar la fila;
  - `lectura` abre el correo y el cursor lo recorre token a token, entre 0,9 y 2,6 s, y la mitad si hay cola. Cada tramo se subraya con su etiqueta cuando el cursor lo alcanza;
  - un veredicto de la bóveda abre el correo de una vez, como «Firma conocida»;
  - una acción retenida hace parpadear el borde de alerta por 2,6 s;
  - `modelo` suma un punto a la curva y anima los pesos que cambiaron.
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

- Resultados lee `resultados.json`, o `resultados.js` si la página se abre como archivo. Los genera `scripts/resultados_demo.py` desde los JSON de `results/`; cada bloque dice su `fuente` y su `comando`. La página no calcula ninguna tasa.
- Una configuración sin datos se muestra como «—» y «Sin datos», nunca como 0.
- En Episodios, un carril corrido con mockllm lleva la etiqueta «Datos de prueba».
- El escenario que abre Episodios está en `ESCENARIO_POR_DEFECTO`, en `app.js`. `?escenario=` en la URL manda sobre esa constante.
- Operaciones lee la foto de `api/vivo/estado` y después el SSE de `api/vivo`, en el mismo origen. El contrato está en el motor (`scamshield/vivo`).
  - `?motor=http://host:puerto/` apunta a otro origen.
  - Si el motor no responde, o con `?sim`, usa `vivo_simulado.js`, que emite el mismo contrato con textos de los escenarios.
  - ES/EN también cambia el idioma del flujo del motor.
