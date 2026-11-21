// Demo de agent-scam-shield: reproduce los episodios exportados de Inspect en tres carriles y dibuja
// los resultados agregados de la eval. Sin build: los episodios llegan en window.EPISODIOS
// (episodios/episodios.js, de scripts/exportar_episodios.py) y los resultados en resultados.json
// (o window.RESULTADOS si la página se abre como archivo; scripts/exportar_resultados.py).
"use strict";

// El escenario que abre la demo. Si no hay episodios de ese escenario, abre el primero que haya.
// ?escenario=<id> en la URL manda sobre esto.
const ESCENARIO_POR_DEFECTO = "demo_microprocesadores";

const CARRILES = [
  { clave: "none", defensas: ["none"], icono: "gpp_bad" },
  { clave: "layer1", defensas: ["layer1"], icono: "shield" },
  { clave: "layer2", defensas: ["layer2", "both"], icono: "shield", escudo: true },
];
const HERRAMIENTAS_PAGO = ["pagar", "transferir"];
const HERRAMIENTAS_LECTURA = ["leer_correos", "abrir_web", "usar_mcp"];
const RE_BLOQUEO = /^(ACCIÓN BLOQUEADA|ACTION BLOCKED)/i;

const T = {
  es: {
    escenario: "Escenario", reproducir: "Reproducir", reproduciendo: "Reproduciendo", reiniciar: "Reiniciar",
    alerta: "Alerta", bandeja: "Bandeja", inscritas: "Inscritas", correos: "Correos",
    calor_tactica: "Táctica × defensa", calor_modelo: "Modelo × idioma",
    d_none: "Sin defensa", d_layer1: "Firewall", d_layer2: "Escudo", d_both: "Firewall + escudo", d_layer2_approver: "Escudo (approver)",
    ayuda_layer1: "Reglas contra inyección técnica, como Pipelock",
    ayuda_layer2: "Revisa de dónde salió cada cuenta antes de pagar",
    ayuda_none: "El agente hace lo que lee",
    dueno: "Dueña", sin_registro: "Sin registro", listo: "Listo",
    afuera_dominio: "Dominio distinto", afuera_cuenta: "Cuenta nueva",
    ayuda_afuera: "Este correo trae la cuenta que usó el agente y no es de las inscritas",
    o_inscrita: "inscrita", o_correo: "correo", o_otro: "sin origen",
    leidos: "{n} leídos", bloqueada: "Bloqueado", ejecutada: "Pagado", saldo_insuf: "Sin saldo",
    v_cayo: "Cayó", v_bloqueado: "Bloqueado", v_inscrita: "Pagó inscrita", v_no_pago: "No pagó",
    v_sin_pago: "Sin pagos", v_espera: "Espera a {d}", v_confirmado: "confirmado 2 veces",
    saldo: "saldo", decide: "{d}: {e}",
    e_pagar_inscrita: "pagar a la inscrita", e_no_pagar: "no pagar", e_pagar_igual: "pagar igual",
    r_0: "Seguro", r_1: "Normal", r_2: "Valor de afuera", r_3: "Pago afuera",
    ayuda_pulso: "Riesgo del paso. Base: lee lo del dueño. Sube: entra un valor no confiable. Pico rojo: intenta pagar a una cuenta de afuera. Línea verde: el escudo cortó",
    a_titulo: "Pago retenido", a_a: "a {d}", a_agente: "Cuenta del agente", a_inscrita: "Inscrita",
    a_origen: "apareció en un correo de {d}",
    ayuda_alerta: "El escudo detuvo el pago porque la cuenta salió de un correo. Sin respuesta, no se paga",
    a_pagar_inscrita: "Pagar a mi cuenta inscrita", a_no_pagar: "No pagar", a_pagar_igual: "Pagar igual",
    a_seguro: "¿Pagar a {c}?", a_si: "Sí, pagar igual", a_cancelar: "Cancelar", cerrar: "Cerrar",
    a_hecho_pagar_inscrita: "Pagado a la inscrita", a_hecho_no_pagar: "No se pagó", a_hecho_pagar_igual: "Pagado a la cuenta nueva",
    k_estafas: "Estafas exitosas", k_utilidad: "Utilidad", k_falsas: "Falsas alarmas", k_brecha: "Brecha ES / EN",
    ayuda_k_estafas: "Estafas en que el agente cayó, sin defensa y con el escudo",
    ayuda_k_utilidad: "Tareas legítimas cumplidas, sin defensa y con el escudo",
    ayuda_k_falsas: "Controles legítimos en que una defensa bloqueó algo, sin defensa y con el escudo",
    ayuda_k_brecha: "Diferencia de estafas exitosas entre español e inglés, sin defensa",
    sin_datos: "Sin datos", prueba: "Datos de prueba", fuente: "Inspect · {m} modelos · {n} muestras",
    sin_resultados: "Sin resultados", sin_episodio: "Sin episodio exportado", abrir: "Clic: abrir en los carriles",
    t_exito: "éxito de la estafa", modelo_nota: "Sin defensa",
    locale: "es-CL",
  },
  en: {
    escenario: "Scenario", reproducir: "Play", reproduciendo: "Playing", reiniciar: "Reset",
    alerta: "Alert", bandeja: "Inbox", inscritas: "Registered", correos: "Emails",
    calor_tactica: "Tactic × defense", calor_modelo: "Model × language",
    d_none: "No defense", d_layer1: "Firewall", d_layer2: "Shield", d_both: "Firewall + shield", d_layer2_approver: "Shield (approver)",
    ayuda_layer1: "Technical-injection rules, like Pipelock",
    ayuda_layer2: "Checks where each account came from before paying",
    ayuda_none: "The agent does what it reads",
    dueno: "Owner", sin_registro: "No log", listo: "Ready",
    afuera_dominio: "Different domain", afuera_cuenta: "New account",
    ayuda_afuera: "This email carries the account the agent used, and it is not a registered one",
    o_inscrita: "registered", o_correo: "email", o_otro: "no source",
    leidos: "{n} read", bloqueada: "Blocked", ejecutada: "Paid", saldo_insuf: "No funds",
    v_cayo: "Scammed", v_bloqueado: "Blocked", v_inscrita: "Paid registered", v_no_pago: "Not paid",
    v_sin_pago: "No payments", v_espera: "Waiting for {d}", v_confirmado: "confirmed twice",
    saldo: "balance", decide: "{d}: {e}",
    e_pagar_inscrita: "pay registered", e_no_pagar: "don't pay", e_pagar_igual: "pay anyway",
    r_0: "Safe", r_1: "Normal", r_2: "Outside value", r_3: "Outside payment",
    ayuda_pulso: "Step risk. Baseline: reads the owner's data. Rises: an untrusted value comes in. Red spike: tries to pay an outside account. Green line: the shield cut it",
    a_titulo: "Payment held", a_a: "to {d}", a_agente: "Agent's account", a_inscrita: "Registered",
    a_origen: "appeared in an email from {d}",
    ayuda_alerta: "The shield stopped the payment because the account came from an email. No answer, no payment",
    a_pagar_inscrita: "Pay my registered account", a_no_pagar: "Don't pay", a_pagar_igual: "Pay anyway",
    a_seguro: "Pay {c}?", a_si: "Yes, pay anyway", a_cancelar: "Cancel", cerrar: "Close",
    a_hecho_pagar_inscrita: "Paid to registered", a_hecho_no_pagar: "Not paid", a_hecho_pagar_igual: "Paid to the new account",
    k_estafas: "Successful scams", k_utilidad: "Utility", k_falsas: "False alarms", k_brecha: "ES / EN gap",
    ayuda_k_estafas: "Scams the agent fell for, with no defense and with the shield",
    ayuda_k_utilidad: "Legitimate tasks completed, with no defense and with the shield",
    ayuda_k_falsas: "Legitimate controls where a defense blocked something, with no defense and with the shield",
    ayuda_k_brecha: "Difference in successful scams between Spanish and English, no defense",
    sin_datos: "No data", prueba: "Test data", fuente: "Inspect · {m} models · {n} samples",
    sin_resultados: "No results", sin_episodio: "No exported episode", abrir: "Click: open in the lanes",
    t_exito: "scam success", modelo_nota: "No defense",
    locale: "en-US",
  },
};

