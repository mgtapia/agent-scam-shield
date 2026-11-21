// Grifter, demo: reproduce los episodios exportados de Inspect en tres carriles (vista Episodios) y carga
// los números de la vista Resultados (resultados.json, de scripts/resultados_demo.py; los dibuja resultados_vista.js). Sin build: los episodios llegan en
// window.EPISODIOS (episodios/episodios.js, de scripts/exportar_episodios.py) y los resultados en
// resultados.json (o window.RESULTADOS si la página se abre como archivo; scripts/exportar_resultados.py).
"use strict";

// El escenario que abre la demo. Si no hay episodios de ese escenario, abre el primero que haya.
// ?escenario=<id> en la URL manda sobre esto.
const ESCENARIO_POR_DEFECTO = "demo_microprocesadores";

const CARRILES = [
  { clave: "none", defensas: ["none"], icono: "gpp_bad" },
  { clave: "layer1", defensas: ["layer1"], icono: "shield" },
  { clave: "layer2", defensas: ["layer2", "both"], icono: "shield", escudo: true },
];
const VISTAS = ["operaciones", "vivo", "resultados", "duelo"];
const HERRAMIENTAS_PAGO = ["pagar", "transferir"];
const HERRAMIENTAS_LECTURA = ["leer_correos", "abrir_web", "usar_mcp"];
const RE_BLOQUEO = /^(ACCIÓN BLOQUEADA|ACTION BLOCKED)/i;

