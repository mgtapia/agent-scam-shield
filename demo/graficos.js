// Gráficos de la demo con Apache ECharts. El tema sale de los tokens CSS de :root (ver DESIGN.md):
// aquí no hay colores propios.
"use strict";

const Graficos = (() => {
  const css = getComputedStyle(document.documentElement);
  const tok = (n) => css.getPropertyValue(n).trim();
  const C = {
    fondo: tok("--fondo"), superficie: tok("--superficie"), borde: tok("--borde"),
    texto: tok("--texto"), texto2: tok("--texto-2"), acento: tok("--acento"),
    verde: tok("--verde"), rojo: tok("--rojo"), ambar: tok("--ambar"),
  };
  const MONO = tok("--mono");
  const T1 = parseInt(tok("--t-1"), 10);
  const sinMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hay = typeof window.echarts !== "undefined";

  if (hay) {
    echarts.registerTheme("consola", {
      color: [C.acento, C.rojo, C.verde, C.ambar],
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
      radar: {
        axisName: { color: C.texto2, fontFamily: MONO, fontSize: T1 },
        axisLine: { lineStyle: { color: C.borde } }, splitLine: { lineStyle: { color: C.borde } },
        splitArea: { show: false },
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
    const vieja = echarts.getInstanceByDom(el);
    if (vieja) vieja.dispose();
    const g = echarts.init(el, "consola", { renderer: "canvas" });
    instancias.add(g);
    return g;
  }
  let espera;
  addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(() => instancias.forEach((g) => !g.isDisposed() && g.resize()), 120);
  });

  // --- Agregados desde las filas de resultados.json ---
  // Éxito de la estafa: muestras de estafa con seguridad «I» (cayó) sobre las que tienen seguridad.
  // Utilidad: «C» sobre las que tienen utilidad. Falsa alarma: promedio en los controles.
  function tasa(filas, campo) {
    const vals = filas.map((f) => f[campo]).filter((v) => v !== null && v !== undefined);
    if (!vals.length) return { v: null, n: 0 };
    const pos = campo === "seguridad" ? vals.filter((v) => v === "I").length
      : campo === "utilidad" ? vals.filter((v) => v === "C").length
      : vals.reduce((a, b) => a + Number(b), 0);
    return { v: (100 * pos) / vals.length, n: vals.length };
  }

  const pct = (x) => (x === null ? "—" : `${Math.round(x)}%`);

  // --- Pulso del agente: un electrocardiograma por carril ---
  // nivel 0 verde (cortado por el escudo o pagado a lo inscrito), 1 base (lo del dueño),
  // 2 ámbar (entró un valor no confiable), 3 rojo (pago a una cuenta de afuera).
  const NIVELES = [C.verde, C.acento, C.ambar, C.rojo];
  const BASE = [0.6, 1, 1.6, 2.6];
  const VENTANA = 48;

  function pulso(el) {
    const g = iniciar(el);
    let x = 0;
    let nivel = 1;
    let plano = false;
    const datos = [];
    const opcion = () => ({
      animation: false,
      grid: { left: 0, right: 0, top: 8, bottom: 8 },
      xAxis: { type: "value", show: false, min: Math.max(0, x - VENTANA), max: Math.max(VENTANA, x) },
      yAxis: { type: "value", show: false, min: 0, max: 4.4 },
      // Una serie por nivel: cada tramo toma el color de su nivel y comparte el punto de cambio.
      series: NIVELES.map((color, n) => ({
        type: "line", showSymbol: false, smooth: false, connectNulls: false,
        lineStyle: { width: 1.5, color }, itemStyle: { color },
        data: datos.map(([px, py, pn], i) => (pn === n || datos[i + 1]?.[2] === n ? [px, py] : [px, null])),
      })),
    });
    const punto = (dx, y, n = nivel) => { x += dx; datos.push([+x.toFixed(2), y, n]); };
    const pintar = () => g && g.setOption(opcion(), { replaceMerge: ["series"] });

    // Un latido: onda P, complejo QRS y onda T, a la altura del nivel.
    function latido(alto = 0.4, n = nivel) {
      const b = BASE[n];
      punto(0.4, b, n); punto(0.2, b + 0.08, n); punto(0.2, b, n);
      punto(0.15, b - alto * 0.25, n); punto(0.15, b + alto, n); punto(0.15, b - alto * 0.4, n);
      punto(0.15, b, n); punto(0.3, b + alto * 0.18, n); punto(0.3, b, n);
    }
    return {
      // Avance sin evento: el corazón late a la altura actual, o la línea sigue plana si se cortó.
      tic() { if (plano) punto(1, BASE[nivel]); else latido(0.35); pintar(); },
      evento(n, alto) {
        if (plano) return;
        const antes = nivel;
        if (n === 3) { latido(alto ?? 3.2, 3); nivel = 3; }
        else { nivel = n; latido(alto ?? (n === 2 ? 0.9 : 0.5), n); }
        if (antes !== nivel && n !== 3) punto(0.2, BASE[nivel]);
        pintar();
      },
      // Pico rojo y corte en verde: el escudo bloqueó el pago.
      corte() { latido(3.2, 3); punto(0.1, BASE[0], 0); nivel = 0; plano = true; pintar(); },
      fin() { plano = true; pintar(); },
      nivel: () => nivel,
      vacio() { datos.length = 0; x = 0; nivel = 1; plano = false; pintar(); },
    };
  }

  // --- Radar: una figura por configuración, ejes por táctica ---
  function radar(el, ejes, valores, color, sinDatos) {
    const g = iniciar(el);
    if (!g) return;
    g.setOption({
      animation: !sinMovimiento,
      radar: {
        indicator: ejes.map((e) => ({ name: e, max: 100 })), radius: "62%", center: ["50%", "54%"],
        splitNumber: 4, shape: "polygon",
      },
      tooltip: { trigger: "item" },
      graphic: sinDatos ? [{ type: "text", left: "center", top: "middle",
        style: { text: sinDatos, fill: C.texto2, font: `${T1}px ${MONO}` } }] : [],
      series: sinDatos ? [] : [{
        type: "radar", symbol: "rect", symbolSize: 4,
        lineStyle: { color, width: 1.5 }, itemStyle: { color },
        areaStyle: { color, opacity: 0.12 },
        data: [{ value: valores.map((v) => v.v ?? 0), name: "" }],
        tooltip: { formatter: () => ejes.map((e, i) => `${e}  ${pct(valores[i].v)}  n=${valores[i].n}`).join("<br>") },
      }],
    });
  }

  // --- Mapa de calor: de superficie a rojo según la tasa de éxito de la estafa ---
  function calor(el, { columnas, filas, celdas, alClic, tooltip }) {
    const g = iniciar(el);
    if (!g) return;
    g.setOption({
      animation: false,
      grid: { left: 136, right: 16, top: 8, bottom: 32 },
      xAxis: { type: "category", data: columnas, position: "bottom", splitArea: { show: false },
        axisLabel: { color: C.texto2, interval: 0 } },
      yAxis: { type: "category", data: filas, inverse: true, axisLabel: { color: C.texto, width: 128, overflow: "truncate" } },
      visualMap: {
        show: false, min: 0, max: 100, dimension: 2, seriesIndex: 0,
        inRange: { color: [C.superficie, C.rojo] },
        outOfRange: { color: C.fondo },
      },
      tooltip: { trigger: "item", formatter: (p) => tooltip(p.data) },
      series: [{
        type: "heatmap",
        data: celdas.map((c) => ({ value: [c.x, c.y, c.v === null ? -1 : c.v], ...c })),
        label: { show: true, color: C.texto, fontFamily: MONO, fontSize: T1,
          formatter: (p) => (p.data.v === null ? "—" : pct(p.data.v)) },
        itemStyle: { borderColor: C.borde, borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: C.acento, borderWidth: 1 } },
        cursor: "pointer",
      }],
    });
    g.off("click");
    if (alClic) g.on("click", (p) => alClic(p.data));
  }

  return { C, hay, tasa, pct, pulso, radar, calor, sinMovimiento };
})();
window.Graficos = Graficos;
