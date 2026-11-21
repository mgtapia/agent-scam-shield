// Demo de agent-scam-shield: reproduce los episodios exportados de Inspect en tres carriles.
// Sin build: los episodios llegan en window.EPISODIOS (episodios/episodios.js, generado por
// scripts/exportar_episodios.py), así la página se abre también como archivo, sin servidor.
"use strict";

const CARRILES = [
  { clave: "none", defensas: ["none"] },
  { clave: "layer1", defensas: ["layer1"] },
  { clave: "layer2", defensas: ["layer2", "both"], escudo: true },
];

const T = {
  es: {
    lema: "La misma estafa contra el mismo agente, con tres defensas distintas",
    escenario: "Escenario", reproducir: "▶ Reproducir", reproduciendo: "⏸ Reproduciendo…", reiniciar: "↺ Reiniciar",
    bandeja: "Bandeja", inscritas: "Tus cuentas inscritas", correos: "Correos", leyenda_celular: "El celular del dueño",
    encargo_de: "Encargo de {dueno} · del dueño",
    carril_none: ["Sin defensa", "El agente hace lo que lee"],
    carril_layer1: ["Firewall conocido", "Reglas contra inyección técnica, como Pipelock"],
    carril_layer2: ["Nuestro escudo", "Revisa de dónde salió cada cuenta"],
    listo_para: "Listo para reproducir", sin_registro: "No hay registro de esta configuración.",
    de_correo: "de un correo", tu_inscrita: "tu cuenta inscrita", desconocida: "no aparece en ningún lado",
    aviso_dominio: "⚠ dominio distinto de {d}", aviso_cuenta: "⚠ cuenta nueva",
    destinatario: "a", cuenta: "cuenta", leidos: "{n} correos leídos",
    bloqueada: "⛔ Bloqueada por la defensa", ejecutada: "Pago ejecutado", saldo_insuf: "Saldo insuficiente",
    v_estafado: "❌ Pagaste al estafador",
    v_bloqueado: "⛔ Bloqueado: la cuenta venía de un correo, no de tus cuentas",
    v_inscrita: "✅ Pagaste a la cuenta inscrita",
    v_no_pago: "No se pagó: lo decidiste tú",
    v_sin_pago: "Sin pagos",
    v_esperando: "📱 Esperando al dueño. Sin respuesta, no se paga.",
    v_confirmado: "Lo confirmaste dos veces en el celular",
    saldo: "Saldo", saldo_intacto: "Saldo intacto",
    dueno_decide: "👤 El dueño respondió en el celular: {e}",
    e_pagar_inscrita: "pagar a la cuenta inscrita", e_no_pagar: "no pagar", e_pagar_igual: "pagar igual a la cuenta nueva",
    cel_reposo: "Sin alertas", cel_app: "Agent Scam Shield · ahora",
    cel_titulo: "🛡 Tu agente quiere pagar y algo no calza",
    cel_a: "a {d}", cel_cuenta_agente: "La cuenta que usó tu agente", cel_aparecio: "apareció en un correo de {d}",
    cel_tu_cuenta: "Tu cuenta inscrita",
    cel_pagar_inscrita: "Pagar a mi cuenta inscrita", cel_no_pagar: "No pagar",
    cel_pagar_igual: "Es la nueva cuenta, pagar igual",
    cel_seguro: "¿Seguro? Esa cuenta solo apareció en un correo. Si es una estafa, el dinero no vuelve.",
    cel_si: "Sí, pagar igual", cel_cancelar: "Cancelar",
    cel_nota: "Si no respondes, no se paga.",
    cel_hecho_pagar_inscrita: "✅ Pagado a tu cuenta inscrita", cel_hecho_no_pagar: "No se pagó",
    cel_hecho_pagar_igual: "Pagado a la cuenta nueva",
    locale: "es-CL",
  },
  en: {
    lema: "The same scam against the same agent, with three different defenses",
    escenario: "Scenario", reproducir: "▶ Play", reproduciendo: "⏸ Playing…", reiniciar: "↺ Reset",
    bandeja: "Inbox", inscritas: "Your registered accounts", correos: "Emails", leyenda_celular: "The owner's phone",
    encargo_de: "Request from {dueno} · from the owner",
    carril_none: ["No defense", "The agent does what it reads"],
    carril_layer1: ["Known firewall", "Technical-injection rules, like Pipelock"],
    carril_layer2: ["Our shield", "Checks where each account came from"],
    listo_para: "Ready to play", sin_registro: "No log for this configuration.",
    de_correo: "from an email", tu_inscrita: "your registered account", desconocida: "doesn't appear anywhere",
    aviso_dominio: "⚠ different domain from {d}", aviso_cuenta: "⚠ new account",
    destinatario: "to", cuenta: "account", leidos: "{n} emails read",
    bloqueada: "⛔ Blocked by the defense", ejecutada: "Payment sent", saldo_insuf: "Insufficient funds",
    v_estafado: "❌ You paid the scammer",
    v_bloqueado: "⛔ Blocked: the account came from an email, not from your accounts",
    v_inscrita: "✅ You paid your registered account",
    v_no_pago: "Not paid: your call",
    v_sin_pago: "No payments",
    v_esperando: "📱 Waiting for the owner. No answer, no payment.",
    v_confirmado: "You confirmed it twice on your phone",
    saldo: "Balance", saldo_intacto: "Balance untouched",
    dueno_decide: "👤 The owner answered on the phone: {e}",
    e_pagar_inscrita: "pay my registered account", e_no_pagar: "don't pay", e_pagar_igual: "pay the new account anyway",
    cel_reposo: "No alerts", cel_app: "Agent Scam Shield · now",
    cel_titulo: "🛡 Your agent wants to pay and something doesn't add up",
    cel_a: "to {d}", cel_cuenta_agente: "The account your agent used", cel_aparecio: "appeared in an email from {d}",
    cel_tu_cuenta: "Your registered account",
    cel_pagar_inscrita: "Pay my registered account", cel_no_pagar: "Don't pay",
    cel_pagar_igual: "It's the new account, pay anyway",
    cel_seguro: "Sure? That account only appeared in an email. If it's a scam, the money won't come back.",
    cel_si: "Yes, pay anyway", cel_cancelar: "Cancel",
    cel_nota: "No answer, no payment.",
    cel_hecho_pagar_inscrita: "✅ Paid to your registered account", cel_hecho_no_pagar: "Not paid",
    cel_hecho_pagar_igual: "Paid to the new account",
    locale: "en-US",
  },
};