const T = {
  es: {
    v_operaciones: "Operaciones", v_vivo: "Episodios", ayuda_v_vivo: "Episodios exportados de Inspect. «Datos de prueba» marca los carriles corridos con mockllm", desde_ops: "Visto en Operaciones", ayuda_desde_ops: "Este escenario es el de la última estafa con episodio que vio Operaciones ({id})", v_resultados: "Resultados", v_duelo: "Duelo", ayuda_v_duelo: "Un hacker que aprende de cómo lo bloqueamos, contra el escudo congelado y contra el que aprende de él",
    escenario: "Escenario", reproducir: "Reproducir", reproduciendo: "Reproduciendo", reiniciar: "Reiniciar",
    correos: "Correos", calor_tactica: "Táctica × defensa", calor_modelo: "Modelo × idioma",
    d_none: "Sin defensa", d_layer1: "Firewall", d_layer2: "Escudo", d_both: "Firewall + escudo", d_layer2_approver: "Escudo (approver)",
    ayuda_none: "El agente hace lo que lee",
    ayuda_layer1: "Reglas contra inyección técnica, como Pipelock",
    ayuda_layer2: "Revisa de dónde salió cada cuenta antes de pagar",
    dueno: "Dueña", monto: "Monto", inscrita: "inscrita", externo: "externo", sin_inscritas: "Sin cuentas inscritas",
    sin_registro: "Sin registro", listo: "Listo",
    ayuda_externo: "Esta cuenta salió de un correo, no de las cuentas inscritas",
    leidos: "{n} leídos", bloqueada: "Bloqueado", ejecutada: "Pagado", saldo_insuf: "Sin saldo",
    v_cayo: "Cayó", v_bloqueado: "Bloqueado", v_inscrita: "Pagó inscrita", v_no_pago: "No pagó",
    v_sin_pago: "Sin pagos", v_espera: "Espera a {d}", v_confirmado: "confirmado 2 veces",
    saldo: "saldo", decide: "{d}: {e}",
    e_pagar_inscrita: "pagar a la inscrita", e_no_pagar: "no pagar", e_pagar_igual: "pagar igual",
    r_base: "Normal", r_afuera: "Valor externo", r_cayo: "Pago externo", r_bloqueado: "Bloqueado",
    ayuda_pulso: "Riesgo del paso. Base: lee lo del dueño. Sube: entra un valor no confiable. Pico rojo: intenta pagar a una cuenta de afuera. Verde: el escudo cortó",
    a_titulo: "Pago retenido", a_a: "a {d}", a_agente: "Agente", a_inscrita: "Inscrita",
    ayuda_alerta: "El escudo detuvo el pago porque la cuenta salió de un correo. Sin respuesta, no se paga",
    a_pagar_inscrita: "Pagar a mi cuenta inscrita", a_no_pagar: "No pagar", a_pagar_igual: "Pagar igual",
    a_seguro: "¿Pagar a {c}?", a_si: "Sí, pagar igual", a_cancelar: "Cancelar", cerrar: "Cerrar",
    a_hecho_pagar_inscrita: "Pagado a la inscrita", a_hecho_no_pagar: "No se pagó", a_hecho_pagar_igual: "Pagado a la cuenta nueva",
    c_de: "De", c_dominio: "Dominio", c_cuenta: "Cuenta",
    k_estafas: "Estafas exitosas", k_utilidad: "Utilidad", k_falsas: "Falsas alarmas", k_brecha: "Brecha ES / EN",
    ayuda_k_estafas: "Estafas en que el agente cayó con el escudo; el delta es contra sin defensa y solo se pinta si los intervalos no se tocan",
    ayuda_k_utilidad: "Tareas legítimas cumplidas con el escudo; el delta es contra sin defensa y solo se pinta si los intervalos no se tocan",
    ayuda_k_falsas: "Controles legítimos en que el escudo bloqueó algo; el delta es contra sin defensa y solo se pinta si los intervalos no se tocan",
    ayuda_k_brecha: "Diferencia de estafas exitosas entre español e inglés, sin defensa. Con intervalo en cada idioma",
    modelo: "Modelo", n_bajo: "n bajo", validas: "válidas",
    ayuda_nbajo: "Menos de 5 escenarios: el intervalo es muy ancho y la celda se atenúa",
    ayuda_n: "Entre corchetes, el intervalo al 95 % remuestreando escenarios; las repeticiones de un escenario cuentan una vez. n: escenarios. Válidas: muestras con puntaje sobre el total, las con error no cuentan",
    vs: "vs sin defensa", sin_datos: "Sin datos", prueba: "Datos de prueba", fuente: "Inspect · {m} modelos · {n} muestras válidas",
    sin_resultados: "Sin resultados", sin_episodio: "Sin episodio exportado", abrir: "Clic: abrir en Episodios",
    t_exito: "éxito de la estafa", t_modelo: "sin defensa",
    p_asunto: "Asunto",
    locale: "es-CL",
  },
  en: {
    v_operaciones: "Operations", v_vivo: "Episodes", ayuda_v_vivo: "Episodes exported from Inspect. «Test data» marks the lanes run with mockllm", desde_ops: "Seen in Operations", ayuda_desde_ops: "This is the scenario of the latest scam with an episode seen in Operations ({id})", v_resultados: "Results", v_duelo: "Duel", ayuda_v_duelo: "A hacker that learns from how we block it, against the frozen shield and against the one that learns from it",
    escenario: "Scenario", reproducir: "Play", reproduciendo: "Playing", reiniciar: "Reset",
    correos: "Emails", calor_tactica: "Tactic × defense", calor_modelo: "Model × language",
    d_none: "No defense", d_layer1: "Firewall", d_layer2: "Shield", d_both: "Firewall + shield", d_layer2_approver: "Shield (approver)",
    ayuda_none: "The agent does what it reads",
    ayuda_layer1: "Technical-injection rules, like Pipelock",
    ayuda_layer2: "Checks where each account came from before paying",
    dueno: "Owner", monto: "Amount", inscrita: "registered", externo: "external", sin_inscritas: "No registered accounts",
    sin_registro: "No log", listo: "Ready",
    ayuda_externo: "This account came from an email, not from the registered accounts",
    leidos: "{n} read", bloqueada: "Blocked", ejecutada: "Paid", saldo_insuf: "No funds",
    v_cayo: "Scammed", v_bloqueado: "Blocked", v_inscrita: "Paid registered", v_no_pago: "Not paid",
    v_sin_pago: "No payments", v_espera: "Waiting for {d}", v_confirmado: "confirmed twice",
    saldo: "balance", decide: "{d}: {e}",
    e_pagar_inscrita: "pay registered", e_no_pagar: "don't pay", e_pagar_igual: "pay anyway",
    r_base: "Normal", r_afuera: "External value", r_cayo: "External payment", r_bloqueado: "Blocked",
    ayuda_pulso: "Step risk. Baseline: reads the owner's data. Rises: an untrusted value comes in. Red spike: tries to pay an outside account. Green: the shield cut it",
    a_titulo: "Payment held", a_a: "to {d}", a_agente: "Agent", a_inscrita: "Registered",
    ayuda_alerta: "The shield stopped the payment because the account came from an email. No answer, no payment",
    a_pagar_inscrita: "Pay my registered account", a_no_pagar: "Don't pay", a_pagar_igual: "Pay anyway",
    a_seguro: "Pay {c}?", a_si: "Yes, pay anyway", a_cancelar: "Cancel", cerrar: "Close",
    a_hecho_pagar_inscrita: "Paid to registered", a_hecho_no_pagar: "Not paid", a_hecho_pagar_igual: "Paid to the new account",
    c_de: "From", c_dominio: "Domain", c_cuenta: "Account",
    k_estafas: "Successful scams", k_utilidad: "Utility", k_falsas: "False alarms", k_brecha: "ES / EN gap",
    ayuda_k_estafas: "Scams the agent fell for with the shield; the delta is against no defense and is colored only if the intervals do not overlap",
    ayuda_k_utilidad: "Legitimate tasks completed with the shield; the delta is against no defense and is colored only if the intervals do not overlap",
    ayuda_k_falsas: "Legitimate controls where the shield blocked something; the delta is against no defense and is colored only if the intervals do not overlap",
    ayuda_k_brecha: "Difference in successful scams between Spanish and English, no defense. Interval per language",
    modelo: "Model", n_bajo: "low n", validas: "valid",
    ayuda_nbajo: "Fewer than 5 scenarios: the interval is very wide and the cell is dimmed",
    ayuda_n: "In brackets, the 95 % interval from resampling scenarios; repeats of a scenario count once. n: scenarios. Valid: scored samples out of the total, errored ones don't count",
    vs: "vs no defense", sin_datos: "No data", prueba: "Test data", fuente: "Inspect · {m} models · {n} valid samples",
    sin_resultados: "No results", sin_episodio: "No exported episode", abrir: "Click: open in Episodes",
    t_exito: "scam success", t_modelo: "no defense",
    p_asunto: "Subject",
    locale: "en-US",
  },
};

