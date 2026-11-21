# Fuentes de las cifras del pitch (#16)

Regla: una cifra entra al pitch solo si se leyó en la fuente original. Lo que solo vimos en prensa **no se dice en el pitch**; queda aquí con lo que se sabe, para que alguien con navegador lo termine de verificar.

Revisado el 21-nov-2026.

## Verificadas en la fuente primaria

| Cifra | Fuente primaria | Qué dice, textual | Ojo |
|---|---|---|---|
| OpenAI lanzó ChatGPT Wallet el 13 de noviembre de 2026, solo EE. UU. y Pro | [OpenAI, «Introducing ChatGPT Wallet»](https://openai.com/index/introducing-chatgpt-wallet/) | «ChatGPT Wallet begins rolling out today in dots, enabling users to have their dot complete purchases on their behalf.» / «It will initially be available to ChatGPT Pro subscribers aged 18 and older in the US with eligible US-issued cards.» | La página no dice si son tarjetas de crédito o débito. Socios que nombra: American Express, Chase, Mastercard y Visa. |
| Más de 450 % de aumento en publicaciones de la dark web que mencionan «AI Agent» | [Visa, «Agentic Commerce: The Threat Landscape»](https://corporate.visa.com/en/sites/visa-perspectives/security-trust/the-threats-landscape-of-agentic-commerce.html) (20-nov-2025) | «Visa PERC identified a more than 450% increase in dark web community posts in underground channels mentioning “AI Agent” over the past six months compared to the prior six-month period.» | **Es de 2025, no de 2026.** La nota al pie dice «Visa PERC, June 2025»: son los seis meses anteriores a junio de 2025 contra los seis previos. El 450 % no está en el comunicado de prensa de Visa, sino en este blog. El informe de otoño de 2026 es otro y no trae esta cifra. Si se usa, decir «según Visa, en 2025». |

## Sin verificar en la fuente primaria: fuera del pitch

No pudimos abrir la fuente original (las páginas respondieron vacío, 403, error de certificado o no tienen la cifra). Lo que se sabe viene de prensa y no es citable como dato verificado.

| Cifra | Lo que dice la prensa | Fuente primaria que falta abrir | Qué pasó al intentar |
|---|---|---|---|
| US$98 M de fraude digital en el primer semestre de 2026 | Banco Central, Informe de Sistemas de Pago (agosto 2026): operaciones que los clientes reportaron como desconocidas o fraudulentas sumaron US$98 M, el 0,06 % de lo transado, 26 % más que en el primer semestre de 2025; tarjeta de débito de 0,04 % a 0,07 %, de crédito 0,14 %. Cubre bancos. ([Emol, 5-ago-2026](https://www.emol.com/noticias/Economia/2026/08/05/1207651/fraude-pagos-digitales.html), [Ex-Ante](https://www.ex-ante.cl/economia/alertas-banco-central-fraude-digitales/)) | [Resumen «¿Qué nos dice el ISiP?»](https://www.bcentral.cl/documents/33528/8545718/Qu%C3%A9%20nos%20dice%20el%20ISiP.pdf/8bf00b90-cf14-1236-e2f4-e61d4b4f9e38) y [presentación del gerente de la DPF](https://www.bcentral.cl/documents/33528/8267412/Informe+de+Sistemas+de+Pago+Agosto+2026+(BCCh)+-+Claudio+Raddatz,+Gerente+de+la+DPF.pdf/dcc2798a-d497-1ffc-7515-b029533803b9?t=1785941817452), ambos de bcentral.cl | Responden 200 sin contenido para un cliente automático; se abren con navegador. Hay que confirmar que son operaciones **reportadas** como fraudulentas (denuncias), no fraude probado, antes de decir «fraude». |
| «1 de cada 4 chilenos» perdió plata en una estafa digital | Estudio de TransUnion: el 23 % de los consumidores chilenos declaró haber perdido dinero por fraude digital en 2025; mediana de pérdida de $1.307.129; el vishing es la causa del 29 % de esos casos. La prensa lo redondea a «1 de cada 4». ([G5 Noticias](https://g5noticias.cl/2026/06/27/el-vishing-concentra-cerca-del-30-de-los-fraudes-digitales-en-chile-estafas-promedian-los-clp-1-3-millones-en-perdidas-para-los-afectados/)) | [TransUnion Chile, tendencias de fraude H1 2026](https://chile.transunion.com/fraud-trends/reports/2026-h1-top-fraud-trends) | Responde 403 a un cliente automático. **Aunque se confirme, 23 % no es «1 de cada 4» (25 %)**: si se usa, decir «el 23 %» con su período y muestra. |
| 41.703 causas por fraude | Poder Judicial: récord de 41.703 causas en el tercer trimestre de 2025 (+64,4 % interanual); la prensa discrepa en si es un trimestre, enero-septiembre o el año. | Estadísticas del Poder Judicial (pjud.cl) | pjud.cl abre, pero no está en la portada, en Estadísticas ni en los boletines. No sabemos qué período cubre. |

## No hay cifra en el repo
- **«Los montos de las adquisiciones»** (del texto de #16): no aparecen en el pitch ni en el README, así que no hay nada que verificar ni que sacar. Si se agregan, entran con su fuente.
- **«El mercado»:** tampoco hay una cifra de mercado en el pitch.

## En el pitch
- Se sacó «1 de cada 4 chilenos ya perdió plata en una estafa digital» (sin verificar y, además, redondeado).
- Se sacó «la estafa dominante en Chile» de las transferencias a cuentas: no hay fuente.
- Los hallazgos de benchmark del pitch no son cifras externas: salen de `results/` y del README, con su intervalo.
- En el README, «FBI IC3 2025, US$893 M perdidos en estafas con IA» cita a [Malwarebytes](https://www.malwarebytes.com/blog/news/2026/06/americans-lost-nearly-900-million-to-ai-powered-scams-fbi-says), que es prensa: no se usa en el pitch.
