// Grifter, vista Operaciones: el centro de operaciones en vivo. Cada cosa que se mueve responde a un
// evento del flujo /api/vivo (contrato en DESIGN.md, «Operaciones»). Si el motor no está, usa el emisor
// falso de vivo_simulado.js y lo dice en el sello. Depende de app.js (t, esc, plata, ms, estado, bordeAlerta).
"use strict";

const Operaciones = (() => {
  Object.assign(T.es, {
    o_evasion: "evasión", o_capa2: "pagos con capa 2", o_indicadores_r: "indicadores", o_repetidos: "{n} ya vistos", o_juez: "Juez", ayuda_juez: "Correo escrito a mano y enviado a /api/probar: solo se evalúa, no entrena ni entra a la bóveda", o_cola: "Entrada", o_lectura: "Lectura", o_registro: "Registro", o_capas: "Defensa en capas", o_boveda: "Bóveda", o_modelo: "Modelo",
    o_sello_real: "Simulación · motor real", o_sello_sim: "Simulación · emisor local", o_sello_conectando: "Conectando",
    o_sello_reconectando: "Reconectando", ayuda_sello: "Los agentes y los correos son simulados. La defensa (firewall, escudo, bóveda y clasificador) corre sobre cada evento",
    o_pausa: "Pausa", o_seguir: "Seguir",
    ea_leyendo: "Leyendo", ea_pensando: "Pensando", ea_pagando: "Pagando", ea_esperando: "Esperando", ea_inactivo: "Inactivo", ea_retenido: "Retenido",
    o_mas_agentes: "+{n} agentes", o_menos_agentes: "Ver solo {n}", ayuda_mas_agentes: "No caben todos: se ven los de más peligro y los más recientes. También están {nombres}",
    ayuda_menos_agentes: "Mostrar solo los {n} de más peligro y más recientes", o_en_cola: "{n} en cola", o_cola_n: "{n}", o_estado_cola: "En cola", o_estado_leyendo: "Leyendo",
    o_dec_seguro: "Seguro", o_dec_sospechoso: "Sospechoso", o_dec_estafa: "Estafa",
    capa_1: "Firewall", capa_2: "Escudo", capa_boveda: "Bóveda",
    ayuda_capa_1: "Acciones retenidas por la capa 1: reglas contra lo técnico (instrucciones inyectadas, MCP envenenado, fuga de secretos)",
    ayuda_capa_2: "Acciones retenidas por la capa 2: revisa de dónde salió cada cuenta y dato antes de actuar",
    ayuda_capa_boveda: "Veredictos atajados por la bóveda: un indicador ya visto en una estafa confirmada",
    f_tecnico: "Técnico", f_ingenieria_social: "Ingeniería social", f_legitimo: "Legítimo",
    o_detenidas: "{a}/{n} detenidas", o_retenidas: "{a}/{n} retenidas",
    ayuda_familia: "Acciones de los agentes por familia. Cada tramo es la capa que detuvo la acción; rojo es una acción de ataque que pasó",
    fu_boveda: "Firma conocida", fu_origen: "Política de origen", fu_clasificador: "Clasificador {v}",
    ac_ejecutada: "Ejecutada", ac_retenida: "Retenida", ac_escalada: "Escalada",
    o_confianza: "confianza", o_leyendo_pct: "leyendo {p}%", o_indicadores: "{n} indicadores", o_ejemplos: "{n} ejemplos",
    o_precision: "Precisión", o_recall: "Detecta", o_el_clasificador: "El clasificador", o_falsas: "Falsas alarmas",
    o_grifter: "Grifter completo", o_grifter_completo: "{r} de {a} frenados", o_ver_resultados: "Ver en Resultados",
    ayuda_grifter_completo: "Con las capas 2 y 3, en el benchmark: {r} de {a} ataques frenados, en {f} tipos. El clasificador de arriba es una señal más, no la defensa: lo que se le escapa lo frenan las capas. Sale de cobertura.totales en resultados.json", o_en_pausa: "En pausa",
    ayuda_precision: "De lo que marcó como estafa, cuánto lo era. Evaluado en un conjunto apartado que nunca se usa para entrenar",
    ayuda_recall: "Detección del clasificador (recall): de las estafas, cuántas marcó. Es solo el clasificador, no la cobertura de Grifter",
    ayuda_falsas: "Correos legítimos marcados como estafa",
    o_de: "{f}/{l}",
    ayuda_falsas_n: "Correos legítimos marcados como estafa: {f} de {l} en el conjunto apartado del motor (un tercio de los escenarios, fijo, que nunca entrena). Cada legítimo pesa {pp} puntos y cada escenario trae 3 variantes, así que un solo escenario mueve la cifra de a {ep} puntos.{marcados}{cv}",
    o_marcados: " Marcados ahora: {lista}.", o_cv_falsas: " Con validación cruzada por familia (9 corridas): {m} % [{a}-{b}].",
    o_colados: "Se colaron", o_colados_ninguna: "Ninguna",
    ayuda_colados: "Estafas del conjunto apartado (un tercio de los escenarios, que nunca entrena) que el modelo dejó bajo 0,5: son las que bajan la cobertura. Cuentan correos, por tipo de estafa. No se pagan solas: la capa 1 y la capa 2 corren igual. La validación cruzada por familia está en Resultados",
    ayuda_colado: "{e} · {c} · {n} de {d} · probabilidad media {p}",
    o_sin_correo: "Sin correos", o_bv_vacia: "Sin indicadores", o_sin_modelo: "Sin versión",
    bv_cuenta: "cuenta", bv_dominio: "dominio", bv_plantilla: "plantilla", bv_origen: "origen {o} · primera vez {h}",
    o_pesos: "Pesos",
    s_dominio_parecido: "dominio parecido", s_cambio_cuenta: "cambio de cuenta", s_pide_codigo: "pide código", s_pide_secreto: "pide secreto",
    s_inyeccion: "instrucción inyectada", s_cuenta_nueva: "cuenta nueva", s_urgencia: "urgencia", s_monto_inusual: "monto inusual",
    s_primer_contacto: "primer contacto", s_servicio_legitimo_con_pago: "servicio legítimo con cuenta nueva", s_proveedor_inscrito: "proveedor inscrito", s_firma_conocida: "firma conocida",
    s_secreto: "pide secreto", s_enlace: "enlace", s_autoridad: "autoridad", s_instruccion_oculta: "instrucción oculta",
    tr_cuenta: "cuenta", tr_dominio: "dominio", tr_urgencia: "urgencia", tr_codigo: "código", tr_monto: "monto", tr_autoridad: "autoridad",
    tr_inyeccion: "inyección", tr_secreto: "secreto",
  });
  Object.assign(T.en, {
    o_evasion: "evasion", o_capa2: "payments with layer 2", o_indicadores_r: "indicators", o_repetidos: "{n} already seen", o_juez: "Judge", ayuda_juez: "Email written by hand and sent to /api/probar: only evaluated, never trained on or added to the vault", o_cola: "Inbox", o_lectura: "Reading", o_registro: "Log", o_capas: "Layered defense", o_boveda: "Vault", o_modelo: "Model",
    o_sello_real: "Simulation · real engine", o_sello_sim: "Simulation · local emitter", o_sello_conectando: "Connecting",
    o_sello_reconectando: "Reconnecting", ayuda_sello: "Agents and emails are simulated. The defense (firewall, shield, vault and classifier) runs on every event",
    o_pausa: "Pause", o_seguir: "Resume",
    ea_leyendo: "Reading", ea_pensando: "Thinking", ea_pagando: "Paying", ea_esperando: "Waiting", ea_inactivo: "Idle", ea_retenido: "Held",
    o_mas_agentes: "+{n} agents", o_menos_agentes: "Show only {n}", ayuda_mas_agentes: "They do not all fit: the most dangerous and most recent are shown. Also here: {nombres}",
    ayuda_menos_agentes: "Show only the {n} most dangerous and most recent", o_en_cola: "{n} queued", o_cola_n: "{n}", o_estado_cola: "Queued", o_estado_leyendo: "Reading",
    o_dec_seguro: "Safe", o_dec_sospechoso: "Suspicious", o_dec_estafa: "Scam",
    capa_1: "Firewall", capa_2: "Shield", capa_boveda: "Vault",
    ayuda_capa_1: "Layer 1: rules against technical attacks (injected instructions, poisoned MCP, secret leaks)",
    ayuda_capa_2: "Layer 2: checks where every account and value came from before acting",
    ayuda_capa_boveda: "Verdicts caught by the vault: an indicator already seen in a confirmed scam",
    f_tecnico: "Technical", f_ingenieria_social: "Social engineering", f_legitimo: "Legitimate",
    o_detenidas: "{a}/{n} stopped", o_retenidas: "{a}/{n} held",
    ayuda_familia: "Agent actions by family. Each segment is the layer that stopped the action; red is an attack action that went through",
    fu_boveda: "Known signature", fu_origen: "Origin policy", fu_clasificador: "Classifier {v}",
    ac_ejecutada: "Executed", ac_retenida: "Held", ac_escalada: "Escalated",
    o_confianza: "confidence", o_leyendo_pct: "reading {p}%", o_indicadores: "{n} indicators", o_ejemplos: "{n} examples",
    o_precision: "Precision", o_recall: "Detects", o_el_clasificador: "The classifier", o_falsas: "False alarms",
    o_grifter: "Full Grifter", o_grifter_completo: "{r} of {a} stopped", o_ver_resultados: "See in Results",
    ayuda_grifter_completo: "With layers 2 and 3, on the benchmark: {r} of {a} attacks stopped, across {f} types. The classifier above is one more signal, not the defense: what it misses, the layers stop. From cobertura.totales in resultados.json", o_en_pausa: "Paused",
    ayuda_precision: "Of what it flagged as a scam, how much was. Evaluated on a held-out set never used for training",
    ayuda_recall: "Classifier recall: of the scams, how many it flagged. It is only the classifier, not Grifter's coverage",
    ayuda_falsas: "Legitimate emails flagged as scams",
    o_de: "{f}/{l}",
    ayuda_falsas_n: "Legitimate emails flagged as scams: {f} of {l} in the engine's held-out set (a fixed third of the scenarios, never trained on). Each legitimate email weighs {pp} points and each scenario brings 3 variants, so a single scenario moves the figure by {ep} points.{marcados}{cv}",
    o_marcados: " Flagged now: {lista}.", o_cv_falsas: " With cross-validation by family (9 runs): {m} % [{a}-{b}].",
    o_colados: "Slipped through", o_colados_ninguna: "None",
    ayuda_colados: "Held-out scams (a third of the scenarios, never trained on) the model left below 0.5: they are what lowers recall. Counted in emails, by scam type. They are not paid on their own: layers 1 and 2 still run. The cross-validation by family is in Results",
    ayuda_colado: "{e} · {c} · {n} of {d} · mean probability {p}",
    o_sin_correo: "No emails", o_bv_vacia: "No indicators", o_sin_modelo: "No version",
    bv_cuenta: "account", bv_dominio: "domain", bv_plantilla: "template", bv_origen: "source {o} · first seen {h}",
    o_pesos: "Weights",
    s_dominio_parecido: "lookalike domain", s_cambio_cuenta: "account change", s_pide_codigo: "asks for code", s_pide_secreto: "asks for secret",
    s_inyeccion: "injected instruction", s_cuenta_nueva: "new account", s_urgencia: "urgency", s_monto_inusual: "unusual amount",
    s_primer_contacto: "first contact", s_servicio_legitimo_con_pago: "legitimate service with a new account", s_proveedor_inscrito: "registered vendor", s_firma_conocida: "known signature",
    s_secreto: "asks for secret", s_enlace: "link", s_autoridad: "authority", s_instruccion_oculta: "hidden instruction",
    tr_cuenta: "account", tr_dominio: "domain", tr_urgencia: "urgency", tr_codigo: "code", tr_monto: "amount", tr_autoridad: "authority",
    tr_inyeccion: "injection", tr_secreto: "secret",
  });

  const FAMILIAS = ["tecnico", "ingenieria_social", "legitimo"];
  const CAPAS = ["1", "2", "boveda"];
  const ICONO_ESTADO = { leyendo: "visibility", pensando: "psychology", pagando: "payments", esperando: "hourglass_top", inactivo: null, retenido: "block" };
  // «Inactivo» va con un círculo vacío dibujado: el ícono de pausa se leía como dos rectángulos.
  const SVG_INACTIVO = `<svg class="ms" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="4.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`;
  const iconoEstado = (est) => (ICONO_ESTADO[est] ? ms(ICONO_ESTADO[est]) : SVG_INACTIVO);
  const ICONO_BOVEDA = { cuenta: "account_balance", dominio: "language", plantilla: "description" };
  const ICONO_DEC = { seguro: "check", sospechoso: "flag", estafa: "gpp_bad" };
  const MAX_COLA = 40, MAX_REGISTRO = 240, MAX_CURVA = 40;
  const quieto = () => Graficos.sinMovimiento;

  const o = {
    fuente: null, sello: "conectando", pausa: false, velocidad: 1,
    agentes: new Map(), tick: 0, agentesTodos: false,
    correos: new Map(), orden: [], filas: new Map(),
    lecturas: [], leyendo: null, mostrado: null, espera: null,
    boveda: new Map(), modelo: null, historial: [], pesos: {}, cambios: {},
    bloqueos: {}, desenlace: new Map(), capas: {}, contadas: new Set(), retomar: false, estafas: [],
    alarma: null, curva: null, visible: false, iniciado: false,
  };

  // --- Utilidades ---
  const hora = (ts) => new Date((ts || Date.now() / 1000) * 1000).toLocaleTimeString(t("locale"), { hour12: false });
  const pct = (x) => `${Math.round((x || 0) * 100)}%`;
  const senal = (n) => (T[estado.idioma]?.[`s_${n}`] || T.es[`s_${n}`] || String(n).replaceAll("_", " "));
  const clase = (c) => (T[estado.idioma]?.[`tr_${c}`] || T.es[`tr_${c}`] || String(c));
  const capa = (c) => (c ? t(`capa_${c}`) : "");
  const tagCapa = (c) => (c ? `<span class="tag capa" data-ayuda="${esc(t(`ayuda_capa_${c}`))}">${esc(capa(c))}</span>` : "");
  const riesgoClase = (r) => (r >= 0.6 ? "alto" : r >= 0.3 ? "medio" : "bajo");
  const escPausa = (ms_) => ms_ / o.velocidad;
  function reanimar(el, clase_) {
    if (!el || quieto()) return;
    el.classList.remove(clase_);
    void el.offsetWidth; // reinicia la animación
    el.classList.add(clase_);
  }
  function correo(id) {
    if (!o.correos.has(id)) o.correos.set(id, { id, fase: "cola" });
    return o.correos.get(id);
  }

  // --- Agentes: una celda por agente con su estado y su cola ---
  function colaDe(agente) {
    let n = 0;
    for (const id of o.orden) { const c = o.correos.get(id); if (c?.agente === agente && c.fase === "cola") n++; }
    return n;
  }
  function htmlAgente(a) {
    const est = a.retenido ? "retenido" : a.estado || "inactivo";
    const n = colaDe(a.agente);
    const foco = o.mostrado && o.correos.get(o.mostrado)?.agente === a.agente;
    return `<li class="agente${foco ? " foco" : ""}" data-estado="${est}" id="ag-${esc(a.agente)}" data-ayuda="${esc(a.tarea || "")}">
      <div class="ag-l1"><span class="ag-nombre">${esc(a.agente)}</span>
        <span class="ag-estado">${iconoEstado(est)}<span>${esc(t(`ea_${est}`))}</span></span></div>
      <div class="ag-l2"><span class="ag-tarea" data-ayuda="${esc(a.tarea || "")}">${esc(a.tarea || "")}</span>${a.retenido ? tagCapa(a.retenido) : ""}${n ? `<span class="tag" data-ayuda="${esc(t("o_en_cola", { n }))}">+${n}</span>` : ""}</div></li>`;
  }
  // Una celda nueva entra antes del botón «+N», que va siempre al final.
  function ponerAgente(a) {
    const li = document.getElementById(`ag-${a.agente}`);
    if (li) li.outerHTML = htmlAgente(a);
    else {
      const mas = $("#ops-agentes").querySelector(".ag-mas");
      if (mas) mas.insertAdjacentHTML("beforebegin", htmlAgente(a)); else $("#ops-agentes").insertAdjacentHTML("beforeend", htmlAgente(a));
    }
  }
  function pintarAgentes() {
    for (const a of o.agentes.values()) ponerAgente(a);
    ajustarAgentes();
  }
  function pintarAgente(nombre, cambio) {
    const a = o.agentes.get(nombre);
    if (!a) return;
    ponerAgente(a);
    if (cambio) reanimar(document.getElementById(`ag-${nombre}`), "cambia");
    ajustarAgentes();
  }

  // Si no caben todos en una fila, se ven los 4 de más peligro y, a igual peligro, los que cambiaron hace menos.
  // El que está en Lectura siempre se ve. El orden del DOM no cambia: solo se esconden las celdas que sobran.
  const AG_ANCHO = 176, AG_GAP = 16, AG_VISIBLES = 4;
  function peligroAgente(a) {
    if (o.mostrado && o.correos.get(o.mostrado)?.agente === a.agente) return 4;   // el que se está leyendo
    if (a.retenido) return 3;                                                       // acaba de frenarse un ataque
    const est = a.estado || "inactivo";
    if (est === "pagando") return 2;                                                // está por mover plata
    return est === "esperando" || est === "inactivo" ? 0 : 1;
  }
  function ajustarAgentes() {
    const ul = document.getElementById("ops-agentes");
    if (!ul) return;
    const celdas = [...ul.querySelectorAll(".agente")];
    ul.querySelector(".ag-mas")?.remove();
    celdas.forEach((li) => { li.hidden = false; });
    const caben = Math.floor((ul.clientWidth + AG_GAP) / (AG_ANCHO + AG_GAP));
    if (!ul.clientWidth || celdas.length <= AG_VISIBLES || caben >= celdas.length) return;
    const orden = celdas
      .map((li) => o.agentes.get(li.id.slice(3)) || { agente: li.id.slice(3) })
      .sort((x, y) => peligroAgente(y) - peligroAgente(x) || (y.t || 0) - (x.t || 0));
    const ocultos = orden.slice(AG_VISIBLES).map((a) => a.agente);
    if (!o.agentesTodos) for (const nombre of ocultos) document.getElementById(`ag-${nombre}`).hidden = true;
    const texto = o.agentesTodos ? t("o_menos_agentes", { n: AG_VISIBLES }) : t("o_mas_agentes", { n: ocultos.length });
    const ayuda = o.agentesTodos ? t("ayuda_menos_agentes", { n: AG_VISIBLES }) : t("ayuda_mas_agentes", { nombres: ocultos.join(", ") });
    ul.insertAdjacentHTML("beforeend", `<li class="ag-mas"><button type="button" class="ag-mas-b" aria-expanded="${o.agentesTodos}" data-ayuda="${esc(ayuda)}">${esc(texto)}</button></li>`);
  }

  // --- Entrada: un correo por fila, el más nuevo arriba ---
  // Las estafas que vio Operaciones, la más reciente al final, para que Episodios abra el mismo escenario.
  function anotarEstafa(escenario, id) {
    if (!escenario || escenario === "juez") return;
    o.estafas = o.estafas.filter((x) => x.escenario !== escenario);
    o.estafas.push({ escenario, id, ts: Date.now() / 1000 });
    if (o.estafas.length > 40) o.estafas.shift();
  }
  const tagJuez = () => `<span class="tag juez" data-ayuda="${esc(t("ayuda_juez"))}">${esc(t("o_juez"))}</span>`;
  function htmlRemitente(de = "") {
    const m = /<([^<>]+@[^<>]+)>/.exec(de);
    if (m) de = m[1].trim();
    const i = de.lastIndexOf("@");
    if (i < 0) return `<span class="de-local">${esc(de)}</span>`;
    return `<span class="de-local">${esc(de.slice(0, i))}</span><span class="de-dom">${esc(de.slice(i))}</span>`;
  }
  function htmlFila(c) {
    const v = c.veredicto;
    let icono = "schedule", etiqueta = t("o_estado_cola"), cls = "cola";
    if (c.fase === "leyendo") { icono = "document_scanner"; etiqueta = t("o_estado_leyendo"); cls = "leyendo"; }
    else if (v && c.fase === "leido") { icono = ICONO_DEC[v.decision] || "check"; etiqueta = t(`o_dec_${v.decision}`); cls = v.decision; }
    const a = c.accion;
    const capaFila = c.fase !== "leido" ? null : a && a.resultado !== "ejecutada" ? a.capa : v && v.decision !== "seguro" ? v.capa : null;
    return `${ms(icono)}<span class="f-agente">${c.juez ? tagJuez() : esc(c.agente || "")}</span><span class="f-de">${htmlRemitente(c.de)}</span>
      <span class="f-dec">${esc(etiqueta)}</span><span class="f-asunto">${esc(c.asunto || "")}</span><span class="f-capa">${tagCapa(capaFila)}</span>`;
  }
  function pintarFila(id, nueva) {
    const c = o.correos.get(id);
    if (!c || !c.de) return;
    let li = o.filas.get(id);
    if (!li) {
      $("#ops-cola .vacio")?.remove();
      li = document.createElement("li");
      li.className = "fila-op";
      o.filas.set(id, li);
      $("#ops-cola").prepend(li);
      if (nueva) reanimar(li, "entra-fila");
      while (o.filas.size > MAX_COLA) {
        const viejo = o.orden.find((x) => o.filas.has(x));
        o.filas.get(viejo)?.remove(); o.filas.delete(viejo);
      }
    }
    li.dataset.estado = c.fase === "leido" && c.veredicto ? c.veredicto.decision : c.fase;
    li.innerHTML = htmlFila(c);
    $("#n-cola").textContent = String(o.orden.length);
  }

  // --- Lectura: el correo se abre y se lee token a token; los tramos se marcan cuando el cursor pasa ---
  // Los offsets indexan el cuerpo crudo: se corta el texto crudo y se escapa cada pedazo.
  function tramosDe(c) {
    const cuerpo = c.cuerpo || "";
    const ok = [], fuera = [];
    for (const [k, x] of (c.lectura?.tramos || []).entries()) {
      let i = Number.isInteger(x.inicio) ? x.inicio : -1, f = Number.isInteger(x.fin) ? x.fin : -1;
      if (i < 0 || f <= i || cuerpo.slice(i, f) !== x.texto) { i = x.texto ? cuerpo.indexOf(x.texto) : -1; f = i < 0 ? -1 : i + x.texto.length; }
      (i < 0 ? fuera : ok).push({ ...x, inicio: i, fin: f, k });
    }
    ok.sort((a, b) => a.inicio - b.inicio);
    const limpios = [];
    for (const x of ok) if (!limpios.length || x.inicio >= limpios.at(-1).fin) limpios.push(x); else fuera.push(x);
    return { dentro: limpios, fuera };
  }
  const tokens = (s) => s.match(/\S+\s*|\s+/g) || [];
  function htmlCuerpo(c, tr) {
    const cuerpo = c.cuerpo || "";
    let html = "", pos = 0, n = 0;
    const tk = (s) => `<span class="tk" data-n="${n++}">${esc(s)}</span>`;
    for (const x of tr.dentro) {
      html += tokens(cuerpo.slice(pos, x.inicio)).map(tk).join("");
      const primero = n;
      // El último token del tramo y su etiqueta no se separan: la etiqueta nunca queda sola al inicio de una línea
      // y una cuenta no se parte en su guion.
      const partes = tokens(cuerpo.slice(x.inicio, x.fin)).map(tk);
      const fin = partes.pop() || "";
      html += `<mark class="tramo r-${riesgoClase(x.riesgo)}" data-k="${x.k}" data-desde="${primero}" data-ayuda="${esc(x.nota || "")}">${partes.join("")}<span class="tramo-fin">${fin}<span class="tramo-tag">${esc(clase(x.clase))}</span></span></mark>`;
      pos = x.fin;
    }
    html += tokens(cuerpo.slice(pos)).map(tk).join("");
    return { html, n };
  }
  function htmlDe(c, tr) {
    const de = c.de || "";
    const dom = tr.fuera.find((x) => x.texto && de.includes(x.texto));
    if (!dom) return esc(de);
    const i = de.indexOf(dom.texto);
    return `${esc(de.slice(0, i))}<mark class="tramo r-${riesgoClase(dom.riesgo)}" data-k="${dom.k}" data-desde="0" data-ayuda="${esc(dom.nota || "")}">${esc(dom.texto)}<span class="tramo-tag">${esc(clase(dom.clase))}</span></mark>${esc(de.slice(i + dom.texto.length))}`;
  }
  function htmlHallazgo(x) {
    return `<li class="hallazgo r-${riesgoClase(x.riesgo)}" data-k="${x.k}" tabindex="0" data-ayuda="${esc(x.nota || "")}">
      <span class="tag">${esc(clase(x.clase))}</span><span class="h-texto">${esc(x.texto)}</span>
      <span class="h-nota">${esc(x.nota || "")}</span><span class="h-riesgo"><span class="medidor"><span style="width:${Math.round(x.riesgo * 100)}%"></span></span><span class="dato">${x.riesgo.toFixed(2)}</span></span></li>`;
  }

  function abrirLectura(id) {
    const c = o.correos.get(id);
    const tr = tramosDe(c);
    const cuerpo = htmlCuerpo(c, tr);
    const anterior = o.mostrado;
    o.mostrado = id;
    const vista = $("#ops-lectura");
    vista.innerHTML = `
      <div class="lec-meta">
        <span class="rotulo">${esc(t("c_de"))}</span><span class="dato lec-de">${htmlDe(c, tr)}</span>
        <span class="lec-quien">${c.juez ? tagJuez() : `${ms("smart_toy")}${esc(c.agente || "")}`}<span class="dato c-2">${esc(c.id)} · ${esc(hora(c.ts))}</span>${c.escenario && window.hayEpisodioDe?.(c.escenario) ? `<button type="button" class="lec-ep" data-episodio="${esc(c.escenario)}" data-ayuda="${esc(t("ayuda_ver_episodio"))}">${ms("replay")}${esc(t("ver_episodio"))}</button>` : ""}</span>
        <span class="rotulo">${esc(t("p_asunto"))}</span><span class="lec-asunto">${esc(c.asunto || "")}</span>
      </div>
      <div class="lec-cuerpo">${cuerpo.html}</div>
      <ol class="hallazgos"></ol>
      <div class="lec-veredicto"></div>`;
    const previo = anterior && o.correos.get(anterior)?.agente;
    if (previo) pintarAgente(previo);
    if (c.agente) pintarAgente(c.agente);
    return { tr, total: cuerpo.n, vista };
  }

  // Marca hasta el token n: lo leído en texto, el cursor en el token actual y los tramos alcanzados.
  function marcarHasta(L, n, fin) {
    const tks = L.vista.querySelectorAll(".lec-cuerpo .tk");
    for (let i = L.marcado; i < Math.min(n, tks.length); i++) tks[i].classList.add("leido");
    L.marcado = Math.max(L.marcado, Math.min(n, tks.length));
    L.cursor?.classList.remove("cursor");
    L.cursor = fin ? null : tks[Math.min(n, tks.length - 1)] || null;
    L.cursor?.classList.add("cursor");
    const cuerpo = L.vista.querySelector(".lec-cuerpo");
    if (cuerpo && L.cursor) {
      const y = L.cursor.offsetTop;
      if (y + L.cursor.offsetHeight > cuerpo.scrollTop + cuerpo.clientHeight || y < cuerpo.scrollTop) cuerpo.scrollTop = Math.max(0, y - cuerpo.clientHeight / 3);
    }
    if (cuerpo && fin) {
      const alto = cuerpo.querySelector(".tramo.r-alto");
      if (alto) cuerpo.scrollTop = Math.max(0, alto.offsetTop - cuerpo.clientHeight / 3);
    }
    for (const m of L.vista.querySelectorAll(".tramo:not(.visto)")) {
      if (Number(m.dataset.desde) <= n || fin) {
        m.classList.add("visto");
        const x = [...L.tr.dentro, ...L.tr.fuera].find((y) => String(y.k) === m.dataset.k);
        if (x) {
          const lista = L.vista.querySelector(".hallazgos");
          lista.insertAdjacentHTML("beforeend", htmlHallazgo(x));
          lista.scrollTop = lista.scrollHeight;
          if (!fin) reanimar(lista.lastElementChild, "golpe");
        }
      }
    }
    if (fin) for (const x of L.tr.fuera) {
      if (!L.vista.querySelector(`.hallazgo[data-k="${x.k}"]`)) L.vista.querySelector(".hallazgos").insertAdjacentHTML("beforeend", htmlHallazgo(x));
    }
    const pctLeido = L.total ? Math.round((100 * L.marcado) / L.total) : 100;
    $("#n-lectura").textContent = fin ? o.mostrado || "" : t("o_leyendo_pct", { p: pctLeido });
  }

  function siguienteLectura() {
    if (o.leyendo || o.espera) return;
    const id = o.lecturas.shift();
    if (!id) return;
    const c = o.correos.get(id);
    if (!c?.cuerpo) return siguienteLectura();
    const L = abrirLectura(id);
    L.id = id; L.marcado = 0; L.t = 0; L.cursor = null;
    // Duración acotada: no se queda atrás del flujo. Con cola pendiente, se lee más rápido.
    const base = Math.min(2600, Math.max(900, (c.cuerpo.length || 0) * 8));
    L.dur = base * (o.lecturas.length ? 0.5 : 1);
    o.leyendo = L;
    c.fase = "leyendo";
    pintarFila(id);
    const instantaneo = quieto() || !o.visible || c.veredicto?.fuente === "boveda";
    if (instantaneo) return terminarLectura();
    let previo = performance.now();
    const paso = (ahora) => {
      if (o.leyendo !== L) return;
      if (!o.pausa) L.t += (ahora - previo) * o.velocidad;
      previo = ahora;
      if (L.t >= L.dur) return terminarLectura();
      marcarHasta(L, Math.floor((L.t / L.dur) * L.total), false);
      L.raf = requestAnimationFrame(paso);
    };
    L.raf = requestAnimationFrame(paso);
  }

  // Contadores por capa, como `bloqueos_por_capa` del motor: Firewall y Escudo cuentan acciones retenidas;
  // Bóveda, veredictos atajados. Son números propios: no tienen por qué sumar lo mismo que las barras.
  function contarCapa(id, k) {
    const clave = `${id}:${k}`;
    if (!k || o.contadas.has(clave)) return;
    o.contadas.add(clave);
    o.capas[k] = (o.capas[k] || 0) + 1;
  }
  function desenlaceBoveda(c, animar) {
    contarCapa(c.id, "boveda");
    contar(c.id, c.veredicto?.familia, "boveda", "retenida");
    pintarCapas(animar ? "boveda" : null);
  }
  function desenlaceAccion(c, animar) {
    const e = c.accion;
    contar(e.id, e.familia || c.veredicto?.familia, e.capa, e.resultado);
    if (e.resultado === "retenida" && (e.capa === "1" || e.capa === "2")) contarCapa(e.id, e.capa);
    const detenida = e.resultado !== "ejecutada";
    pintarCapas(animar && detenida ? e.capa : null);
    pintarFila(e.id);
    pintarAccion(c);
    if (!animar) return;
    if (detenida && e.agente && e.capa) {
      const a = o.agentes.get(e.agente);
      if (a) { a.retenido = e.capa; a.t = ++o.tick; pintarAgente(e.agente, true); }
    }
    if (e.resultado === "retenida") alarma();
  }
  function aplicarPendiente(c) {
    if (!c.pendiente) return;
    c.pendiente = false;
    if (c.veredicto?.capa === "boveda") desenlaceBoveda(c, true);
    if (c.accion) desenlaceAccion(c, true);
  }

  function terminarLectura() {
    const L = o.leyendo;
    if (!L) return;
    cancelAnimationFrame(L.raf);
    marcarHasta(L, L.total, true);
    o.leyendo = null;
    const c = o.correos.get(L.id);
    c.fase = "leido";
    pintarFila(L.id);
    if (c.agente) pintarAgente(c.agente);
    if (c.veredicto) pintarVeredicto(c);
    aplicarPendiente(c);
    // El veredicto queda a la vista un momento antes de abrir el siguiente. En pausa, espera a «Seguir».
    o.espera = setTimeout(() => { o.espera = null; if (o.pausa) o.retomar = true; else siguienteLectura(); }, escPausa(c.veredicto ? 1100 : 700));
  }

  function pintarVeredicto(c, nuevo = true) {
    if (o.mostrado !== c.id) return;
    const caja = $("#ops-lectura .lec-veredicto");
    if (!caja) return;
    const v = c.veredicto;
    if (!v) { caja.innerHTML = ""; return; }
    const fuente = v.fuente === "boveda" ? t("fu_boveda") : v.fuente === "origen" ? t("fu_origen") : t("fu_clasificador", { v: v.version_modelo || "" });
    const senales = [...(v.senales || [])].sort((a, b) => Math.abs(b.peso) - Math.abs(a.peso));
    const vistas = senales.slice(0, 3), resto = senales.slice(3);
    const maxPeso = Math.max(0.5, ...senales.map((s) => Math.abs(s.peso)));
    caja.dataset.decision = v.decision;
    caja.dataset.ayuda = [fuente, ...(v.senales || []).map((x) => `${senal(x.nombre)}  ${Number(x.peso).toFixed(2)}`)].join("\n");
    caja.innerHTML = `
      <div class="ver-l1">
        ${ms(ICONO_DEC[v.decision] || "check", true)}<span class="ver-dec">${esc(t(`o_dec_${v.decision}`))}</span>
        <span class="ver-conf"><span class="dato">${pct(v.confianza)}</span><span class="medidor"><span style="width:${pct(v.confianza)}"></span></span><span class="c-2">${esc(t("o_confianza"))}</span></span>
        <span class="ver-fuente">${v.decision !== "seguro" ? tagCapa(v.capa) : ""}<span class="${v.fuente === "boveda" ? "" : "c-2"}">${esc(fuente)}</span></span>
      </div>
      ${vistas.length ? `<ol class="ver-senales">${vistas.map((s) => `<li data-ayuda="${esc(senal(s.nombre))}"><span>${esc(senal(s.nombre))}</span><span class="medidor"><span style="width:${Math.round((Math.abs(s.peso) / maxPeso) * 100)}%"></span></span><span class="dato">${s.peso.toFixed(2)}</span></li>`).join("")}${resto.length ? `<span class="mas" tabindex="0" data-ayuda="${esc(resto.map((s) => `${senal(s.nombre)}  ${s.peso.toFixed(2)}`).join("\n"))}">+${resto.length}</span>` : ""}</ol>` : ""}
      <div class="ver-accion"></div>`;
    if (nuevo) reanimar(caja, "golpe");
    const anuncio = $("#ops-anuncio");
    if (anuncio && nuevo) anuncio.textContent = `${c.agente || ""}: ${t(`o_dec_${v.decision}`)} ${pct(v.confianza)}${v.capa && v.decision !== "seguro" ? ` · ${capa(v.capa)}` : ""}`;
    pintarAccion(c);
  }

  function textoAccion(a) {
    const g = a.args || {};
    const partes = [a.herramienta];
    if (g.monto) partes.push(plata(g.monto));
    if (g.cuenta) partes.push(`→ ${g.cuenta}`);
    else if (g.a) partes.push(`→ ${g.a}`);
    if (g.adjunto) partes.push(g.adjunto);
    if (g.ruta) partes.push(g.ruta);
    return partes.join(" ");
  }
  function pintarAccion(c) {
    if (o.mostrado !== c.id) return;
    const caja = $("#ops-lectura .ver-accion");
    const a = c.accion;
    if (!caja || !a) return;
    const detenida = a.resultado !== "ejecutada";
    const malo = !detenida && c.veredicto?.decision === "estafa";
    caja.className = `ver-accion ${detenida ? "detenida" : malo ? "mala" : ""}`;
    caja.innerHTML = `${ms(detenida ? "block" : a.herramienta === "pagar" || a.herramienta === "transferir" ? "payments" : "smart_toy")}
      <span class="dato a-txt">${esc(textoAccion(a))}</span><span class="a-res">${esc(t(`ac_${a.resultado}`))}</span>${detenida ? tagCapa(a.capa) : ""}`;
    caja.dataset.ayuda = a.motivo || "";
    reanimar(caja, "golpe");
  }

  // --- Registro: todos los eventos, con hora, en mono ---
  // Una ráfaga (varios indicadores que entran a la bóveda juntos, o varias versiones del modelo seguidas) va en
  // una sola línea que se actualiza, en vez de llenar el registro de líneas iguales.
  const VENTANA_GRUPO = 3;   // segundos entre eventos del mismo tipo para que cuenten como una ráfaga
  function agrupar(ol, e) {
    if (e.tipo !== "boveda" && e.tipo !== "modelo") return false;
    // La ráfaga puede venir intercalada con la otra (modelo, bóveda, modelo): se busca en las últimas líneas.
    let li = ol.lastElementChild;
    for (let k = 0; li && k < 3 && li.dataset.grupo !== e.tipo; k++) li = li.previousElementSibling;
    if (!li || li.dataset.grupo !== e.tipo || (e.ts || 0) - Number(li.dataset.ts || 0) > VENTANA_GRUPO) return false;
    const g = JSON.parse(li.dataset.g);
    let txt;
    if (e.tipo === "boveda") {
      const i = e.indicador || {};
      g.n++;
      if (i.veces > 1) g.repetidos++;
      g.tipos[i.tipo] = (g.tipos[i.tipo] || 0) + 1;
      txt = textoBoveda(g);
    } else {
      g.hasta = e.version;
      txt = `${g.desde} → ${e.version} · p ${Number(e.precision).toFixed(2)} r ${Number(e.recall).toFixed(2)} fa ${Number(e.falsas_alarmas).toFixed(2)}`;
    }
    li.dataset.g = JSON.stringify(g);
    li.dataset.ts = String(e.ts || 0);
    li.querySelector(".r-txt").textContent = txt;
    li.querySelector("time").textContent = hora(e.ts);
    reanimar(li, "golpe");
    return true;
  }
  function textoBoveda(g) {
    const partes = Object.entries(g.tipos).map(([tipo, n]) => `${n} ${t(`bv_${tipo}`)}`);
    return `+${g.n} ${t("o_indicadores_r")} · ${partes.join(" · ")}${g.repetidos ? ` · ${t("o_repetidos", { n: g.repetidos })}` : ""}`;
  }

  function registrar(e) {
    const ol = $("#ops-registro");
    if (!ol) return;
    if (agrupar(ol, e)) { $("#n-registro").textContent = String(o.eventos = (o.eventos || 0) + 1); return; }
    let cls = "", txt;
    const id = e.id ? `${e.id} ` : "";
    switch (e.tipo) {
      case "agente_estado": cls = "r-baja"; txt = `${e.agente} ${e.estado}${e.tarea ? ` · ${e.tarea}` : ""}`; break;
      case "correo_nuevo": txt = `${id}${e.agente} ← ${e.de}`; break;
      case "lectura": { const tr = e.tramos || []; txt = `${id}${tr.length} tramos${tr.length ? ` · máx ${Math.max(...tr.map((x) => x.riesgo)).toFixed(2)}` : ""}`; break; }
      case "veredicto": cls = e.decision === "estafa" ? "r-rojo" : ""; txt = `${id}${String(t(`o_dec_${e.decision}`)).toUpperCase()} ${Number(e.confianza).toFixed(2)}${e.capa && e.decision !== "seguro" ? ` · ${capa(e.capa)}` : ""}`; break;
      case "accion": cls = e.resultado !== "ejecutada" ? "r-verde" : ""; txt = `${id}${textoAccion(e)} · ${t(`ac_${e.resultado}`)}${e.capa && e.resultado !== "ejecutada" ? ` · ${capa(e.capa)}` : ""}`; break;
      case "boveda": { const i = e.indicador || {}; txt = `${i.veces > 1 ? `×${i.veces}` : "+"} ${t(`bv_${i.tipo}`)} ${i.valor}`; break; }
      case "duelo": txt = `g${e.generacion} · ${t("o_evasion")} ${pct(e.evasion)} · recall ${Number(e.recall).toFixed(2)} · ${t("o_capa2")} ${e.exitosas_capa2}`; break;
      case "modelo": txt = `${e.version} · p ${Number(e.precision).toFixed(2)} r ${Number(e.recall).toFixed(2)} fa ${Number(e.falsas_alarmas).toFixed(2)}`; break;
      default: txt = JSON.stringify(e).slice(0, 120);
    }
    const abajo = ol.scrollHeight - ol.scrollTop - ol.clientHeight < 24;
    // La primera línea de una ráfaga posible guarda lo necesario para sumarle las siguientes.
    let grupo = "";
    if (e.tipo === "boveda") {
      const i = e.indicador || {};
      grupo = ` data-grupo="boveda" data-ts="${e.ts || 0}" data-g="${esc(JSON.stringify({ n: 1, repetidos: i.veces > 1 ? 1 : 0, tipos: { [i.tipo]: 1 } }))}"`;
    } else if (e.tipo === "modelo") {
      grupo = ` data-grupo="modelo" data-ts="${e.ts || 0}" data-g="${esc(JSON.stringify({ desde: e.version, hasta: e.version }))}"`;
    }
    ol.insertAdjacentHTML("beforeend", `<li class="${cls}"${grupo}><time>${esc(hora(e.ts))}</time><span class="r-tipo">${esc(e.tipo === "agente_estado" ? "agente" : e.tipo === "correo_nuevo" ? "correo" : e.tipo)}</span><span class="r-txt">${esc(txt)}</span></li>`);
    while (ol.children.length > MAX_REGISTRO) ol.firstElementChild.remove();
    if (abajo) ol.scrollTop = ol.scrollHeight;
    $("#n-registro").textContent = String(o.eventos = (o.eventos || 0) + 1);
  }

  // --- Defensa en capas: contadores por capa y una barra apilada por familia ---
  // Una sola unidad para contadores y barras: el desenlace de cada correo. Manda la capa que retuvo la
  // acción (Firewall o Escudo); la bóveda cuenta cuando ninguna capa la retuvo; «paso» si se ejecutó.
  // Así el número grande cuadra con las barras y se ve qué frena cada capa.
  function contar(id, familia, capa_, resultado) {
    const k = resultado === "ejecutada" ? "paso" : capa_;
    if (!k) return;
    const previo = o.desenlace.get(id);
    if (previo) {
      if (!(previo.k === "boveda" && (k === "1" || k === "2"))) return;
      o.bloqueos[previo.f].boveda--;
    }
    const fam = previo?.f || familia || "legitimo";
    o.desenlace.set(id, { f: fam, k });
    const b = (o.bloqueos[fam] ||= {});
    b[k] = (b[k] || 0) + 1;
  }
  function pintarCapas(golpe) {
    const tot = (k) => o.capas[k] || 0;
    const filas = FAMILIAS.map((f) => {
      const b = o.bloqueos[f] || {};
      const n = CAPAS.reduce((s, k) => s + (b[k] || 0), 0) + (b.paso || 0);
      const det = n - (b.paso || 0);
      const seg = (k, cls) => (b[k] ? `<span class="seg ${cls}" style="flex-grow:${b[k]}" data-ayuda="${esc(k === "paso" ? t("ac_ejecutada") : capa(k))}: ${b[k]}"></span>` : "");
      return `<li class="familia" tabindex="0" data-ayuda="${esc(t("ayuda_familia"))}">
        <span class="fa-nombre">${esc(t(`f_${f}`))}</span><span class="dato c-2">${n ? esc(t(f === "legitimo" ? "o_retenidas" : "o_detenidas", { a: det, n })) : "—"}</span>
        <span class="apilada">${seg("1", "s-1")}${seg("2", "s-2")}${seg("boveda", "s-b")}${seg("paso", f === "legitimo" ? "s-ok" : "s-mal")}</span></li>`;
    }).join("");
    $("#ops-capas").innerHTML = `<ul class="contadores">${CAPAS.map((k) => `<li data-capa="${k}" tabindex="0" data-ayuda="${esc(t(`ayuda_capa_${k}`))}"><span class="muestra s-${k === "boveda" ? "b" : k}"></span><span>${esc(capa(k))}</span><span class="dato">${tot(k)}</span></li>`).join("")}</ul><ol class="familias">${filas}</ol>`;
    if (golpe) reanimar($(`#ops-capas [data-capa="${golpe}"] .dato`), "golpe");
  }

  // --- Bóveda: la cuarentena de indicadores ---
  function htmlIndicador(i) {
    return `${ms(ICONO_BOVEDA[i.tipo] || "description")}<span class="dato bv-valor">${esc(i.valor)}</span>
      <span class="bv-tipo">${esc(t(`bv_${i.tipo}`))}</span><span class="dato bv-veces">×${i.veces || 1}</span><time class="dato">${esc(hora(i.primera_vez))}</time>`;
  }
  function pintarIndicador(i, animar) {
    const ol = $("#ops-boveda");
    ol.querySelector(".vacio")?.remove();
    let li = ol.querySelector(`[data-valor="${CSS.escape(i.valor)}"]`);
    const nuevo = !li;
    if (!li) { li = document.createElement("li"); li.className = "fila-bv"; li.dataset.valor = i.valor; ol.prepend(li); }
    li.dataset.ayuda = t("bv_origen", { o: i.origen || "—", h: hora(i.primera_vez) });
    li.innerHTML = htmlIndicador(i);
    if (animar) reanimar(li, nuevo ? "entra-fila" : "golpe");
    $("#n-boveda").textContent = t("o_indicadores", { n: o.boveda.size });
  }
  function pintarBoveda() {
    const ol = $("#ops-boveda");
    ol.innerHTML = o.boveda.size ? "" : `<li class="vacio">${esc(t("o_bv_vacia"))}</li>`;
    [...o.boveda.values()].sort((a, b) => (a.primera_vez || 0) - (b.primera_vez || 0)).forEach((i) => pintarIndicador(i, false));
    $("#n-boveda").textContent = t("o_indicadores", { n: o.boveda.size });
  }

  // --- Modelo: versión, métricas, curva y pesos ---
  function pintarModelo(animar) {
    const m = o.modelo;
    $("#ops-version").textContent = m ? `v${m.version}` : "";
    $("#n-modelo").textContent = m ? t("o_ejemplos", { n: m.ejemplos }) : t("o_sin_modelo");
    if (animar) reanimar($("#ops-version"), "golpe");
    const ant = o.historial.at(-2);
    // Falsas alarmas: el conteo detrás del porcentaje (con pocos legítimos apartados, cada uno pesa varios puntos).
    const conteo = m && Number.isFinite(m.legitimos) && m.legitimos > 0;
    const ayudaFalsas = () => {
      if (!conteo) return t("ayuda_falsas");
      const cv = window.RESULTADOS?.clasificador?.falsas_alarmas || estado.resultados?.clasificador?.falsas_alarmas;
      const marcados = (m.marcados || []).map((x) => `${x.escenario} (${x.n})`).join(", ");
      return t("ayuda_falsas_n", { f: m.falsas, l: m.legitimos, pp: (100 / m.legitimos).toFixed(1), ep: (300 / m.legitimos).toFixed(1),
        marcados: marcados ? t("o_marcados", { lista: marcados }) : "",
        cv: cv ? t("o_cv_falsas", { m: Math.round(cv.media * 100), a: Math.round(cv.min * 100), b: Math.round(cv.max * 100) }) : "" });
    };
    const met = (clave, campo, linea, menosEsMejor) => {
      const v = m?.[campo];
      const d = ant && v !== undefined ? Math.round((v - ant[campo]) * 1000) / 10 : 0;
      const dcls = !d ? "" : (d < 0) === menosEsMejor ? "c-verde" : "c-rojo";
      const falsas = clave === "o_falsas";
      const n = falsas && conteo ? `<span class="m-n">${esc(t("o_de", { f: m.falsas, l: m.legitimos }))}</span>` : "";
      return `<div class="metrica" data-ayuda="${esc(falsas ? ayudaFalsas() : t(`ayuda_${clave.slice(2)}`))}">
        <span class="m-et"><span class="linea ${linea}"></span>${esc(t(clave))}</span>
        <span class="m-val dato">${v === undefined ? "—" : pct(v)}</span>
        <span class="m-delta dato ${dcls}">${n}${d ? `${d > 0 ? "+" : ""}${d.toFixed(1)}` : ""}</span></div>`;
    };
    $("#ops-metricas").innerHTML = `<span class="m-de">${esc(t("o_el_clasificador"))}</span>` + met("o_precision", "precision", "l-1") + met("o_recall", "recall", "l-2") + met("o_falsas", "falsas_alarmas", "l-3", true);
    pintarGrifter();
    if (animar) $("#ops-metricas").querySelectorAll(".m-val").forEach((el) => reanimar(el, "golpe"));
    pintarPesos();
    pintarColados();
    pintarCurva();
  }
  // Lo que frena Grifter completo en el benchmark, junto a la detección del clasificador, para que no se confundan.
  function pintarGrifter() {
    const el = $("#ops-grifter");
    const to = estado.resultados?.cobertura?.totales;
    if (!el) return;
    if (!to) { el.hidden = true; return; }
    el.hidden = false;
    el.dataset.ayuda = t("ayuda_grifter_completo", { r: to.frenadas_bench, a: to.ataques_bench, f: to.familias });
    el.innerHTML = `${ms("verified_user")}<span class="og-txt"><span class="og-de">${esc(t("o_grifter"))}</span><span class="dato">${esc(t("o_grifter_completo", { r: to.frenadas_bench, a: to.ataques_bench }))}</span></span>
      <a href="#resultados" aria-label="${esc(t("o_ver_resultados"))}" data-ayuda="${esc(t("o_ver_resultados"))}">${ms("arrow_forward")}</a>`;
  }
  // Se colaron: las estafas apartadas que el modelo dejó como no-estafa (`colados` del evento `modelo`), por tipo.
  function pintarColados() {
    const lista = o.modelo?.colados;
    const ol = $("#ops-colados");
    $("#t-colados").dataset.ayuda = t("ayuda_colados");
    if (!Array.isArray(lista)) { ol.innerHTML = ""; $("#n-colados").textContent = ""; return; }
    const grupos = new Map();
    for (const c of lista) {
      const g = grupos.get(c.familia) || { familia: c.familia, n: 0, de: 0, detalle: [] };
      g.n += c.n || 0; g.de += c.de || 0;
      g.detalle.push(t("ayuda_colado", { e: c.escenario, c: nombreCanal(c.canal), n: c.n, d: c.de, p: Number(c.probabilidad).toFixed(2) }));
      grupos.set(c.familia, g);
    }
    const filas = [...grupos.values()].sort((a, b) => b.n - a.n || b.n / b.de - a.n / a.de || String(a.familia).localeCompare(b.familia));
    $("#n-colados").textContent = String(filas.reduce((x, g) => x + g.n, 0));
    ol.innerHTML = filas.length ? filas.map((g) => `<li data-ayuda="${esc(g.detalle.join("\n"))}"><span class="co-nombre">${esc(nombreFamilia(g.familia))}</span><span class="dato">${g.n}/${g.de}</span></li>`).join("")
      : `<li class="vacio">${esc(t("o_colados_ninguna"))}</li>`;
  }
  function pintarPesos() {
    const filas = Object.entries(o.pesos).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 8);
    const max = Math.max(0.5, ...filas.map(([, p]) => Math.abs(p)));
    const ol = $("#ops-pesos");
    const previos = new Map([...ol.querySelectorAll("li")].map((li) => [li.dataset.senal, li]));
    ol.innerHTML = filas.map(([n, p]) => {
      const c = o.cambios[n];
      return `<li data-senal="${esc(n)}" class="${p < 0 ? "negativo" : ""}"><span class="p-nombre">${esc(senal(n))}</span>
        <span class="medidor"><span style="width:${Math.round((Math.abs(p) / max) * 100)}%"></span></span>
        <span class="dato">${p.toFixed(2)}</span><span class="dato p-delta">${c ? `${c > 0 ? "+" : ""}${c.toFixed(2)}` : ""}</span></li>`;
    }).join("");
    // La barra crece desde su ancho anterior: el cambio de peso se ve.
    for (const li of ol.querySelectorAll("li")) {
      const prev = previos.get(li.dataset.senal);
      const barra = li.querySelector(".medidor > span");
      if (prev && barra && !quieto()) {
        const w = barra.style.width;
        barra.style.width = prev.querySelector(".medidor > span")?.style.width || w;
        requestAnimationFrame(() => requestAnimationFrame(() => { barra.style.width = w; }));
      }
      if (o.cambios[li.dataset.senal]) reanimar(li, "golpe");
    }
  }
  function pintarCurva() {
    if (!o.visible || !Graficos.hay) return;
    const el = $("#ops-curva");
    if (!o.curva || !el.isConnected || !echarts.getInstanceByDom(el)) o.curva = Graficos.curvas(el);
    // Una versión sin ejemplos no tiene métricas: no se grafica como 0 %.
    const h = o.historial.filter((m) => m.ejemplos > 0 && m.precision !== null && m.precision !== undefined).slice(-MAX_CURVA);
    o.curva?.poner([h.map((m) => [m.ejemplos, m.precision * 100]), h.map((m) => [m.ejemplos, m.recall * 100]), h.map((m) => [m.ejemplos, m.falsas_alarmas * 100])], [t("o_precision"), t("o_recall"), t("o_falsas")]);
  }

  // --- Estado de alerta: el borde rojo parpadea cuando la defensa retiene una acción ---
  function alarma() {
    if (!o.visible) return;
    clearTimeout(o.alarma);
    bordeAlerta(true);
    o.alarma = setTimeout(() => { o.alarma = null; if (o.visible) bordeAlerta(false); }, escPausa(2600));
  }

  // --- Eventos ---
  function aplicar(e) {
    if (!e || !e.tipo) return;
    registrar(e);
    switch (e.tipo) {
      case "agente_estado": {
        const a = o.agentes.get(e.agente) || { agente: e.agente };
        const cambio = a.estado !== e.estado;
        o.agentes.set(e.agente, { ...a, estado: e.estado, tarea: e.tarea, retenido: null, t: ++o.tick });
        pintarAgente(e.agente, cambio);
        break;
      }
      case "correo_nuevo": {
        const c = correo(e.id);
        Object.assign(c, { agente: e.agente, de: e.de, asunto: e.asunto, cuerpo: e.cuerpo, ts: e.ts, juez: !!e.juez || e.escenario === "juez", escenario: e.escenario || null });
        if (!o.orden.includes(e.id)) o.orden.push(e.id);
        if (o.orden.length > 200) { const v = o.orden.shift(); if (v !== o.mostrado) o.correos.delete(v); }
        pintarFila(e.id, true);
        if (e.agente) pintarAgente(e.agente);
        break;
      }
      case "lectura": {
        correo(e.id).lectura = e;
        if (!o.lecturas.includes(e.id)) o.lecturas.push(e.id);
        // Si la fila se atrasa, la lectura en curso se adelanta.
        if (o.leyendo && o.lecturas.length > 1) o.leyendo.dur = Math.min(o.leyendo.dur, o.leyendo.t + 300);
        siguienteLectura();
        break;
      }
      case "veredicto": {
        const c = correo(e.id);
        c.veredicto = e;
        if (e.decision === "estafa" && !c.juez) anotarEstafa(e.escenario || c.escenario, c.id);
        if (o.leyendo?.id === e.id && e.fuente === "boveda") terminarLectura();
        else if (c.fase === "leido") { pintarFila(e.id); pintarVeredicto(c); }
        if (!c.cuerpo) { c.fase = "leido"; pintarFila(e.id); }
        if (e.capa === "boveda") { if (c.fase === "leido") desenlaceBoveda(c, true); else c.pendiente = true; }
        break;
      }
      case "accion": {
        const c = correo(e.id);
        c.accion = e;
        // Si el correo todavía está en cola o en lectura, el desenlace espera a que Lectura lo termine.
        if (c.fase === "leido" || !c.cuerpo) desenlaceAccion(c, true); else c.pendiente = true;
        break;
      }
      case "boveda": {
        const i = e.indicador;
        if (!i?.valor) break;
        o.boveda.set(i.valor, { ...o.boveda.get(i.valor), ...i });
        pintarIndicador(o.boveda.get(i.valor), true);
        break;
      }
      case "duelo": window.Duelo?.aplicar(e); break;
      case "modelo": {
        o.modelo = e;
        if (!o.historial.some((m) => m.version === e.version)) o.historial.push(e);
        if (o.historial.length > 200) o.historial.shift();
        o.cambios = {};
        for (const c of e.cambios || []) { o.pesos[c.senal] = c.peso_despues; o.cambios[c.senal] = c.peso_despues - c.peso_antes; }
        if (e.pesos) Object.assign(o.pesos, e.pesos);
        pintarModelo(true);
        break;
      }
    }
  }

  // La foto de /api/vivo/estado. Claves supuestas: agentes, boveda, modelo, historial_modelo, correos
  // (cada uno con lectura, veredicto y accion anidados), bloqueos_por_capa. Se lee con tolerancia.
  function cargarFoto(f) {
    if (!f || typeof f !== "object") return;
    const lista = (x) => (Array.isArray(x) ? x : x && typeof x === "object" ? Object.values(x) : []);
    for (const a of lista(f.agentes)) if (a?.agente) o.agentes.set(a.agente, { ...o.agentes.get(a.agente), ...a });
    for (const i of lista(f.boveda)) { const x = i?.indicador || i; if (x?.valor) o.boveda.set(x.valor, x); }
    o.historial = lista(f.historial_modelo || f.modelo?.historial).filter((m) => m?.version);
    o.modelo = f.modelo?.version ? f.modelo : o.historial.at(-1) || null;
    if (o.modelo && !o.historial.some((m) => m.version === o.modelo.version)) o.historial.push(o.modelo);
    if (o.modelo?.pesos) Object.assign(o.pesos, o.modelo.pesos);
    else for (const m of o.historial) for (const c of m.cambios || []) o.pesos[c.senal] = c.peso_despues;
    for (const c of lista(f.correos)) {
      if (!c?.id) continue;
      const x = correo(c.id);
      Object.assign(x, { agente: c.agente, de: c.de, asunto: c.asunto, cuerpo: c.cuerpo, ts: c.ts, fase: "leido", juez: !!c.juez || c.escenario === "juez", escenario: c.escenario || null });
      x.lectura = c.lectura || (c.tramos ? { tramos: c.tramos } : null);
      x.veredicto = c.veredicto || (c.decision ? { decision: c.decision, confianza: c.confianza, senales: c.senales, fuente: c.fuente, capa: c.capa, version_modelo: c.version_modelo } : null);
      x.accion = c.accion || null;
      if (!x.veredicto) x.fase = "cola";
      if (x.veredicto?.capa === "boveda") { contar(c.id, x.veredicto.familia, "boveda", "retenida"); contarCapa(c.id, "boveda"); }
      if (x.accion) contar(c.id, x.accion.familia || x.veredicto?.familia, x.accion.capa, x.accion.resultado);
      if (x.accion?.resultado === "retenida" && (x.accion.capa === "1" || x.accion.capa === "2")) contarCapa(c.id, x.accion.capa);
      if (x.veredicto?.decision === "estafa" && !x.juez) anotarEstafa(x.veredicto.escenario || x.escenario, c.id);
      if (!x.veredicto && (x.accion || x.lectura)) x.pendiente = !!x.accion;
      if (!o.orden.includes(c.id)) o.orden.push(c.id);
    }
    // Los contadores del motor cubren también lo anterior a los últimos 50 correos.
    const b = f.bloqueos_por_capa;
    if (b && typeof b === "object") for (const k of CAPAS) if (typeof b[k] === "number") o.capas[k] = Math.max(o.capas[k] || 0, b[k]);
    window.Duelo?.cargar(f.historial_duelo);
    if (typeof f.pausa === "boolean") o.pausa = f.pausa;
    if ([1, 2, 4].includes(Number(f.velocidad))) { o.velocidad = Number(f.velocidad); estado.velocidad = o.velocidad; }
    pintarTodo();
    // El último correo con veredicto queda abierto, sin animación, para que la vista arranque con contexto.
    const ultimo = [...o.orden].reverse().find((id) => o.correos.get(id)?.veredicto && o.correos.get(id)?.cuerpo);
    if (ultimo) {
      const L = abrirLectura(ultimo);
      L.marcado = 0;
      marcarHasta(L, L.total, true);
      pintarVeredicto(o.correos.get(ultimo), false);
    }
  }

  function pintarTodo() {
    $("#ops-agentes").innerHTML = "";
    pintarAgentes();
    $("#ops-cola").innerHTML = "";
    o.filas.clear();
    for (const id of o.orden.slice(-MAX_COLA)) pintarFila(id, false);
    if (!o.orden.length) $("#ops-cola").innerHTML = `<li class="vacio">${esc(t("o_sin_correo"))}</li>`;
    pintarCapas();
    pintarBoveda();
    pintarModelo(false);
    pintarControles();
    if (o.mostrado && o.correos.get(o.mostrado)?.cuerpo && !o.leyendo) {
      const L = abrirLectura(o.mostrado);
      L.marcado = 0;
      marcarHasta(L, L.total, true);
      pintarVeredicto(o.correos.get(o.mostrado), false);
    } else if (!o.mostrado) $("#ops-lectura").innerHTML = `<p class="vacio">${esc(t("o_sin_correo"))}</p>`;
  }

  // --- Fuente: el motor real por SSE o el emisor local ---
  function pintarControles() {
    const sello = $("#ops-sello");
    sello.textContent = o.pausa ? `${t(`o_sello_${o.sello}`)} · ${t("o_en_pausa")}` : t(`o_sello_${o.sello}`);
    sello.dataset.estado = o.sello;
    window.Duelo?.pintarVivo();   // la celda «En vivo» del Duelo dice de dónde salen sus números
    sello.dataset.pausa = String(o.pausa);
    const b = $("#ops-pausa");
    b.setAttribute("aria-pressed", String(o.pausa));
    b.setAttribute("aria-label", t("o_pausa"));
    b.dataset.ayuda = t(o.pausa ? "o_seguir" : "o_pausa");
    b.querySelector(".ms").textContent = o.pausa ? "play_arrow" : "pause";
    document.querySelectorAll("[data-ops-velocidad]").forEach((x) => x.setAttribute("aria-pressed", String(Number(x.dataset.opsVelocidad) === o.velocidad)));
  }

  async function control(accion, valor) {
    if (accion === "pausa" || accion === "seguir") o.pausa = accion === "pausa";
    if (accion === "seguir" && o.retomar) { o.retomar = false; siguienteLectura(); }
    if (accion === "velocidad") { o.velocidad = valor; estado.velocidad = valor; }
    pintarControles();
    try { await o.fuente?.control({ accion, ...(valor ? { valor } : {}) }); }
    catch (err) { console.warn("control del flujo falló", err); }
  }

  function reiniciar() {
    if (o.leyendo) cancelAnimationFrame(o.leyendo.raf);
    clearTimeout(o.espera);
    Object.assign(o, { correos: new Map(), orden: [], filas: new Map(), lecturas: [], leyendo: null, mostrado: null, espera: null, retomar: false,
      boveda: new Map(), historial: [], bloqueos: {}, desenlace: new Map(), capas: {}, contadas: new Set() });
  }

  function usarSimulado() {
    o.sello = "sim";
    const sim = VivoSimulado.crear(aplicar);
    o.fuente = { tipo: "sim", control: async (c) => sim.control(c) };
    cargarFoto(sim.estado());
  }

  async function conectar() {
    const p = new URLSearchParams(location.search);
    const base = p.get("motor") ? p.get("motor").replace(/\/?$/, "/") : "";
    if (p.has("sim") || location.protocol === "file:" || typeof EventSource === "undefined") return usarSimulado();
    try {
      const r = await fetch(`${base}api/vivo/estado`, { cache: "no-store", signal: AbortSignal.timeout?.(1500) });
      if (!r.ok) throw new Error(String(r.status));
      const foto = await r.json();
      o.sello = "conectando";
      cargarFoto(foto);
      o.idiomaMotor = foto.idioma;
    } catch (_) { return usarSimulado(); }
    const es = new EventSource(`${base}api/vivo`);
    o.fuente = {
      tipo: "real",
      control: async (c) => {
        const r = await fetch(`${base}api/vivo/control`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(c) });
        if (!r.ok) throw new Error(String(r.status));
      },
    };
    // El motor arranca en español; si la página está en inglés, se lo pide.
    if (o.idiomaMotor && o.idiomaMotor !== estado.idioma && o.idiomaMotor !== "ambos") control("idioma", estado.idioma);
    // Tras un corte, los eventos perdidos descuadran todo: se vuelve a pedir la foto y se reconstruye.
    es.onopen = async () => {
      if (o.sello === "reconectando") {
        try { const r = await fetch(`${base}api/vivo/estado`, { cache: "no-store" }); if (r.ok) { reiniciar(); cargarFoto(await r.json()); } }
        catch (_) { /* se queda con lo que tiene */ }
      }
      o.sello = "real"; pintarControles();
    };
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) { reiniciar(); return usarSimulado(); }
      o.sello = "reconectando"; pintarControles();
    };
    es.onmessage = (m) => { try { aplicar(JSON.parse(m.data)); } catch (err) { console.warn("evento ilegible", err); } };
  }

  // --- Vista ---
  function alCambiarVista(vista) {
    const antes = o.visible;
    o.visible = vista === "operaciones";
    if (!o.iniciado) return;
    if (o.visible && !antes) {
      clearTimeout(o.alarma); o.alarma = null;
      bordeAlerta(false);
      requestAnimationFrame(() => { pintarCurva(); Graficos.redimensionar(); });
    } else if (!o.visible && antes) {
      clearTimeout(o.alarma); o.alarma = null;
      // Al salir, el borde vuelve a lo que diga En vivo: una alerta sin responder.
      bordeAlerta(!!(estado.alerta && !estado.carriles.layer2?.decision));
    }
  }

  function elegirPanel(panel) {
    $("#vista-operaciones").dataset.panel = panel;
    document.querySelectorAll(".ops-tabs [data-panel]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.panel === panel)));
    if (panel === "modelo") requestAnimationFrame(() => { pintarCurva(); Graficos.redimensionar(); });
    if (panel === "registro") { const ol = $("#ops-registro"); ol.scrollTop = ol.scrollHeight; }
  }
  function espejos() {
    for (const el of document.querySelectorAll("[data-espejo]")) {
      const origen = document.getElementById(el.dataset.espejo);
      if (!origen) continue;
      const copiar = () => { el.textContent = (origen.textContent.match(/v?[\d.]+/) || [""])[0]; };
      copiar();
      new MutationObserver(copiar).observe(origen, { childList: true, characterData: true, subtree: true });
    }
  }

  function iniciar() {
    o.iniciado = true;
    espejos();
    document.querySelectorAll(".ops-tabs [data-panel]").forEach((b) => b.addEventListener("click", () => elegirPanel(b.dataset.panel)));
    pintarTextos();
    pintarTodo();
    alCambiarVista(estado.vista);
    $("#ops-agentes").addEventListener("click", (ev) => {
      if (!ev.target.closest(".ag-mas-b")) return;
      o.agentesTodos = !o.agentesTodos;
      ajustarAgentes();
    });
    if (window.ResizeObserver) {
      let ancho = 0;   // solo importa el ancho: esconder celdas cambia el alto y no debe disparar otra vuelta
      new ResizeObserver(() => {
        const w = $("#ops-agentes").clientWidth;
        if (w !== ancho) { ancho = w; ajustarAgentes(); }
      }).observe($("#ops-agentes"));
    }
    $("#ops-pausa").addEventListener("click", () => control(o.pausa ? "seguir" : "pausa"));
    document.querySelectorAll("[data-ops-velocidad]").forEach((b) => b.addEventListener("click", () => control("velocidad", Number(b.dataset.opsVelocidad))));
    document.querySelectorAll("[data-idioma]").forEach((b) => b.addEventListener("click", () => {
      pintarTodo();
      if (o.fuente?.tipo === "real") control("idioma", estado.idioma);
    }));
    conectar();
  }

  return { iniciar, alCambiarVista, aplicar, pintarGrifter, ultimaEstafa: (sirve = () => true) => [...o.estafas].reverse().find((x) => sirve(x.escenario)) || null, _o: o };
})();
window.Operaciones = Operaciones;
Operaciones.alCambiarVista(estado.vista);
Operaciones.iniciar();

// El enlace «Ver el episodio» del panel Lectura abre ese escenario en Episodios.
document.addEventListener("click", (e) => {
  const b = e.target.closest(".lec-ep[data-episodio]");
  if (b) window.abrirEpisodio?.(b.dataset.episodio);
});
