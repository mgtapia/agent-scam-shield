// Grifter, vista Duelo (#82): un hacker que aprende de cómo lo bloqueamos, contra un escudo que se reentrena con él.
// Cada evento `duelo` del flujo /api/vivo es una generación; /api/vivo/estado trae `historial_duelo`. Operaciones
// recibe el flujo y le pasa estos eventos (aplicar) y la historia de la foto (cargar). Lo que se mueve responde a
// una generación nueva. Depende de app.js (T, t, esc, ms, $, estado) y de graficos.js.
"use strict";

const Duelo = (() => {
  Object.assign(T.es, {
    du_curva: "Hacker contra escudo", du_hacker: "Lo que aprende el hacker", du_gens: "Generaciones",
    du_gen: "Generación", du_evasion: "Evasión del hacker", du_recall: "Recall del escudo", du_capa2: "Estafas exitosas con capa 2",
    du_eje: "generación", du_c_evasion: "Evasión", du_c_recall: "Recall", du_c_capa2: "Con capa 2", du_n: "{c} correos por generación · modelo {v}",
    ayuda_du_evasion: "Correos mutados que el clasificador dejó pasar como seguros. Sube cuando el hacker encuentra una mutación nueva",
    ayuda_du_recall: "Recall del clasificador en el conjunto apartado, que nunca entrena. Responde cuando aprende de las mutaciones",
    ayuda_du_capa2: "La capa 2 no se entrena: la cuenta sigue saliendo de un correo, así que ninguna mutación paga",
    du_de: "de {n} intentos", du_sin_capa2: "{n} pasarían sin la capa 2",
    du_top: "Mutaciones que más le sirven", du_ultimo: "Motivo del último bloqueo", du_contra: "contra {s}",
    du_exitos: "{e} de {i}", du_vacio_top: "Todavía ninguna mutación le sirve",
    du_vacio: "El duelo no está corriendo en el motor", du_vacio_det: "El motor emite eventos «duelo» cuando el duelo está activo. Mientras tanto, la vista funciona con el emisor local:",
    du_g_gen: "gen.", du_g_evasion: "evasión", du_g_recall: "recall", du_g_capa2: "capa 2", du_g_mut: "mutación top", du_g_motivo: "motivo del bloqueo",
    mu_parafrasear: "Parafrasear", mu_sacar_urgencia: "Sacar la urgencia", mu_cambiar_autoridad: "Cambiar de autoridad",
    mu_partir_cuenta: "Partir la cuenta", mu_cuenta_con_letras: "Cuenta con letras", mu_deletrear_cuenta: "Deletrear la cuenta",
    mu_homoglifo_dominio: "Homoglifo en el dominio", mu_remitente_conocido: "Remitente conocido", mu_repartir_en_dos: "Repartir en dos correos",
    mu_reenviar: "Reenviar", s_ninguna: "ninguna", s_boveda: "bóveda", s_clasificador: "clasificador",
  });
  Object.assign(T.en, {
    du_curva: "Hacker versus shield", du_hacker: "What the hacker learns", du_gens: "Generations",
    du_gen: "Generation", du_evasion: "Hacker evasion", du_recall: "Shield recall", du_capa2: "Successful scams with layer 2",
    du_eje: "generation", du_c_evasion: "Evasion", du_c_recall: "Recall", du_c_capa2: "With layer 2", du_n: "{c} emails per generation · model {v}",
    ayuda_du_evasion: "Mutated emails the classifier let through as safe. Rises when the hacker finds a new mutation",
    ayuda_du_recall: "Classifier recall on the held-out set, never trained on. Responds when it learns from the mutations",
    ayuda_du_capa2: "Layer 2 is not trained: the account still comes from an email, so no mutation gets paid",
    du_de: "of {n} attempts", du_sin_capa2: "{n} would get through without layer 2",
    du_top: "Mutations that help it most", du_ultimo: "Reason for the last block", du_contra: "against {s}",
    du_exitos: "{e} of {i}", du_vacio_top: "No mutation helps it yet",
    du_vacio: "The duel is not running in the engine", du_vacio_det: "The engine emits «duel» events when the duel is on. Meanwhile, the view works with the local emitter:",
    du_g_gen: "gen.", du_g_evasion: "evasion", du_g_recall: "recall", du_g_capa2: "layer 2", du_g_mut: "top mutation", du_g_motivo: "block reason",
    mu_parafrasear: "Paraphrase", mu_sacar_urgencia: "Drop the urgency", mu_cambiar_autoridad: "Change the authority",
    mu_partir_cuenta: "Split the account", mu_cuenta_con_letras: "Account in letters", mu_deletrear_cuenta: "Spell the account",
    mu_homoglifo_dominio: "Homoglyph in the domain", mu_remitente_conocido: "Known sender", mu_repartir_en_dos: "Split into two emails",
    mu_reenviar: "Forward", s_ninguna: "none", s_boveda: "vault", s_clasificador: "classifier",
  });

  const MAX_GENS = 50;
  const d = { historial: [], visible: false, curva: null, ultimaGen: 0 };
  const pct = (x) => `${Math.round((x || 0) * 100)}%`;
  const mutacion = (m) => (m ? t(`mu_${m}`) : "—");
  const senal = (s) => (window.Operaciones?.senal ? Operaciones.senal(s) : String(s || "").replaceAll("_", " "));
  const quieto = () => Graficos.sinMovimiento;
  function reanimar(el, clase) {
    if (!el || quieto()) return;
    el.classList.remove(clase);
    void el.offsetWidth;
    el.classList.add(clase);
  }

  // La franja: generación, evasión, recall y la garantía de la capa 2, con el cambio contra la generación anterior.
  function pintarFranja(golpe) {
    const e = d.historial.at(-1), a = d.historial.at(-2);
    const delta = (k, menosEsMejor) => {
      if (!e || !a) return "";
      const x = Math.round((e[k] - a[k]) * 100);
      if (!x) return "";
      const cls = (x < 0) === menosEsMejor ? "c-verde" : "c-rojo";
      return `<span class="dato du-delta ${cls}">${ms(x > 0 ? "arrow_upward" : "arrow_downward")}${Math.abs(x)}</span>`;
    };
    $("#duelo-franja").innerHTML = !e ? "" : `
      <div class="du-celda"><span class="rotulo">${esc(t("du_gen"))}</span><span class="dato du-num" data-k="gen">${e.generacion}</span></div>
      <div class="du-celda" data-ayuda="${esc(t("ayuda_du_evasion"))}"><span class="rotulo">${esc(t("du_evasion"))}</span><span class="du-fila"><span class="dato du-num c-rojo" data-k="evasion">${pct(e.evasion)}</span>${delta("evasion", true)}</span></div>
      <div class="du-celda" data-ayuda="${esc(t("ayuda_du_recall"))}"><span class="rotulo">${esc(t("du_recall"))}</span><span class="du-fila"><span class="dato du-num" data-k="recall">${pct(e.recall)}</span>${delta("recall", false)}</span></div>
      <div class="du-celda" data-ayuda="${esc(t("ayuda_du_capa2"))}"><span class="rotulo">${esc(t("du_capa2"))}</span><span class="du-fila"><span class="dato du-num c-verde" data-k="capa2">${e.exitosas_capa2}</span><span class="c-2">${esc(t("du_de", { n: e.candidatos }))} · ${esc(t("du_sin_capa2", { n: e.sin_capa2 ?? 0 }))}</span></span></div>`;
    if (golpe) for (const el of $("#duelo-franja").querySelectorAll(".du-num")) reanimar(el, "golpe");
    $("#n-duelo").textContent = e ? t("du_n", { c: e.candidatos, v: e.version_modelo || "—" }) : "";
  }

  function pintarCurva() {
    if (!d.visible || !Graficos.hay) return;
    const el = $("#duelo-lienzo");
    if (!d.historial.length) return;
    if (!d.curva || !echarts.getInstanceByDom(el)) {
      d.curva = Graficos.curvaDuelo(el, { eje: t("du_eje"), gen: t("du_gen"), evasion: t("du_c_evasion"), recall: t("du_c_recall"), capa2: t("du_c_capa2") });
    }
    const h = d.historial.slice(-MAX_GENS);
    d.curva?.poner([h.map((e) => [e.generacion, e.evasion * 100]), h.map((e) => [e.generacion, e.recall * 100]),
      h.map((e) => [e.generacion, e.candidatos ? (100 * e.exitosas_capa2) / e.candidatos : 0])]);
  }

  // Lo que aprende el hacker: sus mejores mutaciones y por qué lo bloquearon la última vez.
  function pintarHacker(golpe) {
    const e = d.historial.at(-1);
    const caja = $("#duelo-hacker");
    if (!e) { caja.innerHTML = ""; return; }
    const top = e.top_mutaciones || [];
    const maxM = Math.max(1, ...Object.values(e.motivos || {}));
    caja.innerHTML = `
      <p class="du-sub">${esc(t("du_top"))}</p>
      <ol class="du-top">${top.length ? top.map((m, i) => `<li class="${i === 0 ? "primera" : ""}">
        <span class="du-mut">${esc(mutacion(m.mutacion))}</span>
        <span class="medidor"><span style="width:${Math.round((100 * m.exitos) / Math.max(1, m.intentos))}%"></span></span>
        <span class="dato">${esc(t("du_exitos", { e: m.exitos, i: m.intentos }))}</span>
        ${m.contra ? `<span class="c-2 du-contra">${esc(t("du_contra", { s: senal(m.contra) }))}</span>` : ""}</li>`).join("")
        : `<li class="vacio">${esc(t("du_vacio_top"))}</li>`}</ol>
      <p class="du-sub">${esc(t("du_ultimo"))}</p>
      <p class="du-motivo">${ms("block")}<span>${esc(senal(e.motivo_bloqueo))}</span></p>
      <ol class="du-motivos">${Object.entries(e.motivos || {}).sort((a, b) => b[1] - a[1]).map(([s, n]) => `<li>
        <span>${esc(senal(s))}</span><span class="medidor"><span style="width:${Math.round((100 * n) / maxM)}%"></span></span><span class="dato">${n}</span></li>`).join("")}</ol>`;
    if (golpe) reanimar(caja.querySelector(".du-top li"), "golpe");
  }

  function htmlGen(e) {
    return `<li><span class="dato">g${e.generacion}</span>
      <span class="dato c-rojo" title="${esc(t("du_g_evasion"))}">${pct(e.evasion)}</span>
      <span class="dato" title="${esc(t("du_g_recall"))}">${pct(e.recall)}</span>
      <span class="dato c-verde" title="${esc(t("du_g_capa2"))}">${e.exitosas_capa2}</span>
      <span class="du-g-mut">${esc(mutacion(e.mutacion_top))}</span>
      <span class="c-2 du-g-motivo">${esc(senal(e.motivo_bloqueo))}</span></li>`;
  }
  const cabGens = () => `<li class="cab" aria-hidden="true"><span>${esc(t("du_g_gen"))}</span><span>${esc(t("du_g_evasion"))}</span><span>${esc(t("du_g_recall"))}</span><span>${esc(t("du_g_capa2"))}</span><span>${esc(t("du_g_mut"))}</span><span>${esc(t("du_g_motivo"))}</span></li>`;
  function pintarGens() {
    $("#duelo-gens").innerHTML = cabGens() + [...d.historial].reverse().slice(0, MAX_GENS).map(htmlGen).join("");
    $("#n-duelo-gens").textContent = d.historial.length ? `${d.historial.length}` : "";
  }

  // Sin eventos «duelo»: lo dice, con cómo verlo funcionando.
  function pintarVacio() {
    const vacio = !d.historial.length;
    $("#vista-duelo").classList.toggle("sin-duelo", vacio);
    if (!vacio) return;
    $("#duelo-franja").innerHTML = `<div class="du-vacio">${ms("hourglass_top", true)}<div><p class="du-vacio-tit">${esc(t("du_vacio"))}</p>
      <p class="c-2">${esc(t("du_vacio_det"))} <code class="dato">?sim</code></p></div></div>`;
  }

  function pintarTodo() {
    pintarVacio();
    if (!d.historial.length) return;
    pintarFranja(false);
    pintarHacker(false);
    pintarGens();
    pintarCurva();
  }

  function aplicar(e) {
    if (!e || e.generacion === undefined) return;
    if (d.historial.some((x) => x.generacion === e.generacion)) return;
    const primera = !d.historial.length;
    d.historial.push(e);
    if (d.historial.length > 200) d.historial.shift();
    if (primera) return pintarTodo();
    pintarFranja(true);
    pintarHacker(true);
    const ol = $("#duelo-gens");
    ol.querySelector(".cab").insertAdjacentHTML("afterend", htmlGen(e));
    reanimar(ol.children[1], "entra-fila");
    while (ol.children.length > MAX_GENS + 1) ol.lastElementChild.remove();
    $("#n-duelo-gens").textContent = `${d.historial.length}`;
    pintarCurva();
  }

  function cargar(historial) {
    if (!Array.isArray(historial)) return;
    d.historial = historial.filter((e) => e && e.generacion !== undefined).sort((a, b) => a.generacion - b.generacion);
    pintarTodo();
  }

  function alCambiarVista(vista) {
    const antes = d.visible;
    d.visible = vista === "duelo";
    if (d.visible && !antes) requestAnimationFrame(() => { pintarCurva(); Graficos.redimensionar(); });
  }

  document.querySelectorAll("[data-idioma]").forEach((b) => b.addEventListener("click", () => { d.curva = null; pintarTodo(); }));
  pintarTodo();
  return { aplicar, cargar, alCambiarVista, _d: d };
})();
window.Duelo = Duelo;
Duelo.alCambiarVista(estado.vista);
