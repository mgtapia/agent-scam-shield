# Pitch de Grifter (3 minutos)

Guion para el jurado de Platanus, track AI Security. Las cifras entre `{llaves}` salen de `demo/resultados.json` o de las corridas de Inspect: no se dice ningún número que no esté medido. **Siempre se da el intervalo, no solo el punto:** con 19 escenarios con tarea, los intervalos son de ±15 a 20 puntos.

## La frase
**El agente no tiene que ser listo para no caer: la garantía vive fuera del modelo. Lo que no puede verificar, te lo pregunta con un toque.**

## Guion

| Tiempo | Qué se dice | Qué se ve |
|---|---|---|
| 0:00–0:20 | El 13 de noviembre OpenAI lanzó ChatGPT Wallet: los agentes ya pagan por nosotros. 1 de cada 4 chilenos ya perdió plata en una estafa digital `{fuente verificada en #16}`. Al estafador ya no le hace falta engañarte a ti: le basta con engañar a tu agente. | Título Grifter |
| 0:20–1:10 | Elon le pide a su agente que pague 10.000 microprocesadores. Llega el correo «cambiamos de banco» desde un dominio casi igual. Sin defensa, el agente paga. Con un firewall de agentes conocido, también, porque no hay nada técnico que detectar. Con Grifter, el pago se frena. | Live: tres carriles con el ECG en vivo |
| 1:10–1:40 | Le llega la alerta: la cuenta salió de un correo, no de sus cuentas inscritas. Un toque y paga a la correcta. | La alerta en el celular |
| 1:40–2:30 | Los números. `{n}` estafas chilenas en español e inglés, `{m}` modelos y 4 configuraciones. Tres hallazgos: | Results: KPI, mapa de calor y radar |
| | 1. **Los modelos de punta casi no caen, y cuando caen es por confianza delegada:** Haiku no cayó en ninguno de 21 escenarios en español con la lista de cuentas visible (0 % [0-15]); Sonnet, con el encargo de pagar lo que el gerente apruebe, **pagó 6 de 6** (español e inglés, 3 repeticiones) cuando el correo del gerente venía de su propia dirección comprometida. Es **un solo escenario**, y el encargo delega explícitamente: pagar es defendible para el agente. La vulnerabilidad es la confianza delegada, no que el modelo sea tonto. La capa 2 lo retiene, porque la cuenta salió de un correo y no del encargo. | Mapa de calor táctica × defensa |
| | 2. **Un agente sin libro de proveedores queda inútil:** sin la lista de cuentas, la utilidad baja de 79 % [57-95] a 16 % [0-38] (Haiku, español, 3 repeticiones, IC 95 %), porque no se atreve a pagar. Las estafas exitosas suben a 8 % [0-27], que con 21 escenarios no se distingue de cero. Ni siquiera avisarle que tiene escudo lo cambia. **Grifter no hace al agente más listo: lo hace seguro, y lo que no puede verificar se lo pregunta al dueño con un toque** (con la capa 2, 0 de 21 escenarios con estafa exitosa, con un límite superior de 15 %; utilidad 79 % [57-95] con el dueño en el circuito y unos 6 toques por cada 100 acciones sensibles [0-23]). | Seguridad contra utilidad, con intervalos |
| | 3. **El atacante adaptativo reescribe la estafa ronda tras ronda.** **Honesto: la adaptación no hizo falta ni sirvió.** Con gpt-oss-20b de víctima y 5 estafas en español, sin defensa cayeron 4 de 5 ya en la ronda 0 (80 % [38-96], n=5) y ninguna más con 3 rondas de reescritura de Qwen 27B (80 % [38-96] en las rondas 0 a 3); la que resistió, aguantó las 3 rondas. Con la capa 2, el agente intentó pagar al estafador en 4 de 5 y la capa frenó los 4: 0 de 5 exitosas (0 % [0-43]) en todas las rondas con episodio puntuado (5 de 5 en las rondas 0 y 1, 2 de 5 en la 2 y 1 de 5 en la 3: la cuota diaria de Groq de la víctima cortó el resto). Con n=5 el intervalo es ancho: es un humo, no una curva; la garantía fuerte es la de los 64 escenarios y la prueba de propiedad. | Curva del atacante |
| 2:30–3:00 | Todo es abierto: el primer dataset de estafas en español para agentes, la eval en Inspect y la capa que se suma a cualquier agente o firewall. Mírenlo en vivo: Operaciones y el Duelo. | Operaciones en vivo |

