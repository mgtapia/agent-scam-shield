// Grifter, vista Duelo (#82): un hacker que aprende de cómo lo bloqueamos, contra el escudo congelado y contra el
// escudo que se reentrena con él. Los números salen del bloque `duelo` de resultados.json, que arma
// scripts/resultados_demo.py desde results/duelo/ (seis corridas deterministas de `grifter duelo`). La página no
// calcula nada: solo dibuja. Lo en vivo (eventos `duelo` del flujo /api/vivo e `historial_duelo` de la foto) va en
// una celda aparte: Operaciones le pasa los eventos (aplicar) y la historia (cargar).
// Depende de app.js (T, t, esc, ms, $, estado) y de graficos.js.
"use strict";

const Duelo = (() => {
  Object.assign(T.es, {
    du_titular: "pagos que cruzan la capa 2", du_titular_det: "en {g} generaciones · {c} intentos del hacker",
    ayuda_du_titular: "La capa 2 exige que la cuenta venga del dueño, no de un correo. No se entrena: ninguna mutación la mueve.\nSuma de exitosas_capa2 en las seis corridas, con y sin entrenar.",
    du_sin_capa2: "Sin capa 2 habría cobrado", du_veces: "veces", du_de: "de {n} intentos · {m}",
    ayuda_du_sin_capa2: "Correos mutados que el clasificador dejó pasar como seguros, sumados generación a generación (sin_capa2). Es un conteo de intentos: la misma cepa vuelve en varias generaciones.",
    du_congelado: "Escudo congelado", du_aprende: "Escudo que aprende",
    ayuda_du_congelado: "--sin-entrenar: el clasificador y la bóveda no se reentrenan. El hacker aprende y el escudo no responde.",
    ayuda_du_aprende: "El dueño simulado confirma las estafas de cada generación y el clasificador y la bóveda se reentrenan con ellas.",
    du_evasion: "evasión del hacker contra el clasificador", du_sem: "sem. {s}",
    du_l_congelado: "{i} → {f}", du_l_aprende: "pico {p} → {f}",
    du_eje: "generación", du_gen: "Generación", du_capa2: "capa 2", du_capa2_fin: "capa 2: 0 pagos",
    du_ayuda: "El hacker es un atacante por mutaciones con Thompson sampling, sin API: aprende qué mutación le sirve contra cada señal del escudo. Parte de la recuperación del escudo que aprende la hace la guardia de deriva, que descarta las versiones que empeoran: {r} versiones revertidas en las semillas 0, 1 y 2 (Clasificador.revertidas).",
    du_vivo: "En vivo", du_vivo_val: "g{g} · evasión {e} · capa 2 {c}", du_vivo_vacio: "sin eventos duelo",
    ayuda_du_vivo: "Eventos «duelo» del flujo /api/vivo. Corren en el motor solo con el duelo activo; con ?sim los emite el emisor local, con números de juguete.",
    du_sin_archivo: "No hay corridas del duelo en results/duelo/", du_sin_archivo_det: "Se generan con:",
    du_y: " y ",
  });
  Object.assign(T.en, {
    du_titular: "payments that cross layer 2", du_titular_det: "in {g} generations · {c} hacker attempts",
    ayuda_du_titular: "Layer 2 requires the account to come from the owner, not from an email. It is not trained: no mutation moves it.\nSum of exitosas_capa2 over the six runs, with and without training.",
    du_sin_capa2: "Without layer 2 it would have collected", du_veces: "times", du_de: "of {n} attempts · {m}",
    ayuda_du_sin_capa2: "Mutated emails the classifier let through as safe, summed generation by generation (sin_capa2). It counts attempts: the same strain returns over several generations.",
    du_congelado: "Frozen shield", du_aprende: "Shield that learns",
    ayuda_du_congelado: "--sin-entrenar: the classifier and the vault are not retrained. The hacker learns and the shield does not respond.",
    ayuda_du_aprende: "The simulated owner confirms each generation's scams and the classifier and the vault retrain on them.",
    du_evasion: "hacker evasion against the classifier", du_sem: "seed {s}",
    du_l_congelado: "{i} → {f}", du_l_aprende: "peak {p} → {f}",
    du_eje: "generation", du_gen: "Generation", du_capa2: "layer 2", du_capa2_fin: "layer 2: 0 payments",
    du_ayuda: "The hacker is a mutation attacker with Thompson sampling, no API: it learns which mutation works against each shield signal. Part of the learning shield's recovery comes from the drift guard, which discards versions that get worse: {r} versions rolled back in seeds 0, 1 and 2 (Clasificador.revertidas).",
    du_vivo: "Live", du_vivo_val: "g{g} · evasion {e} · layer 2 {c}", du_vivo_vacio: "no duel events",
    ayuda_du_vivo: "«duelo» events from the /api/vivo stream. They run in the engine only with the duel on; with ?sim the local emitter sends them, with toy numbers.",
    du_sin_archivo: "No duel runs in results/duelo/", du_sin_archivo_det: "They are generated with:",
    du_y: " and ",
  });

  const MODOS = ["congelado", "aprende"];
  const d = { historial: [], visible: false };
  const datos = () => estado.resultados?.duelo || null;
  const num = (n) => Number(n).toLocaleString(t("locale"));
  const pct = (x) => `${Math.round((x || 0) * 100)} %`;
  const lista = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")}${t("du_y")}${xs.at(-1)}` : xs.join(""));
  const fuentes = (m) => m.semillas.map((x) => `${x.fuente}\n${x.comando}`).join("\n");
  const archivos = (modo) => `results/duelo/${modo}_s{${datos()[modo].semillas.map((x) => x.semilla).join(",")}}.json`;
  // Muestra de trazo para la leyenda: el mismo trazo y color que la línea de esa semilla en el gráfico.
  const TRAZO = ["", "6 3", "2 3"];
  const muestra = (i, rojo) => `<svg class="du-trazo" width="24" height="8" aria-hidden="true"><line x1="0" y1="4" x2="24" y2="4"
    stroke="${rojo ? Graficos.C.rojo : [Graficos.C.texto, Graficos.C.texto2, Graficos.C.texto3][i % 3]}" stroke-width="1.5" stroke-dasharray="${TRAZO[i % 3]}"/></svg>`;

  function pintarFranja(D) {
    const celda = (modo) => {
      const m = D[modo];
      return `<div class="du-celda" tabindex="0" data-ayuda="${esc(`${t("ayuda_du_sin_capa2")}\n${fuentes(m)}`)}">
        <span class="rotulo">${esc(t("du_sin_capa2"))}</span>
        <span class="du-fila"><span class="dato du-num">${num(m.sin_capa2)}</span><span>${esc(t("du_veces"))}</span></span>
        <span class="c-2 du-det">${esc(t("du_de", { n: num(m.candidatos), m: t(`du_${modo}`).toLowerCase() }))}</span></div>`;
    };
    $("#duelo-franja").innerHTML = `
      <div class="du-celda du-titular" tabindex="0" data-ayuda="${esc(`${t("ayuda_du_titular")}\n${D.fuente}\n${D.comando}`)}">
        <span class="du-fila"><span class="dato du-num c-verde">${num(D.exitosas_capa2)}</span><span class="du-tit">${esc(t("du_titular"))}</span></span>
        <span class="c-2 du-det">${esc(t("du_titular_det", { g: D.generaciones, c: num(D.candidatos) }))}</span></div>
      ${celda("congelado")}${celda("aprende")}
      <div class="du-celda du-vivo" tabindex="0" data-ayuda="${esc(t("ayuda_du_vivo"))}"><span class="rotulo">${esc(t("du_vivo"))}</span>
        <span class="dato" id="du-vivo"></span></div>`;
    pintarVivo();
  }

  function pintarVivo() {
    const el = $("#du-vivo");
    if (!el) return;
    const e = d.historial.at(-1);
    el.classList.toggle("c-2", !e);
    el.textContent = e ? t("du_vivo_val", { g: e.generacion, e: pct(e.evasion), c: e.exitosas_capa2 }) : t("du_vivo_vacio");
  }

  function pintarModo(D, modo) {
    const m = D[modo], rojo = modo === "congelado";
    const tit = $(`#t-du-${modo}`);
    tit.dataset.ayuda = `${t(`ayuda_du_${modo}`)}\n${fuentes(m)}`;
    $(`#n-du-${modo}`).textContent = archivos(modo);
    $(`#du-ley-${modo}`).innerHTML = m.semillas.map((x, i) => `<li tabindex="0" data-ayuda="${esc(`${x.fuente}\n${x.comando}`)}">
      ${muestra(i, rojo)}<span class="c-2">${esc(t("du_sem", { s: x.semilla }))}</span>
      <span class="dato${rojo ? " c-rojo" : ""}">${esc(rojo ? t("du_l_congelado", { i: pct(x.inicio), f: pct(x.final) })
        : t("du_l_aprende", { p: pct(x.pico), f: pct(x.final) }))}</span></li>`).join("")
      + `<li class="du-ley-que c-2">${esc(t("du_evasion"))}</li>`;
    if (!d.visible || !Graficos.hay) return;
    Graficos.curvaDuelo($(`#du-lienzo-${modo}`), {
      rojo,
      series: m.semillas.map((x) => ({ nombre: t("du_sem", { s: x.semilla }), puntos: x.evasion.map((v, g) => [g + 1, v * 100]) })),
      capa2: m.semillas.map((x) => x.capa2.map((v, g) => [g + 1, v])),
      nombres: { eje: t("du_eje"), gen: t("du_gen"), capa2: t("du_capa2"), capa2_fin: t("du_capa2_fin") },
    });
  }

  function pintarVacio(D) {
    const vacio = !D || D.estado !== "ok";
    $("#vista-duelo").classList.toggle("sin-duelo", vacio);
    if (!vacio) return false;
    $("#duelo-franja").innerHTML = `<div class="du-vacio">${ms("hourglass_top", true)}<div><p class="du-vacio-tit">${esc(t("du_sin_archivo"))}</p>
      <p class="c-2">${esc(t("du_sin_archivo_det"))} <code class="dato">${esc(D?.comando || "grifter duelo --generaciones 20 --semilla N [--sin-entrenar] --json results/duelo/<modo>_sN.json")}</code></p></div></div>`;
    $("#du-ayuda").textContent = "";
    return true;
  }

  function pintar() {
    if (estado.resultados === undefined) return;   // resultados.json todavía no llega
    const D = datos();
    if (pintarVacio(D)) return;
    pintarFranja(D);
    for (const modo of MODOS) pintarModo(D, modo);
    const rev = D.aprende.semillas.map((x) => x.revertidas).filter((r) => r !== null && r !== undefined);
    $("#du-ayuda").textContent = rev.length ? t("du_ayuda", { r: lista(rev.map(num)) }) : "";
    $("#du-ayuda").dataset.ayuda = D.aprende.semillas.map((x) => x.fuente).join("\n");
  }

  function aplicar(e) {
    if (!e || e.generacion === undefined) return;
    if (d.historial.some((x) => x.generacion === e.generacion)) return;
    d.historial.push(e);
    if (d.historial.length > 200) d.historial.shift();
    pintarVivo();
  }

  function cargar(historial) {
    if (!Array.isArray(historial)) return;
    d.historial = historial.filter((e) => e && e.generacion !== undefined).sort((a, b) => a.generacion - b.generacion);
    pintarVivo();
  }

  // ECharts necesita medir el contenedor: los gráficos se dibujan al entrar a la vista.
  function alCambiarVista(vista) {
    const antes = d.visible;
    d.visible = vista === "duelo";
    if (d.visible && !antes) requestAnimationFrame(pintar);
  }

  document.querySelectorAll("[data-idioma]").forEach((b) => b.addEventListener("click", pintar));
  return { aplicar, cargar, alCambiarVista, pintar, _d: d };
})();
window.Duelo = Duelo;
Duelo.alCambiarVista(estado.vista);