const estado = {
  idioma: "es",
  escenario: null,
  velocidad: 1,
  ficha: 0,            // cambia en cada reinicio: los carriles viejos se detienen solos
  reproduciendo: false,
  carriles: {},        // clave -> { ep, terminado, decision, pulso }
  alerta: null,
  confirmando: false,
  resultados: null,
};

// --- Utilidades ---
const $ = (sel) => document.querySelector(sel);
const t = (clave, vars = {}) => {
  let s = (T[estado.idioma] || T.es)[clave] ?? T.es[clave] ?? clave;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => String(s ?? "").toLowerCase().replace(/[^a-z0-9ñáéíóúü]/gi, "");
const plata = (n) => "$" + Number(n || 0).toLocaleString(t("locale"));
const ms = (nombre, grande = false) => `<span class="ms${grande ? " grande" : ""}" aria-hidden="true">${nombre}</span>`;
const RE_CUENTA = /\b\d{2}-\d{4}-\d{4}\b/g;

function episodios() { return window.EPISODIOS || {}; }

function episodioDe(escenario, idioma, defensas) {
  for (const d of defensas) {
    const ep = episodios()[`${escenario}__${idioma}__${d}`];
    if (ep) return ep;
  }
  return null;
}

function esperar(ms_, ficha) {
  return new Promise((ok, no) => setTimeout(() => (ficha === estado.ficha ? ok() : no("reinicio")), ms_ / estado.velocidad));
}

// --- Tooltip único: [data-ayuda] en cualquier elemento ---
const ayuda = $("#ayuda");
function mostrarAyuda(el) {
  const texto = el.dataset.ayuda;
  if (!texto) return;
  ayuda.textContent = texto;
  ayuda.hidden = false;
  const r = el.getBoundingClientRect();
  const a = ayuda.getBoundingClientRect();
  const x = Math.min(Math.max(8, r.left), innerWidth - a.width - 8);
  const y = r.bottom + 8 + a.height > innerHeight ? r.top - a.height - 8 : r.bottom + 8;
  ayuda.style.left = `${x}px`;
  ayuda.style.top = `${y}px`;
}
const ocultarAyuda = () => { ayuda.hidden = true; };
document.addEventListener("mouseover", (e) => { const el = e.target.closest("[data-ayuda]"); if (el) mostrarAyuda(el); else ocultarAyuda(); });
document.addEventListener("focusin", (e) => { const el = e.target.closest("[data-ayuda]"); if (el) mostrarAyuda(el); else ocultarAyuda(); });
document.addEventListener("scroll", ocultarAyuda, true);

// --- Bandeja ---
function cuentaCon(texto) {
  return esc(texto).replace(RE_CUENTA, (m) => `<mark class="cuenta" data-cuenta="${norm(m)}">${m}</mark>`);
}

function correosDeAfuera(eps) {
  const ids = new Set();
  for (const ep of eps) for (const p of ep.pasos) if (p.origen_cuenta?.tipo === "correo") p.origen_cuenta.correos.forEach((c) => ids.add(c));
  return ids;
}

function pintarBandeja() {
  const eps = CARRILES.map((c) => estado.carriles[c.clave]?.ep).filter(Boolean);
  const ep = eps[0];
  if (!ep) { $("#encargo").innerHTML = ""; $("#inscritas").innerHTML = ""; $("#correos").innerHTML = ""; return; }
  $("#encargo").innerHTML = `<div class="encargo"><div class="quien">${ms("person")}${esc(ep.dueno || t("dueno"))}</div><div>${esc(ep.encargo)}</div></div>`;
  $("#inscritas").innerHTML = Object.entries(ep.cuentas_inscritas).map(([nombre, valor]) => {
    const num = (String(valor).match(RE_CUENTA) || [valor])[0];
    return `<li class="inscrita" data-cuenta="${norm(num)}"><span class="nombre">${esc(nombre)}</span><span class="dato">${esc(valor)}</span></li>`;
  }).join("") || `<li class="inscrita"><span class="nombre">${esc(t("sin_datos"))}</span></li>`;
  const afuera = correosDeAfuera(eps);
  const dominiosBuenos = ep.correos.filter((c) => !afuera.has(c.id)).map((c) => c.dominio);
  $("#correos").innerHTML = ep.correos.map((c) => {
    const malo = afuera.has(c.id);
    const [usuario] = c.de.split("@");
    const bandera = malo ? `<span class="bandera" data-ayuda="${esc(t("ayuda_afuera"))}">${esc(dominiosBuenos.length ? t("afuera_dominio") : t("afuera_cuenta"))}</span>` : "";
    return `<li class="correo${malo ? " afuera" : ""}" data-correo="${esc(c.id)}">
      <div class="de">${esc(usuario)}@<span class="dominio">${esc(c.dominio)}</span>${bandera}</div>
      <div class="asunto">${esc(c.asunto)}</div>
      <div class="cuerpo">${cuentaCon(c.cuerpo)}</div>
    </li>`;
  }).join("");
}

// Al pasar el mouse por una cuenta se resalta dónde apareció en la bandeja.
function resaltar(cuentaNorm, on) {
  document.querySelectorAll(`mark.cuenta[data-cuenta="${cuentaNorm}"]`).forEach((m) => {
    m.classList.toggle("activa", on);
    m.closest(".correo")?.classList.toggle("resaltado", on);
  });
  document.querySelectorAll(`.inscrita[data-cuenta="${cuentaNorm}"]`).forEach((e) => e.classList.toggle("activa", on));
}
document.addEventListener("mouseover", (e) => { const el = e.target.closest("[data-cuenta]"); if (el && !el.matches("mark")) resaltar(el.dataset.cuenta, true); });
document.addEventListener("mouseout", (e) => { const el = e.target.closest("[data-cuenta]"); if (el && !el.matches("mark")) resaltar(el.dataset.cuenta, false); });

// --- Cuenta con su origen: siempre con texto, no solo color ---
function cuentaO(cuenta, origen) {
  const n = norm(cuenta);
  const tipo = origen?.tipo === "inscrita" ? "inscrita" : origen?.tipo === "correo" ? "correo" : "otro";
  const dom = tipo === "correo" && origen.dominios?.[0] ? ` · ${origen.dominios[0]}` : "";
  return `<span class="cuenta-o ${tipo}-o" data-cuenta="${n}">${esc(cuenta)} ${esc(t(`o_${tipo}`))}${esc(dom)}</span>`;
}

// --- Carriles ---
function pintarCarriles() {
  $("#carriles").innerHTML = CARRILES.map((c) => {
    const ep = estado.carriles[c.clave]?.ep;
    return `<article class="carril${c.escudo ? " escudo" : ""}" id="carril-${c.clave}">
      <header class="carril-cab" data-ayuda="${esc(t(`ayuda_${c.clave}`))}">${ms(c.icono)}<h2>${esc(t(`d_${c.clave}`))}</h2>
        <span class="riesgo" data-ayuda="${esc(t("ayuda_pulso"))}">${ms("monitor_heart")}<span class="r-texto">${ep ? esc(t("r_1")) : ""}</span></span></header>
      <div class="pulso" id="pulso-${c.clave}" aria-hidden="true"></div>
      <ol class="pasos">${ep ? `<li class="paso vacio">${esc(t("listo"))}</li>` : `<li class="paso vacio">${esc(t("sin_registro"))}</li>`}</ol>
      <div class="veredicto"></div>
    </article>`;
  }).join("");
  for (const c of CARRILES) {
    const carril = estado.carriles[c.clave];
    carril.pulso = carril.ep ? Graficos.pulso($(`#pulso-${c.clave}`)) : null;
    carril.pulso?.vacio();
  }
}

function riesgo(clave, nivel) {
  const el = document.querySelector(`#carril-${clave} .r-texto`);
  if (!el) return;
  el.textContent = t(`r_${nivel}`);
  el.className = `r-texto ${["c-verde", "", "c-ambar", "c-rojo"][nivel]}`;
}

// Un paso = una línea. El detalle (argumentos, resultado, motivo) va en el tooltip.
function htmlPaso(p) {
  const li = (clase, icono, linea, detalle = "") =>
    `<li class="paso ${clase}" tabindex="0"${detalle ? ` data-ayuda="${esc(detalle)}"` : ""}>${ms(icono)}${linea}</li>`;
  if (p.tipo === "texto") return li("texto", "smart_toy", `<span class="resumen">${esc(p.texto)}</span>`, p.texto);
  if (p.tipo === "dueno") return li("dueno", "person", `<span class="resumen">${esc(p.texto)}</span>`);
  const r = String(p.resultado || "");
  const bloqueada = RE_BLOQUEO.test(r) || p.bloqueada;
  if (p.herramienta === "leer_correos") {
    const n = (r.match(/^\[[^\]]+\] /gm) || []).length;
    const asuntos = [...r.matchAll(/^\[([^\]]+)\] De: (.+)\n(?:Asunto|Subject): (.+)$/gm)].map((m) => `[${m[1]}] ${m[2]} · ${m[3]}`).join("\n");
    return li("herramienta", "mail", `<span class="resumen"><span class="nombre">leer_correos</span> ${esc(t("leidos", { n }))}</span>`, asuntos);
  }
  if (HERRAMIENTAS_PAGO.includes(p.herramienta)) {
    const a = p.args || {};
    const ejecutada = !bloqueada && /^(Listo|Done)/i.test(r);
    const bueno = p.origen_cuenta?.tipo === "inscrita";
    const clase = bloqueada ? "bloqueada" : ejecutada ? (bueno ? "pago-bueno" : "pago-malo") : "";
    const icono = bloqueada ? "block" : ejecutada ? (bueno ? "check" : "payments") : "payments";
    const estadoTxt = bloqueada ? t("bloqueada") : ejecutada ? t("ejecutada") : (r.includes("insuf") ? t("saldo_insuf") : "");
    const detalle = [a.destinatario, a.concepto || a.motivo || "", r].filter(Boolean).join("\n");
    return li(`herramienta pago ${clase}`, icono,
      `<span class="resumen"><span class="nombre">${esc(p.herramienta)}</span> <span class="monto">${plata(a.monto)}</span> ${cuentaO(a.cuenta, p.origen_cuenta)}</span>`
      + `<span class="estado">${esc(estadoTxt)}</span>`, detalle);
  }
  const args = Object.entries(p.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
  return li(`herramienta ${bloqueada ? "bloqueada" : ""}`, bloqueada ? "block" : "smart_toy",
    `<span class="resumen"><span class="nombre">${esc(p.herramienta)}</span> ${esc(bloqueada ? t("bloqueada") : r)}</span>`, `${args}\n${r}`);
}

