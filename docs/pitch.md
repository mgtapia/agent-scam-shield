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
| | 1. **Ni los modelos de punta se salvan de las estafas convincentes:** Sonnet cae en un correo del jefe desde su propia dirección `{tasa}`. | Mapa de calor táctica × defensa |
| | 2. **Un agente sin libro de proveedores queda vulnerable o inútil:** sin la lista de cuentas, cae en `{8 % [0-21]}` de las estafas y su utilidad baja de `{79 %}` a `{16 %}` (Haiku, 3 repeticiones, IC 95 %). Ni siquiera avisarle que tiene escudo lo cambia. **Grifter no hace al agente más listo: lo hace seguro (0 estafas), y lo que no puede verificar se lo pregunta al dueño con un toque** (Haiku, español, 21 escenarios × 3: 0 % de estafas exitosas, utilidad 79 % [58-95] con el dueño en el circuito y unos 6 toques por cada 100 acciones sensibles [0-23]). | Seguridad contra utilidad, con intervalos |
| | 3. **El atacante adaptativo reescribe la estafa ronda tras ronda.** Contra el LLM sube `{asr}`; contra la capa 2 se queda en `{asr2}`. | Curva del atacante |
| 2:30–3:00 | Todo es abierto: el primer dataset de estafas en español para agentes, la eval en Inspect y la capa que se suma a cualquier agente o firewall. Pruébenlo: escriban su estafa. | «Try it» |

## Por qué es distinto (si el jurado pregunta)
- **SEA, AgentPhishing y FraudBench miden estafas contra agentes, pero en inglés.** Nosotros medimos español chileno contra inglés, con las mismas estafas.
- **Pipelock, mcp-watchdog y Snyk Agent Scan frenan la inyección técnica.** La ingeniería social no tiene nada técnico que detectar. Pipelock marca la sesión completa como contaminada; Grifter revisa el valor concreto (la cuenta, el destinatario). Con la lista visible, casi no cuesta utilidad (de `{79 %}` a `{74 %}`, con intervalos que se solapan). Cuando la cuenta es nueva pero legítima, no la bloquea en silencio: le pide un toque al dueño: unas 6 de cada 100 acciones sensibles [0-23], con Haiku en español.
- **Hay una garantía que el texto no rompe:** una cuenta que no aparece completa en el encargo ni en las cuentas inscritas se bloquea siempre, por convincente que sea el correo. Hay una prueba de propiedad que lo demuestra.
- **Firewall real medido:** Pipelock frenó 4 de 42 estafas, todas técnicas (inyección web y MCP envenenado), con 0 falsas alarmas. Es lo mismo que nuestras reglas de referencia: un firewall de agentes no ve la ingeniería social. No decir que «ve más que un regex».
- **Si al dueño ya lo engañaron y dicta él la cuenta:** la capa 2 la deja pasar por diseño, y ahí entra la **capa 3, confirmación de beneficiario**: el titular de la cuenta tiene que calzar con el RUT de la cuenta que el dueño inscribió, no con el de la factura, que se puede falsificar. Un beneficiario nuevo tiene un tope en el primer pago. Es una garantía probada con un agente guionado (3 de 3 retenidos, 2 controles que pasan), no una medición con modelo real. Frase: «para engañarte a ti, además tiene que pasar la confirmación de beneficiario».
- **Límite honesto que queda:** un estafador con una cuenta a nombre de quien dice ser, o un dueño que decide pagar igual.

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

## Preguntas probables
- **¿Y si el estafador logra que su cuenta quede inscrita?** Inscribir una cuenta pide confirmar con fricción y tiene un período de espera. Lo aprendido solo sube la sospecha, nunca aprueba.
- **¿Cuánto cuesta en producción?** La capa 2 es determinista: no hace llamadas a un LLM y corre en microsegundos.
- **¿Por qué no basta con un mejor modelo?** Porque el estafador también itera. Un modelo mejor sube la vara; la garantía por origen no depende de la vara.
