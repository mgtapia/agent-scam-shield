// Grifter, demo versión C (grafo.html): la historia de la versión B (dinamica.html) contada sobre un grafo animado.
// El grafo es el escenario desde que el agente va a pagar: las fuentes a la izquierda (Marta, la dueña, y las de
// afuera: la llamada, el correo, la tienda), el agente al centro (la constelación), la compuerta de Grifter sobre
// las aristas de salida y las acciones a la derecha. Cada dato viaja como un paquete rotulado que lleva el color y el
// ícono de su origen, y los conserva al pasar por el agente: eso es el seguimiento de origen. Lo que viene de afuera
// choca con la compuerta; lo que viene de Marta, pasa.
//
//   Espacio o «Iniciar»  arranca, pausa y sigue. Esa pulsación del presentador habilita el audio.
//   R  reinicia      1-7  salta al paso de la historia      M  silencia
//   ?whatsapp=1&clave=…  en vivo: el pedido le llega de verdad a Pablo y la demo espera su rechazo (S sigue sin él)
//   ← →  mueve 1 s (con Mayús, 0,1 s) y deja la demo en pausa en ese cuadro
//   ?revisar=1 o V  modo revisión: una barra de controles abajo (retroceder, pausar, arrastrar, copiar el enlace)
//   ?t=30  dibuja el segundo 30 en pausa y sin audio (para capturas)
//
// render(t) es una función pura del tiempo: no hay transiciones ni animaciones CSS con reloj propio y nada usa
// Math.random (las fases salen de semillas fijas), así que ?t=N da siempre el mismo cuadro. Con movimiento reducido
// cada cosa salta a su estado final. Toda la demo va narrada (audio/grafo_*.mp3, voz sintética de biblioteca), salvo
// la llamada, donde hablan Marta y su «nieto». Las cifras son las de docs/cifras.md (filas 4, 8 y 9), que salen de
// demo/resultados.json. Personas y marcas ficticias.
"use strict";