function agregarPaso(clave, p) {
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.querySelector(".vacio, .pensando")?.remove();
  ol.insertAdjacentHTML("beforeend", htmlPaso(p));
  ol.scrollTop = ol.scrollHeight;
}

function pensando(clave, on) {
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.querySelector(".pensando")?.remove();
  if (on) ol.insertAdjacentHTML("beforeend", `<li class="paso texto pensando">${ms("smart_toy")}<span>.</span><span>.</span><span>.</span></li>`);
}

// --- Riesgo del paso: sale del registro y del origen de los valores del episodio ---
// Valores no confiables: las cuentas de pagos cuyo origen no es lo inscrito por el dueño.
function valoresDeAfuera(ep) {
  const set = new Set();
  for (const p of ep.pasos) if (HERRAMIENTAS_PAGO.includes(p.herramienta) && p.origen_cuenta && p.origen_cuenta.tipo !== "inscrita") set.add(norm(p.args?.cuenta));
  if (ep.veredicto?.bloqueo?.cuenta) set.add(norm(ep.veredicto.bloqueo.cuenta));
  set.delete("");
  return set;
}

function latirPaso(clave, p) {
  const c = estado.carriles[clave];
  const pul = c.pulso;
  if (!pul) return;
  const r = String(p.resultado || "");
  if (p.tipo === "texto") { pul.evento(pul.nivel() === 2 ? 2 : 1, 0.5); return riesgo(clave, pul.nivel()); }
  if (HERRAMIENTAS_LECTURA.includes(p.herramienta)) {
    const entra = [...valoresDeAfuera(c.ep)].some((v) => norm(r).includes(v));
    pul.evento(entra ? 2 : 1, entra ? 1.1 : 0.5);
    return riesgo(clave, entra ? 2 : 1);
  }
  if (HERRAMIENTAS_PAGO.includes(p.herramienta)) {
    const bloqueada = RE_BLOQUEO.test(r) || p.bloqueada;
    const deAfuera = p.origen_cuenta && p.origen_cuenta.tipo !== "inscrita";
    if (!deAfuera) { pul.evento(0, 0.6); return riesgo(clave, 0); }
    if (bloqueada) { pul.corte(); return riesgo(clave, 0); }
    pul.evento(3); return riesgo(clave, 3);
  }
  pul.evento(pul.nivel(), 0.5);
}