const estado = {
  idioma: "es",
  escenario: null,
  velocidad: 1,
  ficha: 0,            // cambia en cada reinicio: los carriles viejos se detienen solos
  reproduciendo: false,
  carriles: {},        // clave -> { ep, mostrados, terminado, decision }
  alerta: null,
};

// --- Utilidades ---
const $ = (sel) => document.querySelector(sel);
const t = (clave, vars = {}) => {
  let s = (T[estado.idioma] || T.es)[clave] ?? T.es[clave] ?? clave;
  if (typeof s === "string") for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => String(s ?? "").toLowerCase().replace(/[^a-z0-9ñáéíóúü]/gi, "");
const plata = (n) => "$" + Number(n || 0).toLocaleString(t("locale"));
const RE_CUENTA = /\b\d{2}-\d{4}-\d{4}\b/g;

function episodios() { return window.EPISODIOS || {}; }

function episodioDe(escenario, idioma, defensas) {
  for (const d of defensas) {
    const ep = episodios()[`${escenario}__${idioma}__${d}`];
    if (ep) return ep;
  }
  return null;
}

function esperar(ms, ficha) {
  return new Promise((ok, no) => setTimeout(() => (ficha === estado.ficha ? ok() : no("reinicio")), ms / estado.velocidad));
}

// --- Bandeja ---
function cuentaCon(texto) {
  return esc(texto).replace(RE_CUENTA, (m) => `<mark class="cuenta" data-cuenta="${norm(m)}">${m}</mark>`);
}

function correosSospechosos(eps) {
  const ids = new Set();
  for (const ep of eps) for (const p of ep.pasos) if (p.origen_cuenta?.tipo === "correo") p.origen_cuenta.correos.forEach((c) => ids.add(c));
  return ids;
}

function pintarBandeja() {
  const eps = CARRILES.map((c) => estado.carriles[c.clave]?.ep).filter(Boolean);
  const ep = eps[0];
  if (!ep) { $("#encargo").innerHTML = ""; $("#inscritas").innerHTML = ""; $("#correos").innerHTML = ""; return; }
  $("#encargo").innerHTML = `<div class="encargo"><div class="quien">${esc(t("encargo_de", { dueno: ep.dueno }))}</div>${esc(ep.encargo)}</div>`;
  $("#inscritas").innerHTML = Object.entries(ep.cuentas_inscritas).map(([nombre, valor]) => {
    const num = (String(valor).match(RE_CUENTA) || [valor])[0];
    return `<span class="etiqueta verde" data-cuenta="${norm(num)}" data-inscrita="1">✓ ${esc(nombre)}: ${esc(valor)} <small>${esc(t("tu_inscrita"))}</small></span>`;
  }).join("") || "—";
  const sospechosos = correosSospechosos(eps);
  const dominiosBuenos = ep.correos.filter((c) => !sospechosos.has(c.id)).map((c) => c.dominio);
  $("#correos").innerHTML = ep.correos.map((c) => {
    const malo = sospechosos.has(c.id);
    const aviso = malo ? `<span class="aviso">${esc(dominiosBuenos.length ? t("aviso_dominio", { d: dominiosBuenos[0] }) : t("aviso_cuenta"))}</span>` : "";
    const [usuario] = c.de.split("@");
    return `<article class="correo${malo ? " estafa" : ""}" data-correo="${esc(c.id)}">
      <div class="de">${malo ? "⚠" : "✉"} ${esc(usuario)}@<span class="dominio">${esc(c.dominio)}</span>${aviso}</div>
      <div class="asunto">${esc(c.asunto)}</div>
      <div class="cuerpo">${cuentaCon(c.cuerpo)}</div>
    </article>`;
  }).join("");
}

// Al pasar el mouse por una cuenta se resalta dónde apareció en la bandeja.
function resaltar(cuentaNorm, on) {
  document.querySelectorAll(`mark.cuenta[data-cuenta="${cuentaNorm}"]`).forEach((m) => {
    m.classList.toggle("activa", on);
    m.closest(".correo")?.classList.toggle("resaltado", on);
  });
  document.querySelectorAll(`.inscritas [data-cuenta="${cuentaNorm}"]`).forEach((e) => {
    e.style.boxShadow = on ? "0 0 0 4px rgba(34,197,94,.4)" : "";
  });
}
document.addEventListener("mouseover", (e) => { const el = e.target.closest("[data-cuenta]"); if (el && !el.matches("mark")) resaltar(el.dataset.cuenta, true); });
document.addEventListener("mouseout", (e) => { const el = e.target.closest("[data-cuenta]"); if (el && !el.matches("mark")) resaltar(el.dataset.cuenta, false); });

// --- Etiqueta de origen de una cuenta: siempre con texto, no solo color ---
function etiquetaCuenta(cuenta, origen) {
  const n = norm(cuenta);
  if (origen?.tipo === "inscrita") return `<span class="etiqueta verde" data-cuenta="${n}">✓ ${esc(cuenta)} <small>${esc(t("tu_inscrita"))}</small></span>`;
  if (origen?.tipo === "correo") {
    const dom = origen.dominios?.[0] ? ` · ${esc(origen.dominios[0])}` : "";
    return `<span class="etiqueta naranjo" data-cuenta="${n}">✉ ${esc(cuenta)} <small>${esc(t("de_correo"))}${dom}</small></span>`;
  }
  return `<span class="etiqueta gris" data-cuenta="${n}">? ${esc(cuenta)} <small>${esc(t("desconocida"))}</small></span>`;
}

// --- Carriles ---
function pintarCarriles() {
  $("#carriles").innerHTML = CARRILES.map((c) => {
    const [nombre, sub] = t(`carril_${c.clave}`);
    const ep = estado.carriles[c.clave]?.ep;
    return `<article class="panel carril${c.escudo ? " escudo" : ""}" id="carril-${c.clave}">
      <header><h2>${c.escudo ? "🛡 " : ""}${esc(nombre)}</h2><p>${esc(sub)}</p></header>
      <ol class="pasos">${ep ? `<li class="escribiendo">${esc(t("listo_para"))}</li>` : `<li class="sin-registro">${esc(t("sin_registro"))}</li>`}</ol>
      <div class="veredictos"></div>
    </article>`;
  }).join("");
}

function htmlPaso(p) {
  if (p.tipo === "texto") return `<li class="paso texto"><span aria-hidden="true">🤖</span><div class="burbuja">${esc(p.texto)}</div></li>`;
  if (p.tipo === "dueno") return `<li class="paso dueno">${esc(p.texto)}</li>`;
  const r = String(p.resultado || "");
  const bloqueada = /^(ACCIÓN BLOQUEADA|ACTION BLOCKED)/i.test(r) || p.bloqueada;
  if (p.herramienta === "leer_correos") {
    const n = (r.match(/^\[[^\]]+\] /gm) || []).length;
    return `<li class="paso herramienta"><span class="nombre">📥 leer_correos()</span><div class="resultado ok">${esc(t("leidos", { n }))}</div></li>`;
  }
  if (p.herramienta === "pagar" || p.herramienta === "transferir") {
    const a = p.args || {};
    const ejecutada = !bloqueada && /^(Listo|Done)/i.test(r);
    const bueno = p.origen_cuenta?.tipo === "inscrita";
    const clase = bloqueada ? "bloqueada" : ejecutada ? (bueno ? "pago-bueno" : "pago-malo") : "";
    const resultado = bloqueada ? `<div class="resultado bloqueada">${esc(t("bloqueada"))}</div>`
      : ejecutada ? `<div class="resultado ejecutada${bueno ? " buena" : ""}">${bueno ? "✓" : "✗"} ${esc(t("ejecutada"))}</div>`
      : `<div class="resultado ok">${esc(r.includes("insuf") ? t("saldo_insuf") : r)}</div>`;
    return `<li class="paso herramienta ${clase}"><span class="nombre">💸 ${esc(p.herramienta)}()</span>
      <div class="datos">
        <div class="fila"><span class="monto">${plata(a.monto)}</span>${a.destinatario ? `<span>${esc(t("destinatario"))} <strong>${esc(a.destinatario)}</strong></span>` : ""}</div>
        <div class="fila">${etiquetaCuenta(a.cuenta, p.origen_cuenta)}</div>
      </div>${resultado}</li>`;
  }
  const args = Object.entries(p.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
  return `<li class="paso herramienta"><span class="nombre">🔧 ${esc(p.herramienta)}(${esc(args)})</span>
    <div class="resultado ${bloqueada ? "bloqueada" : "ok"}">${esc(bloqueada ? t("bloqueada") : r.slice(0, 140))}</div></li>`;
}

function agregarPaso(clave, p) {
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.querySelector(".escribiendo")?.remove();
  ol.insertAdjacentHTML("beforeend", htmlPaso(p));
}

function escribiendo(clave, on) {
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.querySelector(".escribiendo")?.remove();
  if (on) ol.insertAdjacentHTML("beforeend", `<li class="escribiendo">🤖 <span>●</span><span>●</span><span>●</span></li>`);
}

function htmlVeredicto(clase, grande, detalle = "") {
  return `<div class="veredicto ${clase}"><div class="grande">${esc(grande)}</div>${detalle ? `<div class="detalle">${detalle}</div>` : ""}</div>`;
}

function pintarVeredicto(clave) {
  const c = estado.carriles[clave];
  const caja = document.querySelector(`#carril-${clave} .veredictos`);
  if (!c?.ep || !c.terminado) { caja.innerHTML = ""; return; }
  const v = c.ep.veredicto;
  const saldo = (n) => `${esc(t("saldo"))}: <strong>${plata(n)}</strong>`;
  let html = "";
  if (v.tipo === "estafado") {
    const p = v.pagos[0] || {};
    html = htmlVeredicto("rojo", t("v_estafado"), `−${plata(v.pagado)} → ${esc(p.cuenta)} · ${saldo(v.saldo_final)}`);
  } else if (v.tipo === "bloqueado") {
    html = htmlVeredicto("verde", t("v_bloqueado"), `${esc(t("saldo_intacto"))}: <strong>${plata(v.saldo_final)}</strong>`);
    const b = v.bloqueo || {};
    if (!c.decision) html += htmlVeredicto("gris", t("v_esperando"));
    else if (c.decision === "pagar_inscrita") html += htmlVeredicto("verde", t("v_inscrita"), `−${plata(b.monto)} → ${esc(b.cuenta_inscrita_numero)} · ${saldo(v.saldo_final - b.monto)}`);
    else if (c.decision === "no_pagar") html += htmlVeredicto("gris", t("v_no_pago"), saldo(v.saldo_final));
    else if (c.decision === "pagar_igual") html += htmlVeredicto("rojo", t("v_estafado"), `${esc(t("v_confirmado"))} · −${plata(b.monto)} → ${esc(b.cuenta)} · ${saldo(v.saldo_final - b.monto)}`);
  } else if (v.tipo === "pago_inscrita") {
    const p = v.pagos[0] || {};
    html = htmlVeredicto("verde", t("v_inscrita"), `−${plata(v.pagado)} → ${esc(p.cuenta)} · ${saldo(v.saldo_final)}`);
  } else {
    html = htmlVeredicto("gris", t("v_sin_pago"), saldo(v.saldo_final));
  }
  caja.innerHTML = html;
}

async function correrCarril(clave, ficha) {
  const c = estado.carriles[clave];
  if (!c?.ep) return;
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.innerHTML = "";
  for (const p of c.ep.pasos) {
    if (p.tipo === "texto") {
      escribiendo(clave, true);
      await esperar(800, ficha);
      agregarPaso(clave, p);
      await esperar(1300, ficha);
    } else {
      agregarPaso(clave, p);
      if (CARRILES.find((x) => x.clave === clave)?.escudo && (p.herramienta === "pagar" || p.herramienta === "transferir")
          && c.ep.veredicto.bloqueo && /^(ACCIÓN BLOQUEADA|ACTION BLOCKED)/i.test(p.resultado || "")) {
        notificar(alertaDe(c.ep));
      }
      await esperar(1700, ficha);
    }
  }
  c.terminado = true;
  pintarVeredicto(clave);
}

// --- Reproducción ---
function cargarEscenario() {
  estado.ficha++;
  estado.reproduciendo = false;
  estado.alerta = null;
  estado.carriles = {};
  for (const c of CARRILES) {
    const ep = episodioDe(estado.escenario, estado.idioma, c.defensas);
    estado.carriles[c.clave] = { ep, terminado: false, decision: null };
  }
  pintarTextos();
  pintarBandeja();
  pintarCarriles();
  pintarCelular();
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
// Canales hoy: el celular dibujado y el servidor (POST /api/alertas). Telegram se enchufa en el
// servidor (demo/notificar.py) sin tocar la página.
const CANALES = [mostrarEnCelular, enviarAlServidor];

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

function mostrarEnCelular(alerta) {
  pintarCelular();
  const cel = $("#celular");
  cel.classList.remove("vibra"); void cel.offsetWidth; cel.classList.add("vibra");
  try { navigator.vibrate?.([120, 60, 120]); } catch (_) { /* sin vibración */ }
}

function pintarCelular(confirmando = false) {
  const caja = $("#cel-contenido");
  const a = estado.alerta;
  const escudo = estado.carriles.layer2;
  if (!a) {
    const ahora = new Date();
    caja.innerHTML = `<div class="reposo"><div class="hora">${ahora.getHours()}:${String(ahora.getMinutes()).padStart(2, "0")}</div><div class="sub">${esc(t("cel_reposo"))}</div></div>`;
    return;
  }
  const decision = escudo?.decision;
  let acciones;
  if (decision) {
    const clase = decision === "pagar_igual" ? "veredicto rojo" : decision === "pagar_inscrita" ? "veredicto verde" : "veredicto gris";
    acciones = `<div class="hecho ${clase}">${esc(t(`cel_hecho_${decision}`))}</div>`;
  } else if (confirmando) {
    acciones = `<div class="confirmar">${esc(t("cel_seguro"))}
      <div class="fila"><button class="boton peligro" data-decision="pagar_igual">${esc(t("cel_si"))}</button>
      <button class="boton" data-accion="cancelar">${esc(t("cel_cancelar"))}</button></div></div>`;
  } else {
    acciones = `<button class="boton principal" data-decision="pagar_inscrita">${esc(t("cel_pagar_inscrita"))}</button>
      <button class="boton" data-decision="no_pagar">${esc(t("cel_no_pagar"))}</button>
      <button class="enlace-riesgo" data-accion="confirmar">${esc(t("cel_pagar_igual"))}</button>
      <div class="nota">${esc(t("cel_nota"))}</div>`;
  }
  caja.innerHTML = `<div class="alerta" role="alertdialog" aria-label="${esc(t("cel_titulo"))}">
    <div class="app">${esc(t("cel_app"))}</div>
    <h3>${esc(t("cel_titulo"))}</h3>
    <div><div class="monto">${plata(a.monto)}</div><div>${esc(t("cel_a", { d: a.destinatario }))}</div></div>
    <div class="linea"><span class="rotulo">${esc(t("cel_cuenta_agente"))}</span>
      <span class="etiqueta naranjo" data-cuenta="${norm(a.cuenta)}">✉ ${esc(a.cuenta)} <small>${esc(t("cel_aparecio", { d: a.dominio }))}</small></span></div>
    <div class="linea"><span class="rotulo">${esc(t("cel_tu_cuenta"))}</span>
      <span class="etiqueta verde" data-cuenta="${norm(a.cuenta_inscrita_numero)}">✓ ${esc(a.cuenta_inscrita || a.cuenta_inscrita_numero)}</span></div>
    ${acciones}
  </div>`;
}

$("#cel-contenido").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.accion === "confirmar") return pintarCelular(true);
  if (b.dataset.accion === "cancelar") return pintarCelular(false);
  if (b.dataset.decision) decidir(b.dataset.decision);
});

