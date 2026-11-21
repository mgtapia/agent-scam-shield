// Grifter, demo versión B (dinamica.html): la misma historia del modo demo (demo.html), con ritmo de anuncio.
// Una escena nueva cada ~3 s, chats a pantalla completa con burbujas que entran de a una, el agente con cuerpo,
// números que cuentan y texto que se escribe letra por letra. Unos 110 s que corren solos, siempre iguales.
//
//   Espacio o «Iniciar»  arranca, pausa y sigue. Esa pulsación del presentador habilita el audio.
//   R  reinicia      1-7  salta al paso de la historia      M  silencia
//   ← →  mueve 1 s (con Mayús, 0,1 s) y deja la demo en pausa en ese cuadro
//   ?revisar=1  modo revisión: el segundo actual arriba a la derecha y la barra de progreso clicable
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
    ["gancho", 0, "zoom"], ["agentes", 4.6, "der"],
    // 2. El cuento del tío: el encargo, la llamada y cada frase del nieto en su escena
    ["encargo", 8.0, "abajo"], ["suena", 11.2, "zoom"], ["contesta", 13.6, "der"],
    ["n1", 15.9, "der"], ["n2", 20.65, "golpe"], ["n3", 22.6, "izq"], ["fianza", 26.6, "zoom"],
    ["n4", 29.55, "der"], ["cuenta", 32.6, "zoom"], ["n5", 37.35, "abajo"],
    // 3. El agente va a pagar y Grifter retiene
    ["paga", 40.9, "abajo"], ["frena", 44.2, "golpe"], ["motivo", 45.8, "zoom"],
    // 4. Pagar igual: doble autorización, Marta aprueba con su código y Pablo rechaza
    ["alerta", 50.0, "abajo"], ["quorum", 53.8, "der"], ["codigo", 56.6, "abajo"], ["uno", 60.2, "zoom"],
    ["pablo", 62.4, "der"], ["nada", 67.0, "zoom"],
    // 5. Dos estafas más
    ["banco", 70.6, "abajo"], ["responde", 74.0, "der"], ["clave", 76.0, "golpe"],
    ["aprobaste", 79.6, "zoom"], ["cobra", 82.4, "golpe"], ["calza", 85.0, "zoom"],
    // 6. Cifras
    ["estafas", 87.6, "zoom"], ["pasan", 91.0, "corte"], ["atacante", 94.0, "der"], ["cruzan", 97.8, "corte"],
    // 7. Cierre: la frase final (sin voz) y el logo que se arma
    ["remate", 101.0, "zoom"], ["cierre", 105.0, "zoom"],
  ];
  const DURACION = 110;
  const PASOS = [0, 8.0, 40.9, 50.0, 70.6, 87.6, 101.0];   // teclas 1 a 7

  // La narración (ElevenLabs, eleven_v3, voz de biblioteca). `pal` es el inicio de cada palabra en el mp3, sacado
  // de /with-timestamps: el texto de pantalla se escribe al ritmo de la voz, sin cargar audio (sirve para ?t=N).
  const NARR = {
    gancho:   { src: "audio/dinamica_01_gancho.mp3",   en: 0.3,   dur: 4.0,  pal: [0.14, 0.21, 0.37, 0.62, 1.01, 1.65, 1.98, 2.39, 2.75, 2.84, 3, 3.43] },
    agentes:  { src: "audio/dinamica_02_agentes.mp3",  en: 4.8,   dur: 2.64, pal: [0, 0.13, 0.65, 0.87, 1.35, 1.72, 1.91] },
    retiene:  { src: "audio/dinamica_03_retiene.mp3",  en: 44.6,  dur: 4.64, pal: [0.13, 0.51, 0.64, 1.28, 1.82, 2.22, 2.51, 2.6, 2.77, 3.55, 3.81, 3.95, 4.06] },
    banco:    { src: "audio/dinamica_04_banco.mp3",    en: 70.8,  dur: 3.04, pal: [0, 0.16, 0.63, 1.04, 1.31, 1.43, 1.88, 2.24] },
    clave:    { src: "audio/dinamica_05_clave.mp3",    en: 76.1,  dur: 3.12, pal: [0, 0.21, 0.52, 0.7, 1.25, 1.58, 1.9, 2.11, 2.22] },
    tienda:   { src: "audio/dinamica_06_tienda.mp3",   en: 79.7,  dur: 4.8,  pal: [0, 0.63, 1.49, 1.76, 2.76, 2.85, 3.01, 3.4, 3.82, 4.13, 4.46] },
    calza:    { src: "audio/dinamica_07_calza.mp3",    en: 85.2,  dur: 1.6,  pal: [0, 0.16, 0.6, 0.75, 0.82, 0.92] },
    estafas:  { src: "audio/dinamica_08_estafas.mp3",  en: 87.8,  dur: 6.0,  pal: [0, 0.52, 1.1, 1.89, 2.04, 2.36, 2.44, 2.64, 3.3, 3.65, 4.23, 5.15, 5.6] },
    atacante: { src: "audio/dinamica_09_atacante.mp3", en: 94.2,  dur: 6.56, pal: [0, 0.13, 0.66, 0.78, 1.31, 1.58, 2.08, 2.52, 2.74, 3.42, 3.84, 4.51, 5.5, 5.87, 5.98, 6.36] },
    remate:   { src: "audio/dinamica_11_remate.mp3",   en: 101.2, dur: 3.52, pal: [0, 0.13, 0.6, 0.86, 1.32, 1.41, 2.47, 2.56, 3.28] },
    cierre:   { src: "audio/dinamica_10_cierre.mp3",   en: 105.3, dur: 2.88, pal: [0.13, 1.17, 1.71, 1.89, 2.36, 2.53] },
  };
  // Cuándo empieza la palabra i de una narración, en segundos de la demo.
  const palabra = (n, i) => NARR[n].en + NARR[n].pal[i];
  // Las palabras desde la i, para que un texto de pantalla se escriba al ritmo de esa parte de la voz.
  const desdePalabra = (n, i) => ({ t0: palabra(n, i), pal: NARR[n].pal.slice(i).map((x) => x - NARR[n].pal[i]) });

  // La llamada: los mp3 de la versión A. FRASES son los inicios de cada frase del nieto en su mp3 (demo.js).
  const LL = { suena: 11.4, contesta: 13.6, abuela: 13.8, nieto: 15.9, cuelga: 40.6 };
  const FRASES = [0, 4.75, 6.7, 13.65, 21.45];
  const frase = (i) => LL.nieto + FRASES[i];
  // Cuándo «habla» el agente (su cuerpo se mueve y la boca sigue la voz) y cuándo suena cada voz de la llamada.
  const HABLA_AGENTE = [[9.3, 10.9], [41.1, 43.3], [74.1, 75.7]];
  const HABLA = { marta: [[LL.abuela, LL.abuela + 1.7]], nieto: [[LL.nieto, LL.cuelga]] };
  const ALARMA = [44.2, 65.3];   // el borde rojo: desde que Grifter retiene hasta que Pablo rechaza
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

  // El agente con cuerpo: cabeza cuadrada, dos ojos que parpadean y una boca de barras que sigue la voz.
  const agente = (cls = "") => `
        <div class="dn-agente ${cls}" aria-hidden="true">
          <i class="dn-antena"></i>
          <div class="dn-cabeza"><i class="dn-ojo"></i><i class="dn-ojo"></i><div class="dn-boca">${"<i></i>".repeat(5)}</div></div>
          <div class="dn-torso"><i></i><i></i></div>
        </div>`;
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
      h.push(`<section class="dn-escena dn-e-${id} ${cls}" data-desde="${desde}" data-hasta="${hasta}" data-entra="${entra}">${contenido}</section>`);
    };

    // 1. Gancho
    esc_("gancho", `
        <div class="dn-personas">${[0, 1, 2, 3].map((i) => `<span class="dn-persona"${ap(palabra("gancho", 3) + i * 0.08, "pop")}>${ic("person")}${i === 3 ? `<span class="dn-persona-cae"${ap(palabra("gancho", 6), "nada")}>${ic("person")}</span>` : ""}</span>`).join("")}</div>
        <h1 class="dn-titular dn-enorme">${saltan("1 de cada 4 chilenos", "gancho", 0)}</h1>
        <p class="dn-bajada">${escribe("ya perdió plata en una estafa digital.", 0, desdePalabra("gancho", 5))}</p>`, "dn-centro");
    esc_("agentes", `
        <div class="dn-agentes-fila">
          <div${ap(4.65, "pop")}>${agente("grande")}</div>
          <ul class="dn-tareas">
            <li${ap(5.3, "der")}>${ic("payments")}<span>paga la luz</span></li>
            <li${ap(5.7, "der")}>${ic("shopping_cart")}<span>compra en línea</span></li>
            <li${ap(6.1, "der")}>${ic("arrow_forward")}<span>transfiere</span></li>
          </ul>
        </div>
        <h1 class="dn-titular">${escribe("Ahora los agentes pagan por nosotros.", 0, desdePalabra("agentes", 1))}</h1>`, "dn-centro");

    // 2. El cuento del tío
    esc_("encargo", `
        <div class="dn-con-agente">
          <div class="dn-lado">${agente("grande")}<p class="dn-nombre">Agente de Marta</p></div>
          <div class="dn-chat">${cabeceraAgente([["en línea", 8.0, 9.3], ["escribiendo…", 9.3, 9.9], ["en línea", 9.9, null]])}
            <div class="dn-msgs">
              <div class="dn-burbuja yo"${ap(8.3, "pop")}><span class="dn-de">Marta</span>${esc(encargo)}</div>
              ${puntos(9.3, 9.9)}
              <div class="dn-burbuja ag"${ap(9.9, "pop")}>Listo, Marta. Yo contesto tus llamadas.</div>
            </div>
          </div>
        </div>`);
    esc_("suena", `
        <p class="dn-rotulo"${ap(11.25, "cae")}>El cuento del tío · la estafa telefónica más conocida de Chile</p>
        <div class="dn-vibra">
          ${fotoNieto("dn-xl dn-llama")}
          <p class="dn-quien-llama"${ap(11.4, "sube")}>Número privado</p>
          <p class="dn-sub"${ap(11.6, "sube")}>Llamada entrante</p>
          <div class="dn-ll-botones"${ap(11.8, "sube")}>
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
    esc_("fianza", `
        ${reloj()}
        <p class="dn-etiqueta"${ap(26.7, "cae")}>«Son…</p>
        <p class="dn-monto dn-ambar">${cuenta(0, 650000, 26.9, 1.7, { pesos: true })}</p>
        <p class="dn-etiqueta"${ap(28.5, "sube")}>…abuelita»</p>
        <span class="dn-tag ext"${ap(28.8, "pop")}>${ic("call")}dictado en la llamada</span>`, "dn-centro");
    esc_("n4", habla("Anota la cuenta del abogado:", frase(3) + 0.05, 16));
    esc_("cuenta", `
        ${reloj()}
        <p class="dn-etiqueta"${ap(32.8, "cae")}>Banco Austral · cuenta vista</p>
        <p class="dn-monto dn-ambar dato">${escribe("48-2210-7735", 33.3, { cps: 3.8 })}</p>
        <span class="dn-tag ext"${ap(36.6, "pop")}>${ic("call")}dictada por un número privado</span>`, "dn-centro");
    esc_("n5", `
        ${reloj()}
        <div class="dn-pila-centro">
          ${fotoNieto("dn-m")}${barras("nieto")}
          <h1 class="dn-titular">${escribe("Hazlo rápido, por favor, no me cortí.", frase(4) + 0.1, { cps: 14 })}</h1>
          <span class="dn-tag rojo"${ap(LL.cuelga, "pop")}>${ic("call_end")}Llamada finalizada · 0:27</span>
        </div>`, "dn-centro");

    // 3. El agente va a pagar y Grifter retiene
    esc_("paga", `
        <div class="dn-con-agente">
          <div class="dn-lado">${agente("grande")}<p class="dn-nombre">Agente de Marta</p></div>
          <div class="dn-chat">${cabeceraAgente([["en línea", 0, 41.1], ["escribiendo…", 41.1, 41.7], ["en línea", 41.7, null]])}
            <div class="dn-msgs">
              <div class="dn-burbuja yo"${ap(0, "pop")}><span class="dn-de">Marta</span>${esc(encargo)}</div>
              <div class="dn-burbuja ag"${ap(0, "pop")}>Listo, Marta. Yo contesto tus llamadas.</div>
              <p class="dn-sistema"${ap(40.95, "nada")}>${ic("call")}Llamada de número privado · 0:27</p>
              ${puntos(41.1, 41.7)}
              <div class="dn-burbuja ag"${ap(41.7, "pop")}>${escribe("Marta, Tomás necesita la fianza. Pago [[$650.000]] a la cuenta [[48-2210-7735]].", 41.7, { cps: 60 })}</div>
              <div class="dn-accion"${ap(43.0, "izq")}>${ic("payments")}<span class="dato">pagar $650.000 ${ic("arrow_forward", "chico")} 48-2210-7735</span><span class="dn-tag ext">llamada</span></div>
            </div>
          </div>
        </div>`);
    esc_("frena", `
        <div class="dn-escudo-golpe"${ap(44.25, "golpe")}>${ic("gpp_good")}</div>
        <h1 class="dn-titular dn-enorme"${ap(44.55, "sube")}>Pago retenido</h1>
        <p class="dn-tachado dato"${ap(44.85, "sube")}><span>$650.000 → 48-2210-7735</span><i${ap(45.15, "raya")}></i></p>`, "dn-centro");
    esc_("motivo", `
        <h1 class="dn-titular">${escribe("La cuenta salió de [[una llamada]], no de tu encargo.", 0, desdePalabra("retiene", 3))}</h1>
        <div class="dn-versus">
          <span class="dn-tag"${ap(48.6, "izq")}>${ic("person")}Encargo de Marta: contestar sus llamadas</span>
          <span class="dn-tag ext"${ap(49.0, "der")}>${ic("call")}Cuenta 48-2210-7735 · llamada</span>
        </div>`, "dn-centro");

    // 4. Pagar igual: doble autorización
    esc_("alerta", `
        <p class="dn-rotulo">${escribe("Marta está convencida: es su nieto.", 50.15, { cps: 30 })}</p>
        <div class="dn-alerta"${ap(50.05, "sube")}>
          <p class="dn-al-titulo">${ic("gpp_good")}<span>Grifter retuvo un pago</span></p>
          <p class="dn-al-motivo">La cuenta viene solo de una llamada, no de tu encargo ni de tus cuentas inscritas.</p>
          <dl class="dn-al-datos">
            <dt>Titular según el banco</dt><dd>J. Contreras V.</dd>
            <dt>Dice llamarse</dt><dd>‹Tomás, tu nieto› · <b class="dato">$650.000</b></dd>
            <dt>Cuenta</dt><dd class="dato">‹48-2210-7735›</dd>
            <dt>Apareció en</dt><dd>‹llamada de número privado›</dd>
          </dl>
          <div class="dn-al-botones">
            <span class="dn-b principal">Pagar a mi inscrita</span>
            <span class="dn-b">No pagar</span>
            <span class="dn-b peligro">Pagar igual${dedo(52.5, -420, 160)}</span>
          </div>
        </div>`);
    esc_("quorum", `
        <h1 class="dn-titular">${escribe("«Pagar igual» pide 2 aprobaciones", 53.9, { cps: 30 })}</h1>
        <div class="dn-dos">
          <div class="dn-ficha"${ap(54.9, "pop")}>${fotoMarta("dn-m")}<p>Marta</p></div>
          <div class="dn-ficha"${ap(55.25, "pop")}><span class="dn-sin-foto">${ic("person")}</span><p>Pablo, su hijo</p></div>
        </div>
        <p class="dn-contador dato"${ap(55.7, "pop")}>0 de 2</p>`, "dn-centro");
    esc_("codigo", `
        <div class="dn-notif"${ap(56.8, "cae")}>${ic("mail")}<div><p class="dn-notif-de">Grifter · correo</p><p>Tu código para aprobar el pago de $650.000: <b class="dato">482 913</b></p></div></div>
        <p class="dn-etiqueta"${ap(57.4, "sube")}>Marta ingresa su código</p>
        <div class="dn-digitos">${[...CODIGO].map((d, i) => `<span><b${ap(57.9 + i * 0.28, "pop")}>${d}</b></span>`).join("")}</div>
        <span class="dn-tag verde"${ap(59.6, "pop")}>${ic("check")}Marta aprobó con su código</span>`, "dn-centro");
    esc_("uno", `
        <p class="dn-gigante dato"${ap(60.3, "golpe")}>1 de 2</p>
        <div class="dn-dos">
          <div class="dn-ficha"${ap(60.6, "pop")}>${fotoMarta("dn-m")}<p>Marta <span class="dn-ok">${ic("check")}</span></p></div>
          <div class="dn-ficha dn-pulsa"${ap(60.9, "pop")}><span class="dn-sin-foto">${ic("person")}</span><p>Pablo · falta</p></div>
        </div>
        <p class="dn-etiqueta"${ap(61.3, "sube")}>Falta Pablo, su hijo</p>`, "dn-centro");
    esc_("pablo", `
        <div class="dn-chat dn-chat-ancho">
          <div class="dn-chat-cab"><span class="dn-chat-av escudo">${ic("shield")}</span><p><b>Grifter</b><span class="dn-estado"><span>WhatsApp de Pablo, su hijo</span></span></p></div>
          <div class="dn-msgs">
            ${puntos(62.55, 63.1)}
            <div class="dn-burbuja ag"${ap(63.1, "pop")}>Marta quiere pagar <b class="dato">$650.000</b> a J. Contreras V. La cuenta salió de una llamada de número privado que dice ser Tomás, su nieto.</div>
            <div class="dn-burbuja ag dn-chica"${ap(63.6, "pop")}>${ic("check")}1 de 2: Marta ya aprobó con su código</div>
            <div class="dn-wa-botones"${ap(64.0, "sube", 65.75)}>
              <span class="dn-b">Aprobar (pide tu código)</span>
              <span class="dn-b rechazar">Rechazar${dedo(65.0, -380, 220)}</span>
            </div>
            <p class="dn-sistema dn-resultado"${ap(65.95, "sube")}>${ic("block")}<span>Pablo rechazó.</span><b>No se pagó nada.</b></p>
          </div>
        </div>`);
    esc_("nada", `
        <span class="dn-escudo-ok"${ap(67.05, "golpe")}>${ic("check")}</span>
        <h1 class="dn-titular dn-enorme">${escribe("No se pagó nada.", 67.2, { cps: 18 })}</h1>
        <p class="dn-tachado dato"${ap(68.2, "sube")}><span>$650.000</span><i${ap(68.5, "raya")}></i></p>
        <p class="dn-etiqueta"${ap(69.0, "sube")}>Un solo «no» basta para cancelar</p>`, "dn-centro");

    // 5. Dos estafas más: el código del banco y la tienda que cobra de más
    esc_("banco", `
        <p class="dn-rotulo"${ap(70.65, "cae")}>Otra estafa: el falso Banco Cordillera</p>
        <div class="dn-correo">
          <p class="dn-correo-de"${ap(70.8, "izq")}>${ic("mail")}<span>seguridad@<mark class="dn-marca">bancocordillera-alertas.cl</mark></span></p>
          <p class="dn-correo-asunto"${ap(71.2, "sube")}>Cargo no reconocido por $389.990 en tu tarjeta</p>
          <p class="dn-correo-cuerpo">${escribe("Para revertirlo antes de 30 minutos, responde con el [[código que te llegó por SMS]]. Si no, tu tarjeta será bloqueada.", 71.7, { cps: 75 })}</p>
        </div>`);
    esc_("responde", `
        <div class="dn-con-agente">
          <div class="dn-lado">${agente("grande")}<p class="dn-nombre">Agente de Marta</p></div>
          <div class="dn-respuesta">
            <p class="dn-rot">Respuesta del agente a seguridad@<mark class="dn-marca">bancocordillera-alertas.cl</mark></p>
            <p class="dn-resp-txt">${escribe("Hola, el código de verificación es [[482 913]]", 74.2, { cps: 30 })}</p>
            <span class="dn-b principal dn-enviar"${ap(74.9, "pop")} data-on="75.7">Enviar ${ic("arrow_forward", "chico")}</span>
          </div>
        </div>`);
    esc_("clave", `
        <div class="dn-escudo-golpe chico"${ap(76.05, "golpe")}>${ic("gpp_good")}</div>
        <h1 class="dn-titular">${escribe("La clave del dueño no sale sin su confirmación.", 0, desdePalabra("clave", 0))}</h1>
        <p class="dn-tachado dato chico"${ap(78.3, "sube")}><span>código 482 913 · no se envió</span><i${ap(78.6, "raya")}></i></p>`, "dn-centro");
    esc_("aprobaste", `
        <p class="dn-rotulo"${ap(79.65, "cae")}>${ic("shopping_cart")}Componentes Volcán · Orden VOL-5512 · 10.000 × chip MX-3 de 3 nm</p>
        <p class="dn-etiqueta"${ap(79.8, "sube")}>Aprobaste</p>
        <p class="dn-monto">${cuenta(0, 412000, palabra("tienda", 1) - 0.1, 1.2, { pesos: true })}</p>`, "dn-centro");
    esc_("cobra", `
        <p class="dn-etiqueta"${ap(82.45, "cae")}>La tienda cobra</p>
        <p class="dn-monto dn-sube-rojo" data-on="83.5">${cuenta(412000, 4120000, 82.6, 0.9, { pesos: true })}</p>
        <span class="dn-tag ext"${ap(83.7, "pop")}>10 veces lo que aprobaste</span>`, "dn-centro");
    esc_("calza", `
        <div class="dn-escudo-golpe chico"${ap(85.05, "golpe")}>${ic("gpp_good")}</div>
        <h1 class="dn-titular dn-enorme">${escribe("No calza con lo que aprobaste.", 0, desdePalabra("calza", 0))}</h1>
        <div class="dn-versus">
          <span class="dn-tag"${ap(86.2, "izq")}>Aprobaste <b class="dato">$412.000</b></span>
          <span class="dn-tag rojo"${ap(86.5, "pop")}>Cobra <b class="dato">$4.120.000</b></span>
          <span class="dn-tag verde"${ap(86.8, "der")}>${ic("block")}no se pagó</span>
        </div>`, "dn-centro");

    // 6. Cifras (docs/cifras.md: 150 estafas de 32 tipos, 0 pasan Grifter completo; 5.280 intentos, 0 cruzan la capa 2)
    esc_("estafas", `
        <p class="dn-cifra dato">${cuenta(0, 150, palabra("estafas", 0), 1.1)}</p>
        <p class="dn-cifra-txt"${ap(palabra("estafas", 2), "pop")}>estafas</p>
        <p class="dn-cifra-txt dn-2"${ap(palabra("estafas", 3), "sube")}>de <b class="dato">${cuenta(0, 32, palabra("estafas", 4), 0.7)}</b> tipos</p>
        <p class="dn-fuente dato"${ap(90.0, "nada")}>agente que hace todo lo que lee · grifter bench</p>`, "dn-centro");
    esc_("pasan", `
        <p class="dn-cifra dato dn-a-verde" data-on="93.3">${cuenta(150, 0, 91.3, 2.0, { baja: true })}</p>
        <p class="dn-cifra-txt"${ap(palabra("estafas", 8), "pop")}>pasan con Grifter completo</p>
        <p class="dn-fuente dato"${ap(92.2, "nada")}>150 de 150 frenadas · capas 2 y 3 · docs/cifras.md</p>`, "dn-centro");
    esc_("atacante", `
        <p class="dn-cifra dato">${cuenta(0, 5280, palabra("atacante", 4), 1.6)}</p>
        <p class="dn-cifra-txt"${ap(palabra("atacante", 0), "pop")}>intentos de un atacante que aprende</p>
        <p class="dn-fuente dato"${ap(96.6, "nada")}>120 generaciones · 6 corridas · grifter duelo</p>`, "dn-centro");
    esc_("cruzan", `
        <p class="dn-cifra dato dn-a-verde" data-on="99.6">${cuenta(5280, 0, 98.0, 1.6, { baja: true })}</p>
        <p class="dn-cifra-txt"${ap(palabra("atacante", 11), "pop")}>cruzan la capa 2</p>
        <p class="dn-fuente dato"${ap(99.0, "nada")}>5.280 intentos contra la capa 2 · grifter duelo · docs/cifras.md</p>`, "dn-centro");

    // 7. Cierre: la frase final se escribe con la voz; después el escudo se dibuja, «Grifter» cae letra por letra y el lema se escribe con la voz
    esc_("remate", `
        <h1 class="dn-titular dn-frase-final">${escribe(FRASE_FINAL[0], 0, desdePalabra("remate", 0))}<span class="dn-remate-2">${escribe(FRASE_FINAL[1], 0, desdePalabra("remate", FRASE_FINAL[0].split(" ").length))}</span></h1>`, "dn-centro");
    esc_("cierre", `
        <div class="dn-logo">
          <svg class="dn-logo-ic" viewBox="0 -960 960 960" aria-hidden="true">
            <defs><mask id="dn-trazo" maskUnits="userSpaceOnUse" x="0" y="-960" width="960" height="960">
              <path id="dn-trazo-p" d="M480-860 L780-746 V-516 Q780-250 480-110 Q180-250 180-516 V-746 Z" fill="none" stroke="#fff" stroke-width="150" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>
            </mask></defs>
            <path d="${P.shield}" mask="url(#dn-trazo)"/>
          </svg>
          <span class="dn-logo-txt">${[..."Grifter"].map((c, i) => `<span${ap(palabra("cierre", 0) - 0.05 + i * 0.07, "cae")}>${c}</span>`).join("")}</span>
        </div>
        <p class="dn-lema">${escribe("Escudo para agentes que pagan", 0, desdePalabra("cierre", 1))}</p>
        <p class="dn-url dato"${ap(107.8, "sube")}>grifter.onrender.com</p>
        <p class="dn-aviso"${ap(108.3, "nada")}>Personas y marcas ficticias · voces sintéticas</p>`, "dn-centro");

    h.push(`<div class="dn-progreso" aria-hidden="true"><i id="dn-barra"></i></div>
      <div class="dn-portada" aria-hidden="true">
        <div class="dn-logo">${ic("shield", "dn-logo-ic")}<span>Grifter</span></div>
        <p class="dn-lema">1 de cada 4 chilenos ya perdió plata en una estafa digital.</p>
      </div>
      <button type="button" class="dn-inicio" id="dn-inicio" aria-label="Iniciar o pausar la demo (Espacio)">${ic("play_arrow")}<span>Espacio</span></button>`);
    $("#dn-escenario").innerHTML = h.join("");
    $("#dn-inicio").addEventListener("click", alternar);
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
      agentes: [...el.querySelectorAll(".dn-agente")],
      barras: [...el.querySelectorAll(".dn-barras")],
      puntos: [...el.querySelectorAll(".dn-puntos i")],
      anillos: [...el.querySelectorAll(".dn-anillo")],
      relojes: [...el.querySelectorAll(".dn-reloj-s")],
      pulsa: [...el.querySelectorAll(".dn-pulsa")],
      vibra: el.querySelector(".dn-vibra"),
      contestar: el.querySelector(".contestar"),
      trazo: el.querySelector("#dn-trazo-p"),
    }));
  }

  function aparecer(el, tt) {
    const v = +el.dataset.v, h = el.dataset.h === undefined ? Infinity : +el.dataset.h;
    let a;
    if (tt < v || tt >= h + 0.15) a = 0;
    else if (quieto) a = tt < h ? 1 : 0;
    else a = Math.min(clamp((tt - v) / 0.35), tt >= h ? 1 - (tt - h) / 0.15 : 1);
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
      // El agente: respira siempre (salvo con movimiento reducido) y mueve la boca y la cabeza cuando habla.
      const hablaAg = dentro(tt, HABLA_AGENTE);
      for (const ag of s.agentes) {
        ag.classList.toggle("habla", hablaAg);
        ag.style.setProperty("--bob", quieto ? "0px" : `${(Math.sin(tt * 2 * Math.PI * 0.8) * (hablaAg ? 12 : 7)).toFixed(1)}px`);
        ag.style.setProperty("--tilt", quieto || !hablaAg ? "0deg" : `${(Math.sin(tt * 5.1) * 4).toFixed(2)}deg`);
        ag.style.setProperty("--ojo", !quieto && tt % 2.9 < 0.13 ? 0.1 : 1);
        ag.querySelectorAll(".dn-boca i").forEach((b, i) => {
          const hb = hablaAg ? (quieto ? 0.6 : 0.2 + 0.8 * Math.abs(0.6 * Math.sin(tt * 13 + i * 1.3) + 0.4 * Math.sin(tt * 21 + i * 2.2))) : 0.12;
          b.style.setProperty("--h", hb.toFixed(3));
        });
      }
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
      if (s.trazo) s.trazo.setAttribute("stroke-dashoffset", (quieto ? (tt >= s.desde ? 0 : 1) : 1 - salida(clamp((tt - s.desde - 0.15) / 1.3))).toFixed(3));
    }
    // El borde rojo de alerta, mientras el pago está retenido y nadie lo rechazó. Late en opacidad (fijo si reducido).
    const alarma = tt >= ALARMA[0] && tt < ALARMA[1];
    document.body.classList.toggle("dn-alarma", alarma);
    document.body.style.setProperty("--alarma", quieto ? 1 : (0.35 + 0.65 * (0.5 + 0.5 * Math.cos(((tt - ALARMA[0]) * 2 * Math.PI) / 1.2))).toFixed(3));
    $("#dn-barra").style.width = `${(Math.min(tt, DURACION) / DURACION) * 100}%`;
    if (revisor) revisor.firstChild.textContent = `t = ${tt.toFixed(1)} s`;
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
  function alternar() {
    if (tiempo >= DURACION) return irA(0, true);
    corriendo = !corriendo;
    document.body.classList.toggle("dn-corriendo", corriendo);
    if (corriendo) { document.body.classList.remove("dn-en-portada"); reanudar(tiempo); previo = 0; requestAnimationFrame(cuadro); } else callar();
  }
  function irA(s, seguir) {
    callar();
    document.body.classList.remove("dn-en-portada");
    tiempo = s;
    corriendo = false;
    document.body.classList.remove("dn-corriendo");
    render(tiempo);
    if (seguir) alternar();
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === " " || e.code === "Space") { e.preventDefault(); alternar(); }
    else if (e.key === "r" || e.key === "R") irA(0, true);
    else if (e.key === "m" || e.key === "M") { mudo = !mudo; if (mudo) callar(); else if (corriendo) reanudar(tiempo); }
    else if (/^[1-7]$/.test(e.key)) irA(PASOS[+e.key - 1], true);
    // Revisión: las flechas mueven 1 s (con Mayús, 0,1 s) y dejan la demo en pausa en ese cuadro.
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const paso = (e.shiftKey ? 0.1 : 1) * (e.key === "ArrowRight" ? 1 : -1);
      irA(Math.max(0, Math.min(DURACION, Math.round((tiempo + paso) * 10) / 10)), false);
    }
  });

  // --- Escala: el escenario es de 1920×1080 y se ajusta a la ventana sin cambiar de forma ---
  const escalar = () => document.documentElement.style.setProperty("--dn-k", Math.min(innerWidth / 1920, innerHeight / 1080));
  addEventListener("resize", escalar);
  escalar();
  construir();
  preparar();
  // --- Modo revisión (?revisar=1): el segundo actual, para decir «en t = 48,7 cambia esto». No sale en el pitch. ---
  let revisor = null;
  if (params.get("revisar") === "1") {
    revisor = document.createElement("div");
    revisor.className = "dn-revisor";
    revisor.append("t = 0.0 s", document.createElement("small"));
    revisor.lastChild.textContent = "Espacio pausa · ← → 1 s · Mayús 0,1 s · clic en la barra salta";
    document.body.append(revisor);
    document.body.classList.add("dn-revisando");
    $(".dn-progreso").addEventListener("click", (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      irA(Math.round(((e.clientX - r.left) / r.width) * DURACION * 10) / 10, false);
    });
  }
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