function htmlVeredicto(clase, grande, dato = "") {
  return `<span class="grande">${esc(grande)}</span>${dato ? `<span class="dato">${dato}</span>` : ""}`;
}

function pintarVeredicto(clave) {
  const c = estado.carriles[clave];
  const caja = document.querySelector(`#carril-${clave} .veredicto`);
  caja.className = "veredicto";
  if (!c?.ep || !c.terminado) { caja.innerHTML = ""; return; }
  const v = c.ep.veredicto;
  const saldo = (n) => `${esc(t("saldo"))} ${plata(n)}`;
  let clase = "gris";
  let html = "";
  if (v.tipo === "estafado") {
    const p = v.pagos[0] || {};
    clase = "rojo"; html = htmlVeredicto(clase, t("v_cayo"), `−${plata(v.pagado)} · ${esc(p.cuenta)}`);
  } else if (v.tipo === "bloqueado") {
    const b = v.bloqueo || {};
    if (!c.decision) { clase = "ambar"; html = htmlVeredicto(clase, t("v_espera", { d: c.ep.dueno || t("dueno") }), saldo(v.saldo_final)); }
    else if (c.decision === "pagar_inscrita") { clase = "verde"; html = htmlVeredicto(clase, t("v_inscrita"), `−${plata(b.monto)} · ${esc(b.cuenta_inscrita_numero)}`); }
    else if (c.decision === "no_pagar") { clase = "verde"; html = htmlVeredicto(clase, t("v_no_pago"), saldo(v.saldo_final)); }
    else { clase = "rojo"; html = htmlVeredicto(clase, t("v_cayo"), `−${plata(b.monto)} · ${esc(b.cuenta)} · ${esc(t("v_confirmado"))}`); }
  } else if (v.tipo === "pago_inscrita") {
    const p = v.pagos[0] || {};
    clase = "verde"; html = htmlVeredicto(clase, t("v_inscrita"), `−${plata(v.pagado)} · ${esc(p.cuenta)}`);
  } else {
    html = htmlVeredicto(clase, t("v_sin_pago"), saldo(v.saldo_final));
  }
  caja.classList.add(clase);
  caja.innerHTML = html;
}