(() => {
  // --- Íconos: Material Symbols Sharp en línea (los mismos de demo.js y dinamica.js, más enviar y banco) ---
  const P = {
    block: "M331.86-129.92q-69.37-29.92-120.68-81.21-51.31-51.29-81.25-120.63Q100-401.1 100-479.93q0-78.84 29.92-148.21t81.21-120.68q51.29-51.31 120.63-81.25Q401.1-860 479.93-860q78.84 0 148.21 29.92t120.68 81.21q51.31 51.29 81.25 120.63Q860-558.9 860-480.07q0 78.84-29.92 148.21t-81.21 120.68q-51.29 51.31-120.63 81.25Q558.9-100 480.07-100q-78.84 0-148.21-29.92ZM480-160q56.29 0 108.42-19.04 52.12-19.04 95.27-55.11L234.15-683.69q-35.69 43.15-54.92 95.27Q160-536.29 160-480q0 134 93 227t227 93Zm245.85-116.31q36.07-43.15 55.11-95.27Q800-423.71 800-480q0-134-93-227t-227-93q-56.43 0-108.68 18.85-52.24 18.84-95.01 55.3l449.54 449.54ZM480-480Z",
    call: "M783-140q-116.54 0-232.12-51.89-115.57-51.88-211.34-147.65-95.38-95.77-147.46-211.42Q140-666.61 140-783v-37h206.77l35.46 182.15-110.92 107.7q24.69 43.23 52.84 80.34 28.16 37.12 59.54 67.89 30.54 31.31 67.93 59.15 37.38 27.85 83.15 53.54L645-381.38l175 35.61V-140h-37ZM242.92-586.92l74.85-71.39L297.69-760h-97.07q3.07 45.38 13.65 88.35 10.58 42.96 28.65 84.73Zm348 345.69q38.46 17.77 82.04 27.96 43.58 10.19 87.04 12.04v-96.08l-94.77-19-74.31 75.08Zm-348-345.69Zm348 345.69Z",
    call_end: "M161.77-292.69 29.85-421.38l32.69-33.7q84.61-89.07 195.58-132Q369.08-630 480-630t220.88 43.42q109.97 43.43 196.2 131.5l33.07 33.7-131.92 128.69L650-404.62v-136.3q-41.85-13.93-84.54-21.5Q522.77-570 480-570q-42.77 0-85.46 7.58-42.69 7.57-84.54 21.5v136.3L161.77-292.69ZM250-517.39q-37.08 18.08-71.39 42-34.3 23.93-64.46 51.39l53.08 53.08L250-434.61v-82.78Zm460 1.23v80.78l82.77 64.46L846.62-422q-32.85-29.85-66-53.08-33.16-23.23-70.62-41.08Zm-460-1.23Zm460 1.23Z",
    mail: "M100-180v-600h760v600H100Zm380-277.69L160-662.31V-240h640v-422.31L480-457.69Zm0-62.31 313.85-200h-627.7L480-520ZM160-662.31V-720v480-422.31Z",
    check: "M382-253.85 168.62-467.23 211.38-510 382-339.38 748.62-706l42.76 42.77L382-253.85Z",
    payments: "M550-451.54q-41.92 0-70.96-29.04Q450-509.62 450-551.54q0-41.92 29.04-70.96 29.04-29.04 70.96-29.04 41.92 0 70.96 29.04Q650-593.46 650-551.54q0 41.92-29.04 70.96-29.04 29.04-70.96 29.04ZM213.85-327.69v-447.69h672.3v447.69h-672.3Zm132.3-60h407.7q0-29.92 21.24-51.12Q796.33-460 826.15-460v-183.08q-29.92 0-51.11-21.24-21.19-21.24-21.19-51.06h-407.7q0 29.92-21.24 51.11-21.24 21.19-51.06 21.19V-460q29.92 0 51.11 21.24 21.19 21.24 21.19 51.07Zm-272.3 200v-468.46h60v408.46h633.07v60H73.85Zm200-200v-327.69 327.69Z",
    person: "M381.04-533.35Q340-574.38 340-632.31q0-57.92 41.04-98.96 41.04-41.04 98.96-41.04 57.92 0 98.96 41.04Q620-690.23 620-632.31q0 57.93-41.04 98.96-41.04 41.04-98.96 41.04-57.92 0-98.96-41.04ZM180-187.69v-88.93q0-29.38 15.96-54.42 15.96-25.04 42.66-38.5 59.3-29.07 119.65-43.61 60.35-14.54 121.73-14.54t121.73 14.54q60.35 14.54 119.65 43.61 26.7 13.46 42.66 38.5Q780-306 780-276.62v88.93H180Zm60-60h480v-28.93q0-12.15-7.04-22.5-7.04-10.34-19.11-16.88-51.7-25.46-105.42-38.58Q534.7-367.69 480-367.69q-54.7 0-108.43 13.11-53.72 13.12-105.42 38.58-12.07 6.54-19.11 16.88-7.04 10.35-7.04 22.5v28.93Zm296.5-328.12q23.5-23.5 23.5-56.5t-23.5-56.5q-23.5-23.5-56.5-23.5t-56.5 23.5q-23.5 23.5-23.5 56.5t23.5 56.5q23.5 23.5 56.5 23.5t56.5-23.5Zm-56.5-56.5Zm0 384.62Z",
    shopping_cart: "M236.58-118.12q-20.42-20.42-20.42-49.57 0-29.16 20.42-49.58 20.42-20.42 49.57-20.42 29.16 0 49.58 20.42 20.42 20.42 20.42 49.58 0 29.15-20.42 49.57-20.42 20.43-49.58 20.43-29.15 0-49.57-20.43Zm387.69 0q-20.42-20.42-20.42-49.57 0-29.16 20.42-49.58 20.42-20.42 49.58-20.42 29.15 0 49.57 20.42t20.42 49.58q0 29.15-20.42 49.57Q703-97.69 673.85-97.69q-29.16 0-49.58-20.43ZM240.61-730 342-517.69h280L738.54-730H240.61Zm-28.76-60h628.46L657.46-457.69H324l-54.77 100h474.61v60H167.31l114.38-206L136.16-810H60v-60h113.85l38 80ZM342-517.69h280-280Z",
    play_arrow: "M320-200v-560l440 280-440 280Z",
    arrow_forward: "M665.08-450H180v-60h485.08L437.23-737.85 480-780l300 300-300 300-42.77-42.15L665.08-450Z",
    send: "M120-160v-640l760 320-760 320Zm80-120 474-200-474-200v140l240 60-240 60v140Z",
    banco: "M200-280v-280h80v280h-80Zm240 0v-280h80v280h-80ZM80-120v-80h800v80H80Zm600-160v-280h80v280h-80ZM80-640v-80l400-200 400 200v80H80Zm178-80h444L480-830 258-720Z",
  };
  // El contorno del escudo (solo para el cierre, mientras img/marca.png no carga, y para la figura de partículas).
  const ESCUDO_D = "M60 8 L108 26 V68 C108 100 88 122 60 132 C32 122 12 100 12 68 V26 Z";
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
  // La clave del WhatsApp en vivo no queda a la vista en el proyector: se guarda en la pestaña y sale de la barra.
  let claveVivo = params.get("clave") || "";
  try { if (claveVivo) sessionStorage.setItem("grifter-clave", claveVivo); else claveVivo = sessionStorage.getItem("grifter-clave") || ""; } catch { /* sin almacenamiento, sirve la de la URL */ }
  if (params.has("clave")) { const u = new URL(location.href); u.searchParams.delete("clave"); history.replaceState(null, "", u); }

  // --- La narración (ElevenLabs, voz sintética de biblioteca). `dur` es la duración del mp3 y `pal` el inicio de cada
  // palabra, sacados de /with-timestamps (están también en la ficha .json de cada pista): el texto de pantalla se
  // escribe al ritmo de la voz, sin cargar audio (sirve para ?t=N). Las pistas que ya tenía la versión B están
  // copiadas con nombre propio. Si se regenera la voz, se pega aquí la tabla nueva y nada más: los tiempos de las
  // escenas se calculan abajo desde estas duraciones ---
  const NARR = {
    gancho:   { src: "audio/grafo_01_gancho.mp3", dur: 4.78, pal: [0.07, 0.48, 0.77, 0.93, 1.18, 1.57, 2.19, 2.46, 2.88, 3.36, 3.56, 3.74, 4.15] },
    agentes:  { src: "audio/grafo_02_agentes.mp3", dur: 3.03, pal: [0, 0.15, 0.78, 1.04, 1.67, 2.04, 2.23] },
    encargo:  { src: "audio/grafo_03_encargo.mp3", dur: 2.8, pal: [0, 0.48, 0.7, 1.16, 1.33, 1.92, 2.05, 2.19] },
    sin:      { src: "audio/grafo_04_sin.mp3", dur: 4.08, pal: [0, 0.21, 0.72, 0.94, 1.36, 1.6, 2.3, 2.37, 3.09, 3.27, 3.65, 3.81] },
    retiene:  { src: "audio/grafo_05_retiene.mp3", dur: 4.15, pal: [0.2, 0.61, 0.76, 1.25, 1.42, 1.8, 2.11, 2.2, 2.35, 3.09, 3.23, 3.33, 3.48] },
    pasa:     { src: "audio/grafo_06_pasa.mp3", dur: 1.91, pal: [0, 0.12, 0.28, 0.51, 0.62, 1.5] },
    insiste:  { src: "audio/grafo_07_insiste.mp3", dur: 3.74, pal: [0, 0.36, 0.92, 1.35, 1.79, 2.34, 2.68] },
    aprueban: { src: "audio/grafo_08_aprueban.mp3", dur: 4.55, pal: [0, 0.4, 0.84, 1.01, 1.19, 1.81, 2.69, 2.88, 3.44, 3.87, 3.98] },
    rechaza:  { src: "audio/grafo_08b_rechaza.mp3", dur: 2.53, pal: [0, 0.21, 0.4, 1.12, 1.49, 1.66, 2.08] },
    banco:    { src: "audio/grafo_09_banco.mp3", dur: 2.14, pal: [0, 0.2, 0.63, 1.08, 1.41, 1.59] },
    clave:    { src: "audio/grafo_10_clave.mp3", dur: 2.53, pal: [0, 0.17, 0.72, 0.94, 1.26, 1.47, 1.58] },
    tienda:   { src: "audio/grafo_11_tienda.mp3", dur: 4.23, pal: [0, 0.72, 1.68, 2, 2.45, 2.6, 3.1, 3.51, 3.76] },
    calza:    { src: "audio/grafo_12_calza.mp3", dur: 1.75, pal: [0, 0.18, 0.6, 0.75, 0.84, 1] },
    estafas:  { src: "audio/grafo_13_estafas.mp3", dur: 2.8, pal: [0, 0.4, 0.94, 1.88, 2.32] },
    atacante: { src: "audio/grafo_14_atacante.mp3", dur: 5.51, pal: [0, 0.3, 0.56, 1.2, 1.69, 2.53, 2.67, 2.77, 3.44, 3.74, 4.68, 4.94] },
    remate:   { src: "audio/grafo_15_remate.mp3", dur: 3.42, pal: [0, 0.11, 0.55, 0.92, 1.34, 1.42, 2.45, 2.55, 3.07] },
    cierre:   { src: "audio/grafo_16_cierre.mp3", dur: 2.72, pal: [0.07, 0.91, 1.41, 1.65, 2.04, 2.24] },
  };

  // --- Línea de tiempo (segundos). Cada escena dura lo que dura su voz: las pistas van una tras otra con una décima
  // de aire, ninguna se encima con otra ni con la llamada, y fuera de la llamada no queda más de 1 s sin voz. La
  // llamada (de «contesta» a «n5») va igual que en la versión B: sus mp3 y su sincronía no se tocan. E es el inicio
  // de cada escena; NARR[x].en, el de cada pista. El tope es 120 s; los respiros entre pistas no se recortan ---
  const E = {};
  const r5 = (x) => Math.round(x * 20) / 20;
  const pista = (n, t) => { NARR[n].en = r5(t); return NARR[n].en + NARR[n].dur; };   // pone la pista y devuelve dónde termina
  const enPalabra = (n, i) => NARR[n].en + NARR[n].pal[i];
  let fin;
  // 1. Gancho, y 2. el encargo de Marta
  E.gancho = 0; fin = pista("gancho", 0.3);
  E.agentes = r5(fin + 0.4); fin = pista("agentes", E.agentes + 0.1);   // medio segundo de aire después de «…estafa digital»: la cifra respira
  E.encargo = r5(fin); fin = pista("encargo", E.encargo + 0.1);
  // La llamada. Suena 1,3 s y Marta contesta. El nieto dice «Abuelita, soy yo po, tu nieto.» y Marta lo interrumpe y
  // le pone nombre («¿Tomás? ¿Qué te pasó, mijo?»); después él sigue con «No le digai a nadie, por favor. Choqué el
  // auto…». El mp3 del nieto no se corta: se pausa en CORTE y sigue desde ahí. En ese mp3, «tu nieto.» termina en
  // 2,44 s y «No le digai» empieza en 2,87 s (medido con la envolvente del audio): el corte va al medio del silencio.
  // Cada escena va a su segundo del mp3 del nieto: nieto(s) es el segundo de la demo en que el mp3 va en s.
  E.suena = r5(fin); E.contesta = r5(E.suena + 1.3);
  const CORTE = 2.65, DUR_NIETO = 23.52, DUR_ABUELA = 1.92, DUR_TOMAS = 2.88;   // duraciones de los mp3 de la llamada
  const LL = { suena: E.suena + 0.1, contesta: E.contesta, abuela: E.contesta + 0.2, nieto: r5(E.contesta + 2.1) };
  LL.abuela2 = r5(LL.nieto + CORTE + 0.05);                   // «¿Tomás? ¿Qué te pasó, mijo?»
  LL.tomas = LL.abuela2 + 0.16;                               // cuando Marta dice «Tomás»: el que llama deja de ser «Desconocido»
  LL.nieto2 = r5(LL.abuela2 + DUR_TOMAS + 0.05);              // el nieto sigue
  LL.cuelga = r5(LL.nieto2 + 24.7 - CORTE);                  // «Llamada finalizada», con el mismo respiro de la versión B tras la última frase
  const nieto = (s) => (s < CORTE ? LL.nieto + s : LL.nieto2 + s - CORTE);
  E.n1 = LL.nieto; E.tomas = r5(LL.abuela2 - 0.05); E.n1b = LL.nieto2;
  for (const [id, s] of [["n2", 4.75], ["n3", 6.7], ["fianza", 10.3], ["n4", 13.65], ["cuenta", 16.7], ["n5", 21.45]]) E[id] = r5(nieto(s));
  E.paga = r5(LL.cuelga + 0.3);
  // 3. El grafo a pantalla completa: el agente paga (sin Grifter), se rebobina, Grifter retiene y lo de Marta pasa
  fin = pista("sin", E.paga + 0.1);
  E.sin = r5(enPalabra("sin", 6) - 0.05);                 // «Sin Grifter…»
  E.frena = r5(fin + 0.6);                                // medio segundo de rebobinado
  fin = pista("retiene", E.frena + 0.05);
  E.motivo = r5(enPalabra("retiene", 3) - 0.03);          // «…la cuenta salió de una llamada»
  E.pasa = r5(fin + 0.05); fin = pista("pasa", E.pasa + 0.05);
  // 4. Pagar igual: doble aprobación, Marta aprueba con su código y Pablo rechaza
  E.alerta = r5(fin + 0.05); fin = pista("insiste", E.alerta + 0.1);
  E.codigo = r5(fin + 0.05); fin = pista("aprueban", E.codigo + 0.05);
  E.pablo = r5(enPalabra("aprueban", 5) - 0.07);          // «Pablo, su hijo, recibe un mensaje.»
  // Aquí termina la pista (a). En vivo (?whatsapp=1) el tiempo se detiene en este punto hasta que Pablo rechaza de
  // verdad desde su WhatsApp; sin eso, la demo sigue de corrido con el toque dibujado y la pista (b).
  E.rechaza = r5(fin + 0.05); fin = pista("rechaza", E.rechaza + 0.4);
  // 5. Dos estafas más sobre el mismo grafo
  E.banco = r5(fin + 0.05); fin = pista("banco", E.banco + 0.1);
  E.responde = r5(fin - 0.05); E.clave = r5(E.responde + 0.75); fin = pista("clave", E.clave + 0.05);
  E.aprobaste = r5(fin + 0.1); fin = pista("tienda", E.aprobaste + 0.1);
  E.cobra = r5(enPalabra("tienda", 4) - 0.08);            // «Te cobran…»
  E.calza = r5(fin + 0.05); fin = pista("calza", E.calza + 0.05);
  // 6. Medición: el grafo se aleja
  E.estafas = r5(fin + 0.1); fin = pista("estafas", E.estafas + 0.1);
  E.pasan = r5(enPalabra("estafas", 3) - 0.08);           // «Pasan…»
  E.atacante = r5(fin + 0.1); fin = pista("atacante", E.atacante + 0.1);
  E.cruzan = r5(enPalabra("atacante", 10) - 0.12);        // «Cero…»
  // 7. Cierre: la frase final y la marca que se arma
  E.remate = r5(fin + 0.1); fin = pista("remate", E.remate + 0.1);
  E.cierre = r5(fin + 0.05); fin = pista("cierre", E.cierre + 0.2);
  const DURACION = r5(fin + 0.3);
  // Cómo entra cada escena. Las del grafo son capas de rótulos sobre el mismo grafo: entran de corte.
  const ENTRADA = { gancho: "zoom", agentes: "der", encargo: "abajo", suena: "zoom", contesta: "der", n1: "der", n1b: "corte", n2: "golpe", n3: "izq",
    tomas: "corte", fianza: "zoom", n4: "der", cuenta: "zoom", n5: "abajo", remate: "zoom", cierre: "zoom" };
  const ESCENAS = Object.entries(E).sort((a, b) => a[1] - b[1]).map(([id, desde]) => [id, desde, ENTRADA[id] || "corte"]);
  const PASOS = [0, E.encargo, E.paga, E.alerta, E.banco, E.estafas, E.remate];   // teclas 1 a 7

  // Cuándo empieza la palabra i de una narración, en segundos de la demo.
  const palabra = enPalabra;
  // Las palabras desde la i, para que un texto de pantalla se escriba al ritmo de esa parte de la voz.
  const desdePalabra = (n, i) => ({ t0: palabra(n, i), pal: NARR[n].pal.slice(i).map((x) => x - NARR[n].pal[i]) });

  // FRASES son los inicios de cada frase del nieto en su mp3 (demo.js).
  const FRASES = [0, 4.75, 6.7, 13.65, 21.45];
  const frase = (i) => nieto(FRASES[i]);
  const HABLA = { marta: [[LL.abuela, LL.abuela + 1.7], [LL.abuela2, LL.abuela2 + 2.75]], nieto: [[LL.nieto, LL.nieto + 2.45], [nieto(2.85), nieto(23.45)]] };
  const DUR_LLAMADA = `0:${String(Math.floor(LL.cuelga - LL.contesta)).padStart(2, "0")}`;
  // El toque en «Rechazar», con la voz («…rechaza»); el dedo no asoma antes del punto donde la demo en vivo espera.
  const TOQUE_PABLO = Math.max(palabra("rechaza", 2) + 0.05, E.rechaza + 0.95);

  // Los momentos del grafo (segundos de la demo), atados a las palabras de la voz donde importa.
  const K = {
    monto: nieto(12.4),                       // «$650.000» sale de la llamada hacia el agente (grafo en chico)
    cuenta: E.cuenta + 4.1,                   // «48-2210-7735» sale de la llamada
    sale: palabra("sin", 5),                  // «…y paga»: el pago sale del agente
    enPagar: E.sin + 0.1,                     // sin compuerta, llega a «Pagar»
    enBanco: palabra("sin", 9),               // «la plata se va»: los $650.000 llegan al banco del estafador
    rebobina: NARR.sin.en + NARR.sin.dur + 0.1,
    sale2: E.frena + 0.2,                     // con Grifter: el mismo paquete sale otra vez
    choque1: palabra("retiene", 2),           // «…lo frena»: primer bloqueo
    rastro: palabra("retiene", 4),            // «la cuenta salió de una llamada»: el rastro vuelve hasta la fuente
    legit: E.pasa + 0.1,                      // lo de Marta: de Marta al agente
    legitAgente: E.pasa + 0.8,                // del agente a «Pagar», cruzando la compuerta
    legitPagar: E.pasa + 1.7,
    aviso: E.alerta + 0.05,                   // Grifter le avisa a Marta
    insiste: palabra("insiste", 2),           // «Pagar igual» viaja de Marta a la compuerta
    dos: palabra("insiste", 5),               // «dos aprobaciones»: los dos cupos y Pablo
    codigo0: palabra("aprueban", 0) + 0.1,    // el código de Marta sale
    codigo1: palabra("aprueban", 4),          // «…código»: 1 de 2
    mensaje: palabra("aprueban", 8),          // «…recibe un mensaje»: el pedido viaja de la compuerta a Pablo
    rechaza0: TOQUE_PABLO + 0.3,              // «Rechazar» sale de Pablo
    rechaza1: TOQUE_PABLO + 0.75,             // la compuerta se cierra: no se pagó nada
    pide: palabra("banco", 2),                // el correo pide el código
    envia: E.responde + 0.15,                 // el agente manda «482 913» por «Responder»
    choque2: E.clave + 0.05,                  // segundo bloqueo
    aprobado: palabra("tienda", 1) - 0.2,     // «$412.000» aprobado por Marta
    cobro: E.cobra + 0.05,                    // la tienda cobra «$4.120.000»
    paga3: E.cobra + 1.25,                    // el agente lo manda a «Pagar»
    choque3: E.calza + 0.1,                   // tercer bloqueo
  };
  const BLOQUEOS = [K.choque1, K.choque2, K.choque3];
  // Cuándo «actúa» el agente (su nube pulsa en ámbar).
  const HABLA_AGENTE = [[E.encargo + 0.6, E.encargo + 1.7], [E.paga + 0.2, K.enPagar], [K.sale2 - 0.1, K.choque1], [E.responde, K.choque2], [K.cobro + 0.8, K.choque3]];
  // El borde rojo de alerta: mientras la plata se va (sin Grifter) y desde que Marta insiste hasta que Pablo rechaza.
  const ALARMAS = [[K.enPagar, K.rebobina], [K.insiste + 0.8, K.rechaza1]];
  // La frase final, en dos líneas (su voz es NARR.remate: si cambia el texto, hay que regenerar ese mp3).
  const FRASE_FINAL = ["Tu agente puede creerle a cualquiera.", "Tu plata, no."];
  const dentro = (tt, tramos) => tramos.some(([a, b]) => tt >= a && tt < b);

  // --- Piezas: cada una se registra con su tiempo y render(t) la dibuja ---
  const ESCRIBE = [], CUENTAS = [], DEDOS = [];
  // Aparece desde v (y hasta h) con un movimiento: pop, sube, cae, izq, der, golpe, raya o nada.
  const ap = (v, an = "sube", h = null) => ` data-v="${v}"${h === null ? "" : ` data-h="${h}"`} data-an="${an}"`;
  // [[así]] marca en rojo lo que salió de afuera (la cuenta, el monto); {{así}}, en verde lo que Grifter resolvió.
  const segmentos = (s) => s.split(/(\[\[.+?\]\]|\{\{.+?\}\})/).filter(Boolean).map((p) => (p.startsWith("[[") ? { txt: p.slice(2, -2), cls: "gf-origen" } : p.startsWith("{{") ? { txt: p.slice(2, -2), cls: "gf-verde" } : { txt: p, cls: "" }));
  // Texto que se escribe letra por letra: al ritmo de las palabras de la voz (pal) o a cps letras por segundo.
  // Con desdePalabra(...) como opciones, su t0 manda sobre el segundo argumento. El texto entero está en el DOM desde
  // el principio, una letra por <span>, y render solo cambia cuáles se ven: el layout no cambia mientras se escribe
  // (ninguna palabra salta de línea).
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

  // El cuerpo del agente: una constelación de partículas en una esfera que gira. En el grafo es el nodo del centro.
  //   grande 360 px (escenas del principio) · mini 72 px (encabezado del chat)
  const agente = (cls = "grande") => cls === "mini"
    ? `<canvas class="dn-nube mini" width="144" height="144" aria-hidden="true"></canvas>`
    : `<span class="dn-nube ${cls}" data-ancla="nube" aria-hidden="true"></span>`;
  // Retratos ficticios generados con IA (los de la versión A). Si falta el .jpg, el .svg ilustrado.
  // Con `borrosa`, la foto va desenfocada (--desenfoque, que render baja a 0 desde que Marta dice «Tomás»), sin salirse del círculo.
  const fotoNieto = (cls = "", borrosa = false) => `<div class="dn-foto ${cls}${borrosa ? " gf-borrosa" : ""}"><i class="dn-anillo"></i><i class="dn-anillo"></i><span class="gf-recorte"><img src="img/nieto.jpg" onerror="this.onerror=null;this.src='img/nieto.svg'" alt="" width="400" height="400"></span></div>`;
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

    // 2. El cuento del tío (igual que en la versión B; el grafo espera en chico, abajo a la izquierda)
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
          ${fotoNieto("dn-xl dn-llama", true)}
          <p class="dn-quien-llama"${ap(E.suena + 0.1, "sube")}>Desconocido</p>
          <p class="dn-sub"${ap(E.suena + 0.2, "sube")}>Número privado</p>
          <div class="dn-ll-botones"${ap(E.suena + 0.25, "sube")}>
            <span class="dn-ll-b colgar">${ic("call_end")}</span>
            <span class="dn-ll-b contestar">${ic("call")}${dedo(LL.contesta - 0.4, -260, 180)}</span>
          </div>
        </div>`, "dn-centro");
    esc_("contesta", `
        ${reloj()}
        <div class="dn-habla">
          <div class="dn-habla-foto">${fotoMarta("dn-l")}${barras("marta")}<p class="dn-nombre">Marta</p></div>
          <h1 class="dn-titular dn-izq">${escribe("¿Aló? ¿Quién habla?", LL.abuela + 0.05, { cps: 15 })}</h1>
        </div>`);
    // Hasta que Marta dice «Tomás», el que llama es «Desconocido» y su foto va desenfocada: él nunca dijo quién era.
    const habla = (texto, t0, cps, cls = "", desconocido = false) => `
        ${reloj()}
        <div class="dn-habla ${cls}">
          <div class="dn-habla-foto">${fotoNieto("dn-l", desconocido)}${barras("nieto")}<p class="dn-nombre">${desconocido ? "Desconocido" : "Tomás (nieto)"}<span>Número privado</span></p></div>
          <h1 class="dn-titular dn-izq">${escribe(texto, t0, { cps })}</h1>
        </div>`;
    esc_("n1", habla("Abuelita, soy yo po, tu nieto.", frase(0) + 0.1, 13, "", true));
    // Marta le pone nombre: desde que dice «Tomás», la foto se aclara en 1,8 s y «Desconocido» pasa a «Tomás (nieto)»
    // con un fundido de 1,2 s (render fija --desenfoque, --nombre-a y --nombre-b).
    esc_("tomas", `
        ${reloj()}
        <div class="gf-reconoce">
          <div class="dn-habla-foto">${fotoMarta("dn-l")}${barras("marta")}<p class="dn-nombre">Marta</p></div>
          <h1 class="dn-titular">${escribe("¿Tomás?", LL.abuela2 + 0.12, { cps: 16 })}<span class="gf-linea-2">${escribe("¿Qué te pasó, mijo?", LL.abuela2 + 1.25, { cps: 14 })}</span></h1>
          <div class="dn-habla-foto">${fotoNieto("dn-l", true)}${barras("nieto")}<p class="dn-nombre gf-quien"><b>Desconocido</b><b>Tomás (nieto)</b><span>Número privado</span></p></div>
        </div>`);
    // El nieto sigue donde lo interrumpieron, ya con nombre: esta frase queda pegada a «Choqué el auto…».
    esc_("n1b", habla("No le digai a nadie, por favor.", nieto(2.85), 22));
    esc_("n2", `
        ${reloj()}
        <div class="dn-mini-quien"${ap(frase(1), "izq")}>${fotoNieto("dn-s")}${barras("nieto")}<p>Tomás (nieto)</p></div>
        <h1 class="dn-titular dn-enorme">${escribe("Choqué el auto y me tienen detenido.", frase(1) + 0.05, { cps: 21 })}</h1>`, "dn-centro");
    esc_("n3", habla("El carabinero dice que si pago la fianza ahora me sueltan altiro.", frase(2) + 0.05, 17.5, "dn-al-reves"));
    // «Son seiscientas cincuenta lucas, abuelita»: en el mp3 del nieto, «Son» va en 10,4 s, el número de 10,65 a 11,65 y
    // «abuelita» desde 12,0 (medido con la envolvente del audio). El contador dura 0,6 s y termina con «cincuenta».
    const S2 = E.fianza;
    esc_("fianza", `
        ${reloj()}
        <p class="dn-etiqueta"${ap(S2 + 0.05, "cae")}>«Son…</p>
        <p class="dn-monto dn-rojo"${ap(nieto(11.05) - 0.05, "nada")}>${cuenta(0, 650000, nieto(11.05), 0.6, { pesos: true })}</p>
        <p class="dn-etiqueta"${ap(nieto(12.0), "sube")}>…abuelita»</p>
        <span class="dn-tag rojo"${ap(nieto(12.3), "pop")}>${ic("call")}Dictado en la llamada</span>`, "dn-centro");
    esc_("n4", habla("Anota la cuenta del abogado:", frase(3) + 0.05, 16, "dn-una-linea"));
    const S3 = E.cuenta;
    esc_("cuenta", `
        ${reloj()}
        <p class="dn-etiqueta"${ap(S3 + 0.2, "cae")}>Banco Austral · cuenta vista</p>
        <p class="dn-monto dn-rojo dato">${escribe("48-2210-7735", S3 + 0.7, { cps: 3.8 })}</p>
        <span class="dn-tag rojo"${ap(S3 + 4.0, "pop")}>${ic("call")}Dictada por un número privado</span>`, "dn-centro");
    esc_("n5", `
        ${reloj()}
        <div class="dn-pila-centro">
          ${fotoNieto("dn-m")}${barras("nieto")}
          <h1 class="dn-titular">${escribe("Hazlo rápido, por favor, no me cortí.", frase(4) + 0.1, { cps: 14 })}</h1>
          <span class="dn-tag rojo"${ap(LL.cuelga, "pop")}>${ic("call_end")}Llamada finalizada · ${DUR_LLAMADA}</span>
        </div>`, "dn-centro");

    // 3. El grafo a pantalla completa. Las capas del DOM solo llevan los rótulos: arriba a la izquierda el contexto,
    // abajo la frase que dice la voz, y junto a la compuerta su estado. El grafo se dibuja en el canvas.
    const pie = (contenido, attr = "", cls = "") => `<p class="gf-pie ${cls}"${attr}>${contenido}</p>`;
    const bajoPuerta = (...lineas) => `<div class="gf-bajo-puerta">${lineas.join("")}</div>`;
    const tachado = (txt, v, h = null) => `<p class="dn-tachado dato"${ap(v, "sube", h)}><span>${txt}</span><i${ap(v + 0.25, "raya")}></i></p>`;
    const modo = (v = 0) => `<p class="dn-modo con gf-modo"${ap(v, v ? "cae" : "nada")}>Con Grifter</p>`;
    esc_("paga", `
        <p class="dn-rotulo gf-rotulo"${ap(E.paga + 0.3, "cae")}>${ic("call_end")}Llamada finalizada · ${DUR_LLAMADA}</p>
        ${pie(escribe("El agente le cree y paga.", 0, desdePalabra("sin", 0)))}`, "gf-capa");
    esc_("sin", `
        <p class="dn-modo sin gf-modo"${ap(E.sin + 0.02, "cae")}>Sin Grifter</p>
        ${pie(escribe("Sin Grifter, [[la plata se va.]]", 0, desdePalabra("sin", 6)), ap(0, "nada", K.rebobina - 0.15))}
        <p class="gf-nota gf-pagado gf-origen dato"${ap(K.enBanco + 0.15, "sube", K.rebobina - 0.15)}>Pagado a J. Contreras V.</p>
        ${pie(`<svg class="dn-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 6v12L2.5 12 11 6Zm10.5 0v12L13 12l8.5-6Z"/></svg><span>Rebobinamos: con Grifter</span>`, ap(K.rebobina, "pop"), "gf-rebobina")}`, "gf-capa");
    esc_("frena", `
        ${modo(E.frena + 0.02)}
        ${pie("Pago retenido", ap(K.choque1, "pop"), "gf-grande")}
        ${bajoPuerta(tachado("$650.000 → 48-2210-7735", K.choque1 + 0.25))}`, "gf-capa");
    esc_("motivo", `
        ${modo()}
        ${pie(escribe("La cuenta salió de [[una llamada]], no de tu encargo.", 0, desdePalabra("retiene", 3)))}
        ${bajoPuerta(`<p class="dn-tachado dato"><span>$650.000 → 48-2210-7735</span><i></i></p>`)}
        <p class="gf-nota gf-salio gf-origen"${ap(K.rastro + 0.9, "izq")}>De aquí salió la cuenta</p>`, "gf-capa");
    esc_("pasa", `
        ${modo()}
        ${pie(escribe("Lo que viene de Marta, {{pasa.}}", 0, desdePalabra("pasa", 0)))}`, "gf-capa");

    // 4. Pagar igual: doble aprobación. El panel chico junto a Pablo es su chat con Grifter (el toque va en «Rechazar»).
    const panel = (conDedo) => `
        <div class="gf-panel"${ap(K.dos + 0.5, "sube")}>
          <p class="gf-panel-de"><span>Grifter · WhatsApp a Pablo</span><span class="gf-panel-vivo"></span></p>
          <p class="gf-panel-msg">Marta quiere pagar <b class="dato">$650.000</b> a J. Contreras V.</p>
          <div class="gf-panel-botones">
            <span class="dn-b">Solicitar código</span>
            <span class="dn-b rechazar">Rechazar${conDedo ? dedo(TOQUE_PABLO, 120, 200) : ""}</span>
          </div>
        </div>`;
    const cupos = (txt, v, h = null, cls = "") => `<p class="gf-estado-puerta dato ${cls}"${ap(v, v ? "pop" : "nada", h)}>${txt}</p>`;
    esc_("alerta", `
        ${modo()}
        ${pie(escribe("Marta insiste. «Pagar igual» exige dos aprobaciones.", 0, desdePalabra("insiste", 0)))}
        ${cupos("0 de 2", K.dos)}
        ${panel(false)}`, "gf-capa");
    esc_("codigo", `
        ${modo()}
        ${pie(escribe("Ella aprueba con su código.", 0, desdePalabra("aprueban", 0)))}
        ${cupos("0 de 2", 0, K.codigo1 - 0.15)}${cupos("1 de 2", K.codigo1, null, "gf-verde")}
        ${panel(false)}`, "gf-capa");
    esc_("pablo", `
        ${modo()}
        ${pie(escribe("Pablo, su hijo, recibe un mensaje.", 0, desdePalabra("aprueban", 5)))}
        ${cupos("1 de 2", 0, null, "gf-verde")}
        ${panel(false)}`, "gf-capa");
    // En vivo, la demo espera justo antes de esta escena a que Pablo toque «Rechazar» en su WhatsApp.
    esc_("rechaza", `
        ${modo()}
        ${pie(escribe("Y él rechaza. {{No se pagó nada.}}", 0, desdePalabra("rechaza", 0)))}
        ${cupos("1 de 2", 0, K.rechaza1 - 0.15, "gf-verde")}${cupos("Cerrada", K.rechaza1, null, "gf-verde")}
        ${panel(true)}`, "gf-capa");

    // 5. Dos estafas más, sobre el mismo grafo: cambia la fuente de afuera y el paquete vuelve a chocar
    const S9 = E.banco;
    esc_("banco", `
        <p class="dn-rotulo gf-rotulo"${ap(S9 + 0.05, "cae")}>Otra estafa: el falso Banco Cordillera</p>
        ${pie(escribe("Un falso banco pide tu código.", 0, desdePalabra("banco", 0)))}`, "gf-capa");
    esc_("responde", `
        <p class="dn-rotulo gf-rotulo">Otra estafa: el falso Banco Cordillera</p>
        ${pie("Un falso banco pide tu código.")}`, "gf-capa");
    const S11 = E.clave;
    esc_("clave", `
        <p class="dn-rotulo gf-rotulo">Otra estafa: el falso Banco Cordillera</p>
        ${pie(escribe("Tu clave no sale sin tu confirmación.", 0, desdePalabra("clave", 0)))}
        ${bajoPuerta(tachado("482 913 · no se envió", S11 + 1.1))}`, "gf-capa");
    const S12 = E.aprobaste;
    esc_("aprobaste", `
        <p class="dn-rotulo gf-rotulo"${ap(S12 + 0.05, "cae")}>Otra estafa: Componentes Volcán cobra de más</p>
        ${pie(escribe("Aprobaste $412.000.", 0, desdePalabra("tienda", 0)))}`, "gf-capa");
    esc_("cobra", `
        <p class="dn-rotulo gf-rotulo">Otra estafa: Componentes Volcán cobra de más</p>
        ${pie(`Aprobaste $412.000. ${escribe("[[Te cobran 10 veces más.]]", 0, desdePalabra("tienda", 4))}`)}`, "gf-capa");
    const S14 = E.calza;
    esc_("calza", `
        <p class="dn-rotulo gf-rotulo">Otra estafa: Componentes Volcán cobra de más</p>
        ${pie(escribe("No calza con lo que aprobaste.", 0, desdePalabra("calza", 0)))}
        ${bajoPuerta(tachado("$4.120.000 · no se pagó", S14 + 0.75))}`, "gf-capa");

    // 6. Medición (docs/cifras.md: 150 estafas de 32 tipos, 0 pasan Grifter completo; 5.280 intentos, 0 cruzan la capa 2)
    const S15 = E.estafas, S17 = E.atacante;
    const fila = (num, txt, sub, vNum, vTxt, cls = "") => `
          <p class="gf-num ${cls}"${vNum === null ? "" : ap(vNum, "pop")}>${num}</p>
          <p class="gf-num-txt"${vTxt === null ? "" : ap(vTxt, "pop")}>${txt}</p>
          <p class="gf-num-sub"${vTxt === null ? "" : ap(vTxt + 0.2, "nada")}>${sub}</p>`;
    esc_("estafas", `
        <p class="dn-rotulo gf-rotulo"${ap(S15 + 0.1, "cae")}>La medición: un agente que hace todo lo que lee</p>
        <div class="gf-cifras">${fila(cuenta(0, 150, S15 + 0.5, 0.9), "Estafas", `De ${cuenta(0, 32, palabra("estafas", 2) + 0.2, 0.5)} tipos de ataque`, S15 + 0.45, palabra("estafas", 2))}</div>
        <p class="dn-fuente dato gf-fuente"${ap(S15 + 1.2, "nada")}>Agente que hace todo lo que lee · grifter bench · docs/cifras.md</p>`, "gf-capa");
    esc_("pasan", `
        <p class="dn-rotulo gf-rotulo">La medición: un agente que hace todo lo que lee</p>
        <div class="gf-cifras">${fila("150", "Estafas", "De 32 tipos de ataque", null, null)}${fila("0", "Pasan", "Con Grifter completo", palabra("estafas", 4), palabra("estafas", 3), "gf-verde")}</div>
        <p class="dn-fuente dato gf-fuente">150 de 150 frenadas · capas 2 y 3 · grifter bench · docs/cifras.md</p>`, "gf-capa");
    esc_("atacante", `
        <p class="dn-rotulo gf-rotulo"${ap(S17 + 0.1, "cae")}>El duelo: un atacante que reescribe la estafa</p>
        <div class="gf-cifras">${fila(cuenta(0, 5280, S17 + 0.15, 1.6), "Intentos", "De un atacante que aprende", S17 + 0.1, palabra("atacante", 4))}</div>
        <p class="dn-fuente dato gf-fuente"${ap(S17 + 1.2, "nada")}>120 generaciones · 6 corridas · grifter duelo · docs/cifras.md</p>`, "gf-capa");
    esc_("cruzan", `
        <p class="dn-rotulo gf-rotulo">El duelo: un atacante que reescribe la estafa</p>
        <div class="gf-cifras">${fila("5.280", "Intentos", "De un atacante que aprende", null, null)}${fila("0", "Cruzan", "La capa 2", palabra("atacante", 10), palabra("atacante", 11), "gf-verde")}</div>
        <p class="dn-fuente dato gf-fuente">5.280 intentos contra la capa 2 · grifter duelo · docs/cifras.md</p>`, "gf-capa");

    // 7. Cierre: la frase final con la voz; las partículas arman la marca, la marca nítida la reemplaza con un fundido
    // cruzado de 0,2 s (nunca hay dos marcas a la vista) y «Grifter» cae letra por letra
    esc_("remate", `
        <h1 class="dn-titular dn-frase-final">${escribe(FRASE_FINAL[0], 0, desdePalabra("remate", 0))}<span class="dn-remate-2">${escribe(FRASE_FINAL[1], 0, desdePalabra("remate", FRASE_FINAL[0].split(" ").length))}</span></h1>`, "dn-centro");
    esc_("cierre", `
        <div class="dn-logo">
          <img class="dn-marca-img dn-marca-cierre" src="img/marca.png" alt="" width="160" height="196" data-ancla="logo">
          <span class="dn-logo-txt">${[..."Grifter"].map((c, i) => `<span${ap(palabra("cierre", 0) - 0.05 + i * 0.07, "cae")}>${c}</span>`).join("")}</span>
        </div>
        <p class="dn-lema">${escribe("Escudo para agentes que pagan", 0, desdePalabra("cierre", 1))}</p>
        <p class="dn-url dato"${ap(E.cierre + 2.4, "sube")}>grifter.onrender.com</p>
        <p class="dn-aviso"${ap(E.cierre + 2.7, "nada")}>Personas y marcas ficticias · voces sintéticas</p>`, "dn-centro");

    h.push(`<i id="gf-cursor" aria-hidden="true"></i><p class="gf-hud" id="gf-hud" aria-hidden="true"><span>Bloqueos</span><b class="dato" id="gf-bloqueos">0</b></p>
      <div class="dn-progreso" aria-hidden="true"><i id="dn-barra"></i></div>
      <div class="dn-portada" aria-hidden="true">
        <p class="dn-evento dato">Platanus Hack 26 · AI Security · Equipo 40</p>
        <div class="dn-logo dn-logo-portada"><img class="dn-marca-img" src="img/marca.png" alt="" width="200" height="244"><span>Grifter</span></div>
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
  const suave = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  const mezcla = (a, b, x) => a.map((v, i) => Math.round(v + (b[i] - v) * x));
  // Cuánto actúa el agente (fundido de 0,3 s en cada borde) y su pulso: un golpe cada 0,26 s.
  const pesoHabla = (tt) => Math.max(0, ...HABLA_AGENTE.map(([a, b]) => suave((tt - a) / 0.3) * (1 - suave((tt - b) / 0.3))));
  const pulsoHabla = (tt) => { const ph = (((tt % 0.26) + 0.26) % 0.26); return 0.25 + 0.75 * Math.exp(-ph / 0.12) * (0.7 + 0.3 * Math.abs(Math.sin(tt * 3.1))); };
  // La nube chica del encabezado del chat (un canvas propio de 72 px).
  function dibujarNube(cv, tt) {
    if (!RGB.texto) colores();
    const g = cv.getContext("2d"), k = cv.width / 720;
    g.setTransform(k, 0, 0, k, 0, 0);
    g.clearRect(0, 0, 720, 720);
    const habla = quieto ? +(pesoHabla(tt) > 0.5) : pesoHabla(tt), env = quieto ? 0.5 : pulsoHabla(tt);
    const giro = quieto ? 0.6 : tt * 0.45, cg = Math.cos(giro), sg = Math.sin(giro), tinte = mezcla(RGB.texto, RGB.ambar, habla);
    const pts = ESFERA.map((p) => {
      const x = p.x * cg + p.z * sg, z = -p.x * sg + p.z * cg;
      const pulso = 1 + (quieto ? 0 : 0.02 * Math.sin(tt * 1.6 + p.f)) + env * habla * (0.08 + 0.16 * Math.abs(Math.sin(tt * 9 + p.f)));
      return { x: 360 + x * 300 * pulso, y: 360 + p.y * 300 * pulso, z };
    }).sort((a, b) => a.z - b.z);
    for (const p of pts) {
      const prof = (p.z + 1) / 2;
      g.beginPath();
      g.arc(p.x, p.y, (3 + 5 * prof) * 2.4, 0, 2 * Math.PI);
      g.fillStyle = `rgba(${tinte[0]},${tinte[1]},${tinte[2]},${(0.25 + 0.75 * prof).toFixed(3)})`;
      g.fill();
    }
  }

  // --- Motor de partículas: un solo canvas detrás de las escenas ---
  // Las mismas NM partículas pasan de figura en figura (dispersas → la esfera del agente → el escudo y la marca del
  // cierre). Desde que suena el teléfono, la esfera es el nodo del agente en el grafo, que se dibuja en este mismo
  // canvas: aristas y nodos por detrás de la esfera, paquetes y destellos por delante. Todo es función de t.
  const NM = 400, NF = 90;   // partículas de la nube y del fondo
  const azarM = semilla(7);
  const ESF_M = Array.from({ length: NM }, (_, i) => { const y = 1 - (2 * (i + 0.5)) / NM, r = Math.sqrt(1 - y * y), a = i * 2.39996; return { x: Math.cos(a) * r, y, z: Math.sin(a) * r, f: azarM() * 6.283 }; });
  const RAND_M = Array.from({ length: NM }, () => ({ x: azarM() * 1920, y: azarM() * 1080, retraso: azarM() * 0.25, dx: azarM() * 2 - 1, dy: azarM() * 2 - 1 }));
  const FONDO = Array.from({ length: NF }, () => ({ x: azarM() * 1920, y: azarM() * 1080, vx: (azarM() - 0.5) * 14, vy: (azarM() - 0.5) * 10, s: 1 + azarM() * 1.5, f: azarM() * 6.283 }));
  const FRAG = Array.from({ length: 18 }, () => ({ dx: azarM() * 1.2 - 1.05, dy: azarM() * 2 - 1, s: azarM() }));
  const RGB = {};
  function colores() {
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    for (const k of ["fondo", "superficie", "borde", "texto", "texto-2", "texto-3", "ambar", "verde", "rojo"]) RGB[k] = hex(css("--" + k));
  }

  // Dónde está cada ancla (data-ancla) de cada escena, en coordenadas del escenario. Se mide una vez (y al cargar la
  // letra), mostrando cada escena oculta y sin sus movimientos de entrada.
  let ANCLAS = {};
  function medir() {
    const marco = $("#dn-escenario"), base = marco.getBoundingClientRect(), k = base.width / 1920;
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

  // La marca (img/marca.png, el logo de MR): puntos sacados del canal alfa del PNG, blancos donde el píxel es blanco y
  // verdes donde es verde. Mientras la imagen no carga, el contorno del escudo simple.
  const MUESTRAS = new Map();
  function elegir(pts, n, clave) {
    const az = semilla(clave.length * 131 + 17), orden = pts.map((p, i) => [az(), i]).sort((a, b) => a[0] - b[0]);
    return Array.from({ length: n }, (_, i) => pts[orden[i % orden.length][1]]);
  }
  let IMG_MARCA = null;
  const imgMarca = new Image();
  imgMarca.onload = () => { IMG_MARCA = imgMarca; MUESTRAS.clear(); if (listo) render(tiempo); };
  imgMarca.src = "img/marca.png";
  function puntosLogo(a, n) {
    const clave = `l|${n}|${Math.round(a.x)}|${Math.round(a.w)}|${IMG_MARCA ? 1 : 0}`;
    if (!MUESTRAS.has(clave)) {
      if (!IMG_MARCA) {
        MUESTRAS.set(clave, ESCUDO_M().map((q) => ({ x: a.x + q.x * a.w * 0.6, y: a.y + q.y * a.w * 0.6, color: "texto" })));
      } else {
        const c = document.createElement("canvas");
        c.width = Math.max(1, Math.round(a.w)); c.height = Math.max(1, Math.round(a.h));
        const g = c.getContext("2d");
        g.drawImage(IMG_MARCA, 0, 0, c.width, c.height);
        const d = g.getImageData(0, 0, c.width, c.height).data, pts = [];
        for (let y = 0; y < c.height; y += 3) for (let x = 0; x < c.width; x += 3) {
          const k = (y * c.width + x) * 4;
          if (d[k + 3] > 140) pts.push({ x: a.x - a.w / 2 + x, y: a.y - a.h / 2 + y, color: d[k] > 160 ? "texto" : "verde" });
        }
        MUESTRAS.set(clave, pts.length ? elegir(pts, n, clave) : [{ x: a.x, y: a.y, color: "texto" }]);
      }
    }
    return MUESTRAS.get(clave);
  }

  // --- Las figuras. Cada una da, para cada partícula, posición, color, opacidad y tamaño en el segundo tt ---
  const figEsfera = (centro, { habla = false, rel = 0.37 } = {}) => (tt) => {
    const c = typeof centro === "function" ? centro(tt) : centro, R = c.R ?? c.w * rel;
    const peso = habla ? (quieto ? +(pesoHabla(tt) > 0.5) : pesoHabla(tt)) : 0, env = quieto ? 0.5 : pulsoHabla(tt);
    const giro = quieto ? 0.6 : tt * 0.45, cg = Math.cos(giro), sg = Math.sin(giro);
    const color = mezcla(RGB.texto, RGB.ambar, peso), esc = Math.max(0.5, R / 135);
    return { centro: { x: c.x, y: c.y, R }, p: ESF_M.map((q) => {
      const x = q.x * cg + q.z * sg, z = -q.x * sg + q.z * cg, prof = (z + 1) / 2;
      const pulso = 1 + (quieto ? 0 : 0.02 * Math.sin(tt * 1.6 + q.f)) + env * peso * (0.06 + 0.12 * Math.abs(Math.sin(tt * 9 + q.f)));
      return { x: c.x + x * R * pulso, y: c.y + q.y * R * pulso, c: color, a: 0.25 + 0.75 * prof, s: (1.2 + 2.6 * prof) * esc };
    }) };
  };
  const figEscudo = (centro, rel = 0.37) => (tt) => {
    const c = typeof centro === "function" ? centro(tt) : centro, R = c.R ?? c.w * rel, esc = R / 135;
    return { centro: { x: c.x, y: c.y, R }, p: ESCUDO_M().map((q, i) => ({
      x: c.x + q.x * R * 0.95, y: c.y + q.y * R * 0.95 + (quieto ? 0 : Math.sin(tt * 2 + i) * 0.6), c: RGB.verde, a: 0.95, s: 2.2 * esc + 0.6,
    })) };
  };
  let ESC_CACHE = null;
  function ESCUDO_M() {   // el contorno del escudo, centrado, en unidades de 62 px de su caja de 120×140
    if (!ESC_CACHE) {
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", ESCUDO_D);
      const largo = p.getTotalLength();
      ESC_CACHE = Array.from({ length: NM }, (_, i) => { const q = p.getPointAtLength((i / NM) * largo); return { x: (q.x - 60) / 62, y: (q.y - 70) / 62 }; });
    }
    return ESC_CACHE;
  }
  // Antes del agente, la nube está dispersa y tenue (parte del fondo) y se junta en la esfera cuando él aparece.
  const figDispersa = (tt) => ({ centro: { x: 960, y: 540, R: 300 }, p: RAND_M.map((r, i) => ({
    x: r.x + (quieto ? 0 : Math.sin(tt * 0.4 + i) * 12), y: r.y + (quieto ? 0 : Math.cos(tt * 0.3 + i) * 9), c: RGB["texto-3"], a: 0.14, s: 1.4,
  })) });
  const figLogo = (tt) => {
    const a = ancla("cierre", "logo"), pts = puntosLogo(a, NM), tenue = quieto ? +(tt < MARCA_NITIDA) * 0.95 : 0.95 * (1 - clamp((tt - MARCA_NITIDA) / 0.2));
    return { centro: { x: a.x, y: a.y, R: a.w / 2 }, p: pts.map((q) => ({ x: q.x, y: q.y, c: RGB[q.color], a: tenue, s: 2.6 })) };
  };
  const ARRIBA = { x: 960, y: 190, R: 72 };
  const nube = (id) => () => ancla(id, "nube");

  // ---------- El grafo ----------
  const TAU = Math.PI * 2;
  // Avances de 0 a 1 desde t0: con movimiento reducido son un escalón (la cosa aparece ya en su estado final).
  const tr = (tt, t0, dur = 0.4) => (quieto ? +(tt >= t0) : vaiven(clamp((tt - t0) / dur)));
  const sl = (tt, t0, dur = 0.4) => (quieto ? +(tt >= t0) : salida(clamp((tt - t0) / dur)));
  const lin = (tt, t0, t1) => (quieto ? +(tt >= t0) : clamp((tt - t0) / (t1 - t0)));
  const mix = (a, b, x) => a + (b - a) * x;
  const frac = (x) => x - Math.floor(x);
  const bez = (p, u) => { const v = 1 - u, a = v * v * v, b = 3 * v * v * u, c = 3 * v * u * u, d = u * u * u; return { x: a * p[0].x + b * p[1].x + c * p[2].x + d * p[3].x, y: a * p[0].y + b * p[1].y + c * p[2].y + d * p[3].y }; };
  // Una arista de centro a centro, con tangentes horizontales en los dos extremos.
  const curvaH = (a, b) => { const dx = (b.x - a.x) / 2; return [{ x: a.x, y: a.y }, { x: a.x + dx, y: a.y }, { x: b.x - dx, y: b.y }, { x: b.x, y: b.y }]; };
  // El parámetro de la curva donde su x vale x (las aristas horizontales avanzan siempre hacia la derecha).
  function uEnX(p, x) { let a = 0, b = 1; for (let i = 0; i < 18; i++) { const m = (a + b) / 2; if (bez(p, m).x < x) a = m; else b = m; } return (a + b) / 2; }
  let BASE = 1;   // la opacidad de todo el grafo (entra con la llamada y se va con el cierre)
  const c = (k, a = 1) => { const v = Array.isArray(k) ? k : RGB[k]; return `rgba(${v[0]},${v[1]},${v[2]},${(a * BASE).toFixed(3)})`; };
  const letra = (peso, px) => `${peso} ${px}px "IBM Plex Mono", ui-monospace, monospace`;

  // Las tres disposiciones: en chico durante la llamada (abajo a la izquierda), la principal y la medición (alejada).
  const D = {
    mini: { ag: { x: 470, y: 930, r: 44 }, ext: { x: 150, y: 930, r: 36 } },
    ag: { x: 690, y: 450, r: 100 }, ext: { x: 220, y: 600, r: 56 }, marta: { x: 220, y: 300, r: 56 },
    pagar: { x: 1440, y: 340, r: 56 }, resp: { x: 1440, y: 560, r: 56 }, banco: { x: 1752, y: 340, r: 56 },
    pablo: { x: 890, y: 820, r: 56 }, puerta: { x: 1100, y0: 265, y1: 635 },
    med: { ag: { x: 800, y: 520, r: 56 }, puerta: { y0: 190, y1: 850 }, atacante: { x: 330, y: 520, r: 68 } },
  };
  const PX = D.puerta.x;
  // Las dos aristas de los aprobadores: de Marta a la compuerta por arriba y de Pablo por abajo.
  const E6 = [{ x: 266, y: 268 }, { x: 520, y: 172 }, { x: 900, y: 182 }, { x: PX, y: 253 }];
  const E7 = [{ x: 952, y: 820 }, { x: PX, y: 820 }, { x: PX, y: 750 }, { x: PX, y: 649 }];
  function geo(tt) {
    const m = tr(tt, E.paga, 0.8), z = tr(tt, E.estafas, 0.8), p = (a, b, x) => ({ x: mix(a.x, b.x, x), y: mix(a.y, b.y, x), r: mix(a.r, b.r, x) });
    const fuera = tr(tt, E.estafas, 0.35);   // lo que solo existe en la disposición principal se va antes de que entren las cifras
    return { m, z, fuera, pr: m * (1 - fuera), ag: p(p(D.mini.ag, D.ag, m), D.med.ag, z), ext: p(D.mini.ext, D.ext, m),
      puerta: { x: PX, y0: mix(D.puerta.y0, D.med.puerta.y0, z), y1: mix(D.puerta.y1, D.med.puerta.y1, z) } };
  }
  const centroAgente = (tt) => { const G = geo(tt); return { x: G.ag.x, y: G.ag.y, R: G.ag.r * 0.9 }; };
  // Las fuentes de afuera: ocupan el mismo lugar, de a una, y se ponen rojas cuando traen la estafa.
  const FUENTES = [
    { icono: "call", nombre: "Llamada", sub: "Número privado", entra: E.suena + 0.3, sale: E.banco, mancha: K.monto, arista: LL.contesta },
    { icono: "mail", nombre: "Correo", sub: "bancocordillera-alertas.cl", entra: E.banco + 0.25, sale: E.aprobaste, mancha: K.pide, arista: E.banco + 0.4 },
    { icono: "shopping_cart", nombre: "Tienda", sub: "Componentes Volcán", entra: E.aprobaste + 0.25, sale: E.estafas, mancha: K.cobro, arista: E.aprobaste + 0.4 },
  ];
  const FOTOS = {};
  for (const [k, src] of [["marta", "img/abuela.jpg"], ["pablo", "img/pablo.jpg"]]) { const im = new Image(); im.onload = () => { if (listo) render(tiempo); }; im.src = src; FOTOS[k] = im; }
  // Medición: los 150 ataques en sus 32 tipos (demo/resultados.json, cobertura.familias[].ataques; suman 150).
  const RACIMOS = [12, 12, 12, 10, 10, 10, 8, 8, 8, 6, 4, 4, 4, 4, 4, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2];
  const RAC = (() => {
    const az = semilla(150), celdas = RACIMOS.map((_, i) => [az(), i]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);
    const r = RACIMOS.map((n, i) => ({ n, x: 150 + (celdas[i] % 4) * 152 + (az() - 0.5) * 44, y: 236 + Math.floor(celdas[i] / 4) * 82 + (az() - 0.5) * 22 }));
    [...r].sort((a, b) => a.y - b.y).forEach((q, k) => { q.yp = 214 + k * (612 / 31); });   // su lugar en la compuerta, sin cruces
    let j = 0;
    for (const q of r) q.pts = Array.from({ length: q.n }, (_, i) => { const rad = 10.5 * Math.sqrt(i + 0.5), a = i * 2.39996; return { x: q.x + Math.cos(a) * rad, y: q.y + Math.sin(a) * rad, j: j++ }; });
    return r;
  })();
  const OLAS = 20, POR_OLA = 9;   // las ráfagas del atacante que aprende: 180 paquetes a la vista (la cifra es 5.280)

  // El tiempo del pago sin Grifter: corre hasta el rebobinado, vuelve atrás en 0,5 s y deja de valer con Grifter.
  const tPago = (tt) => (tt < K.rebobina ? tt : tt < E.frena ? (quieto ? -1 : K.rebobina - (K.rebobina - K.sale + 0.2) * vaiven((tt - K.rebobina) / (E.frena - K.rebobina))) : -1);

  const ICONOS = {};
  function dibIcono(g, nombre, x, y, tam, color) {
    ICONOS[nombre] = ICONOS[nombre] || new Path2D(P[nombre]);
    g.save(); g.translate(x - tam / 2, y + tam / 2); g.scale(tam / 960, tam / 960); g.fillStyle = color; g.fill(ICONOS[nombre]); g.restore();
  }
  function arista(g, p, u0, u1, color, { ancho = 3, punta = true, dash = null } = {}) {
    if (u1 - u0 < 0.01) return;
    g.beginPath();
    for (let i = 0; i <= 24; i++) { const q = bez(p, mix(u0, u1, i / 24)); if (i) g.lineTo(q.x, q.y); else g.moveTo(q.x, q.y); }
    g.strokeStyle = color; g.lineWidth = ancho; g.setLineDash(dash || []); g.stroke(); g.setLineDash([]);
    if (punta) {
      const a = bez(p, u1 - 0.02), b = bez(p, u1);
      g.save(); g.translate(b.x, b.y); g.rotate(Math.atan2(b.y - a.y, b.x - a.x));
      g.beginPath(); g.moveTo(9, 0); g.lineTo(-7, -8); g.lineTo(-7, 8); g.closePath(); g.fillStyle = color; g.fill(); g.restore();
    }
  }
  function rotulo(g, x, y, nombre, sub, a, { colSub = "texto-2", px = 28, fondo = false, alin = "center" } = {}) {
    g.textAlign = alin; g.textBaseline = "middle"; g.font = letra(600, px);
    if (fondo) { const w = g.measureText(nombre).width + 20; g.fillStyle = c("fondo", 0.88 * a); g.fillRect(x - w / 2, y - px * 0.7, w, px * 1.4); }
    g.fillStyle = c("texto", a); g.fillText(nombre, x, y);
    if (sub) { g.font = letra(400, 24); g.fillStyle = c(colSub, a); g.fillText(sub, x, y + 32); }
  }
  // Un nodo: disco con su ícono o su foto, anillo del color de su estado y el rótulo debajo.
  function nodo(g, n, { icono = null, foto = null, color = "texto-2", a = 1, nombre = "", sub = "", colSub = "texto-2", px = 28, fondo = false, lado = "abajo" }) {
    if (a <= 0.01) return;
    g.beginPath(); g.arc(n.x, n.y, n.r, 0, TAU); g.fillStyle = c("superficie", a); g.fill();
    if (foto && foto.complete && foto.naturalWidth) {
      const s = Math.min(foto.naturalWidth, foto.naturalHeight);
      g.save(); g.globalAlpha = a * BASE; g.beginPath(); g.arc(n.x, n.y, n.r - 1, 0, TAU); g.clip();
      g.drawImage(foto, (foto.naturalWidth - s) / 2, (foto.naturalHeight - s) / 2, s, s, n.x - n.r, n.y - n.r, n.r * 2, n.r * 2); g.restore();
    } else if (icono) dibIcono(g, icono, n.x, n.y, n.r * 0.95, c(color === "texto-2" || color === "texto-3" ? "texto" : color, a));
    g.beginPath(); g.arc(n.x, n.y, n.r, 0, TAU); g.strokeStyle = c(color, a); g.lineWidth = 3; g.stroke();
    if (nombre && lado === "izq") rotulo(g, n.x - n.r - 22, n.y - (sub ? 16 : 0), nombre, sub, a, { colSub, px, alin: "right" });
    else if (nombre) rotulo(g, n.x, n.y + n.r + 32, nombre, sub, a, { colSub, px, fondo });
  }
  // Un paquete: el dato rotulado, con el color y el ícono de su origen (la marca que viaja con el dato).
  const anchoChip = (g, txt, px = 28, conIcono = false) => { g.font = letra(600, px); return g.measureText(txt).width + px + (conIcono ? px + 8 : 0); };
  function chip(g, x, y, txt, color, { icono = null, px = 28, a = 1, escala = 1 } = {}) {
    if (a <= 0.01) return;
    const w = anchoChip(g, txt, px, !!icono), alto = Math.round(px * 1.72);
    g.save(); g.translate(x, y); g.scale(escala, escala);
    g.fillStyle = c("fondo", a); g.fillRect(-w / 2, -alto / 2, w, alto);
    g.strokeStyle = c(color, a); g.lineWidth = 2.5; g.strokeRect(-w / 2, -alto / 2, w, alto);
    if (icono) dibIcono(g, icono, -w / 2 + px / 2 + px / 2, 0, px, c(color, a));
    g.font = letra(600, px); g.textAlign = "left"; g.textBaseline = "middle"; g.fillStyle = c(color, a);
    g.fillText(txt, -w / 2 + px / 2 + (icono ? px + 8 : 0), 1);
    g.restore();
  }
  // El destello de un bloqueo (o de un paso permitido): un anillo que se abre y unos rayos cortos. Sin brillo.
  function destello(g, x, y, dt, color = "verde", dur = 0.7, tam = 1) {
    if (quieto || dt < 0 || dt > dur) return;
    const p = dt / dur, e = salida(p);
    g.strokeStyle = c(color, 1 - p); g.lineWidth = 5 * (1 - p) + 1;
    g.beginPath(); g.arc(x, y, (18 + 90 * e) * tam, 0, TAU); g.stroke();
    g.beginPath();
    for (let i = 0; i < 10; i++) { const a = (i * TAU) / 10 + 0.3, r0 = (34 + 60 * e) * tam, r1 = (50 + 96 * e) * tam; g.moveTo(x + Math.cos(a) * r0, y + Math.sin(a) * r0); g.lineTo(x + Math.cos(a) * r1, y + Math.sin(a) * r1); }
    g.stroke();
  }
  // Un paquete bloqueado se deshace en pedazos que caen hacia atrás.
  function fragmentos(g, x, y, dt, color) {
    if (quieto || dt < 0 || dt > 0.8) return;
    const p = dt / 0.8, e = salida(p);
    g.fillStyle = c(color, (1 - p) * 0.9);
    for (const f of FRAG) { const s = 5 + 7 * f.s; g.fillRect(x + f.dx * 170 * e - s / 2, y + f.dy * 80 * e + 40 * p * p - s / 2, s, s); }
  }
  // Un paquete que choca con la compuerta: acelera por su arista hasta el tope, rebota y se disuelve.
  function choque(g, tt, ruta, t0, tc, txt, { icono, dy = 0, ancho = null } = {}) {
    if (tt < t0 || tt > tc + 0.85) return;
    const w = ancho || anchoChip(g, txt, 28, !!icono), uT = uEnX(ruta, PX - w / 2 - 14), tope = bez(ruta, uT);
    if (tt < tc) {
      const p = quieto ? 1 : clamp((tt - t0) / (tc - t0)) ** 1.7, q = bez(ruta, uT * p);
      chip(g, q.x, q.y + dy * (1 - p), txt, "rojo", { icono });
    } else {
      const p = lin(tt, tc, tc + 0.6);
      chip(g, tope.x - 80 * salida(p), tope.y, txt, "rojo", { icono, a: 1 - p });
      fragmentos(g, tope.x, tope.y, tt - tc, "rojo");
    }
  }
  function poligono(g, x, y, r, n, giro, color) {
    g.beginPath();
    for (let i = 0; i < n; i++) { const a = giro + (i * TAU) / n; if (i) g.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); else g.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r); }
    g.closePath(); g.fillStyle = color; g.fill();
  }

  // Lo que va por detrás de la esfera del agente: aristas, compuerta, nodos y rótulos. Devuelve la geometría del cuadro.
  function grafoFondo(tt) {
    const g = g2, G = geo(tt);
    BASE = tr(tt, E.suena + 0.2, 0.5) * (1 - tr(tt, E.remate, 0.4));
    if (BASE <= 0.01) return null;
    const { m, z, pr, ag, ext } = G;
    const tv = tPago(tt), pagado = tv >= K.enPagar, cobrado = tv >= K.enBanco;
    const R = G.R = { e1: curvaH(D.marta, ag), e2: curvaH(ext, ag), e3: curvaH(ag, D.pagar), e4: curvaH(ag, D.resp), e5: curvaH(D.pagar, D.banco) };
    const u3 = [uEnX(R.e3, ag.x + ag.r + 12), uEnX(R.e3, PX), uEnX(R.e3, D.pagar.x - D.pagar.r - 14)];
    const u4 = [uEnX(R.e4, ag.x + ag.r + 12), uEnX(R.e4, PX), uEnX(R.e4, D.resp.x - D.resp.r - 14)];
    G.p3 = bez(R.e3, u3[1]); G.p4 = bez(R.e4, u4[1]);
    const hayPuerta = tt >= E.frena;
    // En qué anda cada salida. Cerrado = Grifter retuvo lo último que pasó por ahí.
    const enB = tt >= E.alerta && tt < E.banco;                      // la doble aprobación: el pago sigue retenido
    G.cerr3 = (tt >= K.choque1 && tt < K.legit - 0.3) || enB || tt >= K.choque3;
    G.cerr4 = tt >= K.choque2 && tt < E.aprobaste;
    const enBanco = tr(tt, E.banco, 0.3) - tr(tt, E.aprobaste, 0.3);   // 1 durante la estafa del banco
    const aPagar = pr * mix(1, 0.4, enBanco), aResp = pr * mix(0.4, 1, enBanco);
    const aBanco = pr * tr(tt, E.paga + 0.3, 0.4) * (1 - tr(tt, E.banco, 0.3));
    const aPablo = tr(tt, K.dos + 0.2, 0.4) * (1 - tr(tt, E.banco, 0.3));
    const aE6 = pr * tr(tt, E.alerta + 0.05, 0.3) * (1 - tr(tt, E.banco, 0.3));

    // --- aristas ---
    if (pr > 0.01) {
      const llevaMarta = (tt >= K.legit && tt < K.legitAgente + 0.2) || (tt >= K.aprobado && tt < K.aprobado + 1);
      arista(g, R.e1, uEnX(R.e1, D.marta.x + D.marta.r + 8), uEnX(R.e1, ag.x - ag.r - 16), c(llevaMarta ? "texto" : "texto-2", pr * (llevaMarta ? 1 : 0.8)));
      // del agente a «Pagar» y a «Responder», con la compuerta en el medio
      const salidaAg = (ruta, u, roja, blanca, verde, cerrada, a) => {
        const antes = roja ? "rojo" : blanca ? "texto" : "texto-3";
        if (!hayPuerta) return arista(g, ruta, u[0], u[2], c(antes, a));
        const hueco = uEnX(ruta, PX + 30) - u[1];
        arista(g, ruta, u[0], u[1] - hueco, c(antes, a), { punta: false });
        if (cerrada) arista(g, ruta, u[1] + hueco * 2.2, u[2], c("texto-3", a * 0.55), { dash: [5, 12] });   // la arista queda cortada
        else arista(g, ruta, u[1] + hueco, u[2], c(verde ? "verde" : "texto-3", a));
      };
      const rojo3 = tv >= K.sale || (tt >= K.sale2 && tt < K.legit - 0.3) || tt >= K.paga3;
      const blanco3 = tt >= K.legitAgente && tt < E.alerta;
      salidaAg(R.e3, u3, rojo3, blanco3, tt >= K.legitAgente + 0.5 && tt < E.alerta, G.cerr3, aPagar);
      salidaAg(R.e4, u4, tt >= K.envia && tt < E.aprobaste, false, false, G.cerr4, aResp);
      if (aBanco > 0.01) arista(g, R.e5, uEnX(R.e5, D.pagar.x + D.pagar.r + 8), uEnX(R.e5, D.banco.x - D.banco.r - 14), c(pagado ? "rojo" : "texto-3", aBanco * (pagado ? 1 : 0.7)));
      if (aE6 > 0.01) arista(g, E6, 0, 0.985, c(tt >= K.codigo1 ? "verde" : "texto-2", aE6 * 0.9));
      if (aPablo > 0.01) arista(g, E7, 0, 0.96, c("texto-2", aPablo * 0.9));
    }
    FUENTES.forEach((f) => {
      const a = tr(tt, f.entra, 0.4) * (1 - tr(tt, f.sale, 0.25)) * (1 - G.fuera);
      f.a = a * (f.sale === E.banco ? mix(1, 0.45, tr(tt, E.alerta, 0.4)) : 1);   // la llamada ya terminó: queda tenue
      f.rojo = tr(tt, f.mancha, 0.3);
      f.n = { x: ext.x - 40 * (1 - sl(tt, f.entra, 0.4)), y: ext.y, r: ext.r };
      if (f.a <= 0.01) return;
      const ruta = curvaH(f.n, ag), u0 = uEnX(ruta, f.n.x + f.n.r + 8), u1 = uEnX(ruta, ag.x - ag.r - 16);
      arista(g, ruta, u0, mix(u0, u1, sl(tt, f.arista, 0.5)), c(mezcla(RGB["texto-3"], RGB.rojo, f.rojo), f.a));
    });
    // El rastro: cuando Grifter explica por qué retuvo, el origen se recorre hacia atrás, de la compuerta a la llamada.
    if (tt >= K.rastro && tt < E.pasa && !quieto) {
      const p = clamp((tt - K.rastro) / 1.0), u2 = [uEnX(R.e2, ext.x + ext.r + 8), uEnX(R.e2, ag.x - ag.r - 16)];
      const punto = p < 0.45 ? bez(R.e3, mix(u3[1], u3[0], p / 0.45)) : bez(R.e2, mix(u2[1], u2[0], (p - 0.45) / 0.55));
      arista(g, R.e3, mix(u3[1], u3[0], clamp(p / 0.45)), u3[1] - 0.04, c("rojo"), { ancho: 6, punta: false });
      if (p > 0.45) arista(g, R.e2, mix(u2[1], u2[0], (p - 0.45) / 0.55), u2[1], c("rojo"), { ancho: 6, punta: false });
      if (p < 1) { g.beginPath(); g.arc(punto.x, punto.y, 10, 0, TAU); g.fillStyle = c("rojo"); g.fill(); }
      destello(g, ext.x, ext.y, tt - K.rastro - 1.0, "rojo", 0.7, 1.1);
    }

    // --- la compuerta de Grifter ---
    if (hayPuerta) {
      const P_ = G.puerta, cy = (P_.y0 + P_.y1) / 2, h = ((P_.y1 - P_.y0) / 2) * sl(tt, E.frena, 0.4), y0 = cy - h, y1 = cy + h;
      const cerrada = tt >= K.rechaza1 && tt < E.banco, aP = tr(tt, E.frena, 0.2);
      const abre = quieto ? 0 : Math.sin(Math.PI * clamp((tt - K.legitAgente - 0.35) / 0.6));   // el puerto se abre cuando pasa lo de Marta
      const puertos = tt < E.estafas && tt >= E.frena + 0.4 ? [[G.p3, G.cerr3, abre, aPagar / (pr || 1)], [G.p4, G.cerr4, 0, aResp / (pr || 1)]] : [];
      g.strokeStyle = c("verde", aP); g.lineCap = "butt"; g.lineWidth = cerrada ? 10 : 6;
      g.beginPath();
      let y = y0;
      for (const [p, , ab] of puertos) { const hueco = 22 + 12 * ab; g.moveTo(PX, y); g.lineTo(PX, p.y - hueco); y = p.y + hueco; }
      g.moveTo(PX, y); g.lineTo(PX, y1); g.stroke();
      g.lineWidth = 6; g.beginPath(); g.moveTo(PX - 18, y0); g.lineTo(PX + 18, y0); g.moveTo(PX - 18, y1); g.lineTo(PX + 18, y1); g.stroke();
      for (const [p, cerr, ab] of puertos) {
        const hueco = 22 + 12 * ab;
        if (cerr) { g.fillStyle = c("verde", aP); g.fillRect(PX - 21, p.y - 21, 42, 42); dibIcono(g, "block", PX, p.y, 34, c("fondo", aP)); }
        else { g.lineWidth = 3; g.strokeRect(PX - 15, p.y - hueco, 30, hueco * 2); }   // el puerto abierto: el marco de una puerta, y la arista pasa por dentro
      }
      // los dos cupos de la doble aprobación, a la derecha de la compuerta (el rótulo «n de 2» va al lado, en el DOM)
      const aC = tr(tt, K.dos, 0.3) * (1 - tr(tt, E.banco, 0.3));
      if (aC > 0.01) [0, 1].forEach((i) => {
        const sx = PX + 44 + i * 40, sy = (G.p3.y + G.p4.y) / 2, si = i === 0 && tt >= K.codigo1, no = i === 1 && tt >= K.rechaza1;
        g.fillStyle = c(si ? "verde" : no ? "rojo" : "fondo", aC); g.fillRect(sx - 15, sy - 15, 30, 30);
        g.strokeStyle = c(si ? "verde" : no ? "rojo" : "texto-2", aC); g.lineWidth = 3; g.strokeRect(sx - 15, sy - 15, 30, 30);
        if (si) dibIcono(g, "check", sx, sy, 28, c("fondo", aC));
        if (no) { g.strokeStyle = c("fondo", aC); g.lineWidth = 4; g.beginPath(); g.moveTo(sx - 8, sy - 8); g.lineTo(sx + 8, sy + 8); g.moveTo(sx + 8, sy - 8); g.lineTo(sx - 8, sy + 8); g.stroke(); }
      });
      g.font = letra(600, 28); g.textBaseline = "middle"; g.fillStyle = c("verde", aP * (1 - G.fuera));
      g.textAlign = "left"; g.fillText("Grifter", PX + 28, P_.y0 + 26);
      g.textAlign = "center"; g.fillStyle = c("verde", aP * tr(tt, E.estafas + 0.35, 0.3)); g.fillText("Grifter", PX, P_.y0 - 30);
    }

    // --- nodos ---
    const px = mix(24, 28, m);
    // La dueña: Marta en el cuento del tío; en las otras estafas es otra persona, «Tú», con un ícono genérico.
    nodo(g, D.marta, { foto: FOTOS.marta, icono: "person", color: "texto", a: pr * (1 - tr(tt, E.banco, 0.25)), nombre: "Marta", sub: "Dueña" });
    nodo(g, D.marta, { icono: "person", color: "texto", a: pr * tr(tt, E.banco + 0.25, 0.3), nombre: "Tú", sub: "Quien decide" });
    for (const f of FUENTES) nodo(g, f.n, { icono: f.icono, color: mezcla(RGB["texto-2"], RGB.rojo, f.rojo), a: f.a, nombre: f.nombre, sub: f.sub, colSub: mezcla(RGB["texto-2"], RGB.rojo, f.rojo), px });
    const pasoOk = tt >= K.legitPagar && tt < E.alerta;
    nodo(g, D.pagar, { icono: pasoOk ? "check" : "payments", color: pagado ? "rojo" : pasoOk ? "verde" : "texto-2", a: aPagar, nombre: "Pagar" });
    nodo(g, D.resp, { icono: "send", color: "texto-2", a: aResp, nombre: "Responder", sub: "Compartir dato" });
    nodo(g, D.banco, { icono: "banco", color: cobrado ? "rojo" : "texto-3", a: aBanco * (cobrado ? 1 : 0.6), nombre: "Banco", sub: "Cuenta del estafador", colSub: cobrado ? "rojo" : "texto-2" });
    nodo(g, D.pablo, { foto: FOTOS.pablo, icono: "person", color: "texto", a: aPablo, nombre: "Pablo", sub: "Hijo de Marta", lado: "izq" });
    // el agente: la esfera la dibuja el motor; aquí van su anillo (ámbar cuando actúa) y su rótulo
    const actua = quieto ? +(pesoHabla(tt) > 0.5) : pesoHabla(tt);
    g.beginPath(); g.arc(ag.x, ag.y, ag.r + 6, 0, TAU); g.strokeStyle = c(mezcla(RGB["texto-3"], RGB.ambar, actua), 0.9); g.lineWidth = 2; g.stroke();
    medicion(g, tt, G);
    const yAg = ag.y + ag.r + mix(30, 38, m);
    rotulo(g, ag.x, yAg, "Agente de Marta", "", 1 - tr(tt, E.banco, 0.2), { px });
    rotulo(g, ag.x, yAg, "Tu agente", "", tr(tt, E.banco + 0.2, 0.2) * (1 - tr(tt, E.estafas, 0.2)), { px });
    rotulo(g, ag.x, yAg, "Agente", "", tr(tt, E.estafas + 0.2, 0.2), { px, fondo: true });
    // los destellos de los nodos
    if (tt < K.rebobina) { destello(g, D.pagar.x, D.pagar.y, tt - K.enPagar, "rojo"); destello(g, D.banco.x, D.banco.y, tt - K.enBanco, "rojo", 0.8, 1.2); }
    destello(g, D.pagar.x, D.pagar.y, tt - K.legitPagar, "verde");
    return G;
  }

  // La medición: 150 puntos en 32 racimos, cada racimo con su arista al agente y de ahí a la compuerta; después, el
  // atacante que aprende. Los paquetes de esta parte no llevan rótulo: son muchos.
  function medicion(g, tt, G) {
    const { z, ag } = G;
    if (z <= 0.01) return;
    const aR = z * (1 - tr(tt, E.atacante, 0.5));
    for (const q of RAC) {
      q.r1 = curvaH(q, ag); q.r2 = curvaH(ag, { x: PX, y: q.yp });
      if (aR <= 0.01) continue;
      const nace = sl(tt, E.estafas + 0.5 + q.pts[0].j * 0.006, 0.4);
      if (nace <= 0) continue;
      const u0 = uEnX(q.r1, q.x + 42), u1 = uEnX(q.r1, ag.x - ag.r - 10), v0 = uEnX(q.r2, ag.x + ag.r + 10);
      arista(g, q.r1, u0, mix(u0, u1, nace), c("texto-3", 0.5 * aR), { ancho: 2, punta: false });
      arista(g, q.r2, v0, mix(v0, 1, nace), c("texto-3", 0.5 * aR), { ancho: 2, punta: false });
      g.fillStyle = c("rojo", aR);
      for (const p of q.pts) { const s = sl(tt, E.estafas + 0.5 + p.j * 0.006, 0.25); if (s > 0) { g.beginPath(); g.arc(p.x, p.y, 5 * s, 0, TAU); g.fill(); } }
    }
    const aA = tr(tt, E.atacante + 0.1, 0.4);
    if (aA > 0.01) {
      const at = D.med.atacante, ola = Math.max(0, Math.min(OLAS - 1, Math.floor((tt - E.atacante - 0.3) / 0.2)));
      nodo(g, at, { color: "rojo", a: aA, nombre: "Atacante que aprende" });
      poligono(g, at.x, at.y, 30, 3 + (ola % 4), quieto ? 0 : tt * 1.3, c("rojo", aA));   // cambia de forma con cada generación
    }
  }

  // Lo que va por delante de la esfera: los paquetes y los destellos de la compuerta.
  function grafoFrente(tt, G) {
    if (!G) return;
    const g = g2, { m, z, ag, R } = G, tv = tPago(tt);
    const px = mix(24, 28, m);
    // --- el pago del cuento del tío: «$650.000» y «48-2210-7735», los dos marcados con su origen (la llamada) ---
    const finPago = K.choque1 + 0.85;
    if (tt >= K.monto && tt < finPago) {
      const wM = anchoChip(g, "$650.000", px, true), wC = anchoChip(g, "48-2210-7735", px, true);
      let U = null, aC = 1, aM = 1, dyM = -28, roto = -1;
      if (tv >= K.sale) {   // sin Grifter: llega a «Pagar» y la plata sigue al banco del estafador
        U = bez(R.e3, vaiven(clamp((tv - K.sale) / (K.enPagar - K.sale))));
        aC = 1 - clamp((tv - K.enPagar) / 0.2);
        if (tv > K.enPagar) { const v = vaiven(clamp((tv - K.enPagar) / (K.enBanco - K.enPagar))); U = bez(R.e5, v); dyM = mix(-28, 0, v); }
      } else if (tt >= K.sale2) {   // con Grifter: choca con la compuerta
        const tope = bez(R.e3, uEnX(R.e3, PX - wC / 2 - 14));
        if (tt < K.choque1) U = bez(R.e3, uEnX(R.e3, PX - wC / 2 - 14) * (quieto ? 1 : clamp((tt - K.sale2) / (K.choque1 - K.sale2)) ** 1.7));
        else { const p = lin(tt, K.choque1, K.choque1 + 0.6); U = { x: tope.x - 80 * salida(p), y: tope.y }; aC = aM = 1 - p; roto = tt - K.choque1; fragmentos(g, tope.x, tope.y, roto, "rojo"); }
      }
      [["$650.000", K.monto, wM, aM], ["48-2210-7735", K.cuenta, wC, aC]].forEach(([txt, t0, w, a], i) => {
        if (tt < t0) return;
        let q;
        if (U) q = { x: U.x, y: U.y + (i ? 28 : dyM) };
        else if (tt < t0 + 0.8 && !quieto) q = bez(R.e2, vaiven((tt - t0) / 0.8));
        else {   // en el agente: al lado de la esfera mientras el grafo va en chico, sobre ella en la disposición principal
          const e = sl(tt, t0 + 0.8, 0.3), dx = mix(ag.r + 20 + (i ? wM + 12 + wC / 2 : wM / 2), 0, m), dy = mix(0, i ? 28 : -28, m);
          q = { x: ag.x + dx * e, y: ag.y + dy * e };
        }
        chip(g, q.x, q.y, txt, "rojo", { icono: "call", px, a });
      });
    }
    // --- lo que viene de Marta, pasa ---
    if (tt >= K.legit && tt < K.legitPagar + 0.3) {
      let q, col = "texto";
      if (tt < K.legitAgente) q = bez(R.e1, quieto ? 1 : vaiven(clamp((tt - K.legit) / (K.legitAgente - K.legit - 0.08))));
      else { q = bez(R.e3, lin(tt, K.legitAgente, K.legitPagar)); if (q.x > PX) col = "verde"; }
      chip(g, q.x, q.y, "Cuenta inscrita", col, { icono: "person", a: 1 - lin(tt, K.legitPagar, K.legitPagar + 0.3) });
    }
    // --- la doble aprobación: por la arista de Marta y por la de Pablo ---
    const enArista = (ruta, txt, col, t0, t1, alReves, icono) => {
      if (tt < t0 || tt > t1 + 0.3) return;
      const u = quieto ? 1 : vaiven(clamp((tt - t0) / (t1 - t0))), q = bez(ruta, alReves ? 1 - u : u);
      chip(g, q.x, q.y, txt, col, { icono, a: 1 - lin(tt, t1, t1 + 0.3) });
    };
    enArista(E6, "Pago retenido", "verde", K.aviso, K.aviso + 0.6, true, null);
    enArista(E6, "Pagar igual", "texto", K.insiste, K.insiste + 0.8, false, "person");
    enArista(E6, "Código 482 913", tt >= K.codigo1 - 0.1 ? "verde" : "texto", K.codigo0, K.codigo1, false, "person");
    enArista(E7, "¿Apruebas?", "verde", K.mensaje, K.mensaje + 0.6, true, null);
    enArista(E7, "Rechazar", "texto", K.rechaza0, K.rechaza1, false, "person");
    // --- el falso banco: «Pide tu código» entra, y el agente intenta mandar «482 913» ---
    if (tt >= K.pide && tt < E.aprobaste + 0.3) {
      const e = sl(tt, K.pide + 0.9, 0.3), q = tt < K.pide + 0.9 && !quieto ? bez(R.e2, vaiven((tt - K.pide) / 0.9)) : { x: ag.x, y: ag.y - 28 * e };
      chip(g, q.x, q.y, "Pide tu código", "rojo", { icono: "mail", a: 1 - tr(tt, E.aprobaste, 0.3) });
    }
    if (tt >= K.envia - 0.25 && tt < K.envia) chip(g, ag.x, ag.y + 28, "482 913", "rojo", { icono: "mail", a: sl(tt, K.envia - 0.25, 0.2) });
    choque(g, tt, R.e4, K.envia, K.choque2, "482 913", { icono: "mail", dy: 28 });
    // --- la tienda: lo aprobado por Marta se queda en el agente; el cobro de la tienda choca ---
    if (tt >= K.aprobado && z < 0.99) {
      const e = sl(tt, K.aprobado + 0.8, 0.3), q = tt < K.aprobado + 0.8 && !quieto ? bez(R.e1, vaiven((tt - K.aprobado) / 0.8)) : { x: ag.x, y: ag.y - 28 * e };
      chip(g, q.x, q.y, "$412.000", "texto", { icono: "person", a: 1 - tr(tt, E.estafas, 0.3) });
    }
    if (tt >= K.cobro && tt < K.paga3) {
      const e = sl(tt, K.cobro + 0.8, 0.3), q = tt < K.cobro + 0.8 && !quieto ? bez(R.e2, vaiven((tt - K.cobro) / 0.8)) : { x: ag.x, y: ag.y + 28 * e };
      chip(g, q.x, q.y, "$4.120.000", "rojo", { icono: "shopping_cart" });
    }
    choque(g, tt, R.e3, K.paga3, K.choque3, "$4.120.000", { icono: "shopping_cart", dy: 28 });
    // --- los destellos de la compuerta ---
    destello(g, PX, G.p3.y, tt - K.choque1, "verde", 0.8, 1.2);
    destello(g, PX, G.p4.y, tt - K.choque2, "verde", 0.8, 1.2);
    destello(g, PX, G.p3.y, tt - K.choque3, "verde", 0.8, 1.2);
    destello(g, PX, G.p3.y, tt - K.legitAgente - 0.45, "verde", 0.5, 0.6);
    destello(g, PX, (G.p3.y + G.p4.y) / 2, tt - K.rechaza1, "verde", 0.8, 1.4);
    destello(g, PX + 44, (G.p3.y + G.p4.y) / 2, tt - K.codigo1, "verde", 0.5, 0.5);

    // --- medición: los 150 paquetes, uno por estafa, y las ráfagas del atacante ---
    if (z > 0.01) {
      const aR = z * (1 - tr(tt, E.atacante, 0.5));
      for (const q of RAC) for (const p of q.pts) {
        const dt = tt - (E.estafas + 1.0 + ((p.j * 67) % 150) * (1.25 / 150));
        if (dt < 0) continue;
        if (dt < 0.85 && !quieto) {
          if (aR <= 0.01) continue;
          const u = dt / 0.45, s = dt < 0.45 ? bez(q.r1, u) : bez(q.r2, (dt - 0.45) / 0.4), k = dt < 0.45 ? Math.min(1, u * 4) : 1;
          g.beginPath(); g.arc(mix(p.x, s.x, k), mix(p.y, s.y, k), 4.5, 0, TAU); g.fillStyle = c("rojo", aR); g.fill();
        } else {   // bloqueado: queda su marca en la compuerta
          const y = q.yp + ((p.j % 5) - 2) * 3.4;
          g.fillStyle = c("verde", z); g.fillRect(PX - 20, y - 1.5, 13, 3);
          if (dt - 0.85 < 0.3 && !quieto) { const e = (dt - 0.85) / 0.3; g.strokeStyle = c("verde", 1 - e); g.lineWidth = 2; g.beginPath(); g.arc(PX - 10, y, 4 + 12 * e, 0, TAU); g.stroke(); }
        }
      }
      if (tt >= E.atacante && !quieto) {
        const at = D.med.atacante, a0 = { x: at.x + at.r + 8, y: at.y };
        for (let w = 0; w < OLAS; w++) for (let k = 0; k < POR_OLA; k++) {
          const dt = tt - (E.atacante + 0.4 + w * 0.2 + k * 0.016);
          if (dt < 0 || dt > 0.95) continue;
          const h1 = frac(Math.sin(w * 12.9898 + k * 78.233) * 43758.5453), h2 = frac(Math.sin(w * 39.3468 + k * 11.135) * 24634.6345);
          const yp = 214 + h1 * 612, comba = (h2 - 0.5) * 240;
          if (dt < 0.7) {
            const r1 = [a0, { x: a0.x + 120, y: a0.y + comba }, { x: ag.x - 140, y: ag.y + comba }, { x: ag.x, y: ag.y }], r2 = curvaH(ag, { x: PX - 12, y: yp });
            const en = (d) => (d < 0.35 ? bez(r1, clamp(d / 0.35)) : bez(r2, clamp((d - 0.35) / 0.35)));
            const q = en(dt), cola = en(Math.max(0, dt - 0.05));
            g.strokeStyle = c("rojo", 0.45); g.lineWidth = 2; g.beginPath(); g.moveTo(cola.x, cola.y); g.lineTo(q.x, q.y); g.stroke();
            poligono(g, q.x, q.y, 8, 3 + ((w + k) % 4), tt * 9 + k, c("rojo"));   // cada intento es la misma estafa con otra forma
          } else {
            const e = (dt - 0.7) / 0.25;
            g.strokeStyle = c("verde", 1 - e); g.lineWidth = 2.5; g.beginPath(); g.arc(PX - 12, yp, 5 + 16 * e, 0, TAU); g.stroke();
          }
        }
      }
    }
  }

  // La línea de tiempo de la nube: [desde, figura, duración de la transición, dispersión en el camino (px)].
  const MARCA_NITIDA = E.cierre + 1.15;   // cuando la marca nítida reemplaza a la de partículas (ya en su lugar)
  const FIGURAS = [
    [0, figDispersa, 0.8, 0],
    [E.agentes, figEsfera(nube("agentes")), 1.0, 80],
    [E.encargo, figEsfera(nube("encargo"), { habla: true }), 0.8, 60],
    [E.suena, figEsfera(centroAgente, { habla: true }), 0.8, 60],   // desde aquí es el nodo del agente en el grafo
    [E.remate, figEsfera(ARRIBA), 0.9, 120],
    [palabra("remate", 6), figEscudo(ARRIBA), 0.7, 40],
    [E.cierre + 0.05, figLogo, 0.8, 80],
  ];

  // Dibuja el cuadro tt en el canvas: el fondo, el grafo por detrás, la nube y el grafo por delante. En la transición
  // de una figura a otra, cada partícula sale de la anterior (que sigue moviéndose) con su propio retraso.
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
    const G = grafoFondo(tt);
    // La nube.
    let k2 = 0;
    while (k2 + 1 < FIGURAS.length && tt >= FIGURAS[k2 + 1][0]) k2++;
    const [desde, fig, dura, disp] = FIGURAS[k2];
    const ahora = fig(tt);
    let pts = ahora.p;
    if (k2 > 0 && !quieto && tt < desde + dura + 0.3) {
      const antes = FIGURAS[k2 - 1][1](tt);
      pts = ahora.p.map((b, i) => {
        const a = antes.p[i], r = RAND_M[i], e = vaiven(clamp((tt - desde - r.retraso * Math.min(1, dura / 0.9)) / dura)), abre = Math.sin(Math.PI * e) * disp;
        return { x: a.x + (b.x - a.x) * e + r.dx * abre, y: a.y + (b.y - a.y) * e + r.dy * abre, c: mezcla(a.c, b.c, e), a: (a.a + (b.a - a.a) * e) * (1 - 0.65 * Math.sin(Math.PI * e)), s: a.s + (b.s - a.s) * e };
      });
    }
    for (const p of pts) {
      if (p.a <= 0.01) continue;
      g2.fillStyle = `rgba(${p.c[0]},${p.c[1]},${p.c[2]},${p.a.toFixed(3)})`;
      g2.beginPath(); g2.arc(p.x, p.y, p.s, 0, 6.2832); g2.fill();
    }
    grafoFrente(tt, G);
  }

  // --- Cuadro: qué se ve en el segundo t ---
  let escenas = [], listo = false, hud = null, marco = null, cursor = null;
  function preparar() {
    escenas = [...document.querySelectorAll(".dn-escena")].map((el) => ({
      el, desde: +el.dataset.desde, hasta: +el.dataset.hasta,
      aparecen: [...el.querySelectorAll("[data-v]")],
      on: [...el.querySelectorAll("[data-on]")],
      escribe: [...el.querySelectorAll("[data-e]")].map((x) => {
        const cfg = ESCRIBE[+x.dataset.e];
        x.innerHTML = cfg.segs.map((sg) => [...sg.txt].map((l) => `<span class="gf-l ${sg.cls}">${esc(l)}</span>`).join("")).join("");
        return Object.assign(cfg, { el: x, letras: [...x.children], n: 0, cursor: null });
      }),
      cuentas: [...el.querySelectorAll("[data-c]")].map((x) => Object.assign(CUENTAS[+x.dataset.c], { el: x, txt: "" })),
      dedos: [...el.querySelectorAll("[data-d]")].map((x) => Object.assign(DEDOS[+x.dataset.d], { el: x })),
      nubes: [...el.querySelectorAll(".dn-nube.mini")],
      barras: [...el.querySelectorAll(".dn-barras")],
      puntos: [...el.querySelectorAll(".dn-puntos i")],
      anillos: [...el.querySelectorAll(".dn-anillo")],
      relojes: [...el.querySelectorAll(".dn-reloj-s")],
      vibra: el.querySelector(".dn-vibra"),
      contestar: el.querySelector(".contestar"),
      marcaCierre: el.querySelector(".dn-marca-cierre"),
    }));
    hud = { caja: $("#gf-hud"), num: $("#gf-bloqueos"), n: -1, vivo: "", paneles: [...document.querySelectorAll(".gf-panel-vivo")] };
    marco = $("#dn-escenario");
    cursor = $("#gf-cursor");
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
  // Muestra las primeras n letras (las demás siguen en su lugar, ocultas) y anota cuál es la última escrita: ahí va el
  // cursor ámbar, que es un elemento aparte (#gf-cursor) para no tocar el layout ni cómo se arma el texto.
  function teclear(cfg, n, conCursor) {
    for (let i = Math.min(n, cfg.n); i < Math.max(n, cfg.n); i++) cfg.letras[i].classList.toggle("ve", i < n);
    cfg.n = n;
    let k = n - 1;
    while (k >= 0 && !cfg.letras[k].textContent.trim()) k--;   // el cursor nunca va en un espacio: al final de una línea no tiene caja propia
    const cursor = conCursor && k >= 0 ? cfg.letras[k] : null;
    cfg.cursor = cursor;
  }

  function valor(cfg, tt) {
    if (tt < cfg.t0) return cfg.de;
    if (quieto) return cfg.a;
    const p = clamp((tt - cfg.t0) / cfg.dur);
    return cfg.de + (cfg.a - cfg.de) * (cfg.baja ? vaiven(p) : salida(p));
  }

  function render(tt) {
    let conCursor = null;   // la última letra escrita del texto que se está escribiendo
    for (const s of escenas) {
      const activa = tt >= s.desde && tt < s.hasta;
      s.el.classList.toggle("activo", activa);
      if (!activa) continue;
      s.el.style.setProperty("--e", (quieto ? 1 : salida(clamp((tt - s.desde) / 0.35))).toFixed(3));
      s.aparecen.forEach((el) => aparecer(el, tt));
      s.on.forEach((el) => el.classList.toggle("on", tt >= +el.dataset.on));
      for (const cfg of s.escribe) {
        const n = Math.min(letras(cfg, tt), cfg.letras.length);
        teclear(cfg, n, !quieto && n < cfg.letras.length);
        if (cfg.cursor) conCursor = cfg.cursor;
      }
      for (const cfg of s.cuentas) {
        const txt = (cfg.pesos ? "$" : "") + miles(valor(cfg, tt));
        if (txt !== cfg.txt) { cfg.txt = txt; cfg.el.textContent = txt; }
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
      // La marca nítida del cierre reemplaza a la de partículas con un fundido cruzado de 0,2 s, cuando ya calzan.
      if (s.marcaCierre) s.marcaCierre.style.opacity = (quieto ? +(tt >= MARCA_NITIDA) : clamp((tt - MARCA_NITIDA) / 0.2)).toFixed(3);
    }
    // El panel de Pablo, en vivo: dice que la demo lo espera y, si rechazó de verdad, cuánto tardó.
    const retenida = vivo.esperando && tt >= E.rechaza - 0.002 && tt < E.rechaza;
    const estadoVivo = retenida ? "Esperando a Pablo…" : vivo.real !== null && tt >= K.rechaza1 ? `Rechazo real · ${Number(vivo.real).toLocaleString("es-CL")} s` : "";
    if (estadoVivo !== hud.vivo) { hud.vivo = estadoVivo; hud.paneles.forEach((p) => { p.textContent = estadoVivo; }); }
    // El cursor del texto que se escribe: una barra ámbar a la derecha de la última letra, puesta desde su caja.
    if (conCursor) {
      const base = marco.getBoundingClientRect(), k = base.width / 1920, c = conCursor.getBoundingClientRect(), alto = c.height / k;
      cursor.style.cssText = `display: block; left: ${((c.right - base.left) / k).toFixed(1)}px; top: ${((c.top - base.top) / k + alto * 0.1).toFixed(1)}px; height: ${(alto * 0.8).toFixed(1)}px; border-left-width: ${Math.max(3, alto * 0.055).toFixed(1)}px`;
    } else cursor.style.display = "none";
    // El que llama va desenfocado hasta que Marta dice «Tomás»: desde ahí la foto se aclara en 1,8 s y el nombre cambia
    // con un fundido de 1,2 s (sale «Desconocido» y entra «Tomás (nieto)», sin que se lean los dos encimados).
    const reconoce = quieto ? (tt >= LL.tomas ? 9 : -1) : tt - LL.tomas;
    marco.style.setProperty("--desenfoque", (1 - vaiven(clamp(reconoce / 1.8))).toFixed(3));
    marco.style.setProperty("--nombre-a", (1 - clamp(reconoce / 0.5)).toFixed(3));
    marco.style.setProperty("--nombre-b", clamp((reconoce - 0.5) / 0.7).toFixed(3));
    // El contador de bloqueos: aparece con la compuerta, sube con cada bloqueo (con un salto) y se va con la medición.
    const n = BLOQUEOS.filter((b) => tt >= b).length, ultimo = n ? BLOQUEOS[n - 1] : -9;
    if (n !== hud.n) { hud.n = n; hud.num.textContent = n; }
    hud.caja.style.opacity = (tr(tt, E.frena + 0.05, 0.3) * (1 - tr(tt, E.estafas, 0.3))).toFixed(3);
    hud.num.style.transform = `scale(${(1 + 0.45 * (1 - sl(tt, ultimo, 0.5))).toFixed(3)})`;
    // El borde rojo de alerta. Late en opacidad (fijo si reducido).
    const alarma = ALARMAS.find(([a, b]) => tt >= a && tt < b);
    document.body.classList.toggle("dn-alarma", !!alarma);
    document.body.style.setProperty("--alarma", quieto || !alarma ? 1 : (0.35 + 0.65 * (0.5 + 0.5 * Math.cos(((tt - alarma[0]) * 2 * Math.PI) / 1.2))).toFixed(3));
    $("#dn-barra").style.width = `${(Math.min(tt, DURACION) / DURACION) * 100}%`;
    motor(tt);
    if (revisor) { revisor.reloj.textContent = `t = ${tt.toFixed(1)} s`; if (document.activeElement !== revisor.barra) revisor.barra.value = tt; }
  }

  // --- Audio: las voces de la llamada (versión A) y la narración. Suenan solo después de que el presentador
  // pulsa Espacio o «Iniciar». Al pausar, saltar o reanudar, la pista que corresponde a t sigue desde t - en ---
  const PISTAS = [
    ...Object.values(NARR).map((n) => ({ src: n.src, en: n.en, dur: n.dur })),
    { src: "audio/cuento_del_tio_abuela.mp3", en: LL.abuela, dur: DUR_ABUELA },
    // El mp3 del nieto no se corta: suena «Abuelita, soy yo po, tu nieto.», se pausa en CORTE (corta) y sigue desde
    // ahí (desde) cuando Marta termina de decir «¿Tomás? ¿Qué te pasó, mijo?».
    { src: "audio/cuento_del_tio_nieto.mp3", en: LL.nieto, dur: CORTE, corta: true },
    { src: "audio/cuento_del_tio_abuela_tomas.mp3", en: LL.abuela2, dur: DUR_TOMAS },
    { src: "audio/cuento_del_tio_nieto.mp3", en: LL.nieto2, dur: DUR_NIETO - CORTE, desde: CORTE },
  ];
  let mudo = false;
  function prepararAudio() {
    const porArchivo = {};   // un solo elemento de audio por archivo: los dos tramos del nieto comparten el suyo
    for (const p of PISTAS) {
      if (!porArchivo[p.src]) {
        const a = new Audio(p.src);
        a.preload = "auto";
        a.addEventListener("error", () => { for (const q of PISTAS) if (q.src === p.src) q.a = null; });
        porArchivo[p.src] = a;
      }
      p.a = porArchivo[p.src];
    }
  }
  function tocar(p, desde) {
    if (!p.a || mudo) return;
    try { p.a.currentTime = Math.max(0, (p.desde || 0) + desde); } catch (_) { /* aún sin metadatos: parte del inicio */ }
    p.a.play().catch(() => { /* sin permiso de audio: la demo sigue muda */ });
  }
  let ctx = null, timbre = [];
  function sonarTimbre(desde) {   // el timbre del celular: dos notas, mi y do, como en la versión A
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
    for (const p of PISTAS) {
      if (antes < p.en && ahora >= p.en) tocar(p, ahora - p.en);
      if (p.corta && p.a && antes < p.en + p.dur && ahora >= p.en + p.dur) p.a.pause();   // aquí Marta interrumpe al nieto
    }
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

  // --- En vivo. Con ?whatsapp=1, el pedido a Pablo llega de verdad a su WhatsApp cuando aparece su panel, y su rechazo
  // también puede ser real: al terminar la pista (a) la demo espera su respuesta (el presentador toca
  // «Rechazar» en su teléfono) hasta 7 s desde que se detiene (?espera=N cambia el máximo) y sigue
  // con el rechazo simulado; si el WhatsApp no llega, la tecla S hace lo mismo. Si el envío falla, no espera. Sin
  // ?whatsapp=1 nada de esto corre. Es la lógica de demo.js (versión A) ---
  const ESPERA_S = Number(params.get("espera")) > 0 ? Number(params.get("espera")) : 7;   // máximo de la pausa, contado desde que el video se detiene
  const T_PANEL = K.dos + 0.5;   // cuando aparece el panel «Grifter · WhatsApp a Pablo»
  let avisado = false;
  const vivo = { id: null, desde: 0, esperando: false, real: null, limite: null };
  function avisarEnVivo() {
    if (params.get("whatsapp") !== "1" || avisado || location.protocol === "file:") return;
    avisado = true;
    const clave = claveVivo;
    const corte = new AbortController();
    setTimeout(() => corte.abort(), 5000);
    fetch("api/demo/alerta-en-vivo", { method: "POST", headers: { "Content-Type": "application/json" }, signal: corte.signal,
      body: JSON.stringify({ clave, idioma: "es" }) })
      .then((r) => (r.ok ? r.json() : null))
      .then((r) => { if (r?.id) { Object.assign(vivo, { id: r.id, desde: performance.now(), esperando: true }); sondear(clave); } })
      .catch(() => { /* la demo sigue con el panel dibujado */ });
  }
  async function sondear(clave) {
    while (vivo.esperando && (vivo.limite === null || performance.now() < vivo.limite)) {
      try {
        const r = await fetch(`api/demo/alerta-en-vivo/estado?id=${encodeURIComponent(vivo.id)}`, { headers: { "X-Grifter-Demo-Clave": clave }, cache: "no-store" });
        const e = r.ok ? await r.json() : null;
        if (e?.estado === "rechazado") { vivo.real = e.latencia_s; break; }
      } catch (_) { /* reintenta */ }
      await new Promise((ok) => setTimeout(ok, 500));
    }
    vivo.esperando = false;
  }

  // --- Reloj: un solo requestAnimationFrame; el tiempo avanza solo mientras corre ---
  let tiempo = 0, corriendo = false, previo = 0;
  function cuadro(ahora) {
    if (!corriendo) return;
    const dt = Math.min(0.1, (ahora - (previo || ahora)) / 1000);
    previo = ahora;
    const antes = tiempo;
    tiempo = Math.min(DURACION, tiempo + dt);
    // En vivo, la demo espera a Pablo justo al terminar «…recibe un mensaje.»; cuando él rechaza, sigue desde ahí.
    if (vivo.esperando && antes < E.rechaza && tiempo >= E.rechaza) { tiempo = E.rechaza - 0.001; if (vivo.limite === null) vivo.limite = performance.now() + ESPERA_S * 1000; }
    sonar(antes, tiempo);
    if (antes < T_PANEL && tiempo >= T_PANEL) avisarEnVivo();   // aunque esté en silencio
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
    if (s === 0) { avisado = false; Object.assign(vivo, { id: null, esperando: false, real: null, limite: null }); }   // una corrida nueva (el servidor limita a un envío cada 30 s)
    tiempo = s;
    corriendo = false;
    document.body.classList.remove("dn-corriendo");
    render(tiempo);
    if (seguir) alternar();
  }
  // Letra de los titulares, el logo y las cifras grandes: --titular. Por defecto Outfit; con ?letra= se prueba otra.
  const LETRAS = {
    outfit: ["Outfit", "Outfit:wght@600;700", "-0.02em"],
    plex: ["IBM Plex Sans", "", ""],
    space: ["Space Grotesk", "Space+Grotesk:wght@500;700", "-0.03em"],
    sora: ["Sora", "Sora:wght@600;800", "-0.04em"],
    bricolage: ["Bricolage Grotesque", "Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800", "-0.03em"],
    serif: ["Instrument Serif", "Instrument+Serif:ital@0;1", "-0.01em"],
    syne: ["Syne", "Syne:wght@700;800", "-0.03em"],
  };
  // Al cambiar la letra se vuelven a medir las anclas (con la letra ya cargada).
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
    const relojRev = document.createElement("output");
    relojRev.textContent = "t = 0.0 s";
    caja.append(barra, relojRev);
    const selLetra = document.createElement("select");
    selLetra.title = "Letra de titulares, logo y cifras (vista previa)";
    for (const [clave, [nombre]] of Object.entries(LETRAS)) selLetra.append(new Option(nombre, clave));
    selLetra.value = LETRAS[params.get("letra")] ? params.get("letra") : "outfit";
    selLetra.addEventListener("change", () => { ponerLetra(selLetra.value); selLetra.blur(); });
    caja.append(selLetra);
    boton("Copiar enlace", "Copia el enlace de este cuadro", () => {
      const u = new URL(location.href);
      u.searchParams.set("t", tiempo.toFixed(1));
      navigator.clipboard?.writeText(u.href).catch(() => {});
    });
    document.body.append(caja);
    document.body.classList.add("dn-revisando");
    revisor = { caja, barra, reloj: relojRev };
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === " " || e.code === "Space") { e.preventDefault(); alternar(); }
    else if (e.key === "r" || e.key === "R") irA(0, true);
    else if (e.key === "m" || e.key === "M") { mudo = !mudo; if (mudo) callar(); else if (corriendo) reanudar(tiempo); }
    else if ((e.key === "s" || e.key === "S") && vivo.esperando) vivo.esperando = false;   // respaldo: el WhatsApp no llegó
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
  addEventListener("resize", () => { escalar(); if (listo) render(tiempo); });
  escalar();
  construir();
  preparar();
  medir();
  ponerLetra(LETRAS[params.get("letra")] ? params.get("letra") : "outfit");   // Outfit por defecto; ?letra=plex vuelve a la anterior
  document.fonts?.ready.then(remedir);
  // Los rótulos del grafo se dibujan en el canvas: hay que redibujar cuando carga la letra de datos.
  Promise.all([400, 600].map((p) => document.fonts?.load(`${p} 28px "IBM Plex Mono"`))).then(() => render(tiempo), () => {});
  if (params.get("revisar") === "1") { abrirRevisor(); escalar(); }
  prepararAudio();
  if (params.has("t")) {   // un cuadro fijo para capturas: sin audio hasta que el presentador pulse Espacio
    tiempo = Math.min(DURACION, Math.max(0, Number(params.get("t")) || 0));
    document.body.classList.add("dn-cuadro");
  }
  else document.body.classList.add("dn-en-portada");   // sin ?t: la portada, hasta que el presentador inicia
  listo = true;
  render(tiempo);
  // Solo lectura, para revisar desde la consola: GrifterGrafo.estado()
  window.GrifterGrafo = {
    estado: () => ({ tiempo: Math.round(tiempo * 100) / 100, corriendo, mudo, duracion: DURACION,
      escena: escenas.find((s) => tiempo >= s.desde && tiempo < s.hasta)?.el.dataset.id,
      bloqueos: BLOQUEOS.filter((b) => tiempo >= b).length,
      vivo: { activo: params.get("whatsapp") === "1", avisado, esperando: vivo.esperando, real: vivo.real, espera_en: E.rechaza },
      narracion: Object.entries(NARR).map(([k, n]) => ({ pista: k, desde: n.en, hasta: Math.round((n.en + n.dur) * 100) / 100 })),
      audio: PISTAS.map((p) => ({ src: p.src, listo: p.a ? p.a.readyState : null, sonando: p.a ? !p.a.paused : false })) }),
  };
})();