// El botón del dueño decide el pago en el carril del escudo y deja una etiqueta para el clasificador.
function decidir(eleccion) {
  const c = estado.carriles.layer2;
  const a = estado.alerta;
  if (!c || !a || c.decision) return;
  c.decision = eleccion;
  agregarPaso("layer2", { tipo: "dueno", texto: t("dueno_decide", { e: t(`e_${eleccion}`) }) });
  if (eleccion === "pagar_inscrita") {
    agregarPaso("layer2", { tipo: "herramienta", herramienta: "pagar", resultado: "Listo",
      args: { destinatario: a.destinatario, cuenta: a.cuenta_inscrita_numero, monto: a.monto },
      origen_cuenta: { tipo: "inscrita" } });
  } else if (eleccion === "pagar_igual") {
    agregarPaso("layer2", { tipo: "herramienta", herramienta: "pagar", resultado: "Listo",
      args: { destinatario: a.destinatario, cuenta: a.cuenta, monto: a.monto },
      origen_cuenta: { tipo: "correo", dominios: [a.dominio] } });
  }
  pintarCelular();
  pintarVeredicto("layer2");
  guardarEtiqueta(eleccion, a);
}

async function guardarEtiqueta(eleccion, alerta) {
  const etiqueta = { ts: new Date().toISOString(), eleccion, ...alerta };
  if (location.protocol === "file:") { console.info("etiqueta (sin servidor, no se guarda):", etiqueta); return; }
  try {
    const r = await fetch("api/etiquetas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(etiqueta) });
    if (!r.ok) console.warn("no se guardó la etiqueta", r.status);
  } catch (e) { console.warn("sin servidor para la etiqueta", e); }
}

// --- Textos, selectores y controles ---
function pintarTextos() {
  document.documentElement.lang = estado.idioma;
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  $("#btn-reproducir").textContent = estado.reproduciendo ? t("reproduciendo") : t("reproducir");
  $("#btn-reproducir").disabled = estado.reproduciendo;
  document.querySelectorAll("[data-idioma]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.idioma === estado.idioma)));
  document.querySelectorAll("[data-velocidad]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.velocidad) === estado.velocidad)));
}

function llenarEscenarios() {
  const vistos = new Map();
  for (const ep of Object.values(episodios())) if (!vistos.has(ep.escenario) || ep.idioma === estado.idioma) vistos.set(ep.escenario, ep.descripcion || ep.escenario);
  const sel = $("#sel-escenario");
  sel.innerHTML = [...vistos].map(([id, desc]) => `<option value="${esc(id)}" title="${esc(desc)}">${esc(id.replaceAll("_", " "))}</option>`).join("");
  if (!estado.escenario || !vistos.has(estado.escenario)) estado.escenario = vistos.keys().next().value || null;
  sel.value = estado.escenario;
}

$("#sel-escenario").addEventListener("change", (e) => { estado.escenario = e.target.value; cargarEscenario(); });
document.querySelectorAll("[data-idioma]").forEach((b) => b.addEventListener("click", () => {
  estado.idioma = b.dataset.idioma; llenarEscenarios(); cargarEscenario();
}));
document.querySelectorAll("[data-velocidad]").forEach((b) => b.addEventListener("click", () => {
  estado.velocidad = Number(b.dataset.velocidad); pintarTextos();
}));
$("#btn-reproducir").addEventListener("click", reproducir);
$("#btn-reiniciar").addEventListener("click", cargarEscenario);

const params = new URLSearchParams(location.search);
if (params.get("idioma") === "en") estado.idioma = "en";
llenarEscenarios();
if (params.get("escenario")) estado.escenario = params.get("escenario");
cargarEscenario();
if (params.has("auto")) reproducir();
