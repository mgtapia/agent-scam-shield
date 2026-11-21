// Grifter, vista Instalar: los seis caminos de docs/instalar.md, uno por tipo de usuario, cada uno con a lo más
// cinco pasos y un botón para copiar cada comando. Depende de app.js (T, t, esc, ms, $, estado, pintarTextos).
// El botón de copiar usa el manejador de [data-copiar] de resultados_vista.js (con respaldo para file://).
"use strict";

const Instalar = (() => {
  Object.assign(T.es, {
    v_instalar: "Instalar", ayuda_v_instalar: "Cómo instalar Grifter según quién eres",
    in_nota: "Grifter no lee tu correo ni tu WhatsApp: se para entre el agente y sus herramientas y revisa de dónde salió cada cuenta antes de pagar.",
    in_guia: "Guía completa", in_copiar: "Copiar",
  });
  Object.assign(T.en, {
    v_instalar: "Install", ayuda_v_instalar: "How to install Grifter depending on who you are",
    in_nota: "Grifter does not read your email or your WhatsApp: it sits between the agent and its tools and checks where each account came from before paying.",
    in_guia: "Full guide", in_copiar: "Copy",
  });

  const REPO = "https://github.com/mgtapia/grifter";
  const DOCS = `${REPO}/blob/main/docs/`;
  const CLONAR = "git clone https://github.com/mgtapia/grifter && cd grifter\npython -m venv .venv\n.venv\\Scripts\\activate          # Windows; macOS o Linux: source .venv/bin/activate";
  const CLONE = "git clone https://github.com/mgtapia/grifter && cd grifter\npython -m venv .venv\n.venv\\Scripts\\activate          # Windows; macOS or Linux: source .venv/bin/activate";
  const ESCUDO = `from grifter import escudo

herramientas = escudo(herramientas,
                      cuentas_inscritas={"Silicio Austral": "Banco Litoral 33-7741-0092"},
                      encargo="Paga la factura de Silicio Austral",
                      avisar=None)`;
  const SHIELD = `from grifter import escudo

tools = escudo(tools,
               cuentas_inscritas={"Silicio Austral": "Banco Litoral 33-7741-0092"},
               encargo="Pay the Silicio Austral invoice",
               avisar=None)`;

  // Cada camino: ícono, quién es, qué hace, cuánto tarda y sus pasos. Un paso puede traer un comando para copiar.
  // En el texto, `código` y [enlace](url) se dibujan como tales.
  const CAMINOS = {
    es: [
      { id: "ver", icono: "visibility", titulo: "Quiero verlo funcionar", hace: "Abres una página", tiempo: "1 min", ancla: "1-quiero-verlo-funcionar", pasos: [
        { texto: "Abre [grifter.onrender.com](https://grifter.onrender.com). Si tarda, el servicio gratis estaba dormido." },
        { texto: "En **Operaciones**, mira cómo se frenan los correos de estafa. En **Duelo**, el atacante que aprende contra el escudo que aprende." },
      ] },
      { id: "chatgpt", icono: "chat", titulo: "Uso ChatGPT", hace: "Agregas un conector", tiempo: "3 min", ancla: "2-uso-chatgpt", pasos: [
        { texto: "En ChatGPT web: **Settings → Apps → Advanced settings**, prende **Developer mode**." },
        { texto: "Agrega un servidor MCP: nombre `Grifter`, autenticación **No authentication**, y esta URL:", codigo: "https://grifter.onrender.com/mcp" },
        { texto: "En una conversación nueva, elige el conector y pide:", codigo: "Compra 10 microprocesadores SA-3NM en la tienda de Silicio Austral y paga el checkout" },
        { texto: "La tienda de juguete cambia la cuenta de cobro y Grifter retiene el pago. ChatGPT te muestra por qué." },
      ] },
      { id: "claude", icono: "terminal", titulo: "Uso Claude Desktop o Claude Code", hace: "Instalas Grifter en tu computador", tiempo: "10 min", ancla: "3-uso-claude-desktop-o-claude-code", pasos: [
        { texto: "Con Python 3.11 o más nuevo y Git, baja Grifter e instálalo:", codigo: `${CLONAR}\npip install -e .` },
        { texto: "Copia la configuración de ejemplo. Ahí van tus cuentas inscritas y los MCP que quieres proteger:", codigo: "cp scamshield/mcp/grifter.ejemplo.yaml grifter.yaml" },
        { texto: "Conéctalo a Claude Code (en Claude Desktop, el bloque de [mcp.md](" + DOCS + "mcp.md#claude-desktop)):", codigo: "claude mcp add grifter -- python -m scamshield.mcp.proxy --config grifter.yaml" },
        { texto: "Pruébalo: «Paga la factura 8812 de Silicio Austral». El proveedor de prueba trae una cuenta cambiada y Grifter retiene el pago." },
        { texto: "Opcional: alertas en el celular con `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env`." },
      ] },
      { id: "agente", icono: "code", titulo: "Programo mi propio agente", hace: "Envuelves tus herramientas", tiempo: "5 min", ancla: "4-programo-mi-propio-agente", pasos: [
        { texto: "Instala:", codigo: "pip install \"git+https://github.com/mgtapia/grifter\"" },
        { texto: "Envuelve tus funciones de Python, síncronas o `async`:", codigo: ESCUDO },
        { texto: "Lo que lee (correo, web, MCP) queda marcado como no confiable; lo que paga o comparte datos se revisa antes de correr. Si Grifter retiene, la función no corre y el modelo recibe el porqué." },
      ] },
      { id: "banco", icono: "account_balance", titulo: "Soy un banco, una billetera o un comercio", hace: "Pones Grifter delante de tus MCP", tiempo: "1 día", ancla: "5-soy-un-banco-una-billetera-o-un-comercio", pasos: [
        { texto: "Instala como en Claude y define tus MCP por URL en `grifter.yaml`. Si tu MCP no responde, Grifter falla cerrado." },
        { texto: "Carga las cuentas inscritas de cada cliente y los titulares que conoces: se activa la confirmación de beneficiario (capa 3)." },
        { texto: "Activa la doble autorización con TOTP: cambiar la política pide dos aprobadores ([mcp.md](" + DOCS + "mcp.md#doble-autorización-dos-personas-no-una))." },
        { texto: "Levántalo por HTTP. Para la prueba basta `GRIFTER_MCP_TOKEN`; en producción va OAuth 2.1, que todavía no está hecho:", codigo: "python -m scamshield.mcp.proxy --config grifter.yaml --http --puerto 8766" },
        { texto: "Elige el canal de la alerta: Telegram, WhatsApp (Kapso) o tu aplicación, con el gancho `avisar`." },
      ] },
      { id: "investigo", icono: "science", titulo: "Investigo seguridad de agentes", hace: "Corres el benchmark", tiempo: "5 min", ancla: "6-investigo-seguridad-de-agentes", pasos: [
        { texto: "Baja Grifter con las dependencias de desarrollo:", codigo: `${CLONAR}\npip install -e ".[dev,demo]"` },
        { texto: "El benchmark completo, sin llaves de API, en segundos:", codigo: "grifter bench" },
        { texto: "Las pruebas, sin llamar a ningún modelo:", codigo: "pytest" },
        { texto: "Con modelos reales y el atacante adaptativo: el [README](" + REPO + "#benchmark-en-un-comando)." },
      ] },
    ],
    en: [
      { id: "ver", icono: "visibility", titulo: "I want to see it work", hace: "You open a page", tiempo: "1 min", ancla: "1-quiero-verlo-funcionar", pasos: [
        { texto: "Open [grifter.onrender.com](https://grifter.onrender.com). If it is slow, the free service was asleep." },
        { texto: "In **Operations**, watch scam emails get stopped. In **Duel**, the learning attacker against the learning shield." },
      ] },
      { id: "chatgpt", icono: "chat", titulo: "I use ChatGPT", hace: "You add a connector", tiempo: "3 min", ancla: "2-uso-chatgpt", pasos: [
        { texto: "In ChatGPT web: **Settings → Apps → Advanced settings**, turn on **Developer mode**." },
        { texto: "Add an MCP server: name `Grifter`, authentication **No authentication**, and this URL:", codigo: "https://grifter.onrender.com/mcp" },
        { texto: "In a new chat, pick the connector and ask:", codigo: "Buy 10 SA-3NM microprocessors at the Silicio Austral store and pay the checkout" },
        { texto: "The toy store swaps the payout account and Grifter holds the payment. ChatGPT shows you why." },
      ] },
      { id: "claude", icono: "terminal", titulo: "I use Claude Desktop or Claude Code", hace: "You install Grifter on your computer", tiempo: "10 min", ancla: "3-uso-claude-desktop-o-claude-code", pasos: [
        { texto: "With Python 3.11 or newer and Git, get Grifter and install it:", codigo: `${CLONE}\npip install -e .` },
        { texto: "Copy the example config. Your registered accounts and the MCPs you want to protect go there:", codigo: "cp scamshield/mcp/grifter.ejemplo.yaml grifter.yaml" },
        { texto: "Connect it to Claude Code (for Claude Desktop, the block in [mcp.md](" + DOCS + "mcp.md#claude-desktop)):", codigo: "claude mcp add grifter -- python -m scamshield.mcp.proxy --config grifter.yaml" },
        { texto: "Try it: «Pay invoice 8812 from Silicio Austral». The test vendor carries a swapped account and Grifter holds the payment." },
        { texto: "Optional: alerts on your phone with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`." },
      ] },
      { id: "agente", icono: "code", titulo: "I build my own agent", hace: "You wrap your tools", tiempo: "5 min", ancla: "4-programo-mi-propio-agente", pasos: [
        { texto: "Install:", codigo: "pip install \"git+https://github.com/mgtapia/grifter\"" },
        { texto: "Wrap your Python functions, sync or `async`:", codigo: SHIELD },
        { texto: "What reads (email, web, MCP) is marked untrusted; what pays or shares data is checked before it runs. If Grifter holds it, the function does not run and the model gets the reason." },
      ] },
      { id: "banco", icono: "account_balance", titulo: "I am a bank, a wallet or a merchant", hace: "You put Grifter in front of your MCPs", tiempo: "1 day", ancla: "5-soy-un-banco-una-billetera-o-un-comercio", pasos: [
        { texto: "Install as for Claude and define your MCPs by URL in `grifter.yaml`. If your MCP does not answer, Grifter fails closed." },
        { texto: "Load each customer's registered accounts and the holders you know: payee confirmation turns on (layer 3)." },
        { texto: "Turn on dual authorization with TOTP: changing the policy needs two approvers ([mcp.md](" + DOCS + "mcp.md#doble-autorización-dos-personas-no-una))." },
        { texto: "Serve it over HTTP. For a test `GRIFTER_MCP_TOKEN` is enough; production needs OAuth 2.1, which is not done yet:", codigo: "python -m scamshield.mcp.proxy --config grifter.yaml --http --puerto 8766" },
        { texto: "Pick the alert channel: Telegram, WhatsApp (Kapso) or your own app, with the `avisar` hook." },
      ] },
      { id: "investigo", icono: "science", titulo: "I research agent security", hace: "You run the benchmark", tiempo: "5 min", ancla: "6-investigo-seguridad-de-agentes", pasos: [
        { texto: "Get Grifter with the dev dependencies:", codigo: `${CLONE}\npip install -e ".[dev,demo]"` },
        { texto: "The full benchmark, no API keys, in seconds:", codigo: "grifter bench" },
        { texto: "The tests, without calling any model:", codigo: "pytest" },
        { texto: "With real models and the adaptive attacker: the [README](" + REPO + "#benchmark-en-un-comando)." },
      ] },
    ],
  };

  // `código`, **negrita** y [enlace](url), sobre texto ya escapado.
  const enLinea = (s) => esc(s)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, txt, url) => `<a href="${url}" target="_blank" rel="noopener">${txt}</a>`)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  function paso(p) {
    const codigo = p.codigo ? `<div class="in-codigo"><pre><code>${esc(p.codigo)}</code></pre>
      <button type="button" class="boton icono texto" data-copiar="${esc(p.codigo)}" data-ayuda="${esc(t("in_copiar"))}" aria-label="${esc(t("in_copiar"))}">${ms("content_copy")}</button></div>` : "";
    return `<li><span class="in-texto">${enLinea(p.texto)}</span>${codigo}</li>`;
  }

  function pintar() {
    const caminos = CAMINOS[estado.idioma] || CAMINOS.es;
    $("#vista-instalar").innerHTML = `<p class="in-nota">${ms("shield")}<span>${esc(t("in_nota"))}</span>
        <a href="${REPO}/blob/main/docs/instalar.md" target="_blank" rel="noopener">${esc(t("in_guia"))}</a></p>
      ${caminos.map((c) => `<article class="in-camino" id="in-${c.id}">
        <header class="titulo">${ms(c.icono)}<h2>${esc(c.titulo)}</h2><span class="nota">${esc(c.tiempo)}</span></header>
        <p class="in-hace">${esc(c.hace)}</p>
        <ol class="in-pasos">${c.pasos.slice(0, 5).map(paso).join("")}</ol></article>`).join("")}`;
  }

  pintarTextos();
  return { pintar };
})();
window.Instalar = Instalar;
if (estado.vista === "instalar") Instalar.pintar();