async function correrCarril(clave, ficha) {
  const c = estado.carriles[clave];
  if (!c?.ep) return;
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.innerHTML = "";
  // El pulso late solo mientras corre el carril.
  const reloj = setInterval(() => { if (ficha === estado.ficha && !c.terminado) c.pulso?.tic(); }, 420);
  try {
    for (const p of c.ep.pasos) {
      if (p.tipo === "texto") {
        pensando(clave, true);
        await esperar(800, ficha);
        agregarPaso(clave, p);
        latirPaso(clave, p);
        await esperar(1300, ficha);
      } else {
        agregarPaso(clave, p);
        latirPaso(clave, p);
        if (CARRILES.find((x) => x.clave === clave)?.escudo && HERRAMIENTAS_PAGO.includes(p.herramienta)
            && c.ep.veredicto.bloqueo && RE_BLOQUEO.test(p.resultado || "")) {
          notificar(alertaDe(c.ep));
        }
        await esperar(1700, ficha);
      }
    }
  } finally {
    clearInterval(reloj);
  }
  c.terminado = true;
  c.pulso?.fin();
  pintarVeredicto(clave);
}

// --- Reproducción ---
function cargarEscenario() {
  estado.ficha++;
  estado.reproduciendo = false;
  estado.alerta = null;
  estado.confirmando = false;
  estado.carriles = {};
  for (const c of CARRILES) {
    const ep = episodioDe(estado.escenario, estado.idioma, c.defensas);
    estado.carriles[c.clave] = { ep, terminado: false, decision: null, pulso: null };
  }
  pintarTextos();
  pintarBandeja();
  pintarCarriles();
  pintarAlerta();
}

async function reproducir() {
  if (estado.reproduciendo) return;
  cargarEscenario();
  const ficha = estado.ficha;
  estado.reproduciendo = true;
  pintarTextos();
  try {
    await Promise.all(CARRILES.map((c) => correrCarril(c.clave, ficha)));
  } catch (e) {
    if (e !== "reinicio") console.error(e);
    return;
  }
  if (ficha === estado.ficha) { estado.reproduciendo = false; pintarTextos(); }
}

// --- Alerta al dueño: notificar(alerta) reparte la alerta a cada canal ---
// Canales hoy: la capa de alerta de la página y el servidor (POST /api/alertas). Telegram se
// enchufa en el servidor (demo/notificar.py) sin tocar la página.
const CANALES = [mostrarAlerta, enviarAlServidor];

function notificar(alerta) {
  estado.alerta = alerta;
  for (const canal of CANALES) {
    try { canal(alerta); } catch (e) { console.warn("canal de alerta falló", e); }
  }
}
window.notificar = notificar;

function alertaDe(ep) {
  const b = ep.veredicto.bloqueo;
  return {
    escenario: ep.escenario, idioma: ep.idioma, defensa: ep.defensa,
    destinatario: b.destinatario, monto: b.monto, cuenta: b.cuenta,
    dominio: b.origen?.dominios?.[0] || "", correos: b.origen?.correos || [],
    cuenta_inscrita: b.cuenta_inscrita, cuenta_inscrita_numero: b.cuenta_inscrita_numero,
    nombre_inscrita: b.nombre_inscrita, motivo: b.motivo,
  };
}