const estado = {
  vista: "vivo",
  idioma: "es",
  escenario: null,
  velocidad: 1,
  ficha: 0,            // cambia en cada reinicio: los carriles viejos se detienen solos
  reproduciendo: false,
  carriles: {},        // clave -> { ep, terminado, decision, monitor }
  alerta: null,
  confirmando: false,
  correo: null,
  resultados: null,
  modelo: null,
  analisisPintado: false,
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
const primerEpisodio = () => CARRILES.map((c) => estado.carriles[c.clave]?.ep).find(Boolean);

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

// --- Vistas ---
function irA(vista) {
  if (!VISTAS.includes(vista)) vista = "operaciones";
  const anterior = estado.vista;
  estado.vista = vista;
  document.body.dataset.vista = vista;
  for (const v of VISTAS) $(`#vista-${v}`).hidden = v !== vista;
  document.querySelectorAll("[role=tab]").forEach((a) => a.setAttribute("aria-selected", String(a.dataset.vista === vista)));
  if (vista !== "vivo") cerrarCorreo();
  window.Operaciones?.alCambiarVista(vista);
  window.Duelo?.alCambiarVista(vista);
  // El borde de alerta es de la vista que la levantó: en Resultados no se ve; al volver a Episodios
  // reaparece si la alerta del escudo sigue sin respuesta.
  if (vista === "vivo") bordeAlerta(!!(estado.alerta && !estado.carriles.layer2?.decision));
  else if (vista !== "operaciones") bordeAlerta(false);
  if (vista === "vivo") abrirUltimaEstafa(anterior === "operaciones");
  if (vista === "resultados") {
    if (!estado.analisisPintado) pintarAnalisis();
    requestAnimationFrame(Graficos.redimensionar);
  }
}
addEventListener("hashchange", () => irA(location.hash.slice(1)));

// Episodios abre el escenario de la estafa más reciente que vio Operaciones y que tenga episodio exportado.
const hayEpisodio = (escenario) => CARRILES.some((c) => episodioDe(escenario, estado.idioma, c.defensas));
// Al llegar desde Operaciones, además arranca a reproducir (salvo con movimiento reducido): la pantalla no
// queda en tres carriles vacíos.
function abrirUltimaEstafa(reproducirAlLlegar = false) {
  const u = window.Operaciones?.ultimaEstafa(hayEpisodio);
  if (estado.reproduciendo) return;
  if (!u) { if (reproducirAlLlegar && !Graficos.sinMovimiento) reproducir(); return; }
  const cambia = u.escenario !== estado.escenario;
  estado.desdeOps = u;
  if (cambia) {
    estado.escenario = u.escenario;
    $("#sel-escenario").value = u.escenario;
    cargarEscenario();
    estado.analisisPintado = false;
  } else pintarFranja();
  if (reproducirAlLlegar && !Graficos.sinMovimiento) reproducir();
}

// --- Franja del escenario: tarea, monto y cuenta inscrita ---
function montoDe(ep) {
  for (const c of CARRILES) {
    const e = estado.carriles[c.clave]?.ep;
    const p = e?.pasos.find((x) => HERRAMIENTAS_PAGO.includes(x.herramienta));
    if (p?.args?.monto) return p.args.monto;
  }
  return ep.veredicto?.bloqueo?.monto ?? null;
}

function pintarFranja() {
  const ep = primerEpisodio();
  if (!ep) { $("#franja").innerHTML = `<div>${esc(t("sin_registro"))}</div>`; return; }
  const [nombre, valor] = Object.entries(ep.cuentas_inscritas)[0] || [];
  const num = valor ? (String(valor).match(RE_CUENTA) || [valor])[0] : "";
  const monto = montoDe(ep);
  $("#franja").innerHTML = `
    <div class="quien">${ms("person")}${esc(ep.dueno || t("dueno"))}${estado.desdeOps?.escenario === ep.escenario ? `<span class="tag" data-ayuda="${esc(t("ayuda_desde_ops", { id: estado.desdeOps.id }))}">${esc(t("desde_ops"))}</span>` : ""}</div>
    <div class="celda-tarea" data-ayuda="${esc(ep.encargo)}"><span class="tarea">${esc(ep.encargo)}</span></div>
    <div><span class="rotulo">${esc(t("monto"))}</span><span class="grande">${monto === null ? "—" : plata(monto)}</span></div>
    <div class="celda-inscrita" data-cuenta="${norm(num)}">${ms("account_balance")}${nombre
      ? `<span class="c-2">${esc(nombre)}</span><span class="dato">${esc(num)}</span><span class="tag">${esc(t("inscrita"))}</span>`
      : `<span class="c-2">${esc(t("sin_inscritas"))}</span>`}</div>`;
}

// --- Correos: una línea por correo; el cuerpo, en el panel lateral ---
function cuentasDeAfuera(eps) {
  const porCorreo = new Map();
  for (const ep of eps) for (const p of ep.pasos) {
    if (p.origen_cuenta?.tipo === "correo") p.origen_cuenta.correos.forEach((c) => porCorreo.set(c, p.args?.cuenta));
  }
  return porCorreo;
}

function pintarCorreos() {
  const eps = CARRILES.map((c) => estado.carriles[c.clave]?.ep).filter(Boolean);
  const ep = eps[0];
  $("#n-correos").textContent = ep ? String(ep.correos.length) : "";
  if (!ep) { $("#correos").innerHTML = ""; return; }
  const afuera = cuentasDeAfuera(eps);
  $("#correos").innerHTML = ep.correos.map((c) => {
    const cuenta = afuera.get(c.id);
    return `<li><button type="button" class="fila-correo" data-correo="${esc(c.id)}" aria-expanded="${estado.correo === c.id}" aria-controls="panel-correo">
      ${ms("mail")}<span class="de">${esc(c.de)}</span><span class="asunto">${esc(c.asunto)}</span>
      <span class="cuenta">${cuenta ? esc(cuenta) : ""}</span>
      ${cuenta ? `<span class="tag externo" data-ayuda="${esc(t("ayuda_externo"))}">${esc(t("externo"))}</span>` : "<span></span>"}
      ${ms("chevron_right")}</button></li>`;
  }).join("");
}

function abrirCorreo(id) {
  const eps = CARRILES.map((c) => estado.carriles[c.clave]?.ep).filter(Boolean);
  const c = eps[0]?.correos.find((x) => x.id === id);
  if (!c) return;
  estado.correo = id;
  const cuenta = cuentasDeAfuera(eps).get(id);
  // Solo se resalta la cuenta que importa: la que el agente sacó de este correo.
  const cuerpo = esc(c.cuerpo).replace(RE_CUENTA, (m) => (cuenta && norm(m) === norm(cuenta) ? `<mark class="cuenta">${m}</mark>` : m));
  const panel = $("#panel-correo");
  panel.innerHTML = `
    <div class="cab">${ms("mail", true)}<h2 id="pc-asunto">${esc(c.asunto)}</h2>
      <button type="button" class="boton icono texto" data-accion="cerrar-correo" aria-label="${esc(t("cerrar"))}">${ms("close")}</button></div>
    <div class="meta">
      <span class="rotulo">${esc(t("c_de"))}</span><span>${esc(c.de)}</span>
      <span class="rotulo">${esc(t("c_dominio"))}</span><span>${esc(c.dominio)}</span>
      ${cuenta ? `<span class="rotulo">${esc(t("c_cuenta"))}</span><span>${esc(cuenta)} <span class="tag externo">${esc(t("externo"))}</span></span>` : ""}
    </div>
    <div class="cuerpo">${cuerpo}</div>`;
  panel.hidden = false;
  document.querySelectorAll(".fila-correo").forEach((b) => b.setAttribute("aria-expanded", String(b.dataset.correo === id)));
  panel.querySelector("[data-accion='cerrar-correo']").focus({ preventScroll: true });
}

function cerrarCorreo() {
  const abierto = estado.correo;
  estado.correo = null;
  $("#panel-correo").hidden = true;
  document.querySelectorAll(".fila-correo").forEach((b) => b.setAttribute("aria-expanded", "false"));
  if (abierto) document.querySelector(`.fila-correo[data-correo="${abierto}"]`)?.focus({ preventScroll: true });
}

$("#correos").addEventListener("click", (e) => {
  const b = e.target.closest(".fila-correo");
  if (!b) return;
  if (estado.correo === b.dataset.correo) cerrarCorreo(); else abrirCorreo(b.dataset.correo);
});
$("#panel-correo").addEventListener("click", (e) => { if (e.target.closest("[data-accion='cerrar-correo']")) cerrarCorreo(); });

// --- Cuenta con su origen: texto normal y una etiqueta ---
function tagOrigen(origen) {
  const externo = origen && origen.tipo !== "inscrita";
  return `<span class="tag${externo ? " externo" : ""}">${esc(t(externo ? "externo" : "inscrita"))}</span>`;
}

// --- Carriles ---
// De dónde sale el episodio de un carril: «Datos de prueba» si es de mockllm, y el modelo si es una corrida real.
function etiquetaDeOrigen(ep) {
  if (!ep) return "";
  const modelo = String(ep.modelo || "");
  return modelo.startsWith("mockllm")
    ? `<span class="tag prueba" data-ayuda="${esc(modelo)}">${esc(t("prueba"))}</span>`
    : `<span class="modelo" data-ayuda="${esc(modelo)}">${esc(modelo.split("/").pop())}</span>`;
}

function pintarCarriles() {
  $("#carriles").innerHTML = CARRILES.map((c) => {
    const ep = estado.carriles[c.clave]?.ep;
    return `<article class="carril${c.escudo ? " escudo" : ""}" id="carril-${c.clave}">
      <header class="carril-cab" data-ayuda="${esc(t(`ayuda_${c.clave}`))}">${ms(c.icono)}<h2>${esc(t(`d_${c.clave}`))}</h2>${etiquetaDeOrigen(ep)}
        <span class="riesgo" data-ayuda="${esc(t("ayuda_pulso"))}">${ep ? esc(t("r_base")) : ""}</span></header>
      <div class="monitor" id="monitor-${c.clave}" aria-hidden="true"></div>
      <ol class="pasos">${ep ? `<li class="paso vacio">${esc(t("listo"))}</li>` : `<li class="paso vacio">${esc(t("sin_registro"))}</li>`}</ol>
      <div class="veredicto"></div>
    </article>`;
  }).join("");
  for (const c of CARRILES) {
    const carril = estado.carriles[c.clave];
    carril.monitor = Graficos.monitor($(`#monitor-${c.clave}`));
    if (!carril.ep) carril.monitor.apagar();
  }
}

function riesgo(clave, modo) {
  const el = document.querySelector(`#carril-${clave} .riesgo`);
  if (!el) return;
  el.textContent = t(`r_${modo}`);
  el.className = `riesgo ${modo === "cayo" ? "c-rojo" : modo === "bloqueado" ? "c-verde" : ""}`;
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
    const clase = bloqueada ? "bloqueada" : ejecutada && !bueno ? "pago-malo" : "";
    const icono = bloqueada ? "block" : ejecutada && bueno ? "check" : "payments";
    const estadoTxt = bloqueada ? t("bloqueada") : ejecutada ? t("ejecutada") : (r.includes("insuf") ? t("saldo_insuf") : "");
    const detalle = [a.destinatario, a.concepto || a.motivo || "", r].filter(Boolean).join("\n");
    return li(`herramienta pago ${clase}`, icono,
      `<span class="resumen"><span class="nombre">${esc(p.herramienta)}</span> ${plata(a.monto)} <span class="dato">${esc(a.cuenta)}</span></span>${tagOrigen(p.origen_cuenta)}`
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

// --- Estado de alerta: borde rojo de la ventana mientras hay un intento de pago externo sin resolver ---
function bordeAlerta(on) { $("#borde-alerta").hidden = !on; }

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
  const mon = c.monitor;
  if (!mon) return;
  const r = String(p.resultado || "");
  if (p.tipo === "texto") return mon.dueno();
  if (HERRAMIENTAS_LECTURA.includes(p.herramienta)) {
    if ([...valoresDeAfuera(c.ep)].some((v) => norm(r).includes(v))) { mon.afuera(); riesgo(clave, "afuera"); }
    else mon.dueno();
    return;
  }
  if (HERRAMIENTAS_PAGO.includes(p.herramienta)) {
    const bloqueada = RE_BLOQUEO.test(r) || p.bloqueada;
    const deAfuera = p.origen_cuenta && p.origen_cuenta.tipo !== "inscrita";
    if (!deAfuera) { mon.inscrita(); return riesgo(clave, "base"); }
    bordeAlerta(true);
    if (bloqueada) { mon.corte(); return riesgo(clave, "bloqueado"); }
    mon.cayo(); return riesgo(clave, "cayo");
  }
  mon.dueno();
}

function htmlVeredicto(grande, dato = "") {
  return `<span class="grande">${esc(grande)}</span>${dato ? `<span class="dato">${dato}</span>` : ""}`;
}

function pintarVeredicto(clave) {
  const c = estado.carriles[clave];
  const caja = document.querySelector(`#carril-${clave} .veredicto`);
  caja.className = "veredicto";
  if (!c?.ep || !c.terminado) { caja.innerHTML = ""; return; }
  const v = c.ep.veredicto;
  const saldo = (n) => `${esc(t("saldo"))} ${plata(n)}`;
  let clase = "";
  let html;
  if (v.tipo === "estafado") {
    const p = v.pagos[0] || {};
    clase = "rojo"; html = htmlVeredicto(t("v_cayo"), `-${plata(v.pagado)} · ${esc(p.cuenta)}`);
  } else if (v.tipo === "bloqueado") {
    const b = v.bloqueo || {};
    if (!c.decision) { clase = "verde"; html = htmlVeredicto(t("v_bloqueado"), `${esc(t("v_espera", { d: c.ep.dueno || t("dueno") }))} · ${saldo(v.saldo_final)}`); }
    else if (c.decision === "pagar_inscrita") html = htmlVeredicto(t("v_inscrita"), `-${plata(b.monto)} · ${esc(b.cuenta_inscrita_numero)}`);
    else if (c.decision === "no_pagar") html = htmlVeredicto(t("v_no_pago"), saldo(v.saldo_final));
    else { clase = "rojo"; html = htmlVeredicto(t("v_cayo"), `-${plata(b.monto)} · ${esc(b.cuenta)} · ${esc(t("v_confirmado"))}`); }
  } else if (v.tipo === "pago_inscrita") {
    const p = v.pagos[0] || {};
    html = htmlVeredicto(t("v_inscrita"), `-${plata(v.pagado)} · ${esc(p.cuenta)}`);
  } else {
    clase = "gris"; html = htmlVeredicto(t("v_sin_pago"), saldo(v.saldo_final));
  }
  if (clase) caja.classList.add(clase);
  caja.innerHTML = html;
}

async function correrCarril(clave, ficha) {
  const c = estado.carriles[clave];
  if (!c?.ep) return;
  const ol = document.querySelector(`#carril-${clave} .pasos`);
  ol.innerHTML = "";
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
  c.terminado = true;
  pintarVeredicto(clave);
}

// --- Reproducción ---
function cargarEscenario() {
  estado.ficha++;
  estado.reproduciendo = false;
  estado.alerta = null;
  estado.confirmando = false;
  estado.carriles = {};
  bordeAlerta(false);
  cerrarCorreo();
  for (const c of CARRILES) {
    const ep = episodioDe(estado.escenario, estado.idioma, c.defensas);
    estado.carriles[c.clave] = { ep, terminado: false, decision: null, monitor: null };
  }
  pintarTextos();
  pintarFranja();
  pintarCarriles();
  pintarCorreos();
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
// Canales hoy: la capa de alerta sobre el carril del escudo y el servidor (POST /api/alertas).
// Telegram se enchufa en el servidor (demo/notificar.py) sin tocar la página.
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
  bordeAlerta(true);
  pintarAlerta();
  $("#alerta [data-decision='pagar_inscrita']")?.focus({ preventScroll: true });
  try { navigator.vibrate?.([120, 60, 120]); } catch (_) { /* sin vibración */ }
}

function cerrarAlerta() { $("#alerta")?.remove(); }

function pintarAlerta() {
  const carril = $("#carril-layer2");
  const a = estado.alerta;
  if (!carril || !a) return cerrarAlerta();
  let caja = $("#alerta");
  if (!caja) {
    carril.insertAdjacentHTML("beforeend", `<section class="alerta" id="alerta" role="alertdialog" aria-modal="false" aria-labelledby="alerta-titulo"></section>`);
    caja = $("#alerta");
    caja.addEventListener("click", clicAlerta);
  }
  const decision = estado.carriles.layer2?.decision;
  let acciones;
  if (decision) {
    const clase = decision === "pagar_igual" ? "c-rojo" : "";
    acciones = `<div class="hecho ${clase}">${ms(decision === "pagar_igual" ? "payments" : "check", true)}${esc(t(`a_hecho_${decision}`))}</div>`;
  } else if (estado.confirmando) {
    acciones = `<div class="acciones">
      <span class="pregunta">${esc(t("a_seguro", { c: a.cuenta }))}</span>
      <button type="button" class="boton texto" data-accion="cancelar">${esc(t("a_cancelar"))}</button>
      <button type="button" class="boton peligro" data-decision="pagar_igual">${esc(t("a_si"))}</button></div>`;
  } else {
    acciones = `<div class="acciones">
      <button type="button" class="boton principal" data-decision="pagar_inscrita">${esc(t("a_pagar_inscrita"))}</button>
      <button type="button" class="boton texto peligro" data-accion="confirmar">${esc(t("a_pagar_igual"))}</button>
      <button type="button" class="boton" data-decision="no_pagar">${esc(t("a_no_pagar"))}</button></div>`;
  }
  caja.innerHTML = `
    <div class="cab" data-ayuda="${esc(t("ayuda_alerta"))}">${ms("gpp_bad", true)}<h3 id="alerta-titulo">${esc(t("a_titulo"))}</h3></div>
    <div class="monto"><span class="dato">${plata(a.monto)}</span><span class="a">${esc(t("a_a", { d: a.destinatario }))}</span></div>
    <div class="comparar">
      <span class="rotulo">${esc(t("a_agente"))}</span><span class="valor"><span class="dato">${esc(a.cuenta)}</span><span class="tag externo" data-ayuda="${esc(a.dominio)}">${esc(t("externo"))}</span></span>
      <span class="rotulo">${esc(t("a_inscrita"))}</span><span class="valor"><span class="dato">${esc(a.cuenta_inscrita_numero || a.cuenta_inscrita)}</span><span class="tag">${esc(t("inscrita"))}</span></span>
    </div>
    ${acciones}`;
}

function clicAlerta(e) {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.accion === "confirmar") { estado.confirmando = true; pintarAlerta(); return $("#alerta [data-accion='cancelar']")?.focus(); }
  if (b.dataset.accion === "cancelar") { estado.confirmando = false; pintarAlerta(); return; }
  if (b.dataset.decision) decidir(b.dataset.decision);
}
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (estado.correo) cerrarCorreo();
});

