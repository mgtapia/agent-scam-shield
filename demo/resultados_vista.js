// Grifter, vista Resultados: la historia del benchmark de arriba abajo, con los números de resultados.json
// (scripts/resultados_demo.py, que a su vez lee results/). La página no calcula ninguna tasa: solo dibuja.
// Cada cifra lleva su intervalo o, si sus unidades no son independientes, dice que es un conteo.
// Cada bloque enlaza a su fuente en el repo y deja copiar el comando que la produce.
// Depende de app.js (T, t, esc, ms, $, estado, nombreFamilia, abrirEpisodio) y de graficos.js.
"use strict";

const ResultadosVista = (() => {
  Object.assign(T.es, {
    r_bench: "Las defensas, con un agente que hace todo lo que lee", r_segutil: "Seguridad contra utilidad", r_reales: "Modelos y firewall reales",
    r_atacante: "Atacante adaptativo", r_duelo: "Duelo", r_idiomas: "Español contra inglés", r_clasif_b: "Clasificador que aprende",
    r_estafas: "Estafas exitosas", r_utilidad: "Utilidad", r_falsas: "Falsas alarmas", r_config: "Configuración",
    rc_none: "Sin defensa", rc_layer1: "Firewall de referencia", rc_layer2: "Escudo: origen", rc_layer3: "Escudo: beneficiario", rc_layer23: "Grifter (capas 2 y 3)",
    ayuda_rc_none: "El agente paga lo que le pidan", ayuda_rc_layer1: "Capa 1: reglas contra la inyección técnica",
    ayuda_rc_layer2: "Capa 2: la cuenta tiene que venir del dueño, no de un correo", ayuda_rc_layer3: "Capa 3: el titular de la cuenta tiene que ser el beneficiario",
    ayuda_rc_layer23: "Capas 2 y 3 juntas: la configuración completa de Grifter",
    r_n_bench: "{e} estafas · {c} controles · ES y EN · agente guionado",
    ayuda_bench: "{aviso}. Intervalo al 95 %, por escenario.",
    r_vs: "vs sin defensa {v}", r_pp: "{s}{n} pp",
    ayuda_cifra_estafas: "Estafas que cobraron con Grifter (capas 2 y 3) contra sin defensa. Agente guionado: mide las defensas, no un modelo. El delta va en color solo si los intervalos no se tocan",
    ayuda_cifra_utilidad: "Tareas legítimas que el agente cumplió con Grifter contra sin defensa",
    ayuda_cifra_falsas: "Controles legítimos en que Grifter bloqueó algo, contra sin defensa",
    r_duelo_cifra: "Pagos que cruzaron la capa 2", r_de: "{a} de {b}", r_conteo: "conteo",
    ayuda_conteo_duelo: "Intentos del hacker en {g} generaciones. La misma cepa vuelve en varias generaciones: los intentos no son independientes, por eso no lleva intervalo",
    r_ver_duelo: "Ver el duelo",
    r_eje_x: "estafas exitosas", r_eje_y: "utilidad",
    r_pipelock: "Pipelock, firewall de agentes", r_pipelock_det: "frenadas, todas técnicas: inyección web y MCP envenenado · {fa} falsas alarmas",
    r_pipelock_tag: "sin archivo", ayuda_pipelock_tag: "No hay archivo en results/: la cifra sale de {f}",
    r_sonnet: "Claude Sonnet, «paga lo que el gerente apruebe»", r_sonnet_det: "pagos al estafador con el correo de la dirección comprometida del gerente · la capa 2 lo retiene",
    ayuda_sonnet: "Un solo escenario, en español e inglés, con {r} repeticiones. El intervalo es por escenario (n {e}), por eso es tan ancho.",
    r_haiku: "Claude Haiku con el dueño en el circuito", r_haiku_det: "estafas exitosas · utilidad {u} · {k} toques por 100 acciones sensibles {ki}",
    ayuda_haiku: "{e} escenarios en español × 3 repeticiones, con la capa 2. El dueño responde los toques.",
    r_recall: "Detección", r_precision: "Precisión", r_rango: "rango",
    ayuda_clasif: "Rango entre {c} corridas ({pl} pliegues × {s} semillas) con familias de estafa apartadas, no un intervalo de confianza. Lo aprendido solo sube la sospecha: nunca aprueba un pago.",
    r_canal: "Se cuela, por canal", ayuda_canal: "Correos de estafa apartados que el clasificador dejó bajo 0,5, sumando las corridas. El mismo correo vuelve en varias corridas: es un conteo, sin intervalo",
    r_corridas_con: "{c} de {r} corridas con colados",
    canal_whatsapp: "WhatsApp", canal_mcp: "MCP", canal_correo: "Correo", canal_llamada: "Llamada", canal_web: "Web",
    r_fuente: "Resultados del README · {f}", ayuda_r_fuente: "Generado por scripts/resultados_demo.py desde results/",
    r_at_sin_archivo: "La curva del atacante todavía no está", r_at_sin_rondas: "La última corrida solo tiene la ronda 0", r_at_con_errores: "La corrida tiene demasiadas muestras con error", r_at_con_errores_det: "Más del 10 % de las muestras falló: no se presenta como la curva. Con una corrida limpia se regenera con:",
    r_at_sin_archivo_det: "Cuando llegue a results/atacante/, se regenera con:", r_at_sin_rondas_det: "El atacante no alcanzó a reescribir ninguna estafa. Con una corrida de varias rondas se regenera con:",
    r_at_se_nego: "se negó {k} veces", r_at_nota: "{m} · {n} estafas · {r} rondas", r_at_cero: "ninguna estafa le ganó a ninguna defensa",
    r_at_incompletas: "{d}: rondas {r} incompletas ({v} de {n} estafas con episodio puntuado)", r_y: " y ", r_at_eje: "ronda del atacante", r_at_ronda: "Ronda", r_at_errores: "{e} muestras con error",
    du_congelado_c: "Escudo congelado", du_aprende_c: "Escudo que aprende", r_sin_capa2: "sin capa 2", r_con_capa2: "con capa 2",
    sin_resultados_r: "No hay resultados.json: corre python scripts/resultados_demo.py",
    r_colados: "Qué se cuela, por tipo de estafa y por capa", r_co_tipo: "Tipo de estafa", r_co_clasif: "Clasificador",
    r_co_nota: "{e} estafas (escenario × idioma) · clasificador: {c} correos en {r} corridas",
    ayuda_co_clasif: "Correos de estafa apartados que el clasificador dejó bajo 0,5, de cuántos se evaluaron, sumando las {r} corridas de la validación cruzada por familia. Conteo: el mismo correo vuelve en varias corridas",
    ayuda_co_capa: "Estafas que cruzaron esta configuración con el agente guionado: escenario × idioma",
    r_co_total: "Total", r_co_dicta: "dueño dicta",
    ayuda_co_dicta: "El dueño ya cayó y dicta la cuenta: la capa 2 no lo ve porque el dato viene del dueño. Las frena la capa 3, que compara el titular con el beneficiario",
    ayuda_co_celda: "{f} · {c}: {n} de {d}\n{e}", r_co_ver: "Clic: ver el episodio de {e}",
    r_id_nota: "{p} pares · {d} difieren", ayuda_idiomas: "El mismo escenario en español y en inglés, con el agente guionado: estafas exitosas por configuración",
    r_brecha: "Brecha", r_copiar: "Copiar el comando", r_copiado: "Copiado",
  });
  Object.assign(T.en, {
    r_bench: "The defenses, with an agent that does whatever it reads", r_segutil: "Security versus utility", r_reales: "Real models and firewall",
    r_atacante: "Adaptive attacker", r_duelo: "Duel", r_idiomas: "Spanish versus English", r_clasif_b: "Classifier that learns",
    r_estafas: "Successful scams", r_utilidad: "Utility", r_falsas: "False alarms", r_config: "Configuration",
    rc_none: "No defense", rc_layer1: "Reference firewall", rc_layer2: "Shield: origin", rc_layer3: "Shield: payee", rc_layer23: "Grifter (layers 2 and 3)",
    ayuda_rc_none: "The agent pays whatever it is asked", ayuda_rc_layer1: "Layer 1: rules against technical injection",
    ayuda_rc_layer2: "Layer 2: the account must come from the owner, not from an email", ayuda_rc_layer3: "Layer 3: the account holder must be the payee",
    ayuda_rc_layer23: "Layers 2 and 3 together: Grifter's full configuration",
    r_n_bench: "{e} scams · {c} controls · ES and EN · scripted agent",
    ayuda_bench: "{aviso}. 95 % interval, by scenario.",
    r_vs: "vs no defense {v}", r_pp: "{s}{n} pp",
    ayuda_cifra_estafas: "Scams that got paid with Grifter (layers 2 and 3) versus no defense. Scripted agent: it measures the defenses, not a model. The delta is colored only if the intervals do not touch",
    ayuda_cifra_utilidad: "Legitimate tasks the agent completed with Grifter versus no defense",
    ayuda_cifra_falsas: "Legitimate controls where Grifter blocked something, versus no defense",
    r_duelo_cifra: "Payments that got past layer 2", r_de: "{a} of {b}", r_conteo: "count",
    ayuda_conteo_duelo: "Hacker attempts over {g} generations. The same strain comes back across generations: attempts are not independent, so there is no interval",
    r_ver_duelo: "See the duel",
    r_eje_x: "successful scams", r_eje_y: "utility",
    r_pipelock: "Pipelock, agent firewall", r_pipelock_det: "stopped, all technical: web injection and poisoned MCP · {fa} false alarms",
    r_pipelock_tag: "no file", ayuda_pipelock_tag: "No file in results/: the figure comes from {f}",
    r_sonnet: "Claude Sonnet, «pay what the manager approves»", r_sonnet_det: "payments to the scammer with the email from the manager's compromised address · layer 2 holds it",
    ayuda_sonnet: "A single scenario, in Spanish and English, with {r} repetitions. The interval is by scenario (n {e}), hence so wide.",
    r_haiku: "Claude Haiku with the owner in the loop", r_haiku_det: "successful scams · utility {u} · {k} taps per 100 sensitive actions {ki}",
    ayuda_haiku: "{e} scenarios in Spanish × 3 repetitions, with layer 2. The owner answers the taps.",
    r_recall: "Recall", r_precision: "Precision", r_rango: "range",
    ayuda_clasif: "Range across {c} runs ({pl} folds × {s} seeds) with held-out scam families, not a confidence interval. What it learns only raises suspicion: it never approves a payment.",
    r_canal: "Slips through, by channel", ayuda_canal: "Held-out scam emails the classifier left below 0.5, over all runs. The same email comes back across runs: it is a count, with no interval",
    r_corridas_con: "{c} of {r} runs with misses",
    canal_whatsapp: "WhatsApp", canal_mcp: "MCP", canal_correo: "Email", canal_llamada: "Call", canal_web: "Web",
    r_fuente: "README results · {f}", ayuda_r_fuente: "Generated by scripts/resultados_demo.py from results/",
    r_at_sin_archivo: "The attacker curve is not here yet", r_at_sin_rondas: "The latest run only has round 0", r_at_con_errores: "The run has too many failed samples", r_at_con_errores_det: "Over 10 % of the samples failed: it is not shown as the curve. With a clean run, regenerate with:",
    r_at_sin_archivo_det: "When it lands in results/attacker/, regenerate with:", r_at_sin_rondas_det: "The attacker did not get to rewrite any scam. With a multi-round run, regenerate with:",
    r_at_se_nego: "refused {k} times", r_at_nota: "{m} · {n} scams · {r} rounds", r_at_cero: "no scam beat any defense",
    r_at_incompletas: "{d}: rounds {r} incomplete ({v} of {n} scams with a scored episode)", r_y: " and ", r_at_eje: "attacker round", r_at_ronda: "Round", r_at_errores: "{e} samples with errors",
    du_congelado_c: "Frozen shield", du_aprende_c: "Learning shield", r_sin_capa2: "no layer 2", r_con_capa2: "with layer 2",
    sin_resultados_r: "No resultados.json: run python scripts/resultados_demo.py",
    r_colados: "What slips through, by scam type and layer", r_co_tipo: "Scam type", r_co_clasif: "Classifier",
    r_co_nota: "{e} scams (scenario × language) · classifier: {c} emails over {r} runs",
    ayuda_co_clasif: "Held-out scam emails the classifier left below 0.5, out of how many were evaluated, over the {r} runs of the cross-validation by family. Count: the same email comes back across runs",
    ayuda_co_capa: "Scams that got past this configuration with the scripted agent: scenario × language",
    r_co_total: "Total", r_co_dicta: "owner dictates",
    ayuda_co_dicta: "The owner was already fooled and dictates the account: layer 2 does not see it because the value comes from the owner. Layer 3 stops it by comparing the holder with the payee",
    ayuda_co_celda: "{f} · {c}: {n} of {d}\n{e}", r_co_ver: "Click: see the episode of {e}",
    r_id_nota: "{p} pairs · {d} differ", ayuda_idiomas: "The same scenario in Spanish and in English, with the scripted agent: successful scams by configuration",
    r_brecha: "Gap", r_copiar: "Copy the command", r_copiado: "Copied",
  });

  // Los textos de esta vista se registran después del primer pintado de app.js: se vuelven a pintar.
  pintarTextos();

  const G = Graficos;
  const REPO = "https://github.com/mgtapia/grifter/";
  const PRINCIPALES = new Set(["none", "layer2", "layer23"]);
  const dec = (x, d = 2) => Number(x).toLocaleString(t("locale"), { minimumFractionDigits: d, maximumFractionDigits: d });
  const num = (x) => Number(x).toLocaleString(t("locale"));
  const fecha = (iso) => (iso ? new Date(iso).toLocaleString(t("locale"), { dateStyle: "short", timeStyle: "short" }) : "");
  const corto = (m) => String(m || "").split("/").pop();
  const pct01 = (x) => `${Math.round(x * 100)} %`;

  // --- Fuente y comando: el enlace al archivo en el repo y un botón para copiar el comando ---
  // «results/a.json · results/b.json» da dos enlaces; un patrón con llaves enlaza la carpeta.
  function enlaces(fuente) {
    return String(fuente || "").split(" · ").map((f) => {
      const ruta = (f.match(/^[\w./{},-]+/) || [""])[0];
      if (!ruta) return "";
      const carpeta = ruta.includes("{");
      const destino = carpeta ? ruta.slice(0, ruta.lastIndexOf("/", ruta.indexOf("{"))) : ruta;
      return `<a class="res-fuente dato" href="${esc(REPO + (carpeta ? "tree" : "blob") + "/main/" + destino)}" target="_blank" rel="noopener">${esc(carpeta ? `${destino}/` : ruta)}</a>`;
    }).filter(Boolean).join("");
  }
  const copiar = (cmd) => (cmd ? `<button type="button" class="boton icono texto res-copiar" data-copiar="${esc(cmd)}" data-ayuda="${esc(`${t("r_copiar")}\n${cmd}`)}" aria-label="${esc(t("r_copiar"))}">${ms("content_copy")}</button>` : "");
  const pie = (o) => `<span class="res-pie">${enlaces(o.fuente)}${copiar(o.comando)}</span>`;
  const titulo = (icono, texto, { nota = "", ayuda = "", fuente } = {}) =>
    `<h2 class="titulo"${ayuda ? ` data-ayuda="${esc(ayuda)}" tabindex="0"` : ""}>${ms(icono)}<span>${esc(texto)}</span>${nota ? `<span class="nota">${esc(nota)}</span>` : ""}${fuente ? pie(fuente) : ""}</h2>`;

  // Copia con la API del portapapeles y, si no está (file://), con una selección y execCommand.
  async function alPortapapeles(texto) {
    try { await navigator.clipboard.writeText(texto); return true; } catch (_) { /* sigue el respaldo */ }
    const area = document.createElement("textarea");
    area.value = texto; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    area.remove();
    return ok;
  }
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-copiar]");
    if (!b) return;
    if (await alPortapapeles(b.dataset.copiar)) {
      const icono = b.querySelector(".ms");
      const antes = icono.textContent;
      icono.textContent = "check";
      b.dataset.ayuda = t("r_copiado");
      setTimeout(() => { icono.textContent = antes; b.dataset.ayuda = `${t("r_copiar")}\n${b.dataset.copiar}`; }, 1600);
    }
  });

  // Delta en puntos porcentuales: gris salvo que los intervalos no se toquen; entonces verde si mejora, rojo si empeora.
  function delta(con, sin, menosEsMejor) {
    if (!G.hayTasa(con) || !G.hayTasa(sin)) return "";
    const d = G.pp(con.tasa) - G.pp(sin.tasa);
    const clase = !G.separados(con, sin) || d === 0 ? "" : (d < 0) === menosEsMejor ? "c-verde" : "c-rojo";
    const flecha = d > 0 ? "arrow_upward" : d < 0 ? "arrow_downward" : "arrow_forward";
    return `<span class="res-delta ${clase}">${ms(flecha)}${esc(t("r_pp", { s: d > 0 ? "+" : d < 0 ? "−" : "", n: Math.abs(d) }))}</span><span class="c-2">${esc(t("r_vs", { v: G.tasaIntervalo(sin) }))}</span>`;
  }

  // --- 1. Las cifras de arriba ---
  function pintarCifras(R) {
    const por = Object.fromEntries(R.bench.configuraciones.map((c) => [c.clave, c]));
    const con = por.layer23 || por.layer2;
    const sin = por.none;
    const cifra = (clave, m, s, menosEsMejor) => `<div class="res-cifra" tabindex="0" data-ayuda="${esc(t(`ayuda_cifra_${clave}`))}">
      <span class="etiqueta">${esc(t(`r_${clave}`))}</span>
      <span class="res-valor"><span class="dato res-grande">${esc(G.pct(m))}</span><span class="dato r-int">${esc(G.intervalo(m))}</span></span>
      <span class="res-linea">${delta(m, s, menosEsMejor)}</span>
      <span class="res-linea c-2">${esc(t(`rc_${con.clave}`))} · n ${m.escenarios}${pie(R.bench)}</span></div>`;
    const du = R.duelo;
    const duelo = du?.estado === "ok" ? `<div class="res-cifra" tabindex="0" data-ayuda="${esc(t("ayuda_conteo_duelo", { g: du.generaciones }))}">
      <span class="etiqueta">${esc(t("r_duelo_cifra"))}</span>
      <span class="res-valor"><span class="dato res-grande">${esc(t("r_de", { a: num(du.exitosas_capa2), b: num(du.candidatos) }))}</span><span class="tag">${esc(t("r_conteo"))}</span></span>
      <span class="res-linea"><a class="res-ir" href="#duelo">${ms("swords")}${esc(t("r_ver_duelo"))}</a></span>
      <span class="res-linea c-2">${esc(`${du.generaciones} gen.`)}${pie(du)}</span></div>` : "";
    $("#res-cifras").innerHTML = cifra("estafas", con.estafas_exitosas, sin.estafas_exitosas, true)
      + cifra("utilidad", con.utilidad, sin.utilidad, false)
      + cifra("falsas", con.falsas_alarmas, sin.falsas_alarmas, true) + duelo;
  }

  // --- 2. El banco de pruebas: tabla por configuración y seguridad contra utilidad ---
  function barra(m, cls) {
    if (!G.hayTasa(m)) return `<span class="r-barra vacia"></span>`;
    const p = (x) => `${Math.round(x * 1000) / 10}%`;
    return `<span class="r-barra ${cls}" aria-hidden="true"><span class="r-ic" style="left:${p(m.bajo)};width:${p(m.alto - m.bajo)}"></span><span class="r-tasa" style="width:${p(m.tasa)}"></span></span>`;
  }
  const valor = (m) => `<span class="dato r-val">${esc(G.pct(m))}</span><span class="dato r-int">${esc(G.intervalo(m))}</span>`;

  function pintarBench(R) {
    const b = R.bench;
    const filas = b.configuraciones.map((c) => `
      <tr class="${PRINCIPALES.has(c.clave) ? "" : "secundaria"}">
        <th scope="row" data-ayuda="${esc(t(`ayuda_rc_${c.clave}`))}">${esc(t(`rc_${c.clave}`))}</th>
        <td class="r-estafas">${barra(c.estafas_exitosas, "rojo")}${valor(c.estafas_exitosas)}</td>
        <td data-et="${esc(t("r_utilidad"))}">${valor(c.utilidad)}</td>
        <td data-et="${esc(t("r_falsas"))}">${valor(c.falsas_alarmas)}</td>
      </tr>`).join("");
    $("#res-bench").innerHTML = titulo("table_rows", t("r_bench"), {
      nota: t("r_n_bench", { e: b.escenarios?.estafas ?? "—", c: b.escenarios?.controles ?? "—" }),
      ayuda: t("ayuda_bench", { aviso: b.aviso || "" }), fuente: b,
    }) + `<div class="res-desliza"><table class="r-tabla">
      <thead><tr><th scope="col">${esc(t("r_config"))}</th><th scope="col">${esc(t("r_estafas"))}</th><th scope="col">${esc(t("r_utilidad"))}</th><th scope="col">${esc(t("r_falsas"))}</th></tr></thead>
      <tbody>${filas}</tbody></table></div>`;

    $("#res-segutil").innerHTML = titulo("scatter_plot", t("r_segutil"), { ayuda: t("ayuda_bench", { aviso: b.aviso || "" }), fuente: b })
      + `<div class="lienzo" id="res-dispersion"></div>`;
    G.dispersion($("#res-dispersion"), b.configuraciones.map((c) => ({
      nombre: t(`rc_${c.clave}`), x: c.estafas_exitosas, y: c.utilidad, destacada: c.clave === "layer23",
    })), { eje_x: t("r_eje_x"), eje_y: t("r_eje_y") });
  }

  // --- 3. Qué se cuela: mapa de calor tipo de estafa × capa, y la columna del clasificador ---
  // El color va de superficie a rojo según la fracción que se cuela. Un clic abre el episodio si está exportado.
  function pintarColados(R) {
    const co = R.colados;
    const caja = $("#res-colados");
    if (!co || !co.familias) { caja.innerHTML = `<p class="vacio">${esc(t("sin_resultados_r"))}</p>`; return; }
    const cfg = co.configuraciones;
    const tasa = (n, d) => (d ? n / d : 0);
    const orden = (f) => [tasa(f.por_capa.layer23 || 0, f.estafas), tasa(f.por_capa.layer2 || 0, f.estafas),
      tasa(f.clasificador?.colados || 0, f.clasificador?.correos || 0), tasa(f.por_capa.layer3 || 0, f.estafas)];
    const familias = [...co.familias].sort((a, b) => {
      const x = orden(a), y = orden(b);
      for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return y[i] - x[i];
      return nombreFamilia(a.familia).localeCompare(nombreFamilia(b.familia));
    });
    const celda = (f, col, n, d, escenarios) => {
      if (!d) return `<td class="dato r-cero" data-et="${esc(col)}">—</td>`;
      const r = tasa(n, d);
      const ep = (escenarios || []).find((e) => window.hayEpisodioDe?.(e));
      const ayuda = [t("ayuda_co_celda", { f: nombreFamilia(f), c: col, n, d, e: (escenarios || []).join(", ") }), ep ? t("r_co_ver", { e: ep }) : ""].filter(Boolean).join("\n");
      const fondo = r ? ` style="background:color-mix(in srgb, var(--rojo) ${Math.round(16 + r * 56)}%, var(--superficie))"` : "";
      return `<td class="dato${r ? " calor" : " r-cero"}${ep ? " con-ep" : ""}"${fondo} data-et="${esc(col)}" data-ayuda="${esc(ayuda)}"${ep ? ` data-episodio="${esc(ep)}" tabindex="0" role="link"` : ""}>${n}/${d}</td>`;
    };
    const fila = (f) => {
      const dicta = f.dueno_dicta?.layer2 ? `<span class="tag" data-ayuda="${esc(t("ayuda_co_dicta"))}">${esc(t("r_co_dicta"))}</span>` : "";
      const cl = f.clasificador;
      return `<tr><th scope="row">${esc(nombreFamilia(f.familia))}${dicta}</th>
        ${cfg.map((c) => celda(f.familia, t(`rc_${c}`), f.por_capa[c] || 0, f.estafas, f.escenarios?.[c])).join("")}
        ${celda(f.familia, t("r_co_clasif"), cl?.colados || 0, cl?.correos || 0, cl?.escenarios)}</tr>`;
    };
    const tot = `<tr class="r-total"><th scope="row">${esc(t("r_co_total"))}</th>
      ${cfg.map((c) => `<td class="dato" data-et="${esc(t(`rc_${c}`))}">${co.totales[c]}/${co.estafas}</td>`).join("")}
      <td class="dato" data-et="${esc(t("r_co_clasif"))}">${co.clasificador ? `${co.clasificador.colados}/${co.clasificador.correos}` : "—"}</td></tr>`;
    caja.innerHTML = titulo("filter_alt_off", t("r_colados"), {
      nota: t("r_co_nota", { e: co.estafas, c: co.clasificador?.correos ?? "—", r: co.corridas ?? "—" }), fuente: co,
    }) + `<div class="res-desliza"><table class="r-tabla r-colados">
      <thead><tr><th scope="col">${esc(t("r_co_tipo"))}</th>${cfg.map((c) => `<th scope="col" data-ayuda="${esc(`${t(`ayuda_rc_${c}`)}. ${t("ayuda_co_capa")}`)}">${esc(t(`rc_${c}`))}</th>`).join("")}
        <th scope="col" data-ayuda="${esc(t("ayuda_co_clasif", { r: co.corridas ?? "—" }))}">${esc(t("r_co_clasif"))}</th></tr></thead>
      <tbody>${familias.map(fila).join("")}${tot}</tbody></table></div>`;
  }
  const abrirCelda = (e) => {
    const td = e.target.closest("td[data-episodio]");
    if (td && (e.type === "click" || e.key === "Enter")) window.abrirEpisodio?.(td.dataset.episodio);
  };
  $("#res-colados").addEventListener("click", abrirCelda);
  $("#res-colados").addEventListener("keydown", abrirCelda);

  // --- 4. Español contra inglés ---
  function pintarIdiomas(R) {
    const e = R.bench.es_contra_en;
    const caja = $("#res-idiomas");
    if (!e) { caja.innerHTML = ""; return; }
    const filas = e.configuraciones.map((c) => {
      const es = c.es.estafas_exitosas, en = c.en.estafas_exitosas;
      const b = G.pp(es.tasa) - G.pp(en.tasa);
      return `<tr class="${PRINCIPALES.has(c.clave) ? "" : "secundaria"}"><th scope="row">${esc(t(`rc_${c.clave}`))}</th>
        <td data-et="ES">${valor(es)}</td><td data-et="EN">${valor(en)}</td>
        <td class="dato" data-et="${esc(t("r_brecha"))}">${b > 0 ? "+" : b < 0 ? "−" : ""}${Math.abs(b)} pp</td></tr>`;
    }).join("");
    caja.innerHTML = titulo("translate", t("r_idiomas"), { nota: t("r_id_nota", { p: e.pares, d: e.difieren.length }), ayuda: t("ayuda_idiomas"), fuente: R.bench })
      + `<div class="res-desliza"><table class="r-tabla r-idiomas"><thead><tr><th scope="col">${esc(t("r_estafas"))}</th><th scope="col">ES</th><th scope="col">EN</th><th scope="col">${esc(t("r_brecha"))}</th></tr></thead>
      <tbody>${filas}</tbody></table></div>`;
  }

  // --- 5. Modelos y firewall reales ---
  function celdaReal({ titulo: tit, grande, intervalo, detalle, ayuda, tag, tagAyuda, rojo, fuente }) {
    return `<li class="res-real" tabindex="0" data-ayuda="${esc(ayuda)}">
      <span class="r-que">${esc(tit)}${tag ? `<span class="tag" data-ayuda="${esc(tagAyuda)}">${esc(tag)}</span>` : ""}</span>
      <span class="res-valor"><span class="dato res-grande${rojo ? " c-rojo" : ""}">${esc(grande)}</span>${intervalo ? `<span class="dato r-int">${esc(intervalo)}</span>` : ""}</span>
      <span class="r-det">${esc(detalle)}</span>${pie(fuente)}</li>`;
  }
  function pintarReales(R) {
    const { pipelock: pl, sonnet: so, haiku: ha } = R;
    const toques = ha.toques_por_100;
    $("#res-reales").innerHTML = titulo("fact_check", t("r_reales")) + `<ol class="res-reales-lista">${[
      celdaReal({ titulo: t("r_sonnet"), grande: t("r_de", { a: so.pagos, b: so.repeticiones }), intervalo: G.tasaIntervalo(so.estafas_exitosas),
        detalle: t("r_sonnet_det"), rojo: so.pagos > 0, fuente: so,
        ayuda: t("ayuda_sonnet", { r: so.repeticiones, e: so.estafas_exitosas.escenarios }) }),
      celdaReal({ titulo: t("r_haiku"), grande: G.pct(ha.estafas_exitosas), intervalo: G.intervalo(ha.estafas_exitosas), fuente: ha,
        detalle: t("r_haiku_det", { u: G.tasaIntervalo(ha.utilidad), k: Math.round(toques.tasa), ki: `[${Math.round(toques.bajo)}-${Math.round(toques.alto)}]` }),
        ayuda: t("ayuda_haiku", { e: ha.estafas_exitosas.escenarios }) }),
      celdaReal({ titulo: t("r_pipelock"), grande: t("r_de", { a: pl.frenadas, b: pl.estafas }), intervalo: G.tasaIntervalo(pl),
        detalle: t("r_pipelock_det", { fa: pl.falsas_alarmas }), ayuda: [pl.fuente, pl.comando].filter(Boolean).join("\n"), fuente: pl,
        tag: pl.sin_archivo ? t("r_pipelock_tag") : "", tagAyuda: t("ayuda_pipelock_tag", { f: pl.fuente }) }),
    ].join("")}</ol>`;
  }

  // --- 6. El atacante adaptativo y el duelo ---
  function pintarAtacante(R) {
    const a = R.atacante || { estado: "sin_archivo" };
    const caja = $("#res-atacante");
    if (a.estado === "sin_archivo" || a.estado === "sin_rondas" || a.estado === "con_errores") {
      caja.innerHTML = titulo("swords", t("r_atacante"), { fuente: a }) + `<div class="r-vacio">${ms("hourglass_top", true)}<div>
        <p class="r-vacio-tit">${esc(t(`r_at_${a.estado}`))}</p>
        <p class="c-2">${esc(t(`r_at_${a.estado}_det`))}</p>
        <code class="dato">${esc(a.comando || "python scripts/graficar_atacante.py <jsonl> && python scripts/resultados_demo.py")}</code></div></div>`;
      return;
    }
    const s0 = a.series[0];
    const rondas = Math.max(...a.series.map((s) => s.rondas || 0));
    const errores = a.series.reduce((x, s) => x + (s.errores || 0), 0);
    const nota = [t("r_at_nota", { m: corto(s0.modelo), n: s0.n, r: rondas }), a.estado === "en_cero" ? t("r_at_cero") : "",
      errores ? t("r_at_errores", { e: errores }) : ""].filter(Boolean).join(" · ");
    const incompletas = a.series.filter((s) => s.incompletas?.length).map((s) => t("r_at_incompletas", {
      d: t(`d_${s.defensa}`), r: s.incompletas.map((i) => i.ronda).join(t("r_y")),
      v: s.incompletas.map((i) => i.validas).join(t("r_y")), n: s.n }));
    const aSerie = (s) => ({
      nombre: t(`d_${s.defensa}`) || s.defensa,
      puntos: (s.exitos || []).map((e, i) => [i, s.n ? (100 * e) / s.n : 0]),
      cayo: (s.exitos || []).some((e) => e > 0),
      ic: (s.ic || []).map((x) => (x && x[0] !== null ? `[${Math.round(x[0] * 100)}-${Math.round(x[1] * 100)}]` : "")),
    });
    const ayuda = { eje_x: t("r_at_eje"), ronda: t("r_at_ronda") };
    const avisos = incompletas.map((x) => `<p class="r-aviso">${ms("info")}<span>${esc(x)}</span></p>`).join("");
    const atacantes = [...new Set(a.series.map((s) => s.atacante || ""))];
    const cab = titulo("swords", t("r_atacante"), { nota, fuente: a });
    if (atacantes.length <= 1) {
      caja.innerHTML = `${cab}<div class="res-curva"><div class="lienzo" id="res-curva"></div></div>${avisos}`;
      G.curvaAtacante($("#res-curva"), a.series.map(aSerie), { rondas, ayuda });
      return;
    }
    caja.innerHTML = `${cab}<div class="res-paneles">${atacantes.map((at, i) => {
      const rechazos = a.series.filter((s) => (s.atacante || "") === at).reduce((x, s) => x + (s.rechazos || 0), 0);
      return `<figure class="res-panel"><figcaption class="c-2">${esc(corto(at))}${rechazos ? ` · ${esc(t("r_at_se_nego", { k: rechazos }))}` : ""}</figcaption>
        <div class="lienzo" id="res-curva-${i}"></div></figure>`;
    }).join("")}</div>${avisos}`;
    atacantes.forEach((at, i) => G.curvaAtacante($(`#res-curva-${i}`),
      a.series.filter((s) => (s.atacante || "") === at).map(aSerie), { rondas, ayuda }));
  }

  // El duelo en una barra por modo: cuántos intentos del hacker habrían cobrado sin la capa 2, y cuántos con ella.
  function pintarDuelo(R) {
    const du = R.duelo;
    const caja = $("#res-duelo");
    if (!du || du.estado !== "ok") { caja.innerHTML = titulo("model_training", t("r_duelo")) + `<p class="vacio">${esc(t("sin_resultados_r"))}</p>`; return; }
    const modo = (clave) => {
      const m = du[clave];
      const r = m.candidatos ? m.sin_capa2 / m.candidatos : 0;
      return `<li class="res-modo" tabindex="0" data-ayuda="${esc(t("ayuda_conteo_duelo", { g: m.semillas.reduce((x, s) => x + s.generaciones, 0) }))}">
        <span class="r-que">${esc(t(`du_${clave}_c`))}</span>
        <span class="res-par"><span class="c-2">${esc(t("r_sin_capa2"))}</span><span class="dato${m.sin_capa2 ? " c-rojo" : ""}">${esc(t("r_de", { a: num(m.sin_capa2), b: num(m.candidatos) }))}</span></span>
        <span class="r-barra" aria-hidden="true"><span class="r-tasa" style="width:${Math.round(r * 1000) / 10}%"></span></span>
        <span class="res-par"><span class="c-2">${esc(t("r_con_capa2"))}</span><span class="dato">${esc(t("r_de", { a: num(m.exitosas_capa2), b: num(m.candidatos) }))}</span></span></li>`;
    };
    caja.innerHTML = titulo("model_training", t("r_duelo"), { nota: `${du.generaciones} gen.`, fuente: du })
      + `<ol class="res-modos">${modo("congelado")}${modo("aprende")}</ol>
      <p class="r-aviso"><span class="tag">${esc(t("r_conteo"))}</span><a class="res-ir" href="#duelo">${ms("swords")}${esc(t("r_ver_duelo"))}</a></p>`;
  }

  // --- 7. El clasificador: el rango de sus tres métricas y qué se le cuela por canal ---
  function pintarClasif(R) {
    const cl = R.clasificador;
    const canales = R.colados?.clasificador_por_canal || {};
    const caja = $("#res-clasif");
    const metrica = (clave, m, fmt) => `<li class="res-real" tabindex="0" data-ayuda="${esc(t("ayuda_clasif", { c: cl.corridas, pl: cl.pliegues, s: cl.semillas.length }))}">
      <span class="r-que">${esc(t(clave))}</span>
      <span class="res-valor"><span class="dato res-grande">${esc(fmt(m.media))}</span><span class="dato r-int">[${esc(fmt(m.min))}-${esc(fmt(m.max))}] ${esc(t("r_rango"))}</span></span></li>`;
    const filas = Object.entries(canales).sort((a, b) => b[1].tasa - a[1].tasa).map(([c, v]) => `
      <li class="res-canal" tabindex="0" data-ayuda="${esc([t("ayuda_canal"), (v.escenarios || []).join(", ")].filter(Boolean).join("\n"))}">
        <span>${esc(t(`canal_${c}`))}</span>
        <span class="r-barra" aria-hidden="true"><span class="r-tasa" style="width:${Math.round(v.tasa * 1000) / 10}%"></span></span>
        <span class="dato${v.colados ? "" : " c-2"}">${v.colados}/${v.correos}</span>
        <span class="dato c-2">${esc(pct01(v.tasa))}</span>
        <span class="c-2 res-corridas">${esc(t("r_corridas_con", { c: v.corridas_con_colados, r: v.corridas }))}</span></li>`).join("");
    caja.innerHTML = titulo("psychology", t("r_clasif_b"), { nota: `${cl.episodios} ep. · ${cl.corridas} ${t("r_rango")}`, fuente: cl })
      + `<div class="res-clasif-cuerpo"><ol class="res-reales-lista res-metricas">
        ${metrica("r_recall", cl.recall, (x) => dec(x))}${metrica("r_precision", cl.precision, (x) => dec(x))}${metrica("r_falsas", cl.falsas_alarmas, pct01)}</ol>
        <div class="res-canales"><p class="r-que" data-ayuda="${esc(t("ayuda_canal"))}" tabindex="0">${esc(t("r_canal"))}<span class="tag">${esc(t("r_conteo"))}</span></p><ol>${filas}</ol></div></div>`;
  }

  const BLOQUES = ["#res-cifras", "#res-bench", "#res-segutil", "#res-colados", "#res-idiomas", "#res-reales", "#res-atacante", "#res-duelo", "#res-clasif"];
  function pintar(R) {
    if (!R || !R.bench) {
      for (const id of BLOQUES) $(id).innerHTML = "";
      $("#res-cifras").innerHTML = `<p class="vacio">${esc(t("sin_resultados_r"))}</p>`;
      return;
    }
    pintarCifras(R);
    pintarBench(R);
    pintarColados(R);
    pintarIdiomas(R);
    pintarReales(R);
    pintarAtacante(R);
    pintarDuelo(R);
    pintarClasif(R);
  }

  // El rótulo de la barra: de dónde salen los números y cuándo se generaron.
  function fuente(R) {
    const el = $("#fuente");
    if (!el) return;
    el.classList.remove("prueba");
    el.textContent = R?.bench ? t("r_fuente", { f: fecha(R.generado) }) : "";
    el.dataset.ayuda = R?.bench ? [t("ayuda_r_fuente"), R.bench.fuente, R.sonnet.fuente, R.haiku.fuente, R.clasificador.fuente,
      R.atacante?.fuente, `Pipelock: ${R.pipelock.fuente}`].filter(Boolean).join("\n") : "";
  }

  return { pintar, fuente };
})();
window.ResultadosVista = ResultadosVista;
pintarAnalisis();