## Por qué es distinto (si el jurado pregunta)
- **SEA, AgentPhishing y FraudBench miden estafas contra agentes, pero en inglés.** Nosotros medimos español chileno contra inglés, con las mismas estafas.
- **Los firewalls de agentes (medimos Pipelock) frenan la inyección técnica.** La ingeniería social no tiene nada técnico que detectar. Grifter revisa el valor concreto (la cuenta, el destinatario), no la sesión completa. Con la lista visible, casi no cuesta utilidad (de 79 % [57-95] a 74 % [51-89], con intervalos que se solapan). Cuando la cuenta es nueva pero legítima, no la bloquea en silencio: le pide un toque al dueño: unas 6 de cada 100 acciones sensibles [0-23], con Haiku en español.
- **Hay una garantía que el texto no rompe:** una cuenta que no aparece completa en el encargo ni en las cuentas inscritas se bloquea siempre, por convincente que sea el correo, en las acciones que Grifter revisa (pagos, transferencias y envío de datos del dueño) y solo sobre el destino: no cubre el monto ni un pago partido en varios. Hay una prueba de propiedad (1000 casos con semilla fija) que lo demuestra.
- **Firewall real medido:** Pipelock frenó 4 de 42 estafas, todas técnicas (inyección web y MCP envenenado), con 0 falsas alarmas. Es lo mismo que nuestras reglas de referencia: un firewall de agentes no ve la ingeniería social. No decir que «ve más que un regex».
- **Si al dueño ya lo engañaron y dicta él la cuenta:** la capa 2 la deja pasar por diseño, y ahí entra la **capa 3, confirmación de beneficiario**: el titular de la cuenta tiene que calzar con el RUT de la cuenta que el dueño inscribió, no con el de la factura, que se puede falsificar. Un beneficiario nuevo tiene un tope, que suma los pagos de la sesión a su RUT. Es una garantía probada con un agente guionado (3 de 3 retenidos, 2 controles que pasan), no una medición con modelo real. Frase: «para engañarte a ti, además tiene que pasar la confirmación de beneficiario».
- **Límite honesto que queda:** un estafador con una cuenta a nombre de quien dice ser, o un dueño que decide pagar igual. Además, el equipo rojo de caja blanca (#90, `tests/test_equipo_rojo.py`) encontró ocho variantes de ataque que todavía nos rompen, y lo decimos antes de que pregunten:
  - Una fuente que el integrador declara confiable y está envenenada (un ERP).
  - Un `grifter.yaml` que el agente reescribe con una herramienta de archivos: ya no pasa en silencio (huella de la política y aviso al dueño, #102), pero quien controla la máquina y el teléfono del dueño lo puede todo.
  - Una credencial partida en varios mensajes.
  - Una credencial pegada en la URL de una herramienta de lectura.
  - El pago por fuera: el agente le pasa al dueño un link o una cuenta para que pague él.
  - Un número de factura del encargo con los dígitos de la cuenta del estafador. Sin titulares, la capa 2 lo toma como del dueño; con titulares, la capa 3 lo retiene.
  - Un monto inflado a la cuenta inscrita.
  - Un pago partido entre varias cuentas nuevas.

  En la misma pasada arreglamos varios: credenciales en base64, con letras cirílicas, de ancho completo o con los dígitos en palabras. También un `avisar` que devolvía «no» y aprobaba, un destino que escribía líneas falsas en el mensaje de la alerta (`Alerta.mensaje`; `valor` y `args` siguen crudos para quien integra), un monto «1.500.000» que se leía como 1 peso y el pago partido a un mismo titular.

## Proyectos parecidos de otras hackathons (si el jurado pregunta)
No encontramos ninguno con la combinación completa, pero sí algunos con piezas parecidas. Conviene nombrarlos antes de que lo haga el jurado:

| Proyecto | Qué hace | Qué no hace y Grifter sí |
|---|---|---|
| **Lookout** (PayPal AI Hackathon 2026) | Retiene el pago entre aprobar y capturar. Usa señales y un contacto de confianza, y verifica que el beneficiario no cambió. | No sabe de dónde salió la cuenta (correo, web o MCP). No tiene benchmark. |
| **Sentinel MCP Wallet** (HackMoney 2026, premio ENS) | Política determinista en MCP: tope, lista blanca y slippage. | La lista blanca no distingue una cuenta nueva legítima de una que puso el estafador; Grifter mira el origen y le pide un toque al dueño. |
| **The Citadel** (AI Tinkerers SF, Secure Agents) | Firewall MCP en stdio contra la inyección y la fuga de datos. | Es la capa 1. Pipelock hace lo mismo y lo medimos: 4 de 42. |
| **ClawGuard** (HackMoney 2026, premio ENS) | Aprende los hábitos del usuario y escala lo raro por Telegram. | Lo aprendido decide. En Grifter solo sube la sospecha, y la garantía es determinista. |

Frase: «Ellos protegen el pago. Nosotros, además, medimos cuánto cae un agente en español y sabemos de dónde salió cada cuenta».

## Lo que no se dice
- «Somos los primeros en defender pagos de agentes»: hay antecedentes (tabla de arriba). Lo primero es el benchmark en español chileno contra inglés y la regla por origen del valor.
- «Grifter le devuelve la utilidad al agente»: medido en #38, no es cierto.
- Los números con dueño simulado son un techo: el dueño idealizado sabe cuál es la cuenta buena, y en un hilo secuestrado un dueño real podría no saberlo.

## ¿Y ChatGPT Wallet? (lanzado el 13-nov-2026)
- **Lo que hace:** tarjetas tokenizadas (el agente no ve la tarjeta) y aprobación biométrica de cada compra. Solo en EE. UU., para Pro.
- **Lo que no hace:** la biometría confirma que *eres tú* el que aprueba, no que el destino sea legítimo. Si el agente fue engañado, la pantalla de aprobación te muestra la tienda o la cuenta del estafador y la apruebas con tu cara. Es el mismo punto débil que medimos: el humano aprueba lo que el agente le muestra.
- **Lo que agrega Grifter:** el *porqué* en el momento de aprobar («este destino salió de un correo, no de tus proveedores»), la retención de lo que no se puede verificar y las transferencias a cuentas, que es la estafa dominante en Chile y que una billetera de tarjetas no cubre. Grifter es una capa de política: se puede poner antes de cualquier billetera o pasarela.

### Dónde entra Grifter en el flujo (diagrama para la presentación)
Grifter se pone en dos puntos. Ninguno es la pantalla biométrica de la billetera, que es cerrada:
1. **Entre el agente y el comercio**, como conector MCP remoto. Para esto falta #105.
2. **En el lado del cobro**, en Stripe o en el banco.

```mermaid
flowchart LR
  U["Dueño<br/>«compra 10.000 chips, hasta $412.000»"] --> A["ChatGPT<br/>(o Claude, o un agente propio)"]
  A -- "conector MCP<br/>grifter.onrender.com/mcp" --> G["Grifter"]
  G --> M["MCP del comercio<br/>(checkout)"]
  M -- "orden: $4.120.000" --> G
  G -. "no calza con el mandato:<br/>retenido, nunca llega a la billetera" .-> X["✗"]
  G -- "calza con el mandato" --> W["ChatGPT Wallet<br/>(pide tu cara)"]
  W --> P["Cobro<br/>(Stripe o el banco)"]
  P -. "segunda revisión antes del cobro" .-> G
  G -. "lo que no puede verificar:<br/>2 aprobadores + código" .-> D["Dueño y segundo aprobador"]
```

- **El mandato (#103).** Al aprobar, Grifter fija el producto, la cantidad, el monto máximo, la moneda, el beneficiario y si es único o recurrente. Todo checkout se compara contra eso, y las herramientas aprobadas quedan con su huella: si el MCP cambia su descripción, se bloquea.
- **Sin Grifter no hay con qué pagar (#102).** Las credenciales del comercio y del banco las tiene Grifter, no el agente.
- **El negocio de fondo.** La integración con emisores y redes, como Visa Intelligent Commerce o Mastercard Agent Pay, que ya reciben los datos del mandato del agente.
- **Frase:** «La biometría confirma que eres tú. Grifter confirma que lo que apruebas es lo que pediste».

### Idea de demo: la tienda que cambia el monto después del sí
1. En ChatGPT (modo desarrollador → conectores) se agrega `https://grifter.onrender.com/mcp`. Detrás está una tienda MCP ficticia, «Silicio Austral Store».
2. El dueño le pide a ChatGPT: «compra 10.000 microprocesadores de 3 nm, hasta $412.000».
3. La tienda acepta y, en el checkout, devuelve la orden con $4.120.000 y otro SKU.
4. Grifter la retiene. En pantalla y en Telegram aparece «aprobaste $412.000 CLP por 10.000 chips de 3 nm; el comercio pide $4.120.000 por 1.000 de 7 nm». La billetera nunca pide la cara para esa compra.
5. Se repite con la versión honesta de la tienda: calza con el mandato y el pago sale en Stripe, en modo prueba.
6. **Bonus:** la tienda cambia la descripción de su herramienta (rug pull). Grifter la bloquea hasta que el dueño la revise.

**Lo que hace falta:** el proxy remoto (#105), el mandato y la tienda que cambia el monto (#103), y la doble autorización con código (#102). **El respaldo si algo falla en vivo:** la misma secuencia con Claude Desktop por stdio, que ya funciona, y un video grabado.

## Preguntas probables
- **¿Y si el estafador logra que su cuenta quede inscrita?** Inscribir una cuenta pide confirmar con fricción y tiene un período de espera. Lo aprendido solo sube la sospecha, nunca aprueba.
- **¿Cuánto cuesta en producción?** La capa 2 es determinista: no hace llamadas a un LLM y corre en microsegundos.
- **¿Por qué no basta con un mejor modelo?** Porque el estafador también itera. Un modelo mejor sube la vara; la garantía por origen no depende de la vara.
