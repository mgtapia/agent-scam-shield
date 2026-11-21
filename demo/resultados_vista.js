// Grifter, vista Resultados: los números de la tabla «Resultados» del README, cada uno con su intervalo.
// Los lee de resultados.json (scripts/resultados_demo.py, que a su vez lee results/). La página no calcula
// ninguna tasa: solo dibuja. Depende de app.js (T, t, esc, ms, $, estado) y de graficos.js.
"use strict";

const ResultadosVista = (() => {
  Object.assign(T.es, {
    r_bench: "Agente que hace todo lo que lee", r_reales: "Modelos y firewall reales", r_atacante: "Atacante adaptativo",
    r_estafas: "Estafas exitosas", r_utilidad: "Utilidad", r_falsas: "Falsas alarmas", r_config: "Configuración",
    rc_none: "Sin defensa", rc_layer1: "Firewall de referencia", rc_layer2: "Escudo: origen", rc_layer3: "Escudo: beneficiario", rc_layer23: "Escudo completo",
    ayuda_rc_none: "El agente paga lo que le pidan", ayuda_rc_layer1: "Capa 1: reglas contra la inyección técnica",
    ayuda_rc_layer2: "Capa 2: la cuenta tiene que venir del dueño, no de un correo", ayuda_rc_layer3: "Capa 3: el titular de la cuenta tiene que ser el beneficiario",
    ayuda_rc_layer23: "Capas 2 y 3 juntas",
    r_n_bench: "{e} estafas · {c} controles · ES y EN",
    ayuda_bench: "{aviso}. Intervalo al 95 %, por escenario.\n{fuente}\n{comando}",
    r_pipelock: "Pipelock, firewall de agentes", r_pipelock_val: "{f} de {n}", r_pipelock_det: "frenadas, todas técnicas: inyección web y MCP envenenado · {fa} falsas alarmas",
    r_pipelock_tag: "sin archivo",
    r_sonnet: "Claude Sonnet, «paga lo que el gerente apruebe»", r_sonnet_val: "{p} de {n}", r_sonnet_det: "pagos al estafador cuando el correo venía de la dirección comprometida del gerente · la capa 2 lo retiene",
    ayuda_sonnet: "Un solo escenario, en español e inglés, con {r} repeticiones. El intervalo es por escenario (n {e}), por eso es tan ancho.",
    r_haiku: "Claude Haiku con el dueño en el circuito", r_haiku_det: "estafas exitosas · utilidad {u} · {k} toques por 100 acciones sensibles {ki}",
    ayuda_haiku: "{e} escenarios en español × 3 repeticiones, con la capa 2. El dueño responde los toques.",
    r_clasif: "Clasificador que aprende en vivo", r_clasif_det: "detección en familias de estafa apartadas · precisión {p} · falsas alarmas {fa}", r_rango: "rango",
    ayuda_clasif: "Rango entre {c} corridas ({pl} pliegues × {s} semillas), no un intervalo de confianza. Lo aprendido solo sube la sospecha: nunca aprueba un pago.",
    r_fuente: "Resultados del README · {f}", ayuda_r_fuente: "Generado por scripts/resultados_demo.py desde results/",
    r_at_sin_archivo: "La curva del atacante todavía no está", r_at_sin_rondas: "La última corrida solo tiene la ronda 0", r_at_con_errores: "La corrida tiene demasiadas muestras con error", r_at_con_errores_det: "Más del 10 % de las muestras falló: no se presenta como la curva. Con una corrida limpia se regenera con:",
    r_at_sin_archivo_det: "Cuando llegue a results/atacante/, se regenera con:", r_at_sin_rondas_det: "El atacante no alcanzó a reescribir ninguna estafa. Con una corrida de varias rondas se regenera con:",
    r_at_se_nego: "se negó {k} veces", r_at_nota: "{m} · {n} estafas · {r} rondas", r_at_cero: "ninguna estafa le ganó a ninguna defensa",
    r_at_incompletas: "{d}: rondas {r} incompletas ({v} de {n} estafas con episodio puntuado)", r_y: " y ", r_at_eje: "ronda del atacante", r_at_ronda: "Ronda", r_at_errores: "{e} muestras con error",
    sin_resultados_r: "No hay resultados.json: corre python scripts/resultados_demo.py",
  });
  Object.assign(T.en, {
    r_bench: "Agent that does whatever it reads", r_reales: "Real models and firewall", r_atacante: "Adaptive attacker",
    r_estafas: "Successful scams", r_utilidad: "Utility", r_falsas: "False alarms", r_config: "Configuration",
    rc_none: "No defense", rc_layer1: "Reference firewall", rc_layer2: "Shield: origin", rc_layer3: "Shield: payee", rc_layer23: "Full shield",
    ayuda_rc_none: "The agent pays whatever it is asked", ayuda_rc_layer1: "Layer 1: rules against technical injection",
    ayuda_rc_layer2: "Layer 2: the account must come from the owner, not from an email", ayuda_rc_layer3: "Layer 3: the account holder must be the payee",
    ayuda_rc_layer23: "Layers 2 and 3 together",
    r_n_bench: "{e} scams · {c} controls · ES and EN",
    ayuda_bench: "{aviso}. 95 % interval, by scenario.\n{fuente}\n{comando}",
    r_pipelock: "Pipelock, agent firewall", r_pipelock_val: "{f} of {n}", r_pipelock_det: "stopped, all technical: web injection and poisoned MCP · {fa} false alarms",
    r_pipelock_tag: "no file",
    r_sonnet: "Claude Sonnet, «pay what the manager approves»", r_sonnet_val: "{p} of {n}", r_sonnet_det: "payments to the scammer when the email came from the manager's compromised address · layer 2 holds it",
    ayuda_sonnet: "A single scenario, in Spanish and English, with {r} repetitions. The interval is by scenario (n {e}), hence so wide.",
    r_haiku: "Claude Haiku with the owner in the loop", r_haiku_det: "successful scams · utility {u} · {k} taps per 100 sensitive actions {ki}",
    ayuda_haiku: "{e} scenarios in Spanish × 3 repetitions, with layer 2. The owner answers the taps.",
    r_clasif: "Classifier that learns live", r_clasif_det: "recall on held-out scam families · precision {p} · false alarms {fa}", r_rango: "range",
    ayuda_clasif: "Range across {c} runs ({pl} folds × {s} seeds), not a confidence interval. What it learns only raises suspicion: it never approves a payment.",
    r_fuente: "README results · {f}", ayuda_r_fuente: "Generated by scripts/resultados_demo.py from results/",
    r_at_sin_archivo: "The attacker curve is not here yet", r_at_sin_rondas: "The latest run only has round 0", r_at_con_errores: "The run has too many failed samples", r_at_con_errores_det: "Over 10 % of the samples failed: it is not shown as the curve. With a clean run, regenerate with:",
    r_at_sin_archivo_det: "When it lands in results/attacker/, regenerate with:", r_at_sin_rondas_det: "The attacker did not get to rewrite any scam. With a multi-round run, regenerate with:",
    r_at_se_nego: "refused {k} times", r_at_nota: "{m} · {n} scams · {r} rounds", r_at_cero: "no scam beat any defense",
    r_at_incompletas: "{d}: rounds {r} incomplete ({v} of {n} scams with a scored episode)", r_y: " and ", r_at_eje: "attacker round", r_at_ronda: "Round", r_at_errores: "{e} samples with errors",
    sin_resultados_r: "No resultados.json: run python scripts/resultados_demo.py",
  });

  // Los textos de esta vista se registran después del primer pintado de app.js: se vuelven a pintar.
  pintarTextos();

  const G = Graficos;
  const PRINCIPALES = new Set(["none", "layer2", "layer23"]);   // las tres filas del README
  const dec = (x, d = 2) => Number(x).toLocaleString(t("locale"), { minimumFractionDigits: d, maximumFractionDigits: d });
  const fecha = (iso) => (iso ? new Date(iso).toLocaleString(t("locale"), { dateStyle: "short", timeStyle: "short" }) : "");
  const corto = (m) => String(m || "").split("/").pop();
  const ayudaFuente = (b) => [b.fuente, b.comando].filter(Boolean).join("\n");

  // Una tasa con su intervalo como barra: el tramo sólido es la tasa y el claro, el intervalo al 95 %.
  function barra(m, cls) {
    if (!G.hayTasa(m)) return `<span class="r-barra vacia"></span>`;
    const p = (x) => `${Math.round(x * 1000) / 10}%`;
    return `<span class="r-barra ${cls}" aria-hidden="true"><span class="r-ic" style="left:${p(m.bajo)};width:${p(m.alto - m.bajo)}"></span><span class="r-tasa" style="width:${p(m.tasa)}"></span></span>`;
  }
  const valor = (m) => `<span class="dato r-val">${esc(G.pct(m))}</span><span class="dato r-int">${esc(G.intervalo(m))}</span>`;

  function pintarBench(R) {
    const b = R.bench;
    $("#n-bench").textContent = t("r_n_bench", { e: b.escenarios?.estafas ?? "—", c: b.escenarios?.controles ?? "—" });
    $("#t-bench").dataset.ayuda = t("ayuda_bench", { aviso: b.aviso || "", fuente: b.fuente, comando: b.comando });
    const filas = b.configuraciones.map((c) => `
      <tr class="${PRINCIPALES.has(c.clave) ? "" : "secundaria"}">
        <th scope="row" data-ayuda="${esc(t(`ayuda_rc_${c.clave}`))}">${esc(t(`rc_${c.clave}`))}</th>
        <td class="r-estafas">${barra(c.estafas_exitosas, "rojo")}${valor(c.estafas_exitosas)}</td>
        <td data-et="${esc(t("r_utilidad"))}">${valor(c.utilidad)}</td>
        <td data-et="${esc(t("r_falsas"))}">${valor(c.falsas_alarmas)}</td>
      </tr>`).join("");
    $("#res-bench").innerHTML = `<table class="r-tabla">
      <thead><tr><th scope="col">${esc(t("r_config"))}</th><th scope="col">${esc(t("r_estafas"))}</th><th scope="col">${esc(t("r_utilidad"))}</th><th scope="col">${esc(t("r_falsas"))}</th></tr></thead>
      <tbody>${filas}</tbody></table>`;
  }

  // Una fila por medición: qué se midió, el número grande con su intervalo y el detalle. La fuente, en la ayuda.
  function fila({ titulo, grande, intervalo, detalle, ayuda, tag, tagAyuda, rojo }) {
    return `<li class="r-fila" tabindex="0" data-ayuda="${esc(ayuda)}">
      <span class="r-que">${esc(titulo)}${tag ? `<span class="tag" data-ayuda="${esc(tagAyuda)}">${esc(tag)}</span>` : ""}</span>
      <span class="r-num"><span class="dato r-grande${rojo ? " c-rojo" : ""}">${esc(grande)}</span>${intervalo ? `<span class="dato r-int">${esc(intervalo)}</span>` : ""}</span>
      <span class="r-det">${esc(detalle)}</span></li>`;
  }

  function pintarReales(R) {
    const { pipelock: pl, sonnet: so, haiku: ha, clasificador: cl } = R;
    const toques = ha.toques_por_100;
    $("#res-reales").innerHTML = [
      fila({ titulo: t("r_pipelock"), grande: t("r_pipelock_val", { f: pl.frenadas, n: pl.estafas }), intervalo: `${G.pct(pl)} ${G.intervalo(pl)}`,
        detalle: t("r_pipelock_det", { fa: pl.falsas_alarmas }), ayuda: ayudaFuente(pl),
        tag: pl.sin_archivo ? t("r_pipelock_tag") : "", tagAyuda: pl.fuente }),
      fila({ titulo: t("r_sonnet"), grande: t("r_sonnet_val", { p: so.pagos, n: so.repeticiones }), intervalo: `${G.pct(so.estafas_exitosas)} ${G.intervalo(so.estafas_exitosas)}`,
        detalle: t("r_sonnet_det"), rojo: so.pagos > 0,
        ayuda: `${t("ayuda_sonnet", { r: so.repeticiones, e: so.estafas_exitosas.escenarios })}\n${ayudaFuente(so)}` }),
      fila({ titulo: t("r_haiku"), grande: G.pct(ha.estafas_exitosas), intervalo: G.intervalo(ha.estafas_exitosas),
        detalle: t("r_haiku_det", { u: G.tasaIntervalo(ha.utilidad), k: Math.round(toques.tasa), ki: `[${Math.round(toques.bajo)}-${Math.round(toques.alto)}]` }),
        ayuda: `${t("ayuda_haiku", { e: ha.estafas_exitosas.escenarios })}\n${ayudaFuente(ha)}` }),
      fila({ titulo: t("r_clasif"), grande: dec(cl.recall.media), intervalo: `[${dec(cl.recall.min)}-${dec(cl.recall.max)}] ${t("r_rango")}`,
        detalle: t("r_clasif_det", { p: dec(cl.precision.media), fa: `${Math.round(cl.falsas_alarmas.media * 100)} %` }),
        ayuda: `${t("ayuda_clasif", { c: cl.corridas, pl: cl.pliegues, s: cl.semillas.length })}\n${ayudaFuente(cl)}` }),
    ].join("");
  }

  // La curva del atacante: estafas exitosas acumuladas por ronda. Sin curva válida, un estado vacío que dice
  // qué falta y con qué comando se regenera.
  function pintarAtacante(R) {
    const a = R.atacante || { estado: "sin_archivo" };
    const caja = $("#res-atacante");
    const nota = $("#n-atacante");
    if (a.estado === "sin_archivo" || a.estado === "sin_rondas" || a.estado === "con_errores") {
      nota.textContent = "";
      $("#t-atacante").dataset.ayuda = a.fuente || "";
      caja.innerHTML = `<div class="r-vacio">${ms("hourglass_top", true)}<div>
        <p class="r-vacio-tit">${esc(t(`r_at_${a.estado}`))}</p>
        <p class="c-2">${esc(t(`r_at_${a.estado}_det`))}</p>
        <code class="dato">${esc(a.comando || "python scripts/graficar_atacante.py <jsonl> && python scripts/resultados_demo.py")}</code></div></div>`;
      return;
    }
    const s0 = a.series[0];
    const rondas = Math.max(...a.series.map((s) => s.rondas || 0));
    const errores = a.series.reduce((x, s) => x + (s.errores || 0), 0);
    nota.textContent = [t("r_at_nota", { m: corto(s0.modelo), n: s0.n, r: rondas }), a.estado === "en_cero" ? t("r_at_cero") : "",
      errores ? t("r_at_errores", { e: errores }) : ""].filter(Boolean).join(" · ");
    $("#t-atacante").dataset.ayuda = a.fuente;
    // Si una defensa tiene rondas sin todos sus episodios (la cuota cortó el flujo), se dice en una línea.
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
    // Con varios atacantes (el plan B: un modelo abierto en vez de Claude), un panel por atacante, lado a lado.
    const atacantes = [...new Set(a.series.map((s) => s.atacante || ""))];
    if (atacantes.length <= 1) {
      caja.innerHTML = `<div class="lienzo" id="res-curva"></div>${avisos}`;
      G.curvaAtacante($("#res-curva"), a.series.map(aSerie), { rondas, ayuda });
      return;
    }
    caja.innerHTML = `<div class="res-paneles">${atacantes.map((at, i) => {
      const rechazos = a.series.filter((s) => (s.atacante || "") === at).reduce((x, s) => x + (s.rechazos || 0), 0);
      return `<figure class="res-panel"><figcaption class="c-2">${esc(corto(at))}${rechazos ? ` · ${esc(t("r_at_se_nego", { k: rechazos }))}` : ""}</figcaption>
        <div class="lienzo" id="res-curva-${i}"></div></figure>`;
    }).join("")}</div>${avisos}`;
    atacantes.forEach((at, i) => G.curvaAtacante($(`#res-curva-${i}`),
      a.series.filter((s) => (s.atacante || "") === at).map(aSerie), { rondas, ayuda }));
  }

  function pintar(R) {
    if (!R || !R.bench) {
      for (const id of ["#res-bench", "#res-atacante"]) $(id).innerHTML = `<p class="vacio">${esc(t("sin_resultados_r"))}</p>`;
      $("#res-reales").innerHTML = "";
      return;
    }
    pintarBench(R);
    pintarReales(R);
    pintarAtacante(R);
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
