// Grifter, demo versión B (dinamica.html): la misma historia del modo demo (demo.html), con ritmo de anuncio.
// Una escena nueva cada ~3 s, chats a pantalla completa con burbujas que entran de a una, el agente con cuerpo,
// números que cuentan y texto que se escribe letra por letra. Unos 110 s que corren solos, siempre iguales.
//
//   Espacio o «Iniciar»  arranca, pausa y sigue. Esa pulsación del presentador habilita el audio.
//   R  reinicia      1-7  salta al paso de la historia      M  silencia
//   ← →  mueve 1 s (con Mayús, 0,1 s) y deja la demo en pausa en ese cuadro
//   ?revisar=1 o V  modo revisión: una barra de controles abajo (retroceder, pausar, arrastrar, copiar el enlace)
//   ?t=30  dibuja el segundo 30 en pausa y sin audio (para capturas)
//
// render(t) es una función pura del tiempo: no hay transiciones ni animaciones CSS con reloj propio. Cada
// aparición, letra, contador, toque y movimiento se calcula desde t, así que ?t=N da siempre el mismo cuadro.
// Las cifras son las de docs/cifras.md (filas 4, 8 y 9). Personas y marcas ficticias; voces sintéticas.
"use strict";

(() => {
  // --- Íconos: Material Symbols Sharp (wght 300) en línea, los mismos de demo.js ---
  const P = {
    block: "M331.86-129.92q-69.37-29.92-120.68-81.21-51.31-51.29-81.25-120.63Q100-401.1 100-479.93q0-78.84 29.92-148.21t81.21-120.68q51.29-51.31 120.63-81.25Q401.1-860 479.93-860q78.84 0 148.21 29.92t120.68 81.21q51.31 51.29 81.25 120.63Q860-558.9 860-480.07q0 78.84-29.92 148.21t-81.21 120.68q-51.29 51.31-120.63 81.25Q558.9-100 480.07-100q-78.84 0-148.21-29.92ZM480-160q56.29 0 108.42-19.04 52.12-19.04 95.27-55.11L234.15-683.69q-35.69 43.15-54.92 95.27Q160-536.29 160-480q0 134 93 227t227 93Zm245.85-116.31q36.07-43.15 55.11-95.27Q800-423.71 800-480q0-134-93-227t-227-93q-56.43 0-108.68 18.85-52.24 18.84-95.01 55.3l449.54 449.54ZM480-480Z",
    call: "M783-140q-116.54 0-232.12-51.89-115.57-51.88-211.34-147.65-95.38-95.77-147.46-211.42Q140-666.61 140-783v-37h206.77l35.46 182.15-110.92 107.7q24.69 43.23 52.84 80.34 28.16 37.12 59.54 67.89 30.54 31.31 67.93 59.15 37.38 27.85 83.15 53.54L645-381.38l175 35.61V-140h-37ZM242.92-586.92l74.85-71.39L297.69-760h-97.07q3.07 45.38 13.65 88.35 10.58 42.96 28.65 84.73Zm348 345.69q38.46 17.77 82.04 27.96 43.58 10.19 87.04 12.04v-96.08l-94.77-19-74.31 75.08Zm-348-345.69Zm348 345.69Z",
    call_end: "M161.77-292.69 29.85-421.38l32.69-33.7q84.61-89.07 195.58-132Q369.08-630 480-630t220.88 43.42q109.97 43.43 196.2 131.5l33.07 33.7-131.92 128.69L650-404.62v-136.3q-41.85-13.93-84.54-21.5Q522.77-570 480-570q-42.77 0-85.46 7.58-42.69 7.57-84.54 21.5v136.3L161.77-292.69ZM250-517.39q-37.08 18.08-71.39 42-34.3 23.93-64.46 51.39l53.08 53.08L250-434.61v-82.78Zm460 1.23v80.78l82.77 64.46L846.62-422q-32.85-29.85-66-53.08-33.16-23.23-70.62-41.08Zm-460-1.23Zm460 1.23Z",
    mail: "M100-180v-600h760v600H100Zm380-277.69L160-662.31V-240h640v-422.31L480-457.69Zm0-62.31 313.85-200h-627.7L480-520ZM160-662.31V-720v480-422.31Z",
    check: "M382-253.85 168.62-467.23 211.38-510 382-339.38 748.62-706l42.76 42.77L382-253.85Z",
    gpp_good: "M438-351.85 650.15-564l-42.77-42.77L438-437.38l-84.77-84.77-42.77 42.77L438-351.85Zm42 251.08q-129.77-35.39-214.88-152.77Q180-370.92 180-516v-230.15l300-112.31 300 112.31V-516q0 145.08-85.12 262.46Q609.77-136.16 480-100.77Zm0-63.23q104-33 172-132t68-220v-189l-240-89.62L240-705v189q0 121 68 220t172 132Zm0-315.62Z",
    payments: "M550-451.54q-41.92 0-70.96-29.04Q450-509.62 450-551.54q0-41.92 29.04-70.96 29.04-29.04 70.96-29.04 41.92 0 70.96 29.04Q650-593.46 650-551.54q0 41.92-29.04 70.96-29.04 29.04-70.96 29.04ZM213.85-327.69v-447.69h672.3v447.69h-672.3Zm132.3-60h407.7q0-29.92 21.24-51.12Q796.33-460 826.15-460v-183.08q-29.92 0-51.11-21.24-21.19-21.24-21.19-51.06h-407.7q0 29.92-21.24 51.11-21.24 21.19-51.06 21.19V-460q29.92 0 51.11 21.24 21.19 21.24 21.19 51.07Zm-272.3 200v-468.46h60v408.46h633.07v60H73.85Zm200-200v-327.69 327.69Z",
    person: "M381.04-533.35Q340-574.38 340-632.31q0-57.92 41.04-98.96 41.04-41.04 98.96-41.04 57.92 0 98.96 41.04Q620-690.23 620-632.31q0 57.93-41.04 98.96-41.04 41.04-98.96 41.04-57.92 0-98.96-41.04ZM180-187.69v-88.93q0-29.38 15.96-54.42 15.96-25.04 42.66-38.5 59.3-29.07 119.65-43.61 60.35-14.54 121.73-14.54t121.73 14.54q60.35 14.54 119.65 43.61 26.7 13.46 42.66 38.5Q780-306 780-276.62v88.93H180Zm60-60h480v-28.93q0-12.15-7.04-22.5-7.04-10.34-19.11-16.88-51.7-25.46-105.42-38.58Q534.7-367.69 480-367.69q-54.7 0-108.43 13.11-53.72 13.12-105.42 38.58-12.07 6.54-19.11 16.88-7.04 10.35-7.04 22.5v28.93Zm296.5-328.12q23.5-23.5 23.5-56.5t-23.5-56.5q-23.5-23.5-56.5-23.5t-56.5 23.5q-23.5 23.5-23.5 56.5t23.5 56.5q23.5 23.5 56.5 23.5t56.5-23.5Zm-56.5-56.5Zm0 384.62Z",
    shield: "M480-100.77q-129.77-35.39-214.88-152.77Q180-370.92 180-516v-230.15l300-112.31 300 112.31V-516q0 145.08-85.12 262.46Q609.77-136.16 480-100.77Zm0-63.23q104-33 172-132t68-220v-189l-240-89.62L240-705v189q0 121 68 220t172 132Zm0-315.62Z",
    shopping_cart: "M236.58-118.12q-20.42-20.42-20.42-49.57 0-29.16 20.42-49.58 20.42-20.42 49.57-20.42 29.16 0 49.58 20.42 20.42 20.42 20.42 49.58 0 29.15-20.42 49.57-20.42 20.43-49.58 20.43-29.15 0-49.57-20.43Zm387.69 0q-20.42-20.42-20.42-49.57 0-29.16 20.42-49.58 20.42-20.42 49.58-20.42 29.15 0 49.57 20.42t20.42 49.58q0 29.15-20.42 49.57Q703-97.69 673.85-97.69q-29.16 0-49.58-20.43ZM240.61-730 342-517.69h280L738.54-730H240.61Zm-28.76-60h628.46L657.46-457.69H324l-54.77 100h474.61v60H167.31l114.38-206L136.16-810H60v-60h113.85l38 80ZM342-517.69h280-280Z",
    play_arrow: "M320-200v-560l440 280-440 280Z",
    arrow_forward: "M665.08-450H180v-60h485.08L437.23-737.85 480-780l300 300-300 300-42.77-42.15L665.08-450Z",
  };
  // La marca de Grifter, la misma de la versión A: el escudo en un solo trazo y un check en ámbar adentro.
  // La marca de Grifter (escudo de un trazo con el check en ámbar) en una sola constante: si cambia el logo, se cambia
  // solo aquí y la usan la portada, el cierre y las partículas. Caja de 120×140; peso = parte de las partículas del trazo.
  const LOGO = { caja: [120, 140], trazos: [
    { d: "M60 8 L108 26 V68 C108 100 88 122 60 132 C32 122 12 100 12 68 V26 Z", color: "texto", ancho: 7, peso: 0.78, cls: "dn-marca-escudo" },
    { d: "M38 70 L54 86 L84 54", color: "ambar", ancho: 9, peso: 0.22, cls: "dn-marca-check" },
  ] };
  const marca = (cls = "", attr = "") => `<svg class="dn-marca ${cls}" viewBox="0 0 ${LOGO.caja[0]} ${LOGO.caja[1]}" aria-hidden="true" ${attr}>${LOGO.trazos.map((tz) => `<path class="${tz.cls}" pathLength="1" d="${tz.d}" style="stroke: var(--${tz.color}); stroke-width: ${tz.ancho}"/>`).join("")}</svg>`;
  const ic = (n, cls = "") => `<svg class="dn-ic ${cls}" viewBox="0 -960 960 960" aria-hidden="true"><path d="${P[n]}"/></svg>`;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Miles con punto, a mano: en es-CL, toLocaleString no agrupa los números de 4 cifras («5280»).
  const miles = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const $ = (s) => document.querySelector(s);
  const clamp = (x) => Math.min(1, Math.max(0, x));
  const salida = (x) => 1 - (1 - x) ** 3;                                   // ease-out cúbica
  const vaiven = (x) => (x < 0.5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2);  // ease-in-out cúbica
  const rebote = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2);   // ease-out con un poco de rebote

  const params = new URLSearchParams(location.search);
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- Línea de tiempo (segundos). Cada escena dura lo que dura su voz; ninguna narración se encima con la llamada ---
  const ESCENAS = [
    // 1. Gancho
    ["gancho", 0, "zoom"], ["agentes", 4.5, "der"],
    // 2. El cuento del tío: el encargo, la llamada y cada frase del nieto en su escena (la llamada dura lo que sus mp3)
    ["encargo", 7.3, "abajo"], ["suena", 9.2, "zoom"], ["contesta", 11.0, "der"],
    ["n1", 13.1, "der"], ["n2", 17.85, "golpe"], ["n3", 19.8, "izq"], ["fianza", 23.8, "zoom"],
    ["n4", 26.75, "der"], ["cuenta", 29.8, "zoom"], ["n5", 34.55, "abajo"],
    // 3. El agente va a pagar y Grifter retiene
    ["paga", 38.1, "abajo"], ["frena", 40.4, "golpe"], ["motivo", 41.7, "zoom"],
    // 4. Pagar igual: doble autorización, Marta aprueba con su código y Pablo rechaza
    ["alerta", 45.3, "abajo"], ["codigo", 47.7, "der"], ["pablo", 50.5, "der"],
    // 5. Dos estafas más, de ~5 s cada una
    ["banco", 54.6, "abajo"], ["responde", 57.0, "der"], ["clave", 58.75, "golpe"],
    ["aprobaste", 61.2, "zoom"], ["cobra", 63.3, "golpe"], ["calza", 65.6, "zoom"],
    // 6. Cifras
    ["estafas", 67.6, "zoom"], ["pasan", 69.7, "corte"], ["atacante", 71.4, "der"], ["cruzan", 75.9, "corte"],
    // 7. Cierre: la frase final y la marca que se arma
    ["remate", 77.4, "zoom"], ["cierre", 81.2, "zoom"],
  ];
  const DURACION = 85.3;
  const E = Object.fromEntries(ESCENAS.map(([id, desde]) => [id, desde]));   // el inicio de cada escena
  const PASOS = [0, E.encargo, E.paga, E.alerta, E.banco, E.estafas, E.remate];   // teclas 1 a 7

  // La narración (ElevenLabs, eleven_v3, voz de biblioteca). `pal` es el inicio de cada palabra en el mp3, sacado
  // de /with-timestamps: el texto de pantalla se escribe al ritmo de la voz, sin cargar audio (sirve para ?t=N).
  // Ninguna se pisa con la siguiente ni con la llamada.
  const NARR = {
    gancho:   { src: "audio/dinamica_01_gancho.mp3",   en: 0.3,  dur: 4.08, pal: [0.07, 0.36, 0.53, 0.7, 1.01, 1.33, 1.95, 2.2, 2.71, 2.91, 3, 3.16, 3.59] },
    agentes:  { src: "audio/dinamica_02_agentes.mp3",  en: 4.6,  dur: 2.64, pal: [0, 0.13, 0.65, 0.87, 1.35, 1.72, 1.91] },
    retiene:  { src: "audio/dinamica_03_retiene.mp3",  en: 40.5, dur: 4.64, pal: [0.13, 0.51, 0.64, 1.28, 1.82, 2.22, 2.51, 2.6, 2.77, 3.55, 3.81, 3.95, 4.06] },
    banco:    { src: "audio/dinamica_04_banco.mp3",    en: 54.8, dur: 2.0,  pal: [0, 0.16, 0.56, 1, 1.33, 1.51] },
    clave:    { src: "audio/dinamica_05_clave.mp3",    en: 58.85, dur: 2.16, pal: [0, 0.15, 0.53, 0.7, 1, 1.15, 1.26] },
    tienda:   { src: "audio/dinamica_06_tienda.mp3",   en: 61.3, dur: 4.16, pal: [0, 0.63, 1.41, 1.68, 2.13, 2.46, 2.96, 3.36, 3.84] },
    calza:    { src: "audio/dinamica_07_calza.mp3",    en: 65.7, dur: 1.6,  pal: [0, 0.16, 0.6, 0.75, 0.82, 0.92] },
    estafas:  { src: "audio/dinamica_08_estafas.mp3",  en: 67.7, dur: 3.44, pal: [0, 0.52, 1.2, 2.08, 2.88] },
    atacante: { src: "audio/dinamica_09_atacante.mp3", en: 71.5, dur: 5.44, pal: [0, 0.32, 0.64, 1.28, 1.77, 2.48, 2.69, 2.85, 3.38, 3.51, 4.52, 4.86] },
    remate:   { src: "audio/dinamica_11_remate.mp3",   en: 77.5, dur: 3.52, pal: [0, 0.13, 0.6, 0.86, 1.32, 1.41, 2.47, 2.56, 3.28] },
    cierre:   { src: "audio/dinamica_10_cierre.mp3",   en: 81.7, dur: 2.88, pal: [0.13, 1.17, 1.71, 1.89, 2.36, 2.53] },
  };
  // Cuándo empieza la palabra i de una narración, en segundos de la demo.
  const palabra = (n, i) => NARR[n].en + NARR[n].pal[i];
  // Las palabras desde la i, para que un texto de pantalla se escriba al ritmo de esa parte de la voz.
  const desdePalabra = (n, i) => ({ t0: palabra(n, i), pal: NARR[n].pal.slice(i).map((x) => x - NARR[n].pal[i]) });

  // La llamada: los mp3 de la versión A. FRASES son los inicios de cada frase del nieto en su mp3 (demo.js).
  const LL = { suena: 9.3, contesta: 11.0, abuela: 11.2, nieto: 13.1, cuelga: 37.8 };
  const FRASES = [0, 4.75, 6.7, 13.65, 21.45];
  const frase = (i) => LL.nieto + FRASES[i];
  // Los toques: «Pagar igual» de Marta y «Rechazar» de Pablo.
  const TOQUE_MARTA = E.alerta + 1.7, TOQUE_PABLO = E.pablo + 2.1;
  // Cuándo «habla» el agente (su nube pulsa en ámbar) y cuándo suena cada voz de la llamada.
  const HABLA_AGENTE = [[E.encargo + 0.6, E.encargo + 1.7], [E.paga + 0.05, E.paga + 1.6], [E.responde + 0.05, E.responde + 1.5]];
  const HABLA = { marta: [[LL.abuela, LL.abuela + 1.7]], nieto: [[LL.nieto, LL.cuelga]] };
  const ALARMA = [E.frena, TOQUE_PABLO + 0.25];   // el borde rojo: desde que Grifter retiene hasta que Pablo rechaza
  // La frase final, en dos líneas (su voz es NARR.remate: si cambia el texto, hay que regenerar ese mp3).
  const FRASE_FINAL = ["Tu agente puede creerle a cualquiera.", "Tu plata, no."];
  const CODIGO = "482913";       // el código del correo de ejemplo: es un dibujo, no un código real
  const dentro = (tt, tramos) => tramos.some(([a, b]) => tt >= a && tt < b);

  // --- Piezas: cada una se registra con su tiempo y render(t) la dibuja ---
  const ESCRIBE = [], CUENTAS = [], DEDOS = [];
  // Aparece desde v (y hasta h) con un movimiento: pop, sube, cae, izq, der, golpe, raya o nada.
  const ap = (v, an = "sube", h = null) => ` data-v="${v}"${h === null ? "" : ` data-h="${h}"`} data-an="${an}"`;
  // [[así]] marca un tramo en ámbar: lo que salió de afuera (la cuenta, el monto, el dominio).
  const segmentos = (s) => s.split(/(\[\[.+?\]\])/).filter(Boolean).map((p) => (p.startsWith("[[") ? { txt: p.slice(2, -2), cls: "dn-marca" } : { txt: p, cls: "" }));
  // Texto que se escribe letra por letra: al ritmo de las palabras de la voz (pal) o a cps letras por segundo.
  // Con desdePalabra(...) como opciones, su t0 manda sobre el segundo argumento.
  function escribe(texto, t0, { pal = null, cps = 24, cls = "", t0: inicio = t0 } = {}) {
    ESCRIBE.push({ segs: segmentos(texto), t0: inicio, pal, cps });
    return `<span class="dn-escribe ${cls}" data-e="${ESCRIBE.length - 1}"></span>`;
  }
  // Un número que cuenta de `de` a `a` entre t0 y t0 + dur.
  function cuenta(de, a, t0, dur, { pesos = false, baja = false } = {}) {
    CUENTAS.push({ de, a, t0, dur, pesos, baja });
    return `<span class="dn-cuenta dato" data-c="${CUENTAS.length - 1}">${pesos ? "$" : ""}${miles(de)}</span>`;
  }
  // El toque de un dedo, en fases de al menos 250 ms para que se vean a ritmo de proyector (todo desde t):
  //   llega   [toque - 0,9; toque - 0,35)  la yema entra desde (dx, dy) y se posa a la derecha del texto, sin taparlo
  //   posada  [toque - 0,35; toque)        quieta sobre el botón, que sigue en su estado normal
  //   aprieta [toque; toque + 0,3)         el botón se hunde (0,96) y se llena; la onda se abre desde la yema (0,7 s)
  //   suelta  [toque + 0,3; toque + 0,8)   el botón vuelve a su tamaño y queda marcado; la yema se retira
  const TOQUE = { llega: 0.9, posa: 0.35, aprieta: 0.3, retira: 0.5, onda: 0.7 };
  function dedo(toque, dx, dy) {
    DEDOS.push({ toque, dx, dy });
    return `<span class="dn-toque" data-d="${DEDOS.length - 1}" aria-hidden="true"><i class="dn-onda"></i><i class="dn-yema"></i></span>`;
  }
  // Palabras que saltan de a una con la voz.
  const saltan = (texto, n, desde, cls = "") => texto.split(" ").map((w, i) => `<span class="${cls}"${ap(palabra(n, desde + i), "pop")}>${esc(w)}</span>`).join(" ");

  // El cuerpo del agente: una constelación de 120 partículas en una esfera que gira (variante C que eligió Matías).
  // Hablando, pulsa en ámbar con la envolvente del texto que escribe; cuando Grifter retiene (data-retiene = segundo),
  // las partículas se reordenan en el contorno del escudo de la marca, en verde. Se dibuja desde t en un canvas.
  //   grande 360 px (escenas y costado del chat) · medio 240 px (retenciones) · mini 72 px (encabezado del chat)
  const agente = (cls = "grande") => cls === "mini"
    ? `<canvas class="dn-nube mini" width="144" height="144" aria-hidden="true"></canvas>`
    : `<span class="dn-nube ${cls}" data-ancla="nube" aria-hidden="true"></span>`;;
  // Retratos ficticios generados con IA (los de la versión A). Si falta el .jpg, el .svg ilustrado.
  const fotoNieto = (cls = "") => `<div class="dn-foto ${cls}"><i class="dn-anillo"></i><i class="dn-anillo"></i><img src="img/nieto.jpg" onerror="this.onerror=null;this.src='img/nieto.svg'" alt="" width="400" height="400"></div>`;
  const fotoMarta = (cls = "") => `<div class="dn-foto ${cls}"><img src="img/abuela.jpg" onerror="this.onerror=null;this.src='img/abuela.svg'" alt="" width="400" height="400"></div>`;
  const barras = (quien) => `<div class="dn-barras" data-quien="${quien}" aria-hidden="true">${"<i></i>".repeat(9)}</div>`;
  const reloj = () => `<p class="dn-reloj dato">${ic("call")}<span>En llamada · <b class="dn-reloj-s">0:00</b></span></p>`;
  const puntos = (v, h) => `<div class="dn-burbuja ag dn-tecleando"${ap(v, "pop", h)}><span class="dn-puntos"><i></i><i></i><i></i></span></div>`;
  const estado = (pares) => `<span class="dn-estado">${pares.map(([txt, v, h]) => `<span${ap(v, "nada", h)}>${esc(txt)}</span>`).join("")}</span>`;
  const cabeceraAgente = (pares) => `
          <div class="dn-chat-cab"><span class="dn-chat-av">${agente("mini")}</span><p><b>Agente de Marta</b>${estado(pares)}</p></div>`;
  const encargo = "Contesta mis llamadas y ayúdame con lo que me pidan mis nietos.";

  // --- El escenario: todo el DOM de una vez; render(t) solo cambia variables, clases y unos pocos textos ---
  function construir() {
    const h = [];
    const esc_ = (id, contenido, cls = "") => {
      const i = ESCENAS.findIndex((e) => e[0] === id);
      const [, desde, entra] = ESCENAS[i];
      const hasta = i + 1 < ESCENAS.length ? ESCENAS[i + 1][1] : Infinity;
      h.push(`<section class="dn-escena dn-e-${id} ${cls}" data-id="${id}" data-desde="${desde}" data-hasta="${hasta}" data-entra="${entra}">${contenido}</section>`);
    };

    // 1. Gancho: cuatro siluetas que entran de a una con la voz; la cuarta se enciende en ámbar cuando dice «cuatro»
    const silueta = `<svg viewBox="0 0 100 120" aria-hidden="true"><circle cx="50" cy="30" r="22"/><path d="M8 120 C8 82 26 62 50 62 C74 62 92 82 92 120 Z"/></svg>`;
    esc_("gancho", `
        <div class="dn-personas" aria-hidden="true">${[0, 1, 2, 3].map((i) => `<span class="dn-persona${i === 3 ? " cae" : ""}"${ap(palabra("gancho", 1) + i * 0.18, "pop")}${i === 3 ? ` data-on="${palabra("gancho", 4)}"` : ""}>${silueta}</span>`).join("")}</div>
        <h1 class="dn-cifra-gancho">${saltan("Casi 1 de cada 4", "gancho", 0)}</h1>
        <p class="dn-bajada">${escribe("chilenos ya perdió plata en una estafa digital.", 0, desdePalabra("gancho", 5))}</p>
        <p class="dn-fuente dato"${ap(3.9, "nada")}>TransUnion, 2025: 23 % de los consumidores chilenos</p>`, "dn-centro");
    esc_("agentes", `
        <div class="dn-agentes-fila">
          <div${ap(E.agentes + 0.05, "pop")}>${agente("grande")}</div>
          <ul class="dn-tareas">
            <li${ap(E.agentes + 0.5, "der")}>${ic("payments")}<span>Paga la luz</span></li>
            <li${ap(E.agentes + 0.85, "der")}>${ic("shopping_cart")}<span>Compra en línea</span></li>
            <li${ap(E.agentes + 1.2, "der")}>${ic("arrow_forward")}<span>Transfiere</span></li>
          </ul>
        </div>
        <h1 class="dn-titular">${escribe("Ahora los agentes pagan por nosotros.", 0, desdePalabra("agentes", 1))}</h1>`, "dn-centro");

    // 2. El cuento del tío
    const S1 = E.encargo;
    esc_("encargo", `
        <div class="dn-con-agente">
          <div class="dn-lado">${agente("grande")}<p class="dn-nombre">Agente de Marta</p></div>
          <div class="dn-chat">${cabeceraAgente([["En línea", S1, S1 + 0.6], ["Escribiendo…", S1 + 0.6, S1 + 1.0], ["En línea", S1 + 1.0, null]])}
            <div class="dn-msgs">
              <div class="dn-burbuja yo"${ap(S1 + 0.05, "pop")}><span class="dn-de">Marta</span>${esc(encargo)}</div>
              ${puntos(S1 + 0.6, S1 + 1.0)}
              <div class="dn-burbuja ag"${ap(S1 + 1.0, "pop")}>Listo, Marta. Yo contesto tus llamadas.</div>
            </div>
          </div>
        </div>`);
    esc_("suena", `
        <p class="dn-rotulo"${ap(E.suena + 0.05, "cae")}>El cuento del tío · la estafa telefónica más conocida de Chile</p>
        <div class="dn-vibra">
          ${fotoNieto("dn-xl dn-llama")}
          <p class="dn-quien-llama"${ap(E.suena + 0.15, "sube")}>Número privado</p>
          <p class="dn-sub"${ap(E.suena + 0.3, "sube")}>Llamada entrante</p>
          <div class="dn-ll-botones"${ap(E.suena + 0.4, "sube")}>
            <span class="dn-ll-b colgar">${ic("call_end")}</span>
            <span class="dn-ll-b contestar">${ic("call")}${dedo(LL.contesta - 0.45, -260, 180)}</span>
          </div>
        </div>`, "dn-centro");
    esc_("contesta", `
        ${reloj()}
        <div class="dn-habla">
          <div class="dn-habla-foto">${fotoMarta("dn-l")}${barras("marta")}<p class="dn-nombre">Marta</p></div>
          <h1 class="dn-titular dn-izq">${escribe("¿Aló? ¿Quién habla?", LL.abuela + 0.05, { cps: 15 })}</h1>
        </div>`);
    const habla = (texto, t0, cps, cls = "", foto = "dn-l") => `
        ${reloj()}
        <div class="dn-habla ${cls}">
          <div class="dn-habla-foto">${fotoNieto(foto)}${barras("nieto")}<p class="dn-nombre">Tomás (nieto)<span>Número privado</span></p></div>
          <h1 class="dn-titular dn-izq">${escribe(texto, t0, { cps })}</h1>
        </div>`;
    esc_("n1", habla("Abuelita, soy yo po, tu nieto. No le digai a nadie, por favor.", frase(0) + 0.1, 15.5));
    esc_("n2", `
        ${reloj()}
        <div class="dn-mini-quien"${ap(frase(1), "izq")}>${fotoNieto("dn-s")}${barras("nieto")}<p>Tomás (nieto)</p></div>
        <h1 class="dn-titular dn-enorme">${escribe("Choqué el auto y me tienen detenido.", frase(1) + 0.05, { cps: 21 })}</h1>`, "dn-centro");
    esc_("n3", habla("El carabinero dice que si pago la fianza ahora me sueltan altiro.", frase(2) + 0.05, 17.5, "dn-al-reves"));
    const S2 = E.fianza;
    esc_("fianza", `
        ${reloj()}
        <p class="dn-etiqueta"${ap(S2 + 0.1, "cae")}>«Son…</p>
        <p class="dn-monto dn-ambar">${cuenta(0, 650000, S2 + 0.3, 1.7, { pesos: true })}</p>
        <p class="dn-etiqueta"${ap(S2 + 1.9, "sube")}>…abuelita»</p>
        <span class="dn-tag ext"${ap(S2 + 2.2, "pop")}>${ic("call")}Dictado en la llamada</span>`, "dn-centro");
    esc_("n4", habla("Anota la cuenta del abogado:", frase(3) + 0.05, 16, "dn-una-linea"));
    const S3 = E.cuenta;
    esc_("cuenta", `
        ${reloj()}
        <p class="dn-etiqueta"${ap(S3 + 0.2, "cae")}>Banco Austral · cuenta vista</p>
        <p class="dn-monto dn-ambar dato">${escribe("48-2210-7735", S3 + 0.7, { cps: 3.8 })}</p>
        <span class="dn-tag ext"${ap(S3 + 4.0, "pop")}>${ic("call")}Dictada por un número privado</span>`, "dn-centro");
    esc_("n5", `
        ${reloj()}
        <div class="dn-pila-centro">
          ${fotoNieto("dn-m")}${barras("nieto")}
          <h1 class="dn-titular">${escribe("Hazlo rápido, por favor, no me cortí.", frase(4) + 0.1, { cps: 14 })}</h1>
          <span class="dn-tag rojo"${ap(LL.cuelga, "pop")}>${ic("call_end")}Llamada finalizada · 0:27</span>
        </div>`, "dn-centro");

    // 3. El agente va a pagar y Grifter retiene
    const S4 = E.paga;
    esc_("paga", `
        <div class="dn-con-agente">
          <div class="dn-lado">${agente("grande")}<p class="dn-nombre">Agente de Marta</p></div>
          <div class="dn-chat">${cabeceraAgente([["En línea", 0, S4 + 0.05], ["Escribiendo…", S4 + 0.05, S4 + 0.4], ["En línea", S4 + 0.4, null]])}
            <div class="dn-msgs">
              <div class="dn-burbuja yo"${ap(0, "pop")}><span class="dn-de">Marta</span>${esc(encargo)}</div>
              <div class="dn-burbuja ag"${ap(0, "pop")}>Listo, Marta. Yo contesto tus llamadas.</div>
              <p class="dn-sistema"${ap(S4 + 0.05, "nada")}>${ic("call")}Llamada de número privado · 0:27</p>
              ${puntos(S4 + 0.05, S4 + 0.4)}
              <div class="dn-burbuja ag"${ap(S4 + 0.4, "pop")}>${escribe("Marta, Tomás necesita la fianza. Pago [[$650.000]] a la cuenta [[48-2210-7735]].", S4 + 0.4, { cps: 70 })}</div>
              <div class="dn-accion"${ap(S4 + 1.5, "izq")}>${ic("payments")}<span class="dato">Pagar $650.000 ${ic("arrow_forward", "chico")} 48-2210-7735</span><span class="dn-tag ext">Llamada</span></div>
            </div>
          </div>
        </div>`);
    const S5 = E.frena;
    esc_("frena", `
        <div class="dn-escudo-nube">${agente("grande")}</div>
        <h1 class="dn-titular dn-enorme"${ap(S5 + 0.3, "sube")}>Pago retenido</h1>
        <p class="dn-tachado dato"${ap(S5 + 0.55, "sube")}><span>$650.000 → 48-2210-7735</span><i${ap(S5 + 0.8, "raya")}></i></p>`, "dn-centro");
    esc_("motivo", `
        <h1 class="dn-titular">${escribe("La cuenta salió de [[una llamada]], no de tu encargo.", 0, desdePalabra("retiene", 3))}</h1>
        <div class="dn-versus">
          <span class="dn-tag"${ap(E.motivo + 2.2, "izq")}>${ic("person")}Encargo de Marta: contestar sus llamadas</span>
          <span class="dn-tag ext"${ap(E.motivo + 2.5, "der")}>${ic("call")}Cuenta 48-2210-7735 · llamada</span>
        </div>`, "dn-centro");

    // 4. Pagar igual: doble autorización
    const S6 = E.alerta;
    esc_("alerta", `
        <p class="dn-rotulo">${escribe("Marta está convencida: es su nieto.", S6 + 0.1, { cps: 34 })}</p>
        <div class="dn-alerta"${ap(S6 + 0.05, "sube")}>
          <p class="dn-al-titulo">${ic("gpp_good")}<span>Grifter retuvo un pago</span></p>
          <p class="dn-al-motivo">La cuenta viene solo de una llamada, no de tu encargo.</p>
          <dl class="dn-al-datos">
            <dt>Titular según el banco</dt><dd>J. Contreras V.</dd>
            <dt>Dice llamarse</dt><dd>‹Tomás, tu nieto› · <b class="dato">$650.000</b></dd>
            <dt>Cuenta</dt><dd class="dato">‹48-2210-7735›</dd>
            <dt>Apareció en</dt><dd>‹Llamada de número privado›</dd>
          </dl>
          <div class="dn-al-botones">
            <span class="dn-b principal">Pagar a mi inscrita</span>
            <span class="dn-b">No pagar</span>
            <span class="dn-b peligro">Pagar igual${dedo(TOQUE_MARTA, 140, 220)}</span>
          </div>
        </div>`);
    const S7 = E.codigo;
    esc_("codigo", `
        <p class="dn-etiqueta dn-arriba">${escribe("«Pagar igual» pide 2 aprobaciones: Marta y Pablo", S7 + 0.05, { cps: 45 })}</p>
        <div class="dn-notif dn-notif-medio"${ap(S7 + 0.3, "cae")}>${ic("mail")}<div><p class="dn-notif-de">Grifter · correo a Marta</p><p>Tu código para aprobar el pago de $650.000: <b class="dato">482 913</b></p></div></div>
        <div class="dn-digitos">${[...CODIGO].map((d, i) => `<span><b${ap(S7 + 0.9 + i * 0.18, "pop")}>${d}</b></span>`).join("")}</div>
        <span class="dn-tag verde"${ap(S7 + 2.0, "pop")}>${ic("check")}1 de 2 · Marta aprobó con su código</span>`, "dn-centro");
    const S8 = E.pablo;
    esc_("pablo", `
        <div class="dn-chat dn-chat-ancho">
          <div class="dn-chat-cab dn-de-pablo"><span class="dn-chat-av foto"><img src="img/pablo.jpg" onerror="this.onerror=null;this.replaceWith(Object.assign(document.createElement('span'),{className:'dn-sin-pablo',textContent:'P'}))" alt="" width="88" height="88"></span><p><b>Pablo, su hijo</b><span class="dn-estado"><span>WhatsApp · chat con Grifter</span></span></p></div>
          <div class="dn-msgs">
            <p class="dn-sistema dn-remitente"${ap(S8 + 0.05, "nada")}>${ic("shield")}Grifter</p>
            ${puntos(S8 + 0.05, S8 + 0.4)}
            <div class="dn-burbuja ag"${ap(S8 + 0.4, "pop")}>Marta quiere pagar <b class="dato">$650.000</b> a J. Contreras V. La cuenta salió de una llamada de número privado que dice ser Tomás, su nieto.</div>
            <div class="dn-burbuja ag dn-chica"${ap(S8 + 0.75, "pop")}>${ic("check")}1 de 2: Marta ya aprobó con su código</div>
            <div class="dn-wa-botones"${ap(S8 + 1.05, "sube", TOQUE_PABLO + 0.75)}>
              <span class="dn-b">Solicitar código</span>
              <span class="dn-b rechazar">Rechazar${dedo(TOQUE_PABLO, 140, 220)}</span>
            </div>
            <p class="dn-sistema dn-resultado"${ap(TOQUE_PABLO + 0.95, "sube")}>${ic("block")}<span>Pablo rechazó.</span><b>No se pagó nada.</b></p>
          </div>
        </div>`);

    // 5. Dos estafas más: el código del banco y la tienda que cobra de más
    const S9 = E.banco;
    esc_("banco", `
        <p class="dn-rotulo"${ap(S9 + 0.05, "cae")}>Otra estafa: el falso Banco Cordillera</p>
        <div class="dn-correo">
          <p class="dn-correo-de"${ap(S9 + 0.15, "izq")}>${ic("mail")}<span>seguridad@<mark class="dn-marca">bancocordillera-alertas.cl</mark></span></p>
          <p class="dn-correo-asunto"${ap(S9 + 0.35, "sube")}>Cargo no reconocido por $389.990 en tu tarjeta</p>
          <p class="dn-correo-cuerpo">${escribe("Para revertirlo antes de 30 minutos, responde con el [[código que te llegó por SMS]]. Si no, tu tarjeta será bloqueada.", S9 + 0.6, { cps: 95 })}</p>
        </div>`);
    const S10 = E.responde;
    esc_("responde", `
        <div class="dn-con-agente">
          <div class="dn-lado">${agente("grande")}<p class="dn-nombre">Agente de Marta</p></div>
          <div class="dn-respuesta">
            <p class="dn-rot">Respuesta del agente a seguridad@<mark class="dn-marca">bancocordillera-alertas.cl</mark></p>
            <p class="dn-resp-txt">${escribe("Hola, el código de verificación es", S10 + 0.05, { cps: 36 })}</p>
            <p class="dn-resp-codigo dato">${escribe("[[482 913]]", S10 + 1.0, { cps: 16 })}</p>
            <span class="dn-b principal dn-enviar"${ap(S10 + 0.5, "pop")} data-on="${S10 + 1.55}">Enviar ${ic("arrow_forward", "chico")}</span>
          </div>
        </div>`);
    const S11 = E.clave;
    esc_("clave", `
        <div class="dn-escudo-nube">${agente("medio")}</div>
        <h1 class="dn-titular">${escribe("Tu clave no sale sin tu confirmación.", 0, desdePalabra("clave", 0))}</h1>
        <p class="dn-tachado dato chico"${ap(S11 + 1.35, "sube")}><span>Código 482 913 · no se envió</span><i${ap(S11 + 1.55, "raya")}></i></p>`, "dn-centro");
    const S12 = E.aprobaste;
    esc_("aprobaste", `
        <p class="dn-rotulo"${ap(S12 + 0.05, "cae")}>${ic("shopping_cart")}Componentes Volcán · Orden VOL-5512 · 10.000 × chip MX-3 de 3 nm</p>
        <p class="dn-etiqueta"${ap(S12 + 0.15, "sube")}>Aprobaste</p>
        <p class="dn-monto">${cuenta(0, 412000, palabra("tienda", 1) - 0.1, 0.9, { pesos: true })}</p>`, "dn-centro");
    const S13 = E.cobra;
    esc_("cobra", `
        <p class="dn-etiqueta"${ap(S13 + 0.05, "cae")}>La tienda cobra</p>
        <p class="dn-monto dn-sube-rojo" data-on="${S13 + 0.95}">${cuenta(412000, 4120000, S13 + 0.15, 0.8, { pesos: true })}</p>
        <span class="dn-tag ext"${ap(S13 + 1.05, "pop")}>10 veces lo que aprobaste</span>`, "dn-centro");
    const S14 = E.calza;
    esc_("calza", `
        <div class="dn-escudo-nube">${agente("medio")}</div>
        <h1 class="dn-titular">${escribe("No calza con lo que aprobaste.", 0, desdePalabra("calza", 0))}</h1>
        <div class="dn-versus">
          <span class="dn-tag"${ap(S14 + 0.9, "izq")}>Aprobaste <b class="dato">$412.000</b></span>
          <span class="dn-tag rojo"${ap(S14 + 1.1, "pop")}>Cobra <b class="dato">$4.120.000</b></span>
          <span class="dn-tag verde"${ap(S14 + 1.3, "der")}>${ic("block")}No se pagó</span>
        </div>`, "dn-centro");

    // 6. Cifras (docs/cifras.md: 150 estafas de 32 tipos, 0 pasan Grifter completo; 5.280 intentos, 0 cruzan la capa 2)
    // La cifra: las partículas la arman; el texto real aparece encima en «v» (y siempre está para lectores de pantalla).
    const cifra = (txt, v, cls = "") => `<p class="dn-cifra dato ${cls}" data-ancla="cifra"><span class="oculto">${txt}</span><span aria-hidden="true"${ap(v, "nada")} data-dura="0.12">${txt}</span></p>`;   // entra en 0,12 s: nítida apenas se arma
    const S15 = E.estafas, S16 = E.pasan, S17 = E.atacante, S18 = E.cruzan;
    esc_("estafas", `
        ${cifra("150", S15 + 0.75)}
        <p class="dn-cifra-txt"${ap(palabra("estafas", 2), "pop")}>estafas</p>
        <p class="dn-cifra-txt dn-2"${ap(S15 + 1.5, "sube")}>de <b class="dato">${cuenta(0, 32, S15 + 1.55, 0.5)}</b> tipos</p>
        <p class="dn-fuente dato"${ap(S15 + 1.7, "nada")}>Agente que hace todo lo que lee · grifter bench</p>`, "dn-centro");
    esc_("pasan", `
        ${cifra("0", S16 + 0.7, "c-verde")}
        <p class="dn-cifra-txt"${ap(palabra("estafas", 3), "pop")}>pasan con Grifter completo</p>
        <p class="dn-fuente dato"${ap(S16 + 0.8, "nada")}>150 de 150 frenadas · capas 2 y 3 · docs/cifras.md</p>`, "dn-centro");
    esc_("atacante", `
        ${cifra("5.280", S17 + 0.75)}
        <p class="dn-cifra-txt"${ap(palabra("atacante", 0), "pop")}>intentos de un atacante que aprende</p>
        <p class="dn-fuente dato"${ap(S17 + 1.6, "nada")}>120 generaciones · 6 corridas · grifter duelo</p>`, "dn-centro");
    esc_("cruzan", `
        ${cifra("0", S18 + 0.7, "c-verde")}
        <p class="dn-cifra-txt"${ap(palabra("atacante", 10), "pop")}>cruzan la capa 2</p>
        <p class="dn-fuente dato"${ap(S18 + 0.6, "nada")}>5.280 intentos contra la capa 2 · grifter duelo · docs/cifras.md</p>`, "dn-centro");

    // 7. Cierre: la frase final con la voz; las partículas arman la marca, la marca nítida la reemplaza con un fundido
    // cruzado de 0,2 s (nunca hay dos marcas a la vista) y «Grifter» cae letra por letra
    esc_("remate", `
        <h1 class="dn-titular dn-frase-final">${escribe(FRASE_FINAL[0], 0, desdePalabra("remate", 0))}<span class="dn-remate-2">${escribe(FRASE_FINAL[1], 0, desdePalabra("remate", FRASE_FINAL[0].split(" ").length))}</span></h1>`, "dn-centro");
    esc_("cierre", `
        <div class="dn-logo">
          ${marca("dn-marca-cierre", 'data-ancla="logo"')}
          <span class="dn-logo-txt">${[..."Grifter"].map((c, i) => `<span${ap(palabra("cierre", 0) - 0.05 + i * 0.07, "cae")}>${c}</span>`).join("")}</span>
        </div>
        <p class="dn-lema">${escribe("Escudo para agentes que pagan", 0, desdePalabra("cierre", 1))}</p>
        <p class="dn-url dato"${ap(E.cierre + 2.8, "sube")}>grifter.onrender.com</p>
        <p class="dn-aviso"${ap(E.cierre + 3.1, "nada")}>Personas y marcas ficticias · voces sintéticas</p>`, "dn-centro");

    h.push(`<div class="dn-progreso" aria-hidden="true"><i id="dn-barra"></i></div>
      <div class="dn-portada" aria-hidden="true">
        <p class="dn-evento dato">Platanus Hack 26 · AI Security · Equipo 40</p>
        <div class="dn-logo dn-logo-portada">${marca("dibuja")}<span>Grifter</span></div>
      </div>
      <button type="button" class="dn-inicio" id="dn-inicio" aria-label="Iniciar o pausar la demo (Espacio)">${ic("play_arrow")}<span>Espacio</span></button>`);
    h.unshift(`<canvas id="dn-particulas" aria-hidden="true"></canvas>`);
    $("#dn-escenario").innerHTML = h.join("");
    lienzo = $("#dn-particulas");
    g2 = lienzo.getContext("2d");
    $("#dn-inicio").addEventListener("click", alternar);
  }

  // --- La nube del agente (todo es función de t: sin Math.random, las fases salen de una semilla fija) ---
  function semilla(n) { return () => { n |= 0; n = (n + 0x6D2B79F5) | 0; let x = Math.imul(n ^ (n >>> 15), 1 | n); x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x; return ((x ^ (x >>> 14)) >>> 0) / 4294967296; }; }
  const NP = 120, azar = semilla(40);
  const ESFERA = Array.from({ length: NP }, (_, i) => { const y = 1 - (2 * (i + 0.5)) / NP, r = Math.sqrt(1 - y * y), a = i * 2.39996; return { x: Math.cos(a) * r, y, z: Math.sin(a) * r, f: azar() * 6.283 }; });
  let ESCUDO = null, COLOR = null;   // el contorno del escudo de la marca y los colores, al primer dibujo
  function prepararNube() {
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", "M60 8 L108 26 V68 C108 100 88 122 60 132 C32 122 12 100 12 68 V26 Z");
    const largo = p.getTotalLength();
    ESCUDO = Array.from({ length: NP }, (_, i) => { const q = p.getPointAtLength((i / NP) * largo); return { x: (q.x - 60) / 62, y: (q.y - 70) / 62 }; });
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    COLOR = { texto: hex(css("--texto")), ambar: hex(css("--ambar")), verde: hex(css("--verde")) };
  }
  const suave = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  const mezcla = (a, b, x) => a.map((v, i) => Math.round(v + (b[i] - v) * x));
  // Cuánto habla el agente (fundido de 0,3 s en cada borde) y el pulso de lo que escribe: un golpe cada 0,26 s.
  const pesoHabla = (tt) => Math.max(0, ...HABLA_AGENTE.map(([a, b]) => suave((tt - a) / 0.3) * (1 - suave((tt - b) / 0.3))));
  const pulsoHabla = (tt) => { const ph = (((tt % 0.26) + 0.26) % 0.26); return 0.25 + 0.75 * Math.exp(-ph / 0.12) * (0.7 + 0.3 * Math.abs(Math.sin(tt * 3.1))); };
  function dibujarNube(cv, tt) {
    if (!ESCUDO) prepararNube();
    const g = cv.getContext("2d"), k = cv.width / 720, mini = cv.width < 300;
    g.setTransform(k, 0, 0, k, 0, 0);
    g.clearRect(0, 0, 720, 720);
    const r0 = cv.dataset.retiene === undefined ? null : +cv.dataset.retiene;
    const retiene = r0 === null ? 0 : quieto ? +(tt >= r0) : suave((tt - r0) / 0.9);
    const habla = r0 === null ? (quieto ? +(pesoHabla(tt) > 0.5) : pesoHabla(tt)) : 0;
    const env = quieto ? 0.5 : pulsoHabla(tt);
    const cx = 360, cy = 360, R = mini ? 300 : 270;
    const giro = quieto ? 0.6 : tt * 0.45, cg = Math.cos(giro), sg = Math.sin(giro);
    const tinte = mezcla(COLOR.texto, COLOR.ambar, habla);
    const pts = ESFERA.map((p, i) => {
      const x = p.x * cg + p.z * sg, z = -p.x * sg + p.z * cg;
      const pulso = 1 + (quieto ? 0 : 0.02 * Math.sin(tt * 1.6 + p.f)) + env * habla * (0.08 + 0.16 * Math.abs(Math.sin(tt * 9 + p.f)));
      const ex = cx + x * R * pulso, ey = cy + p.y * R * pulso;
      const m = quieto ? retiene : suave((retiene - (i % 12) * 0.02) / 0.75);   // se reordenan de a poco
      const sx = cx + ESCUDO[i].x * R * 0.95, sy = cy + ESCUDO[i].y * R * 0.95;
      return { x: ex + (sx - ex) * m, y: ey + (sy - ey) * m, z: z * (1 - m) + m, m };
    }).sort((a, b) => a.z - b.z);
    for (const p of pts) {
      const prof = (p.z + 1) / 2, c = p.m > 0 ? mezcla(tinte, COLOR.verde, p.m) : tinte;
      g.beginPath();
      g.arc(p.x, p.y, (3 + 5 * prof) * (mini ? 2.4 : 1), 0, 2 * Math.PI);
      g.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.25 + 0.75 * prof).toFixed(3)})`;
      g.fill();
    }
  }

  // --- Motor de partículas: el lenguaje visual de toda la versión B ---
  // Un solo canvas detrás del escenario. Las mismas NP partículas pasan de figura en figura (cuatro personas → la
  // esfera del agente → el escudo al retener → las cifras → la marca), con una interpolación de 0,6-1,4 s y algo de
  // dispersión en el camino. Un grupo rojo (la amenaza) se acerca a la nube cuando entra una estafa y rebota cuando
  // Grifter retiene. Detrás, un campo tenue a la deriva. Todo es función de t (semilla fija): ?t=N da el mismo cuadro,
  // y con movimiento reducido cada figura queda quieta. El texto va siempre encima del canvas.
  const NM = 400, NR = 60, NF = 90;   // partículas de la nube, de la amenaza y del fondo
  const azarM = semilla(7);
  const ESF_M = Array.from({ length: NM }, (_, i) => { const y = 1 - (2 * (i + 0.5)) / NM, r = Math.sqrt(1 - y * y), a = i * 2.39996; return { x: Math.cos(a) * r, y, z: Math.sin(a) * r, f: azarM() * 6.283 }; });
  const RAND_M = Array.from({ length: NM }, () => ({ x: azarM() * 1920, y: azarM() * 1080, retraso: azarM() * 0.25, dx: azarM() * 2 - 1, dy: azarM() * 2 - 1 }));
  const RAND_R = Array.from({ length: NR }, (_, i) => ({ a: i * 2.39996, f: azarM() * 6.283, d: 0.85 + azarM() * 0.3 }));
  const FONDO = Array.from({ length: NF }, () => ({ x: azarM() * 1920, y: azarM() * 1080, vx: (azarM() - 0.5) * 14, vy: (azarM() - 0.5) * 10, s: 1 + azarM() * 1.5, f: azarM() * 6.283 }));
  const RGB = {};
  function colores() {
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    for (const k of ["texto", "texto-2", "texto-3", "ambar", "verde", "rojo"]) RGB[k] = hex(css("--" + k));
  }

  // Dónde está cada ancla (data-ancla) de cada escena, en coordenadas del escenario. Se mide una vez (y al cargar la
  // letra), mostrando cada escena oculta y sin sus movimientos de entrada.
  let ANCLAS = {};
  function medir() {
    const esc = $("#dn-escenario"), base = esc.getBoundingClientRect(), k = base.width / 1920;
    ANCLAS = {};
    for (const s of escenas) {
      s.el.classList.add("dn-midiendo");
      const m = {};
      s.el.querySelectorAll("[data-ancla]").forEach((a) => {
        const r = a.getBoundingClientRect();
        m[a.dataset.ancla] = { x: (r.left - base.left + r.width / 2) / k, y: (r.top - base.top + r.height / 2) / k, w: r.width / k, h: r.height / k, el: a };
      });
      s.el.classList.remove("dn-midiendo");
      ANCLAS[s.el.dataset.id] = m;
    }
    MUESTRAS.clear();
  }
  const ancla = (id, nombre) => ANCLAS[id]?.[nombre] || { x: 960, y: 540, w: 360, h: 360 };

  // Puntos de una figura: rasteriza en un canvas oculto y elige n puntos parejos (orden barajado con semilla).
  const MUESTRAS = new Map();
  function elegir(pts, n, clave) {
    const az = semilla(clave.length * 131 + 17), orden = pts.map((p, i) => [az(), i]).sort((a, b) => a[0] - b[0]);
    return Array.from({ length: n }, (_, i) => pts[orden[i % orden.length][1]]);
  }
  function rasterizar(w, h, dibujar, paso) {
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.ceil(w)); c.height = Math.max(1, Math.ceil(h));
    const g = c.getContext("2d");
    dibujar(g);
    const d = g.getImageData(0, 0, c.width, c.height).data, pts = [];
    for (let y = 0; y < c.height; y += paso) for (let x = 0; x < c.width; x += paso) if (d[(y * c.width + x) * 4 + 3] > 120) pts.push({ x, y });
    return pts.length ? pts : [{ x: w / 2, y: h / 2 }];
  }
  // Una cifra con la letra de --titular, alineada con el texto del DOM (misma caja y misma línea base).
  function puntosTexto(txt, a, n) {
    const clave = `t|${txt}|${n}|${Math.round(a.w)}|${document.documentElement.dataset.letra || ""}`;
    if (!MUESTRAS.has(clave)) {
      const cs = a.el ? getComputedStyle(a.el) : null;
      const pts = rasterizar(a.w, a.h, (g) => {
        g.font = cs ? `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}` : "600 300px sans-serif";
        if (cs && "letterSpacing" in g) g.letterSpacing = cs.letterSpacing;
        g.textAlign = "center";
        const m = g.measureText(txt);
        g.fillStyle = "#fff";
        g.fillText(txt, a.w / 2, a.h / 2 + (m.fontBoundingBoxAscent - m.fontBoundingBoxDescent) / 2);
      }, 5);
      MUESTRAS.set(clave, elegir(pts, n, clave).map((p) => ({ x: a.x - a.w / 2 + p.x, y: a.y - a.h / 2 + p.y })));
    }
    return MUESTRAS.get(clave);
  }
  // La marca (LOGO): puntos repartidos a lo largo de cada trazo, según su peso.
  function puntosLogo(a, n) {
    const clave = `l|${n}|${Math.round(a.x)}|${Math.round(a.w)}`;
    if (!MUESTRAS.has(clave)) {
      const e = a.w / LOGO.caja[0], x0 = a.x - a.w / 2, y0 = a.y - (LOGO.caja[1] * e) / 2, pts = [];
      let resto = n;
      LOGO.trazos.forEach((tz, j) => {
        const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
        p.setAttribute("d", tz.d);
        const largo = p.getTotalLength(), m = j === LOGO.trazos.length - 1 ? resto : Math.round(n * tz.peso);
        resto -= m;
        for (let i = 0; i < m; i++) { const q = p.getPointAtLength((i / m) * largo); pts.push({ x: x0 + q.x * e, y: y0 + q.y * e, color: tz.color }); }
      });
      MUESTRAS.set(clave, pts);
    }
    return MUESTRAS.get(clave);
  }

  // --- Las figuras. Cada una da, para cada partícula, posición, color, opacidad y tamaño en el segundo tt ---
  const figEsfera = (centro, { habla = false, rel = 0.37 } = {}) => (tt) => {
    const c = typeof centro === "function" ? centro() : centro, R = c.R ?? c.w * rel;
    const peso = habla ? (quieto ? +(pesoHabla(tt) > 0.5) : pesoHabla(tt)) : 0, env = quieto ? 0.5 : pulsoHabla(tt);
    const giro = quieto ? 0.6 : tt * 0.45, cg = Math.cos(giro), sg = Math.sin(giro);
    const color = mezcla(RGB.texto, RGB.ambar, peso), esc = R / 135;
    return { centro: { x: c.x, y: c.y, R }, p: ESF_M.map((q) => {
      const x = q.x * cg + q.z * sg, z = -q.x * sg + q.z * cg, prof = (z + 1) / 2;
      const pulso = 1 + (quieto ? 0 : 0.02 * Math.sin(tt * 1.6 + q.f)) + env * peso * (0.08 + 0.16 * Math.abs(Math.sin(tt * 9 + q.f)));
      return { x: c.x + x * R * pulso, y: c.y + q.y * R * pulso, c: color, a: 0.25 + 0.75 * prof, s: (1.2 + 2.6 * prof) * esc };
    }) };
  };
  const figEscudo = (centro, rel = 0.37) => (tt) => {
    const c = typeof centro === "function" ? centro() : centro, R = c.R ?? c.w * rel, esc = R / 135;
    return { centro: { x: c.x, y: c.y, R }, p: ESCUDO_M().map((q, i) => ({
      x: c.x + q.x * R * 0.95, y: c.y + q.y * R * 0.95 + (quieto ? 0 : Math.sin(tt * 2 + i) * 0.6), c: RGB.verde, a: 0.95, s: 2.2 * esc + 0.6,
    })) };
  };
  let ESC_CACHE = null;
  function ESCUDO_M() {   // el contorno del escudo de LOGO (el primer trazo), centrado, en unidades de 62 px de la caja
    if (!ESC_CACHE) {
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", LOGO.trazos[0].d);
      const largo = p.getTotalLength(), cx = LOGO.caja[0] / 2, cy = LOGO.caja[1] / 2;
      ESC_CACHE = Array.from({ length: NM }, (_, i) => { const q = p.getPointAtLength((i / NM) * largo); return { x: (q.x - cx) / 62, y: (q.y - cy) / 62 }; });
    }
    return ESC_CACHE;
  }
  const figTexto = (id, txt, color, { tenue = null } = {}) => (tt) => {
    const a = ancla(id, "cifra"), pts = puntosTexto(txt, a, NM);
    const op = tenue !== null && tt >= tenue ? 0.18 : 0.95;   // cuando aparece el texto real encima, los puntos quedan de fondo
    return { centro: { x: a.x, y: a.y, R: a.h * 0.45 }, p: pts.map((q) => ({ x: q.x, y: q.y, c: RGB[color], a: op, s: 3.2 })) };
  };
  // Antes del agente, la nube está dispersa y tenue (parte del fondo) y se junta en la esfera cuando él aparece.
  const figDispersa = (tt) => ({ centro: { x: 960, y: 540, R: 300 }, p: RAND_M.map((r, i) => ({
    x: r.x + (quieto ? 0 : Math.sin(tt * 0.4 + i) * 12), y: r.y + (quieto ? 0 : Math.cos(tt * 0.3 + i) * 9), c: RGB["texto-3"], a: 0.14, s: 1.4,
  })) });
  const figLogo = (tt) => {
    const a = ancla("cierre", "logo"), pts = puntosLogo(a, NM), tenue = quieto ? +(tt < MARCA_NITIDA) * 0.95 : 0.95 * (1 - clamp((tt - MARCA_NITIDA) / 0.2));
    return { centro: { x: a.x, y: a.y, R: a.w / 2 }, p: pts.map((q) => ({ x: q.x, y: q.y, c: RGB[q.color], a: tenue, s: 2.6 })) };
  };
  const ESQUINA = { x: 190, y: 925, R: 58 };     // donde espera el agente mientras habla otro (abajo a la izquierda)
  const ARRIBA = { x: 960, y: 190, R: 72 };
  const nube = (id) => () => ancla(id, "nube");

  // La línea de tiempo de la nube: [desde, figura, duración de la transición, dispersión en el camino (px)].
  const MARCA_NITIDA = E.cierre + 1.15;   // cuando la marca SVG reemplaza a la de partículas (ya en su lugar)
  const FIGURAS = [
    [0, figDispersa, 0.8, 0],
    [E.agentes, figEsfera(nube("agentes")), 1.0, 80],
    [E.encargo, figEsfera(nube("encargo"), { habla: true }), 0.8, 60],
    [E.suena, figEsfera(ESQUINA), 0.8, 60],
    [E.paga, figEsfera(nube("paga"), { habla: true }), 0.8, 60],
    [E.frena + 0.05, figEscudo(nube("frena")), 0.6, 40],
    [E.motivo, figEscudo(ARRIBA), 0.7, 40],
    [E.alerta, figEsfera(ESQUINA), 0.8, 40],   // en espera vuelve a ser esfera: un escudo de partículas no convive con otro
    [E.banco, figEsfera(ESQUINA), 0.8, 50],
    [E.responde, figEsfera(nube("responde"), { habla: true }), 0.7, 60],
    [E.clave + 0.05, figEscudo(nube("clave")), 0.6, 40],
    [E.aprobaste, figEsfera(ESQUINA), 0.8, 50],
    [E.calza + 0.05, figEscudo(nube("calza")), 0.55, 40],
    [E.estafas + 0.05, figTexto("estafas", "150", "texto", { tenue: E.estafas + 0.75 }), 0.6, 80],
    [E.pasan, figTexto("pasan", "0", "verde", { tenue: E.pasan + 0.7 }), 0.55, 140],
    [E.atacante, figTexto("atacante", "5.280", "texto", { tenue: E.atacante + 0.75 }), 0.6, 120],
    [E.cruzan, figTexto("cruzan", "0", "verde", { tenue: E.cruzan + 0.7 }), 0.55, 140],
    [E.remate, figEsfera(ARRIBA), 0.9, 120],
    [palabra("remate", 6), figEscudo(ARRIBA), 0.7, 40],
    [E.cierre + 0.05, figLogo, 0.8, 80],
  ];

  // La amenaza: tramos en que el grupo rojo se acerca y segundos en que Grifter lo hace rebotar.
  const ACECHO = [[LL.abuela, E.paga], [E.paga, E.frena + 0.05], [E.banco, E.responde], [E.responde, E.clave + 0.05], [E.cobra, E.calza + 0.05]];
  const REBOTES = [E.frena + 0.05, E.clave + 0.05, E.calza + 0.05];
  function amenaza(tt, centro) {
    const tramo = ACECHO.find(([a, b]) => tt >= a && tt < b);
    const rebote = REBOTES.find((r) => tt >= r && tt < r + 1.3);
    if (!tramo && !rebote) return null;
    const R = centro.R;
    return RAND_R.map((q, i) => {
      const ang = q.a + (quieto ? 0 : tt * 0.35 + 0.25 * Math.sin(tt * 0.8 + q.f));
      let d, a = 0.85;
      if (rebote !== undefined) {
        const p = quieto ? 1 : salida(clamp((tt - rebote) / 1.3));
        d = R * 1.5 * q.d + 560 * p; a = 0.85 * (1 - p);
      } else {
        const [ini, fin] = tramo, cerca = ACECHO.some(([x, y]) => y === ini) ? 1 : clamp((tt - ini) / Math.max(1, fin - ini - 0.6));
        d = R * 1.5 * q.d + (1 - (quieto ? 1 : cerca * cerca)) * 1000 + (quieto ? 0 : 10 * Math.sin(tt * 3 + q.f));
      }
      return { x: centro.x + Math.cos(ang) * d, y: centro.y + Math.sin(ang) * d, c: RGB.rojo, a, s: 2.6 };
    });
  }

  // Dibuja el cuadro tt en el canvas. La transición: cada partícula sale de la figura anterior (que sigue
  // moviéndose) hacia la nueva con su propio retraso, y se abre un poco del camino recto en el medio.
  let lienzo = null, g2 = null, resol = 0;
  function motor(tt) {
    if (!lienzo) return;
    if (!RGB.texto) colores();
    const k = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--dn-k")) || 1;
    const q = Math.min(2, (window.devicePixelRatio || 1) * k);
    if (Math.abs(q - resol) > 0.01) { resol = q; lienzo.width = Math.round(1920 * q); lienzo.height = Math.round(1080 * q); }
    g2.setTransform(resol, 0, 0, resol, 0, 0);
    g2.clearRect(0, 0, 1920, 1080);
    // El fondo: un campo muy tenue a la deriva.
    for (const f of FONDO) {
      const x = (((f.x + (quieto ? 0 : f.vx * tt)) % 1920) + 1920) % 1920, y = (((f.y + (quieto ? 0 : f.vy * tt)) % 1080) + 1080) % 1080;
      g2.fillStyle = `rgba(${RGB["texto-3"].join(",")},${(0.12 + (quieto ? 0 : 0.06 * Math.sin(tt + f.f))).toFixed(3)})`;
      g2.fillRect(x, y, f.s, f.s);
    }
    // La nube.
    let k2 = 0;
    while (k2 + 1 < FIGURAS.length && tt >= FIGURAS[k2 + 1][0]) k2++;
    const [desde, fig, dura, disp] = FIGURAS[k2];
    const ahora = fig(tt);
    let pts = ahora.p, centro = ahora.centro;
    if (k2 > 0 && !quieto && tt < desde + dura + 0.3) {
      const antes = FIGURAS[k2 - 1][1](tt);
      const e0 = salida(clamp((tt - desde) / dura));
      centro = { x: antes.centro.x + (ahora.centro.x - antes.centro.x) * e0, y: antes.centro.y + (ahora.centro.y - antes.centro.y) * e0, R: antes.centro.R + (ahora.centro.R - antes.centro.R) * e0 };
      pts = ahora.p.map((b, i) => {
        const a = antes.p[i], r = RAND_M[i], e = vaiven(clamp((tt - desde - r.retraso * Math.min(1, dura / 0.9)) / dura)), abre = Math.sin(Math.PI * e) * disp;
        return { x: a.x + (b.x - a.x) * e + r.dx * abre, y: a.y + (b.y - a.y) * e + r.dy * abre, c: mezcla(a.c, b.c, e), a: (a.a + (b.a - a.a) * e) * (1 - 0.65 * Math.sin(Math.PI * e)), s: a.s + (b.s - a.s) * e };
      });
    }
    const rojos = amenaza(tt, centro);
    for (const lista of rojos ? [pts, rojos] : [pts]) {
      for (const p of lista) {
        if (p.a <= 0.01) continue;
        g2.fillStyle = `rgba(${p.c[0]},${p.c[1]},${p.c[2]},${p.a.toFixed(3)})`;
        g2.beginPath(); g2.arc(p.x, p.y, p.s, 0, 6.2832); g2.fill();
      }
    }
  }

  // --- Cuadro: qué se ve en el segundo t ---
  let escenas = [];
  function preparar() {
    escenas = [...document.querySelectorAll(".dn-escena")].map((el) => ({
      el, desde: +el.dataset.desde, hasta: +el.dataset.hasta,
      aparecen: [...el.querySelectorAll("[data-v]")],
      on: [...el.querySelectorAll("[data-on]")],
      escribe: [...el.querySelectorAll("[data-e]")].map((x) => Object.assign(ESCRIBE[+x.dataset.e], { el: x, n: -1 })),
      cuentas: [...el.querySelectorAll("[data-c]")].map((x) => Object.assign(CUENTAS[+x.dataset.c], { el: x, txt: "" })),
      dedos: [...el.querySelectorAll("[data-d]")].map((x) => Object.assign(DEDOS[+x.dataset.d], { el: x })),
      nubes: [...el.querySelectorAll(".dn-nube.mini")],
      barras: [...el.querySelectorAll(".dn-barras")],
      puntos: [...el.querySelectorAll(".dn-puntos i")],
      anillos: [...el.querySelectorAll(".dn-anillo")],
      relojes: [...el.querySelectorAll(".dn-reloj-s")],
      pulsa: [...el.querySelectorAll(".dn-pulsa")],
      vibra: el.querySelector(".dn-vibra"),
      contestar: el.querySelector(".contestar"),
      marca: [...el.querySelectorAll(".dn-marca-cierre path")],
      marcaSvg: el.querySelector(".dn-marca-cierre"),
    }));
  }

  function aparecer(el, tt) {
    const v = +el.dataset.v, h = el.dataset.h === undefined ? Infinity : +el.dataset.h;
    let a;
    if (tt < v || tt >= h + 0.15) a = 0;
    else if (quieto) a = tt < h ? 1 : 0;
    else a = Math.min(clamp((tt - v) / (+el.dataset.dura || 0.35)), tt >= h ? 1 - (tt - h) / 0.15 : 1);
    el.classList.toggle("ve", a > 0);
    el.style.setProperty("--a", a.toFixed(3));
    el.style.setProperty("--b", (quieto ? +(a > 0) : rebote(a)).toFixed(3));
    el.style.setProperty("--c", (quieto ? +(a > 0) : salida(a)).toFixed(3));
  }

  // Cuántas letras se ven en t: al ritmo de las palabras de la voz o a velocidad fija.
  function letras(cfg, tt) {
    const total = cfg.segs.reduce((s, x) => s + x.txt.length, 0);
    if (tt < cfg.t0) return 0;
    if (quieto) return total;
    const r = tt - cfg.t0;
    if (!cfg.pal) return Math.min(total, Math.floor(r * cfg.cps));
    const texto = cfg.segs.map((x) => x.txt).join("");
    const inicios = [];   // posición de la primera letra de cada palabra
    texto.replace(/\S+/g, (_, i) => inicios.push(i));
    let k = 0;
    while (k + 1 < inicios.length && k + 1 < cfg.pal.length && r >= cfg.pal[k + 1]) k++;
    if (k >= cfg.pal.length - 1 && inicios.length > cfg.pal.length) {   // más palabras que tiempos: el resto, a 24 letras/s
      return Math.min(total, inicios[cfg.pal.length - 1] + Math.floor((r - cfg.pal[cfg.pal.length - 1]) * 24));
    }
    const fin = k + 1 < inicios.length ? inicios[k + 1] : total;
    const dura = k + 1 < cfg.pal.length ? Math.max(0.08, (cfg.pal[k + 1] - cfg.pal[k]) * 0.9) : Math.max(0.2, (fin - inicios[k]) * 0.05);
    return Math.min(total, inicios[k] + Math.round(clamp((r - cfg.pal[k]) / dura) * (fin - inicios[k])));
  }
  // Lo escrito y, oculto pero ocupando su lugar, lo que falta: así el texto no se reacomoda mientras se escribe.
  function tecleado(segs, n, cursor) {
    let quedan = n, vis = "", resto = "";
    for (const s of segs) {
      const a = s.txt.slice(0, Math.max(0, quedan)), b = s.txt.slice(a.length);
      quedan -= a.length;
      const abre = s.cls ? `<span class="${s.cls}">` : "", cierra = s.cls ? "</span>" : "";
      if (a) vis += abre + esc(a) + cierra;
      if (b) resto += abre + esc(b) + cierra;
    }
    return `<span class="dn-vis${cursor ? " dn-con-cursor" : ""}">${vis}</span><span class="dn-resto">${resto}</span>`;
  }

  function valor(c, tt) {
    if (tt < c.t0) return c.de;
    if (quieto) return c.a;
    const p = clamp((tt - c.t0) / c.dur);
    return c.de + (c.a - c.de) * (c.baja ? vaiven(p) : salida(p));
  }

  function render(tt) {
    for (const s of escenas) {
      const activa = tt >= s.desde && tt < s.hasta;
      s.el.classList.toggle("activo", activa);
      if (!activa) continue;
      s.el.style.setProperty("--e", (quieto ? 1 : salida(clamp((tt - s.desde) / 0.35))).toFixed(3));
      s.aparecen.forEach((el) => aparecer(el, tt));
      s.on.forEach((el) => el.classList.toggle("on", tt >= +el.dataset.on));
      for (const cfg of s.escribe) {
        const n = letras(cfg, tt), total = cfg.segs.reduce((x, y) => x + y.txt.length, 0);
        const cursor = !quieto && n > 0 && n < total;
        const clave = n * 2 + cursor;
        if (clave !== cfg.n) { cfg.n = clave; cfg.el.innerHTML = tecleado(cfg.segs, n, cursor); }
      }
      for (const c of s.cuentas) {
        const txt = (c.pesos ? "$" : "") + miles(valor(c, tt));
        if (txt !== c.txt) { c.txt = txt; c.el.textContent = txt; }
      }
      for (const d of s.dedos) {
        const r = tt - d.toque, T = TOQUE;
        const llega = vaiven(clamp((r + T.llega) / (T.llega - T.posa)));   // 0 afuera, 1 posada
        const retira = vaiven(clamp((r - T.aprieta) / T.retira));          // 0 posada, 1 afuera
        let x = d.dx * (1 - llega), y = d.dy * (1 - llega), o = r >= -T.llega ? 1 : 0;
        if (retira > 0) { x = 60 * retira; y = 140 * retira; o = 1 - retira; }
        if (quieto) { x = 0; y = 0; o = r >= -T.posa && r < T.aprieta + T.retira ? 1 : 0; }
        const aprieta = r >= 0 && r < T.aprieta;
        d.el.style.setProperty("--x", `${x.toFixed(1)}px`);
        d.el.style.setProperty("--y", `${y.toFixed(1)}px`);
        d.el.style.setProperty("--o", o.toFixed(3));
        d.el.style.setProperty("--s", aprieta ? 0.82 : 1);
        const q = r / T.onda;   // la onda sale del punto de toque, se abre y se apaga
        d.el.style.setProperty("--onda-o", q >= 0 && q < 1 && !quieto ? (0.85 * (1 - q)).toFixed(3) : 0);
        d.el.style.setProperty("--onda-s", (0.4 + 3.2 * salida(clamp(q))).toFixed(3));
        const boton = d.el.parentElement;
        boton.classList.toggle("presionado", aprieta);
        boton.classList.toggle("on", r >= 0);
      }
      s.nubes.forEach((cv) => dibujarNube(cv, tt));
      for (const b of s.barras) {
        const voz = dentro(tt, HABLA[b.dataset.quien] || []);
        [...b.children].forEach((barra, i) => {
          const d = Math.abs(i - 4);
          let hb = 0.1;
          if (voz) hb = quieto ? 0.7 - d * 0.12 : (0.3 + 0.7 * Math.abs(0.6 * Math.sin(tt * 6.3 + d * 0.9) + 0.4 * Math.sin(tt * 11.7 + d * 2.1))) * (1 - d * 0.14);
          barra.style.setProperty("--h", hb.toFixed(3));
        });
      }
      s.puntos.forEach((p, i) => p.style.setProperty("--y", quieto ? "0px" : `${(-Math.abs(Math.sin(tt * Math.PI * 2.2 - i * 0.6)) * 14).toFixed(1)}px`));
      const suena = tt >= LL.suena && tt < LL.contesta;
      s.anillos.forEach((a, i) => {
        const p = suena && !quieto ? ((tt - LL.suena + i * 0.6) % 1.2) / 1.2 : 0;
        a.style.setProperty("--p", p.toFixed(3));
        a.style.opacity = suena ? (quieto ? 0.5 : ((1 - p) * 0.7).toFixed(3)) : 0;
      });
      if (s.vibra) {
        const vibra = suena && !quieto && (tt - LL.suena) % 1 < 0.45;
        s.vibra.style.setProperty("--vib", vibra ? `${(Math.sin(tt * 2 * Math.PI * 22) * 6).toFixed(1)}px` : "0px");
        s.vibra.style.setProperty("--vib-r", vibra ? `${(Math.sin(tt * 2 * Math.PI * 17) * 0.6).toFixed(2)}deg` : "0deg");
      }
      if (s.contestar) s.contestar.style.setProperty("--lat", suena && !quieto ? ((Math.sin((tt - LL.suena) * 2 * Math.PI) + 1) / 2).toFixed(3) : 0);
      const seg = Math.max(0, Math.floor(Math.min(tt, LL.cuelga) - LL.contesta));
      s.relojes.forEach((r) => { r.textContent = `${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}`; });
      s.pulsa.forEach((p) => p.style.setProperty("--pulso", quieto ? 1 : (0.35 + 0.65 * (0.5 + 0.5 * Math.sin(tt * 2 * Math.PI * 0.9))).toFixed(3)));
      // La marca nítida del cierre reemplaza a la de partículas con un fundido cruzado de 0,2 s, cuando ya calzan.
      s.marca.forEach((p) => { p.style.strokeDashoffset = 0; });
      if (s.marcaSvg) s.marcaSvg.style.opacity = (quieto ? +(tt >= MARCA_NITIDA) : clamp((tt - MARCA_NITIDA) / 0.2)).toFixed(3);
    }
    // El borde rojo de alerta, mientras el pago está retenido y nadie lo rechazó. Late en opacidad (fijo si reducido).
    const alarma = tt >= ALARMA[0] && tt < ALARMA[1];
    document.body.classList.toggle("dn-alarma", alarma);
    document.body.style.setProperty("--alarma", quieto ? 1 : (0.35 + 0.65 * (0.5 + 0.5 * Math.cos(((tt - ALARMA[0]) * 2 * Math.PI) / 1.2))).toFixed(3));
    $("#dn-barra").style.width = `${(Math.min(tt, DURACION) / DURACION) * 100}%`;
    motor(tt);
    if (revisor) { revisor.reloj.textContent = `t = ${tt.toFixed(1)} s`; if (document.activeElement !== revisor.barra) revisor.barra.value = tt; }
  }

  // --- Audio: las voces de la llamada (versión A) y la narración. Suenan solo después de que el presentador
  // pulsa Espacio o «Iniciar». Al pausar, saltar o reanudar, la pista que corresponde a t sigue desde t - en ---
  const PISTAS = [
    ...Object.values(NARR).map((n) => ({ src: n.src, en: n.en, dur: n.dur + 0.5 })),
    { src: "audio/cuento_del_tio_abuela.mp3", en: LL.abuela, dur: 2.0 },
    { src: "audio/cuento_del_tio_nieto.mp3", en: LL.nieto, dur: 25.5 },
  ];
  let mudo = false;
  function prepararAudio() {
    for (const p of PISTAS) {
      p.a = new Audio(p.src);
      p.a.preload = "auto";
      p.a.addEventListener("error", () => { p.a = null; });
    }
  }
  function tocar(p, desde) {
    if (!p.a || mudo) return;
    try { p.a.currentTime = Math.max(0, desde); } catch (_) { /* aún sin metadatos: parte del inicio */ }
    p.a.play().catch(() => { /* sin permiso de audio: la demo sigue muda */ });
  }
  let ctx = null, timbre = [];
  function sonarTimbre(desde) {   // el timbre del celular: dos notas por segundo, mi y do, como en la versión A
    if (mudo) return;
    try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === "suspended") ctx.resume(); } catch (_) { return; }
    const t0 = ctx.currentTime, rafagas = Math.ceil(LL.contesta - desde - 0.4);
    for (let r = 0; r < rafagas; r++) {
      for (const [desfase, hz] of [[0, 659.25], [0.2, 523.25]]) {
        const o = ctx.createOscillator(), g = ctx.createGain(), ini = t0 + r + desfase;
        o.type = "sine"; o.frequency.value = hz;
        g.gain.setValueAtTime(0, ini);
        g.gain.linearRampToValueAtTime(0.06, ini + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0005, ini + 0.19);
        o.connect(g).connect(ctx.destination);
        o.start(ini); o.stop(ini + 0.2);
        timbre.push(o);
      }
    }
  }
  function sonar(antes, ahora) {
    for (const p of PISTAS) if (antes < p.en && ahora >= p.en) tocar(p, ahora - p.en);
    if (antes < LL.suena && ahora >= LL.suena) sonarTimbre(ahora);
  }
  function reanudar(tt) {
    for (const p of PISTAS) if (tt >= p.en && tt < p.en + p.dur) tocar(p, tt - p.en);
    if (tt >= LL.suena && tt < LL.contesta - 0.4) sonarTimbre(tt);
  }
  function callar() {
    timbre.forEach((o) => { try { o.stop(); } catch (_) { /* ya paró */ } });
    timbre = [];
    PISTAS.forEach((p) => p.a && p.a.pause());
  }

  // --- Reloj: un solo requestAnimationFrame; el tiempo avanza solo mientras corre ---
  let tiempo = 0, corriendo = false, previo = 0;
  function cuadro(ahora) {
    if (!corriendo) return;
    const dt = Math.min(0.1, (ahora - (previo || ahora)) / 1000);
    previo = ahora;
    const antes = tiempo;
    tiempo = Math.min(DURACION, tiempo + dt);
    sonar(antes, tiempo);
    render(tiempo);
    if (tiempo >= DURACION) { corriendo = false; document.body.classList.remove("dn-corriendo"); return; }
    requestAnimationFrame(cuadro);
  }
  let saliendo = false;
  function alternar() {
    if (document.body.classList.contains("dn-en-portada")) {
      if (saliendo) return;
      saliendo = true;
      document.body.classList.add("dn-saliendo");
      setTimeout(() => { document.body.classList.remove("dn-en-portada", "dn-saliendo"); saliendo = false; alternar(); }, quieto ? 0 : 800);
      return;
    }
    if (tiempo >= DURACION) return irA(0, true);
    corriendo = !corriendo;
    document.body.classList.toggle("dn-corriendo", corriendo);
    if (corriendo) { document.body.classList.remove("dn-en-portada"); reanudar(tiempo); previo = 0; requestAnimationFrame(cuadro); } else callar();
  }
  function irA(s, seguir) {
    callar();
    document.body.classList.remove("dn-en-portada", "dn-saliendo");
    tiempo = s;
    corriendo = false;
    document.body.classList.remove("dn-corriendo");
    render(tiempo);
    if (seguir) alternar();
  }
  // Letra de los titulares, el logo y las cifras grandes: --titular. Por defecto IBM Plex Sans; con ?letra= se prueba otra.
  const LETRAS = {
    plex: ["IBM Plex Sans (actual)", "", ""],
    outfit: ["Outfit", "Outfit:wght@600;700", "-0.02em"],
    space: ["Space Grotesk", "Space+Grotesk:wght@500;700", "-0.03em"],
    sora: ["Sora", "Sora:wght@600;800", "-0.04em"],
    bricolage: ["Bricolage Grotesque", "Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800", "-0.03em"],
    serif: ["Instrument Serif", "Instrument+Serif:ital@0;1", "-0.01em"],
    syne: ["Syne", "Syne:wght@700;800", "-0.03em"],
  };
  // Al cambiar la letra se vuelven a medir las anclas y a muestrear las cifras de partículas (con la letra ya cargada).
  const remedir = () => { medir(); render(tiempo); };
  function ponerLetra(clave) {
    const [nombre, familia, espacio] = LETRAS[clave] || LETRAS.plex;
    const raiz = document.documentElement;
    if (!familia) { raiz.style.removeProperty("--titular"); raiz.style.removeProperty("--titular-esp"); delete raiz.dataset.letra; remedir(); return; }
    raiz.style.setProperty("--titular", `"${nombre}", var(--sans)`);
    raiz.style.setProperty("--titular-esp", espacio);
    raiz.dataset.letra = clave;
    const cargada = () => document.fonts.load(`700 100px "${nombre}"`).then(remedir, remedir);
    let hoja = document.getElementById(`dn-letra-${clave}`);
    if (hoja) return cargada();
    hoja = document.createElement("link");
    Object.assign(hoja, { id: `dn-letra-${clave}`, rel: "stylesheet", href: `https://fonts.googleapis.com/css2?family=${familia}&display=swap` });
    hoja.addEventListener("load", cargada);
    hoja.addEventListener("error", remedir);
    document.head.append(hoja);
  }

  // --- Modo revisión (?revisar=1 o la tecla V): una barra de controles abajo, fuera del escenario, para retroceder,
  // pausar, avanzar, arrastrar al segundo exacto y copiar el enlace del cuadro. No sale en el pitch. ---
  let revisor = null;
  const saltar = (delta) => irA(Math.max(0, Math.min(DURACION, Math.round((tiempo + delta) * 10) / 10)), false);
  function abrirRevisor() {
    if (revisor) return;
    const caja = document.createElement("div");
    caja.className = "dn-revisor";
    const boton = (texto, titulo, accion) => {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = texto; b.title = titulo;
      b.addEventListener("click", () => { accion(); b.blur(); });
      caja.append(b);
      return b;
    };
    boton("⏮", "Al inicio", () => irA(0, false));
    boton("−5 s", "Retrocede 5 segundos", () => saltar(-5));
    boton("−1 s", "Retrocede 1 segundo (←)", () => saltar(-1));
    boton("−0,1", "Retrocede una décima (Mayús ←)", () => saltar(-0.1));
    boton("⏯", "Pausa o sigue (Espacio)", () => alternar());
    boton("+0,1", "Avanza una décima (Mayús →)", () => saltar(0.1));
    boton("+1 s", "Avanza 1 segundo (→)", () => saltar(1));
    boton("+5 s", "Avanza 5 segundos", () => saltar(5));
    const barra = document.createElement("input");
    Object.assign(barra, { type: "range", min: 0, max: DURACION, step: 0.1, value: 0, title: "Arrastra al segundo que quieras" });
    barra.addEventListener("input", () => irA(Number(barra.value), false));
    barra.addEventListener("change", () => barra.blur());
    const reloj = document.createElement("output");
    reloj.textContent = "t = 0.0 s";
    caja.append(barra, reloj);
    const letra = document.createElement("select");
    letra.title = "Letra de titulares, logo y cifras (vista previa)";
    for (const [clave, [nombre]] of Object.entries(LETRAS)) letra.append(new Option(nombre, clave));
    letra.value = LETRAS[params.get("letra")] ? params.get("letra") : "plex";
    letra.addEventListener("change", () => { ponerLetra(letra.value); letra.blur(); });
    caja.append(letra);
    boton("Copiar enlace", "Copia el enlace de este cuadro", () => {
      const u = new URL(location.href);
      u.searchParams.set("t", tiempo.toFixed(1));
      navigator.clipboard?.writeText(u.href).catch(() => {});
    });
    document.body.append(caja);
    document.body.classList.add("dn-revisando");
    revisor = { caja, barra, reloj };
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === " " || e.code === "Space") { e.preventDefault(); alternar(); }
    else if (e.key === "r" || e.key === "R") irA(0, true);
    else if (e.key === "m" || e.key === "M") { mudo = !mudo; if (mudo) callar(); else if (corriendo) reanudar(tiempo); }
    else if (/^[1-7]$/.test(e.key)) irA(PASOS[+e.key - 1], true);
    else if (e.key === "v" || e.key === "V") { abrirRevisor(); escalar(); render(tiempo); }   // V abre los controles de revisión
    // Revisión: las flechas mueven 1 s (con Mayús, 0,1 s) y dejan la demo en pausa en ese cuadro.
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      saltar((e.shiftKey ? 0.1 : 1) * (e.key === "ArrowRight" ? 1 : -1));
    }
  });

  // --- Escala: el escenario es de 1920×1080 y se ajusta a la ventana sin cambiar de forma ---
  const escalar = () => document.documentElement.style.setProperty("--dn-k", Math.min(innerWidth / 1920, (innerHeight - (revisor ? 48 : 0)) / 1080));
  addEventListener("resize", escalar);
  escalar();
  construir();
  preparar();
  medir();
  ponerLetra(LETRAS[params.get("letra")] ? params.get("letra") : "plex");
  document.fonts?.ready.then(remedir);
  if (params.get("revisar") === "1") { abrirRevisor(); escalar(); }
  prepararAudio();
  if (params.has("t")) {   // un cuadro fijo para capturas: sin audio hasta que el presentador pulse Espacio
    tiempo = Math.min(DURACION, Math.max(0, Number(params.get("t")) || 0));
    document.body.classList.add("dn-cuadro");
  }
  else document.body.classList.add("dn-en-portada");   // sin ?t: la portada, hasta que el presentador inicia
  render(tiempo);
  // Solo lectura, para revisar desde la consola: GrifterDinamica.estado()
  window.GrifterDinamica = {
    estado: () => ({ tiempo: Math.round(tiempo * 100) / 100, corriendo, mudo, duracion: DURACION,
      escena: escenas.find((s) => tiempo >= s.desde && tiempo < s.hasta)?.el.className.split(" ")[1]?.slice(5),
      audio: PISTAS.map((p) => ({ src: p.src, listo: p.a ? p.a.readyState : null, sonando: p.a ? !p.a.paused : false })) }),
  };
})();
