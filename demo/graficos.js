// Gráficos de la demo. Los colores salen de los tokens CSS de :root (ver DESIGN.md).
// - Monitor de signos vitales: canvas propio, un solo loop de requestAnimationFrame para todos los carriles.
// - Curvas (modelo en Operaciones, atacante en Resultados): Apache ECharts 5.5.1 con un tema hecho de los mismos tokens.
"use strict";

const Graficos = (() => {
  const css = getComputedStyle(document.documentElement);
  const tok = (n) => css.getPropertyValue(n).trim();
  const C = {
    fondo: tok("--fondo"), superficie: tok("--superficie"), borde: tok("--borde"),
    texto: tok("--texto"), texto2: tok("--texto-2"), texto3: tok("--texto-3"),
    verde: tok("--verde"), rojo: tok("--rojo"), ambar: tok("--ambar"),
  };
  const MONO = tok("--mono");
  const T1 = parseInt(tok("--t-1"), 10);
  const sinMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hay = typeof window.echarts !== "undefined";

  // --- Tasas con intervalo ---
  // La página no calcula nada: dibuja los agregados de resultados.json, que salen de
  // scripts/resumen_resultados.py. Cada métrica trae tasa, bajo y alto en 0..1, los escenarios (n) y
  // las repeticiones válidas. Sin escenarios no hay tasa: se muestra «—», nunca un 0 inventado.
  const N_BAJO = 5;      // menos escenarios que esto: el intervalo es tan ancho que la celda se atenúa
  const hayTasa = (m) => !!m && m.escenarios > 0 && m.tasa !== null && m.tasa !== undefined;
  const nBajo = (m) => hayTasa(m) && m.escenarios < N_BAJO;
  const pp = (x) => Math.round(100 * x);                       // fracción a punto porcentual entero
  const pct = (m) => (hayTasa(m) ? `${pp(m.tasa)} %` : "—");
  const intervalo = (m) => (hayTasa(m) ? `[${pp(m.bajo)}-${pp(m.alto)}]` : "");
  const tasaIntervalo = (m) => (hayTasa(m) ? `${pct(m)} ${intervalo(m)}` : "—");
  // ¿Los intervalos de dos métricas no se tocan? Solo entonces una diferencia es más que ruido.
  const separados = (a, b) => hayTasa(a) && hayTasa(b) && (a.alto < b.bajo || b.alto < a.bajo);

  // --- Monitor de signos vitales ---
  // Cada muestra es { v: altura 0..1, c: color }. La línea corre de derecha a izquierda.
  // El riesgo cambia la forma; el color solo marca el pico rojo (pago afuera) y el tramo verde (bloqueado).
  const PX = 2;          // px por muestra
  const VEL = 72;        // px por segundo
  const BASE = 0.42;
  const monitores = new Set();
  let ultimo = 0;
  let corriendo = false;

  function forma(alto, color, base = BASE) {
    const s = [];
    const p = (v) => s.push({ v: base + v, c: color });
    for (const v of [0.02, 0.04, 0.05, 0.04, 0.02, 0, 0, 0]) p(v);          // onda P
    p(-alto * 0.15); p(alto * 0.55); p(alto); p(alto * 0.2); p(-alto * 0.35); p(-alto * 0.1); // QRS
    for (const v of [0, 0, 0, 0.03, 0.06, 0.08, 0.07, 0.04, 0.02, 0]) p(v); // onda T
    return s;
  }
  const rampa = (de, a, n, color) => Array.from({ length: n }, (_, i) => ({ v: de + ((a - de) * (i + 1)) / n, c: color }));

  function monitor(el) {
    const canvas = document.createElement("canvas");
    el.appendChild(canvas);
    const m = {
      el, canvas, ctx: canvas.getContext("2d"), muestras: [], cola: [], resto: 0,
      modo: "base", base: BASE, hasta: 0, barrido: Math.random(), visible: true, ancho: 0, alto: 0,
    };
    // Lo que sigue cuando no hay un evento en cola: el latido del modo actual.
    m.siguiente = () => {
      if (m.cola.length) return m.cola.shift();
      if (m.modo === "apagado") return { v: BASE, c: C.borde };
      if (--m.hasta > 0) return { v: m.base, c: m.modo === "bloqueado" ? C.verde : m.modo === "cayo" ? C.rojo : C.texto3 };
      if (m.modo === "bloqueado") { m.hasta = 60; m.cola.push(...forma(0.12, C.verde, m.base)); }
      else if (m.modo === "cayo") { m.hasta = 10 + Math.floor(Math.random() * 10); m.cola.push(...forma(0.34 + Math.random() * 0.2, C.rojo, m.base)); }
      else { m.hasta = 34; m.cola.push(...forma(m.modo === "afuera" ? 0.42 : 0.26, C.texto3, m.base)); }
      return m.cola.shift();
    };
    m.medir = () => {
      const dpr = devicePixelRatio || 1;
      const w = el.clientWidth, h = el.clientHeight;
      if (w === m.ancho && h === m.alto) return;
      m.ancho = w; m.alto = h;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      m.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.ceil(w / PX) + 2;
      while (m.muestras.length < n) m.muestras.push(m.siguiente());
      if (m.muestras.length > n) m.muestras.splice(0, m.muestras.length - n);
    };
    m.avanzar = (dt) => {
      m.resto += (dt * VEL) / PX;
      while (m.resto >= 1) { m.muestras.shift(); m.muestras.push(m.siguiente()); m.resto -= 1; }
      m.barrido = (m.barrido + dt * 0.22) % 1;
    };
    m.dibujar = () => {
      const { ctx, ancho: w, alto: h, muestras } = m;
      ctx.clearRect(0, 0, w, h);
      // Retícula del monitor: tres líneas horizontales, en el color del borde.
      ctx.strokeStyle = C.borde; ctx.lineWidth = 1;
      ctx.beginPath();
      for (const f of [0.25, 0.5, 0.75]) { const y = Math.round(h * f) + 0.5; ctx.moveTo(0, y); ctx.lineTo(w, y); }
      ctx.stroke();
      // La señal, en tramos de un mismo color.
      const off = sinMovimiento ? 0 : m.resto * PX;
      const y = (v) => h - 8 - v * (h - 16);
      ctx.lineWidth = 1.5; ctx.lineJoin = "round";
      let i = 1;
      while (i < muestras.length) {
        const c = muestras[i].c;
        ctx.strokeStyle = c;
        ctx.beginPath();
        ctx.moveTo((i - 1) * PX - off, y(muestras[i - 1].v));
        while (i < muestras.length && muestras[i].c === c) { ctx.lineTo(i * PX - off, y(muestras[i].v)); i++; }
        ctx.stroke();
      }
      // Barrido de escaneo: una línea vertical que recorre el monitor.
      if (!sinMovimiento && m.modo !== "apagado") {
        const x = Math.round(m.barrido * w) + 0.5;
        ctx.strokeStyle = C.texto3; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
    };
    // Con movimiento reducido no hay loop: el evento se escribe de una vez y se dibuja.
    m.empujar = (muestras) => {
      m.cola.push(...muestras);
      if (sinMovimiento) {
        const n = m.cola.length;
        for (let k = 0; k < n + 24; k++) { m.muestras.shift(); m.muestras.push(m.siguiente()); }
        m.dibujar();
      }
    };
    const api = {
      // Lee lo del dueño: latido base.
      dueno() { if (m.modo === "base" || m.modo === "afuera") m.empujar(forma(0.26, C.texto3, m.base)); },
      // Entró un valor no confiable: la línea sube y late más fuerte.
      afuera() {
        if (m.modo !== "base" && m.modo !== "afuera") return;
        const b = BASE + 0.12;
        m.empujar([...rampa(m.base, b, 6, C.texto3), ...forma(0.42, C.texto3, b)]);
        m.base = b; m.modo = "afuera"; m.hasta = 20;
      },
      // Pagó a una cuenta de afuera: pico rojo y queda alterada en rojo.
      cayo() {
        m.empujar([...forma(0.56, C.rojo, m.base), ...forma(0.5, C.rojo, m.base)]);
        m.modo = "cayo"; m.hasta = 12;
      },
      // El escudo bloqueó: pico rojo y corte a una línea verde estable.
      corte() {
        m.empujar([...forma(0.56, C.rojo, m.base), ...rampa(m.base, BASE, 6, C.verde)]);
        m.base = BASE; m.modo = "bloqueado"; m.hasta = 40;
      },
      // Pagó a lo inscrito: vuelve a la base.
      inscrita() { m.empujar(rampa(m.base, BASE, 6, C.texto3)); m.base = BASE; m.modo = "base"; m.hasta = 20; },
      apagar() { m.modo = "apagado"; },
    };
    if ("IntersectionObserver" in window) new IntersectionObserver(([e]) => { m.visible = e.isIntersecting; }).observe(el);
    m.medir();
    if (sinMovimiento) {
      for (let k = 0; k < m.muestras.length; k++) { m.muestras.shift(); m.muestras.push(m.siguiente()); }
      m.dibujar();
      addEventListener("resize", () => { m.medir(); m.dibujar(); });
    }
    monitores.add(m);
    arrancar();
    return api;
  }

  // Un solo loop para todos los monitores; se limpia solo cuando un carril se redibuja.
  function cuadro(t) {
    const dt = Math.min(0.1, (t - (ultimo || t)) / 1000);
    ultimo = t;
    for (const m of monitores) {
      if (!m.el.isConnected) { monitores.delete(m); continue; }
      m.medir();
      m.avanzar(dt);
      if (m.visible) m.dibujar();
    }
    if (monitores.size) requestAnimationFrame(cuadro);
    else { corriendo = false; ultimo = 0; }
  }
  function arrancar() {
    if (sinMovimiento || corriendo) return;
    corriendo = true;
    requestAnimationFrame(cuadro);
  }

  // --- ECharts ---
  if (hay) {
    echarts.registerTheme("consola", {
      color: [C.texto2, C.rojo, C.verde, C.ambar],
      backgroundColor: "transparent",
      textStyle: { fontFamily: MONO, fontSize: T1, color: C.texto2 },
      categoryAxis: {
        axisLine: { lineStyle: { color: C.borde } }, axisTick: { show: false },
        axisLabel: { color: C.texto2 }, splitLine: { lineStyle: { color: C.borde } },
      },
      valueAxis: {
        axisLine: { lineStyle: { color: C.borde } }, axisLabel: { color: C.texto2 },
        splitLine: { lineStyle: { color: C.borde } },
      },
      tooltip: {
        backgroundColor: C.superficie, borderColor: C.borde, borderWidth: 1, padding: [8, 16],
        textStyle: { color: C.texto, fontFamily: MONO, fontSize: T1 }, extraCssText: "border-radius:0;box-shadow:none;",
      },
    });
  }

  const instancias = new Set();
  function iniciar(el) {
    if (!hay || !el) return null;
    echarts.getInstanceByDom(el)?.dispose();
    const g = echarts.init(el, "consola", { renderer: "canvas" });
    instancias.add(g);
    return g;
  }
  let espera;
  addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(() => instancias.forEach((g) => !g.isDisposed() && g.resize()), 120);
  });
  const redimensionar = () => instancias.forEach((g) => !g.isDisposed() && g.resize());

  // Curvas del modelo (vista Operaciones): precisión, recall y falsas alarmas contra los ejemplos vistos.
  // Tres grises que se distinguen por trazo; cada evento «modelo» agrega un punto y ECharts anima el tramo nuevo.
  function curvas(el) {
    const g = iniciar(el);
    if (!g) return null;
    const serie = (nombre, color, tipo) => ({
      type: "line", name: nombre, showSymbol: false,
      symbol: "rect", symbolSize: 4, smooth: false,
      lineStyle: { color, width: 1.5, type: tipo }, itemStyle: { color }, emphasis: { disabled: true }, data: [],
    });
    g.setOption({
      animation: !sinMovimiento, animationDuration: 480, animationDurationUpdate: 480, animationEasingUpdate: "cubicOut",
      grid: { left: 40, right: 16, top: 12, bottom: 24 },
      xAxis: { type: "value", min: "dataMin", max: "dataMax", splitLine: { show: false }, axisLabel: { color: C.texto2, hideOverlap: true, showMaxLabel: false } },
      yAxis: { type: "value", min: 0, max: 100, interval: 25, axisLabel: { formatter: "{value}%" } },
      tooltip: { trigger: "axis", formatter: (ps) => [`n ${ps[0]?.value[0]}`, ...ps.map((p) => `${p.seriesName}  ${Math.round(p.value[1])}%`)].join("<br>") },
      series: [serie("", C.texto, "solid"), serie("", C.texto2, [6, 3]), serie("", C.texto3, [2, 3])],
    });
    return {
      poner(datos, nombres = []) {
        g.setOption({ series: datos.map((data, i) => ({ data, name: nombres[i] || "", showSymbol: data.length < 3 })) });
      },
    };
  }

  // Curva del atacante adaptativo (vista Resultados): estafas exitosas acumuladas por ronda, una línea por
  // defensa. Grises que se distinguen por trazo; el rojo solo si una estafa le ganó a esa defensa.
  // `series` trae { nombre, puntos: [[ronda, %], ...], cayo }.
  const TRAZOS = ["solid", [6, 3], [2, 3], [10, 3, 2, 3]];
  const GRISES = () => [C.texto, C.texto2, C.texto3, C.texto2];
  function curvaAtacante(el, series, { rondas, ayuda }) {
    const g = iniciar(el);
    if (!g) return;
    g.setOption({
      animation: !sinMovimiento,
      grid: { left: 40, right: 136, top: 16, bottom: 48 },
      xAxis: { type: "value", min: 0, max: Math.max(1, rondas), interval: 1, name: ayuda.eje_x, nameLocation: "middle", nameGap: 24,
        nameTextStyle: { color: C.texto2, fontFamily: MONO, fontSize: T1 }, splitLine: { show: false } },
      yAxis: { type: "value", min: 0, max: 100, interval: 25, axisLabel: { formatter: "{value}%" } },
      tooltip: { trigger: "axis", formatter: (ps) => [`${ayuda.ronda} ${ps[0]?.value[0]}`, ...ps.map((p) => `${p.seriesName}  ${Math.round(p.value[1])}% ${series[p.seriesIndex]?.ic?.[p.dataIndex] || ""}`)].join("<br>") },
      series: series.map((x, i) => {
        const color = x.cayo ? C.rojo : GRISES()[i % 4];
        return { type: "line", name: x.nombre, data: x.puntos, symbol: "rect", symbolSize: 6, showSymbol: true,
          lineStyle: { color, width: 1.5, type: TRAZOS[i % 4] }, itemStyle: { color }, emphasis: { disabled: true },
          // La etiqueta al final de cada línea nombra la defensa: no hace falta leyenda aparte.
          endLabel: { show: true, color, fontFamily: MONO, fontSize: T1, formatter: (p) => `${p.seriesName} ${Math.round(p.value[1])}%` },
          labelLayout: { moveOverlap: "shiftY" } };
      }),
    });
  }

  // Curvas del duelo: por generación, la evasión del hacker (rojo: es el riesgo) contra el recall del escudo
  // (blanco), y las estafas exitosas con la capa 2 (verde, la garantía), que se mantienen en 0.
  function curvaDuelo(el, nombres) {
    const g = iniciar(el);
    if (!g) return null;
    const serie = (nombre, color, tipo, ancho = 1.5) => ({
      type: "line", name: nombre, data: [], showSymbol: false, symbol: "rect", symbolSize: 4, smooth: false,
      lineStyle: { color, width: ancho, type: tipo }, itemStyle: { color }, emphasis: { disabled: true },
      endLabel: { show: true, color, fontFamily: MONO, fontSize: T1, formatter: (p) => `${p.seriesName} ${Math.round(p.value[1])}%` },
      labelLayout: { moveOverlap: "shiftY" },
    });
    g.setOption({
      animation: !sinMovimiento, animationDurationUpdate: 480, animationEasingUpdate: "cubicOut",
      grid: { left: 40, right: 128, top: 16, bottom: 40 },
      xAxis: { type: "value", min: "dataMin", max: "dataMax", minInterval: 1, splitLine: { show: false },
        name: nombres.eje, nameLocation: "middle", nameGap: 24, nameTextStyle: { color: C.texto2, fontFamily: MONO, fontSize: T1 } },
      yAxis: { type: "value", min: 0, max: 100, interval: 25, axisLabel: { formatter: "{value}%" } },
      tooltip: { trigger: "axis", formatter: (ps) => [`${nombres.gen} ${ps[0]?.value[0]}`, ...ps.map((p) => `${p.seriesName}  ${Math.round(p.value[1])}%`)].join("<br>") },
      series: [serie(nombres.evasion, C.rojo, "solid", 2), serie(nombres.recall, C.texto, "solid", 2), serie(nombres.capa2, C.verde, [6, 3])],
    });
    return { poner(datos) { g.setOption({ series: datos.map((data) => ({ data, showSymbol: data.length < 3 })) }); } };
  }

  return { C, hay, curvaDuelo, N_BAJO, hayTasa, nBajo, pp, pct, intervalo, tasaIntervalo, separados, monitor, curvas, curvaAtacante, redimensionar, sinMovimiento };
})();
window.Graficos = Graficos;