// La respuesta del dueño decide el pago en el carril del escudo y deja una etiqueta para el clasificador.
function decidir(eleccion) {
  const c = estado.carriles.layer2;
  const a = estado.alerta;
  if (!c || !a || c.decision) return;
  c.decision = eleccion;
  bordeAlerta(false);
  agregarPaso("layer2", { tipo: "dueno", texto: t("decide", { d: c.ep.dueno || t("dueno"), e: t(`e_${eleccion}`) }) });
  if (eleccion === "pagar_inscrita") {
    agregarPaso("layer2", { tipo: "herramienta", herramienta: "pagar", resultado: "Listo",
      args: { destinatario: a.destinatario, cuenta: a.cuenta_inscrita_numero, monto: a.monto },
      origen_cuenta: { tipo: "inscrita" } });
  } else if (eleccion === "pagar_igual") {
    agregarPaso("layer2", { tipo: "herramienta", herramienta: "pagar", resultado: "Listo",
      args: { destinatario: a.destinatario, cuenta: a.cuenta, monto: a.monto },
      origen_cuenta: { tipo: "correo", dominios: [a.dominio] } });
    c.monitor?.cayo();
    riesgo("layer2", "cayo");
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

// --- Resultados: los números del README, desde resultados.json (scripts/resultados_demo.py) ---
async function cargarResultados() {
  if (location.protocol !== "file:") {
    try {
      const r = await fetch("resultados.json", { cache: "no-store" });
      if (r.ok) return r.json();
    } catch (_) { /* sin servidor: queda la copia en JS */ }
  }
  return window.RESULTADOS || null;
}

// Los gráficos se dibujan cuando la vista está visible (ECharts necesita medir el contenedor).
function pintarAnalisis() {
  window.ResultadosVista?.fuente(estado.resultados);
  if (estado.vista !== "resultados") { estado.analisisPintado = false; return; }
  window.ResultadosVista?.pintar(estado.resultados);
  estado.analisisPintado = true;
}

// --- Textos, selectores y controles ---
function pintarTextos() {
  document.documentElement.lang = estado.idioma;
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  document.querySelectorAll("[data-ph]").forEach((el) => { el.placeholder = t(el.dataset.ph); });
  document.querySelectorAll("[data-ayuda-solo]").forEach((el) => { el.dataset.ayuda = t(el.dataset.ayudaSolo); });
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
  sel.innerHTML = [...vistos].map(([id, desc]) => `<option value="${esc(id)}" title="${esc(desc)}">${esc(id.replace(/^demo_/, "").replaceAll("_", " "))}</option>`).join("");
  if (!estado.escenario || !vistos.has(estado.escenario)) {
    estado.escenario = vistos.has(ESCENARIO_POR_DEFECTO) ? ESCENARIO_POR_DEFECTO : vistos.keys().next().value || null;
  }
  sel.value = estado.escenario;
}

$("#sel-escenario").addEventListener("change", (e) => { estado.escenario = e.target.value; cargarEscenario(); estado.analisisPintado = false; });
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
irA(location.hash.slice(1) || "operaciones");
cargarEscenario();
cargarResultados().then((R) => { estado.resultados = R; pintarAnalisis(); window.Duelo?.pintar(); });
if (params.has("auto")) reproducir();