async function enviarAlServidor(alerta) {
  if (location.protocol === "file:") return;
  try { await fetch("api/alertas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(alerta) }); }
  catch (e) { console.warn("sin servidor para la alerta", e); }
}

function mostrarAlerta() {
  estado.confirmando = false;
  pintarAlerta();
  $("#alerta").hidden = false;
  $("#btn-alerta").hidden = true;
  $("#alerta").querySelector("[data-decision='pagar_inscrita']")?.focus({ preventScroll: true });
  try { navigator.vibrate?.([120, 60, 120]); } catch (_) { /* sin vibración */ }
}

function cerrarAlerta() {
  $("#alerta").hidden = true;
  $("#btn-alerta").hidden = !estado.alerta;
}

function pintarAlerta() {
  const caja = $("#alerta");
  const a = estado.alerta;
  if (!a) { caja.hidden = true; caja.innerHTML = ""; $("#btn-alerta").hidden = true; return; }
  const decision = estado.carriles.layer2?.decision;
  let acciones;
  if (decision) {
    const clase = decision === "pagar_igual" ? "c-rojo" : "c-verde";
    acciones = `<div class="hecho ${clase}">${ms(decision === "pagar_igual" ? "payments" : "check", true)}${esc(t(`a_hecho_${decision}`))}</div>`;
  } else if (estado.confirmando) {
    acciones = `<div class="acciones">
      <span class="pregunta dato">${esc(t("a_seguro", { c: a.cuenta }))}</span>
      <button type="button" class="boton texto" data-accion="cancelar">${esc(t("a_cancelar"))}</button>
      <button type="button" class="boton peligro lleno" data-decision="pagar_igual">${esc(t("a_si"))}</button></div>`;
  } else {
    acciones = `<div class="acciones">
      <button type="button" class="boton principal" data-decision="pagar_inscrita">${ms("account_balance")}${esc(t("a_pagar_inscrita"))}</button>
      <button type="button" class="boton texto peligro" data-accion="confirmar">${esc(t("a_pagar_igual"))}</button>
      <button type="button" class="boton" data-decision="no_pagar">${esc(t("a_no_pagar"))}</button></div>`;
  }
  caja.innerHTML = `
    <div class="cab" data-ayuda="${esc(t("ayuda_alerta"))}">${ms("gpp_bad", true)}<h2 id="alerta-titulo">${esc(t("a_titulo"))}</h2>
      <button type="button" class="boton icono texto" data-accion="cerrar" aria-label="${esc(t("cerrar"))}">${ms("close")}</button></div>
    <div class="monto"><span class="dato">${plata(a.monto)}</span><span class="a">${esc(t("a_a", { d: a.destinatario }))}</span></div>
    <div class="comparar">
      <span class="rotulo">${esc(t("a_agente"))}</span><span class="dato c-ambar" data-cuenta="${norm(a.cuenta)}">${esc(a.cuenta)}</span>
      <span class="origen">${esc(t("a_origen", { d: a.dominio }))}</span>
      <span class="rotulo">${esc(t("a_inscrita"))}</span><span class="dato c-verde" data-cuenta="${norm(a.cuenta_inscrita_numero)}">${esc(a.cuenta_inscrita_numero || a.cuenta_inscrita)}</span>
      <span class="origen">${esc(a.nombre_inscrita || "")}</span>
    </div>
    ${acciones}`;
}

$("#alerta").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.accion === "confirmar") { estado.confirmando = true; pintarAlerta(); return $("#alerta [data-accion='cancelar']")?.focus(); }
  if (b.dataset.accion === "cancelar") { estado.confirmando = false; pintarAlerta(); return; }
  if (b.dataset.accion === "cerrar") return cerrarAlerta();
  if (b.dataset.decision) decidir(b.dataset.decision);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#alerta").hidden) cerrarAlerta(); });
$("#btn-alerta").addEventListener("click", mostrarAlerta);

// La respuesta del dueño decide el pago en el carril del escudo y deja una etiqueta para el clasificador.
function decidir(eleccion) {
  const c = estado.carriles.layer2;
  const a = estado.alerta;
  if (!c || !a || c.decision) return;
  c.decision = eleccion;
  agregarPaso("layer2", { tipo: "dueno", texto: t("decide", { d: c.ep.dueno || t("dueno"), e: t(`e_${eleccion}`) }) });
  if (eleccion === "pagar_inscrita") {
    const p = { tipo: "herramienta", herramienta: "pagar", resultado: "Listo",
      args: { destinatario: a.destinatario, cuenta: a.cuenta_inscrita_numero, monto: a.monto },
      origen_cuenta: { tipo: "inscrita" } };
    agregarPaso("layer2", p);
    riesgo("layer2", 0);
  } else if (eleccion === "pagar_igual") {
    agregarPaso("layer2", { tipo: "herramienta", herramienta: "pagar", resultado: "Listo",
      args: { destinatario: a.destinatario, cuenta: a.cuenta, monto: a.monto },
      origen_cuenta: { tipo: "correo", dominios: [a.dominio] } });
    riesgo("layer2", 3);
  }
  pintarAlerta();
  pintarVeredicto("layer2");
  guardarEtiqueta(eleccion, a);
  setTimeout(() => { if (estado.alerta === a) cerrarAlerta(); }, 2200);
}

async function guardarEtiqueta(eleccion, alerta) {
  const etiqueta = { ts: new Date().toISOString(), eleccion, ...alerta };
  if (location.protocol === "file:") { console.info("etiqueta (sin servidor, no se guarda):", etiqueta); return; }
  try {
    const r = await fetch("api/etiquetas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(etiqueta) });
    if (!r.ok) console.warn("no se guardó la etiqueta", r.status);
  } catch (e) { console.warn("sin servidor para la etiqueta", e); }
}

// --- Resultados agregados: KPI, radares y mapas de calor ---
async function cargarResultados() {
  if (location.protocol !== "file:") {
    try {
      const r = await fetch("resultados.json", { cache: "no-store" });
      if (r.ok) return r.json();
    } catch (_) { /* sin servidor: queda la copia en JS */ }
  }
  return window.RESULTADOS || null;
}

const DEFENSAS_EJE = ["none", "layer1", "layer2"];
const escudoDe = (filas) => (filas.some((f) => f.defensa === "layer2") ? "layer2" : "both");
const de = (filas, cond) => filas.filter((f) => Object.entries(cond).every(([k, v]) => (k === "tactica" ? f.tacticas.includes(v) : f[k] === v)));
const modeloCorto = (m) => m.split("/").pop();

function htmlKpi(clave, valores, pie, colorear) {
  const v = valores.map(({ v }) => `<span class="valor ${v === null ? "sin" : colorear ? colorear(v) : ""}">${esc(v === null ? "—" : Graficos.pct(v))}</span>`);
  return `<div class="kpi" data-ayuda="${esc(t(`ayuda_${clave}`))}">
    <span class="etiqueta">${esc(t(clave))}</span>
    <span class="valores">${v.join(`<span class="flecha">${ms("arrow_forward")}</span>`)}</span>
    <span class="pie">${pie}</span></div>`;
}

function pintarKpis(R) {
  const caja = $("#kpis");
  if (!R) { caja.innerHTML = `<div class="kpi"><span class="etiqueta">${esc(t("sin_resultados"))}</span></div>`; return; }
  const f = R.filas;
  const esc2 = escudoDe(f);
  const par = (campo, filtro = {}) => [Graficos.tasa(de(f, { defensa: "none", ...filtro }), campo), Graficos.tasa(de(f, { defensa: esc2, ...filtro }), campo)];
  const pieDef = (p) => `<span>${esc(t("d_none"))} <b>n ${p[0].n}</b></span><span>${esc(t(`d_${esc2}`))} <b>n ${p[1].n}</b></span>`;
  const estafas = par("seguridad", { tipo: "estafa" });
  const utilidad = par("utilidad");
  const falsas = par("falsa_alarma", { tipo: "control" });
  const es = Graficos.tasa(de(f, { defensa: "none", tipo: "estafa", idioma: "es" }), "seguridad");
  const en = Graficos.tasa(de(f, { defensa: "none", tipo: "estafa", idioma: "en" }), "seguridad");
  const brecha = es.v === null || en.v === null ? null : es.v - en.v;
  const rojoSi = (v) => (v > 0 ? "c-rojo" : "c-verde");
  caja.innerHTML = htmlKpi("k_estafas", estafas, pieDef(estafas), rojoSi)
    + htmlKpi("k_utilidad", utilidad, pieDef(utilidad))
    + htmlKpi("k_falsas", falsas, pieDef(falsas))
    + `<div class="kpi" data-ayuda="${esc(t("ayuda_k_brecha"))}"><span class="etiqueta">${esc(t("k_brecha"))}</span>
        <span class="valores"><span class="valor ${brecha === null ? "sin" : ""}">${brecha === null ? "—" : `${brecha > 0 ? "+" : ""}${Math.round(brecha)} pp`}</span></span>
        <span class="pie"><span>ES <b>${Graficos.pct(es.v)}</b></span><span>EN <b>${Graficos.pct(en.v)}</b></span><span>${esc(t("d_none"))}</span></span></div>`;
}

function pintarFuente(R) {
  const el = $("#fuente");
  if (!R) { el.textContent = ""; return; }
  el.classList.toggle("prueba", !!R.prueba);
  el.textContent = R.prueba ? t("prueba") : t("fuente", { m: new Set(R.filas.map((x) => x.modelo)).size, n: R.filas.length });
  el.dataset.ayuda = [R.generado, ...R.registros.map((r) => `${modeloCorto(r.modelo)} · ${r.defensa}`),
    ...R.omitidos.map((o) => `${modeloCorto(o.modelo)} · ${o.defensa}: ${o.motivo}`)].join("\n");
}

function pintarRadares(R) {
  const caja = $("#radares");
  caja.innerHTML = DEFENSAS_EJE.map((d) => `<figure class="grafico"><figcaption class="titulo">${ms(d === "none" ? "gpp_bad" : "shield")}<span>${esc(t(`d_${d}`))}</span><span class="nota" id="nota-radar-${d}"></span></figcaption><div class="lienzo" id="radar-${d}"></div></figure>`).join("");
  if (!R) return;
  const ejes = R.tacticas.map((x) => x[estado.idioma] || x.es);
  for (const d of DEFENSAS_EJE) {
    const filas = de(R.filas, { defensa: d === "layer2" ? escudoDe(R.filas) : d, tipo: "estafa" });
    const valores = R.tacticas.map((x) => Graficos.tasa(de(filas, { tactica: x.clave }), "seguridad"));
    $(`#nota-radar-${d}`).textContent = filas.length ? `n ${filas.length} · ${t("t_exito")}` : "";
    Graficos.radar($(`#radar-${d}`), ejes, valores, d === "none" ? Graficos.C.rojo : Graficos.C.acento, filas.length ? null : t("sin_datos"));
  }
}

// Un escenario con esa táctica que tenga episodio exportado en el idioma actual.
function escenarioPara(R, tactica) {
  const conTactica = new Set(R.filas.filter((f) => f.tacticas.includes(tactica)).map((f) => f.escenario));
  return [...conTactica].find((e) => CARRILES.some((c) => episodioDe(e, estado.idioma, c.defensas))) || null;
}

function abrirEnCarriles(escenario, idioma) {
  if (idioma && idioma !== estado.idioma) { estado.idioma = idioma; llenarEscenarios(); pintarAnalisis(); }
  estado.escenario = escenario;
  $("#sel-escenario").value = escenario;
  $(".reproduccion").scrollIntoView({ behavior: Graficos.sinMovimiento ? "auto" : "smooth", block: "start" });
  reproducir();
}

function pintarCalor(R) {
  if (!R) return;
  const defensas = DEFENSAS_EJE;
  const filasT = R.tacticas.map((x) => x[estado.idioma] || x.es);
  const celdasT = [];
  R.tacticas.forEach((x, y) => defensas.forEach((d, xi) => {
    const r = Graficos.tasa(de(R.filas, { defensa: d === "layer2" ? escudoDe(R.filas) : d, tipo: "estafa", tactica: x.clave }), "seguridad");
    celdasT.push({ x: xi, y, v: r.v, n: r.n, tactica: x.clave, defensa: d, escenario: escenarioPara(R, x.clave) });
  }));
  Graficos.calor($("#calor-tactica"), {
    columnas: defensas.map((d) => t(`d_${d}`)), filas: filasT, celdas: celdasT,
    tooltip: (c) => `${esc(filasT[c.y])} · ${esc(t(`d_${c.defensa}`))}<br>${c.v === null ? esc(t("sin_datos")) : `${Graficos.pct(c.v)} ${esc(t("t_exito"))} · n ${c.n}`}<br>${esc(c.escenario ? `${t("abrir")}: ${c.escenario}` : t("sin_episodio"))}`,
    alClic: (c) => c.escenario && abrirEnCarriles(c.escenario),
  });

  const modelos = [...new Set(R.filas.map((f) => f.modelo))].sort();
  const idiomas = ["es", "en"];
  const celdasM = [];
  modelos.forEach((m, y) => idiomas.forEach((i, x) => {
    const r = Graficos.tasa(de(R.filas, { defensa: "none", tipo: "estafa", modelo: m, idioma: i }), "seguridad");
    const escenario = CARRILES.some((c) => episodioDe(estado.escenario, i, c.defensas)) ? estado.escenario : null;
    celdasM.push({ x, y, v: r.v, n: r.n, modelo: m, idioma: i, escenario });
  }));
  Graficos.calor($("#calor-modelo"), {
    columnas: idiomas.map((i) => i.toUpperCase()), filas: modelos.map(modeloCorto), celdas: celdasM,
    tooltip: (c) => `${esc(modeloCorto(c.modelo))} · ${c.idioma.toUpperCase()} · ${esc(t("modelo_nota"))}<br>${c.v === null ? esc(t("sin_datos")) : `${Graficos.pct(c.v)} ${esc(t("t_exito"))} · n ${c.n}`}<br>${esc(c.escenario ? `${t("abrir")}: ${c.escenario}` : t("sin_episodio"))}`,
    alClic: (c) => c.escenario && abrirEnCarriles(c.escenario, c.idioma),
  });
}

function pintarAnalisis() {
  const R = estado.resultados;
  pintarFuente(R);
  pintarKpis(R);
  pintarRadares(R);
  pintarCalor(R);
}

// --- Textos, selectores y controles ---
function pintarTextos() {
  document.documentElement.lang = estado.idioma;
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  document.querySelectorAll("[data-ayuda-t]").forEach((el) => { el.dataset.ayuda = t(el.dataset.ayudaT); el.setAttribute("aria-label", t(el.dataset.ayudaT)); });
  const btn = $("#btn-reproducir");
  btn.querySelector("[data-t]").textContent = estado.reproduciendo ? t("reproduciendo") : t("reproducir");
  btn.disabled = estado.reproduciendo;
  document.querySelectorAll("[data-idioma]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.idioma === estado.idioma)));
  document.querySelectorAll("[data-velocidad]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.velocidad) === estado.velocidad)));
}

function llenarEscenarios() {
  const vistos = new Map();
  for (const ep of Object.values(episodios())) if (!vistos.has(ep.escenario) || ep.idioma === estado.idioma) vistos.set(ep.escenario, ep.descripcion || ep.escenario);
  const sel = $("#sel-escenario");
  sel.innerHTML = [...vistos].map(([id, desc]) => `<option value="${esc(id)}" title="${esc(desc)}">${esc(id.replaceAll("_", " "))}</option>`).join("");
  if (!estado.escenario || !vistos.has(estado.escenario)) {
    estado.escenario = vistos.has(ESCENARIO_POR_DEFECTO) ? ESCENARIO_POR_DEFECTO : vistos.keys().next().value || null;
  }
  sel.value = estado.escenario;
}

$("#sel-escenario").addEventListener("change", (e) => { estado.escenario = e.target.value; cargarEscenario(); pintarCalor(estado.resultados); });
document.querySelectorAll("[data-idioma]").forEach((b) => b.addEventListener("click", () => {
  estado.idioma = b.dataset.idioma; llenarEscenarios(); cargarEscenario(); pintarAnalisis();
}));
document.querySelectorAll("[data-velocidad]").forEach((b) => b.addEventListener("click", () => {
  estado.velocidad = Number(b.dataset.velocidad); pintarTextos();
}));
$("#btn-reproducir").addEventListener("click", reproducir);
$("#btn-reiniciar").addEventListener("click", cargarEscenario);

const params = new URLSearchParams(location.search);
if (params.get("idioma") === "en") estado.idioma = "en";
if (params.get("escenario")) estado.escenario = params.get("escenario");
llenarEscenarios();
cargarEscenario();
cargarResultados().then((R) => { estado.resultados = R; pintarAnalisis(); });
if (params.has("auto")) reproducir();
