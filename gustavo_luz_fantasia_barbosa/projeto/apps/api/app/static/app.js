const state = {
  radarResults: [],
  startupSearchResults: [],
  repertoireResults: [],
  historyRows: [],
  demoResults: [],
  selectedStartup: null,
  health: null,
  lastAnalysis: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const THEME_STORAGE_KEY = "seraphim-scout-theme";
const STATIC_PREVIEW_HOSTS = ["localhost", "127.0.0.1", "::1"];
const API_BASE =
  !["http:", "https:"].includes(window.location.protocol)
  || (
    STATIC_PREVIEW_HOSTS.includes(window.location.hostname)
    && window.location.port
    && window.location.port !== "8000"
  )
  || (
    window.location.pathname.endsWith("/index.html")
    && window.location.port !== "8000"
  )
    ? "http://127.0.0.1:8000"
    : "";

const DEMO_SCENARIOS = [
  {
    id: "strong",
    title: "Startup forte",
    badge: "Fit alto",
    goal: "Mostrar playbook acionável, recomendação NVIDIA e timing de abordagem.",
    payload: {
      startup_name: "NeuralMed Brasil Demo",
      sector: "healthcare",
      description: "Startup brasileira usa IA generativa, LLM, dados clínicos e workflow médico para automatizar triagem e atendimento em produção no Brasil.",
      technical_gaps: [
        "latência de inferência",
        "governança de IA",
        "dependência de API externa",
      ],
    },
    what_to_show: [
      "Playbook NVIDIA com hipótese de valor",
      "Gate de evidências com recomendação sustentada",
      "Pergunta sobre custo, latência p95 ou fallback",
    ],
  },
  {
    id: "wrapper",
    title: "Risco wrapper",
    badge: "Risco competitivo",
    goal: "Mostrar risco de comoditização e caminho NVIDIA para sair de API externa.",
    payload: {
      startup_name: "ChatOps Wrapper Demo",
      sector: "customer service",
      description: "Startup brasileira oferece chatbot simples com interface sobre API externa de LLM para atendimento. Ainda não há sinais claros de dados proprietários ou workflow profundo.",
      technical_gaps: [
        "dependência de API externa",
        "custo de inferência",
        "governança de respostas",
      ],
    },
    what_to_show: [
      "Wrapper Risk Score alto",
      "Mapa de risco wrapper",
      "Caminho com NIM, Guardrails ou controle de produção",
    ],
  },
  {
    id: "weak",
    title: "Evidência fraca",
    badge: "Gate",
    goal: "Mostrar que o sistema sabe rebaixar ou bloquear conclusões fracas.",
    payload: {
      startup_name: "Empresa Pouco Clara Demo",
      sector: "desconhecido",
      description: "Empresa brasileira com plataforma digital para negócios.",
      technical_gaps: [],
    },
    what_to_show: [
      "Classificação baixa ou insuficiente",
      "Gate de qualidade de evidências rebaixando a decisão",
      "Contrafactual com o que não recomendar ainda",
    ],
  },
];

const TECH_SUMMARY_PT = {
  "NVIDIA Inception": "Programa para startups que constroem com IA e computação acelerada.",
  "NVIDIA NIM": "Microserviços de inferência otimizados para colocar modelos de IA em produção.",
  "NVIDIA NeMo": "Framework para desenvolver e customizar modelos de IA generativa.",
  "NeMo Guardrails": "Guardrails para controlar comportamento de IA conversacional e agentes.",
  "NVIDIA Triton Inference Server": "Servidor de inferência para modelos em diferentes frameworks.",
  "TensorRT-LLM": "Kit de otimização de inferência para grandes modelos de linguagem.",
  "NVIDIA RAPIDS": "Ciência de dados e analytics acelerados por GPU.",
  "cuDF": "Biblioteca de dataframes em GPU para acelerar cargas tabulares.",
  "cuML": "Biblioteca de machine learning clássico acelerada por GPU.",
  "CUDA": "Plataforma e toolkit de computação paralela para GPUs NVIDIA.",
  "NVIDIA Riva": "IA de voz para ASR, TTS e aplicações conversacionais.",
  "NVIDIA Omniverse": "Plataforma para simulação 3D, gêmeos digitais e workflows industriais.",
  "NVIDIA Clara": "IA e computação acelerada para saúde e ciências da vida.",
  "NVIDIA Morpheus": "Framework de cibersegurança com IA para detecção acelerada de ameaças.",
  "NVIDIA Isaac": "Stack para desenvolvimento, simulação e autonomia em robótica.",
  "NVIDIA AI Enterprise": "Plataforma empresarial para operar IA em produção sobre infraestrutura NVIDIA.",
  "NVIDIA API Catalog": "Catálogo de modelos, APIs, endpoints de inferência e blocos para agentes.",
  "NVIDIA AI Blueprints": "Workflows de referência e exemplos de código para criar aplicações de IA.",
  "NVIDIA Nemotron": "Modelos abertos da NVIDIA para raciocínio, código, agentes, segurança e IA multimodal.",
  "NVIDIA Dynamo": "Plataforma de inferência distribuída para servir IA em múltiplos nós.",
  "NVIDIA Cosmos": "Modelos de mundo e IA física para robótica, simulação e sistemas autônomos.",
  "NVIDIA cuOpt": "Otimização acelerada por GPU para rotas, logística, scheduling e planejamento.",
  "NVIDIA AI Workbench": "Ferramenta para gerenciar projetos de IA em ambientes locais, cloud e GPU.",
  "NVIDIA NGC": "Catálogo de containers, modelos, SDKs e Helm charts otimizados para GPU.",
};

function localizedTechSummary(productName, fallback = "") {
  return TECH_SUMMARY_PT[productName] || fallback;
}

function applyTheme(theme) {
  const normalizedTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = normalizedTheme;
  const toggle = $("#themeToggle");
  if (toggle) {
    const icon = toggle.querySelector(".theme-toggle-icon");
    const label = toggle.querySelector(".theme-toggle-text");
    if (icon) icon.textContent = normalizedTheme === "dark" ? "L" : "D";
    if (label) label.textContent = normalizedTheme === "dark" ? "Claro" : "Escuro";
    toggle.setAttribute(
      "aria-label",
      normalizedTheme === "dark" ? "Alternar para modo claro" : "Alternar para modo escuro",
    );
  }
}

function initTheme() {
  let storedTheme = null;
  try {
    storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    storedTheme = null;
  }
  applyTheme(storedTheme || "light");
}

function toggleTheme() {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  try {
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  } catch {
    // Keep theme switching usable even when storage is blocked.
  }
  applyTheme(nextTheme);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function isHttpUrl(value) {
  return typeof value === "string" && /^https?:\/\//i.test(value);
}

function formatStage(stage) {
  if (!stage) return "desconhecido";
  return String(stage).replaceAll("_", " ");
}

function formatCategory(category) {
  return String(category || "desconhecida").replaceAll("_", " ");
}

function fitBand(percent) {
  if (percent >= 75) return "alto";
  if (percent >= 55) return "medio";
  return "baixo";
}

function clippedText(value, maxLength = 180) {
  const text = String(value || "").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}...` : text;
}

function tooltipAttributes(title, lines) {
  return `
    data-fit-title="${escapeHtml(title)}"
    data-fit-lines="${escapeHtml(lines.join("||"))}"
  `;
}

function toolFitLines(tool) {
  const pct = Number(tool.fit_percent || 0);
  const band = fitBand(pct);
  const category = formatCategory(tool.category);
  const reason = clippedText(tool.reason || "", 190);
  const bandLine =
    band === "alto"
      ? "Por que está alto: a categoria e o motivo recuperado batem bem com o perfil e os gaps da startup."
      : band === "medio"
        ? "Por que está médio: existe aderência, mas ainda faltam sinais mais específicos ou evidências mais fortes."
        : "Por que está baixo: a ferramenta tem algum encaixe, mas o perfil traz poucos termos/gaps diretamente ligados a ela.";

  return [
    `FIT ${pct}% (${band}). Categoria: ${category}.`,
    bandLine,
    "Sobe quando o perfil menciona termos da categoria, problema técnico claro, setor aderente e sinais de IA/produção.",
    "Baixa quando a descrição é genérica, tem pouco contexto técnico ou a categoria fica distante do foco informado.",
    reason ? `Base: ${reason}` : "Base: categoria, sinais e overlap de termos do perfil.",
  ];
}

function renderToolFitBadge(tool, className = "tool-pct") {
  const pct = Number(tool.fit_percent || 0);
  return `
    <span class="${className} fit-tooltip" tabindex="0" aria-label="Detalhes do FIT ${pct}%" ${tooltipAttributes(`FIT de ${tool.technology || "tool"}`, toolFitLines(tool))}>
      <span>${pct}%</span>
    </span>
  `;
}

function nvidiaFitLines(item) {
  const fit = Number(item.nvidia_fit_score || 0);
  const ai = Number(item.ai_native_score || 0);
  const tools = item.top_tools?.length || 0;
  const risk = Number(item.wrapper_risk_score || 0);
  const band = fitBand(fit);
  return [
    `NVIDIA fit ${fit}/100 (${band}).`,
    `Base: AI-native ${ai}/100 + ${tools} ferramenta(s) NVIDIA com aderência.`,
    "Sobe quando há sinais de IA, inferência, dados, pipelines, produção, latência, governança ou otimização.",
    "Baixa quando há poucas recomendações NVIDIA, pouca profundidade técnica ou descrição vaga.",
    `Risco wrapper atual: ${risk}/100. Ele pesa mais na oportunidade geral do que neste fit.`,
  ];
}

function opportunityLines(item) {
  const opportunity = Number(item.opportunity_percent || 0);
  const ai = Number(item.ai_native_score || 0);
  const fit = Number(item.nvidia_fit_score || 0);
  const risk = Number(item.wrapper_risk_score || 0);
  const tools = item.top_tools || [];
  const averageToolFit = tools.length
    ? Math.round(tools.reduce((sum, tool) => sum + Number(tool.fit_percent || 0), 0) / tools.length)
    : 0;
  const signalCount = (item.signals || []).length;
  const signalScore = Math.min(100, 45 + signalCount * 7);
  const topToolNames = tools
    .slice(0, 3)
    .map((tool) => tool.technology)
    .filter(Boolean)
    .join(", ");
  return [
    `Resumo: ${opportunity}% mede o potencial de investigar essa startup para uso de tecnologia NVIDIA.`,
    `Fórmula curta: fit ${fit} x 45% + ferramentas ${averageToolFit} x 40% + sinais ${signalScore} x 15% - risco ${risk} x 12%.`,
    `Fit NVIDIA: encaixe com GPUs, inferência, dados, LLMs, visão ou otimização.`,
    `Ferramentas: ${tools.length} recomendação(ões)${topToolNames ? `, como ${topToolNames}` : "."}`,
    signalCount
      ? `Sinais públicos: ${(item.signals || []).slice(0, 3).join(", ")}.`
      : "Sem sinais públicos fortes nesta fonte.",
    `Risco wrapper: quanto maior, mais parece depender só de API externa. Clique para ver o resumo completo.`,
  ];
}

function opportunityExplainerValues(item) {
  const opportunity = Number(item.opportunity_percent || 0);
  const ai = Number(item.ai_native_score || 0);
  const fit = Number(item.nvidia_fit_score || 0);
  const risk = Number(item.wrapper_risk_score || 0);
  const tools = item.top_tools || [];
  const averageToolFit = tools.length
    ? Math.round(tools.reduce((sum, tool) => sum + Number(tool.fit_percent || 0), 0) / tools.length)
    : 0;
  const signalCount = (item.signals || []).length;
  const signalScore = Math.min(100, 45 + signalCount * 7);
  const topTools = tools
    .slice(0, 3)
    .map((tool) => tool.technology)
    .filter(Boolean);
  return {
    opportunity,
    ai,
    fit,
    risk,
    averageToolFit,
    signalCount,
    signalScore,
    topTools,
  };
}

function opportunityPlainSummary(item) {
  const values = opportunityExplainerValues(item);
  const band = fitBand(values.opportunity);
  const toolText = values.topTools.length ? values.topTools.join(", ") : "nenhuma ferramenta forte";
  return [
    `Resumo: ${values.opportunity}% é um potencial ${band} de conversa comercial/técnica com a NVIDIA.`,
    `A conta favorece startups com bom encaixe NVIDIA, ferramentas recomendadas fortes e sinais públicos de uso real de IA.`,
    `Nesta startup: fit NVIDIA ${values.fit}/100, média das ferramentas ${values.averageToolFit}/100, sinais ${values.signalScore}/100 e risco wrapper ${values.risk}/100.`,
    `Ferramentas que mais puxam o score: ${toolText}.`,
  ];
}

function opportunityExplainerHtml(item) {
  const values = opportunityExplainerValues(item);
  const toolText = values.topTools.length ? values.topTools.join(", ") : "sem ferramenta principal forte";
  return `
    <div class="score-explainer-top">
      <div>
        <span class="score-explainer-eyebrow">Oportunidade NVIDIA</span>
        <h2>${values.opportunity}% para ${escapeHtml(item.startup_name || "esta startup")}</h2>
      </div>
      <button class="score-explainer-close" type="button" aria-label="Fechar explicação">x</button>
    </div>
    <p class="score-explainer-lead">
      Em linguagem simples: esse número estima o quanto vale investigar essa startup como oportunidade para aplicar tecnologia NVIDIA.
    </p>
    <div class="score-explainer-formula">
      <strong>Fórmula resumida</strong>
      <code>fit NVIDIA x 45% + fit das ferramentas x 40% + sinais públicos x 15% - risco wrapper x 12%</code>
    </div>
    <div class="score-explainer-grid">
      <div>
        <strong>Fit NVIDIA</strong>
        <span>${values.fit}/100</span>
        <p>Quanto o problema da startup combina com GPUs, inferência, dados, LLMs, visão, otimização ou ferramentas NVIDIA.</p>
      </div>
      <div>
        <strong>Ferramentas</strong>
        <span>${values.averageToolFit}/100</span>
        <p>Média do encaixe das ferramentas recomendadas. Principais: ${escapeHtml(toolText)}.</p>
      </div>
      <div>
        <strong>Sinais públicos</strong>
        <span>${values.signalScore}/100</span>
        <p>Pistas encontradas sobre IA, produto, setor, maturidade técnica e uso em produção.</p>
      </div>
      <div>
        <strong>Risco wrapper</strong>
        <span>${values.risk}/100</span>
        <p>Quanto parece depender só de uma API externa. Quanto maior, mais o score cai.</p>
      </div>
    </div>
    <div class="score-explainer-summary">
      <strong>Leitura rápida</strong>
      <p>${escapeHtml(opportunityPlainSummary(item)[0])}</p>
      <p>${escapeHtml(clippedText(item.evidence_summary || "Sem resumo de evidência disponível.", 180))}</p>
    </div>
  `;
}

function ensureScoreExplainer() {
  let backdrop = $(".score-explainer-backdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "score-explainer-backdrop hidden";
    backdrop.innerHTML = `
      <section class="score-explainer" role="dialog" aria-modal="true" aria-label="Explicação da porcentagem"></section>
    `;
    document.body.appendChild(backdrop);
  }
  return backdrop;
}

function openOpportunityExplainer(item) {
  const backdrop = ensureScoreExplainer();
  const panel = backdrop.querySelector(".score-explainer");
  panel.innerHTML = opportunityExplainerHtml(item);
  backdrop.classList.remove("hidden");
  panel.querySelector(".score-explainer-close")?.focus();
  hideFitTooltip();
}

function closeOpportunityExplainer() {
  $(".score-explainer-backdrop")?.classList.add("hidden");
}

let activeFitTooltipTarget = null;
let fitTooltipElement = null;

function ensureFitTooltip() {
  if (!fitTooltipElement) {
    fitTooltipElement = document.createElement("div");
    fitTooltipElement.className = "fit-floating-tooltip";
    fitTooltipElement.setAttribute("role", "tooltip");
    document.body.appendChild(fitTooltipElement);
  }
  return fitTooltipElement;
}

function positionFitTooltip(target) {
  const tooltip = ensureFitTooltip();
  const rect = target.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  const width = tooltipRect.width || 320;
  const height = tooltipRect.height || 120;
  const left = Math.min(
    window.innerWidth - width - 12,
    Math.max(12, rect.left + rect.width / 2 - width / 2),
  );
  const shouldOpenAbove = rect.bottom + height + 14 > window.innerHeight;
  const top = shouldOpenAbove
    ? Math.max(12, rect.top - height - 10)
    : rect.bottom + 10;

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function showFitTooltip(target) {
  const title = target.dataset.fitTitle;
  const lines = (target.dataset.fitLines || "").split("||").filter(Boolean);
  if (!title || lines.length === 0) return;

  const tooltip = ensureFitTooltip();
  tooltip.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    ${lines.map((line) => `<span>${escapeHtml(line)}</span>`).join("")}
  `;
  activeFitTooltipTarget = target;
  tooltip.classList.add("show");
  positionFitTooltip(target);
}

function hideFitTooltip(target) {
  if (target && activeFitTooltipTarget !== target) return;
  activeFitTooltipTarget = null;
  fitTooltipElement?.classList.remove("show");
}

function handleFitTooltipPointer(event) {
  const target = event.target.closest(".fit-tooltip");
  if (!target) return;
  showFitTooltip(target);
}

function handleFitTooltipLeave(event) {
  const target = event.target.closest(".fit-tooltip");
  if (!target) return;
  if (event.relatedTarget && target.contains(event.relatedTarget)) return;
  hideFitTooltip(target);
}

function handleFitTooltipReposition() {
  if (activeFitTooltipTarget) {
    positionFitTooltip(activeFitTooltipTarget);
  }
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3200);
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (error) {
    const target = API_BASE || "o mesmo servidor da pagina";
    throw new Error(`não consegui conectar na API (${target}). Abra http://127.0.0.1:8000/ ou confirme que o servidor FastAPI está rodando.`);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function setLoading(button, isLoading, label = "Carregando") {
  if (!button) return;
  button.disabled = isLoading;
  button.dataset.defaultText = button.dataset.defaultText || button.textContent;
  button.textContent = isLoading ? label : button.dataset.defaultText;
}

function navigate(view) {
  $$(".view").forEach((element) => element.classList.remove("active"));
  $(`#view-${view}`)?.classList.add("active");
  $$(".nav-item").forEach((element) => {
    element.classList.toggle("active", element.dataset.view === view);
  });
}

function setStatusDot(id, ok, warn = false) {
  const dot = $(id);
  if (!dot) return;
  dot.classList.toggle("ok", ok);
  dot.classList.toggle("err", !ok && !warn);
  dot.classList.toggle("warn", warn);
}

function setText(selector, value) {
  const element = $(selector);
  if (element) element.textContent = value;
}

async function checkHealth() {
  try {
    const health = await api("/health");
    state.health = health;
    const apiOk = health.status === "ok";
    const qdrantStatus = health.qdrant?.status || "desconhecido";
    const qdrantOk = qdrantStatus === "ok";
    const postgresStatus = health.postgres?.status || "n/a";
    const postgresOk = postgresStatus === "ok";
    const postgresWarn = ["not_configured", "disabled", "n/a"].includes(postgresStatus);
    setText("#statusApi", apiOk ? "ok" : "degradado");
    setText("#statusQdrant", qdrantStatus);
    setText("#statusPostgres", postgresStatus);
    setText("#startupSourcePill", `Fonte startups: ${health.startup_source?.source || "desconhecida"}`);
    setText("#scApi", apiOk ? "ok" : "degradado");
    setText("#scQdrant", qdrantStatus);
    setText("#scPostgres", postgresStatus);
    setStatusDot("#dotApi", apiOk, !apiOk);
    setStatusDot("#dotQdrant", qdrantOk, !qdrantOk);
    setStatusDot("#dotPostgres", postgresOk, postgresWarn);
    return health;
  } catch (error) {
    setText("#statusApi", "fora do ar");
    setText("#statusQdrant", "--");
    setText("#statusPostgres", "--");
    setText("#scApi", "fora do ar");
    setText("#scQdrant", "--");
    setText("#scPostgres", "--");
    setStatusDot("#dotApi", false);
    setStatusDot("#dotQdrant", false, true);
    setStatusDot("#dotPostgres", false, true);
    throw error;
  }
}

function linkButton(url, label) {
  if (!isHttpUrl(url)) return "";
  return `<a class="link-button" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
}

function downloadTextFile(filename, content, mimeType = "text/markdown;charset=utf-8") {
  const blob = new Blob([content || ""], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function renderStructuredProfileGroup(title, items) {
  const cleanItems = (items || []).filter((item) => item?.value);
  if (!cleanItems.length) {
    return "";
  }
  return `
    <section class="profile-group">
      <h3>${escapeHtml(title)}</h3>
      <div class="profile-items">
        ${cleanItems
          .slice(0, 4)
          .map((item) => {
            const source = item.source_url && item.source_url !== "manual_context"
              ? linkButton(item.source_url, "Fonte")
              : "<span class='badge'>Manual</span>";
            return `
              <article class="profile-item">
                <div class="profile-item-top">
                  <strong>${escapeHtml(item.value)}</strong>
                  <span class="badge green">${Number(item.confidence || 0).toFixed(2)}</span>
                </div>
                <p>${escapeHtml(item.evidence || "")}</p>
                <div class="profile-source">${source}</div>
              </article>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderStructuredProfile(profile) {
  if (!profile) return "";
  const sections = [
    renderStructuredProfileGroup("Fundadores e liderança", profile.founders),
    renderStructuredProfileGroup("Funding", profile.funding),
    renderStructuredProfileGroup("Clientes e casos", profile.customers),
    renderStructuredProfileGroup("Tecnologias", profile.technologies),
    renderStructuredProfileGroup("Sinais de IA", profile.ai_signals),
  ].filter(Boolean);
  if (!sections.length) {
    return "";
  }
  return `
    <div class="structured-profile">
      <div class="structured-profile-header">
        <span>Perfil estruturado</span>
        <span class="badge blue">${sections.length} grupos</span>
      </div>
      ${sections.join("")}
    </div>
  `;
}

function renderRecommendationSummary(recommendations) {
  const items = (recommendations || []).filter((item) => item?.technology);
  if (!items.length) {
    return "";
  }
  return `
    <div class="recommendation-summary">
      <div class="structured-profile-header">
        <span>Recomendações NVIDIA</span>
        <span class="badge blue">${items.length} itens</span>
      </div>
      <div class="recommendation-items">
        ${items
          .slice(0, 5)
          .map(
            (item) => `
              <article class="recommendation-item">
                <div class="profile-item-top">
                  <strong>${escapeHtml(item.technology)}</strong>
                  <span class="badge green">${escapeHtml(item.priority || "média")}</span>
                </div>
                <div class="recommendation-meta">
                  <span>${escapeHtml(item.category || "desconhecida")}</span>
                  <span>Complexidade: ${escapeHtml(item.implementation_complexity || "média")}</span>
                  <span>Score ${Number(item.retrieval_score || 0).toFixed(3)}</span>
                </div>
                <p>${escapeHtml(item.next_action || "Validar aderência técnica com a startup.")}</p>
                ${linkButton(item.source_url, "Fonte NVIDIA")}
              </article>
            `,
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderSearchPlan(plan) {
  if (!plan) return "";
  const terms = (plan.search_terms || [])
    .slice(0, 8)
    .map((term) => `<span class="badge green">${escapeHtml(term)}</span>`)
    .join("");
  const sources = (plan.source_priorities || [])
    .slice(0, 6)
    .map((source) => `<span>${escapeHtml(source)}</span>`)
    .join("");
  const targets = (plan.evidence_targets || [])
    .slice(0, 8)
    .map((target) => `<span class="badge">${escapeHtml(target)}</span>`)
    .join("");
  return `
    <div class="search-plan">
      <div class="structured-profile-header">
        <span>Plano de busca</span>
        <span class="badge blue">${escapeHtml(plan.version || "search_plan_v1")}</span>
      </div>
      <p>${escapeHtml(plan.query || "")}</p>
      <div class="signals compact">${terms}</div>
      <div class="search-plan-row"><strong>Fontes</strong><div>${sources}</div></div>
      <div class="search-plan-row"><strong>Evidências</strong><div>${targets}</div></div>
    </div>
  `;
}

function timingFromScores(values) {
  const opportunity = Number(values.opportunity_percent || values.opportunity || 0);
  const fit = Number(values.nvidia_fit_score || values.fit || 0);
  const risk = Number(values.wrapper_risk_score || values.risk || 0);
  const recs = (values.recommendations || values.top_tools || []).length;
  const signals = (values.signals || []).length;
  const coverage = Number(values.quality_metrics?.evidence_coverage_percent || 0);
  if (
    values.approach_timing
    && ["quente", "morno", "exploratorio"].includes(values.approach_timing)
  ) {
    return values.approach_timing;
  }
  if ((opportunity >= 72 || fit >= 80) && recs >= 2 && (signals >= 2 || coverage >= 60) && risk < 65) {
    return "quente";
  }
  if ((opportunity >= 52 || fit >= 60) && recs >= 1) {
    return "morno";
  }
  return "exploratorio";
}

function timingBadgeClass(timing) {
  if (timing === "quente") return "green";
  if (timing === "morno") return "amber";
  return "blue";
}

function primaryRecommendation(result) {
  return (result.recommendations || result.top_tools || []).find(
    (item) => item?.technology,
  );
}

function mainGap(result) {
  return (result.detected_gaps || result.technical_gaps || result.signals || [])[0]
    || "principal gargalo técnico";
}

function recommendationCategory(item) {
  return String(item?.category || "").toLowerCase();
}

function discoveryQuestionForCategory(category) {
  if (category === "model_deployment") {
    return "Qual é hoje o custo por inferência, a latência p95 e o plano de fallback quando o provedor externo falha?";
  }
  if (["data_processing", "data_science"].includes(category)) {
    return "Qual pipeline de dados mais limita experimentação, custo ou tempo de entrega do produto?";
  }
  if (category === "optimization") {
    return "Qual decisão operacional poderia ser otimizada com dados reais de rotas, scheduling, alocação ou planejamento?";
  }
  if (["speech_ai", "conversational_ai"].includes(category)) {
    return "Quais métricas de voz ou atendimento mais pesam hoje: qualidade, latência, custo, privacidade ou escala?";
  }
  return "Qual métrica técnica, se melhorasse nos próximos 30 dias, teria maior impacto no produto ou na margem?";
}

function competitiveRiskText(score) {
  if (score >= 65) {
    return "Alto risco de comoditização por dependência de APIs externas. A abordagem deve enfatizar controle, custo, latência e independência.";
  }
  if (score >= 40) {
    return "Risco intermediário. Vale validar se há dados proprietários, workflow profundo e barreiras técnicas reais.";
  }
  return "Risco wrapper baixo. A conversa pode focar escala, confiabilidade, governança e aceleração do roadmap técnico.";
}

function angelThesis(result) {
  const timing = timingFromScores(result);
  const fit = Number(result.nvidia_fit_score || 0);
  const ai = Number(result.ai_native_score || 0);
  const risk = Number(result.wrapper_risk_score || 0);
  const coverage = Number(result.quality_metrics?.evidence_coverage_percent || result.source_confidence || 0);
  const top = primaryRecommendation(result);
  const technology = top?.technology || "stack NVIDIA";
  const signals = (result.signals || result.detected_gaps || []).filter(Boolean);
  const firstSignal = signals[0] || "sinais publicos ainda limitados";
  const secondSignal = signals[1] || mainGap(result);

  if (coverage < 35 && fit < 55) {
    return {
      badge: "blue",
      title: "Tese exploratória",
      summary: "O scout encontrou uma possibilidade, mas ainda falta lastro para tratar como oportunidade quente.",
      evidence: `Sinais iniciais: ${firstSignal}. Próximo passo é confirmar maturidade AI-native e contexto técnico.`,
      validation: "Antes de abordar, coletar fonte pública melhor, caso de uso real e dor técnica mensurável.",
    };
  }

  if (risk >= 65) {
    return {
      badge: "amber",
      title: "Tese de transformação",
      summary: "A oportunidade está menos em vender uma ferramenta isolada e mais em ajudar a startup a sair de dependência wrapper.",
      evidence: `Sinais: ${firstSignal}; ${secondSignal}. Tecnologia candidata: ${technology}.`,
      validation: "Validar dependência de API externa, custo por inferência, latência p95 e existência de dados proprietários.",
    };
  }

  if ((timing === "quente" || fit >= 75) && ai >= 55) {
    return {
      badge: "green",
      title: "Tese angel-ready",
      summary: "A startup combina sinais de IA, timing de abordagem e fit técnico suficiente para uma conversa prioritária.",
      evidence: `Sinais: ${firstSignal}; ${secondSignal}. Melhor gancho NVIDIA: ${technology}.`,
      validation: "Abrir conversa com uma pergunta técnica objetiva e propor piloto pequeno com métrica de sucesso.",
    };
  }

  return {
    badge: "blue",
    title: "Tese em validação",
    summary: "Existe fit técnico, mas a prioridade depende de confirmar intensidade de uso de IA e dor de produção.",
    evidence: `Sinais: ${firstSignal}; ${secondSignal}. Possível caminho: ${technology}.`,
    validation: "Validar urgência, escala, budget técnico e se o problema é relevante para o roadmap da startup.",
  };
}

function renderAngelThesis(result) {
  const thesis = angelThesis(result);
  return `
    <section class="decision-panel angel-thesis">
      <div class="decision-header">
        <div>
          <span class="decision-kicker">Angel Thesis</span>
          <h3>${escapeHtml(thesis.title)}</h3>
        </div>
        <span class="badge ${thesis.badge}">Scout</span>
      </div>
      <div class="decision-grid">
        <div class="wide">
          <strong>Leitura do scout</strong>
          <p>${escapeHtml(thesis.summary)}</p>
        </div>
        <div>
          <strong>Sinais que sustentam</strong>
          <p>${escapeHtml(thesis.evidence)}</p>
        </div>
        <div>
          <strong>Primeira validação</strong>
          <p>${escapeHtml(thesis.validation)}</p>
        </div>
      </div>
    </section>
  `;
}

function renderApproachPlaybook(result) {
  const timing = timingFromScores(result);
  const top = primaryRecommendation(result);
  const technology = top?.technology || "tecnologia NVIDIA a validar";
  const gap = mainGap(result);
  const risk = Number(result.wrapper_risk_score || 0);
  return `
    <section class="decision-panel">
      <div class="decision-header">
        <div>
          <span class="decision-kicker">Playbook NVIDIA</span>
          <h3>Abordagem ${escapeHtml(timing)}</h3>
        </div>
        <span class="badge ${timingBadgeClass(timing)}">${escapeHtml(timing)}</span>
      </div>
      <div class="decision-grid">
        <div>
          <strong>Hipótese de valor</strong>
          <p>Conectar ${escapeHtml(technology)} ao gap "${escapeHtml(gap)}" com um piloto pequeno e mensurável.</p>
        </div>
        <div>
          <strong>Risco competitivo</strong>
          <p>${escapeHtml(competitiveRiskText(risk))}</p>
        </div>
        <div class="wide">
          <strong>Pergunta de descoberta</strong>
          <p>${escapeHtml(discoveryQuestionForCategory(recommendationCategory(top)))}</p>
        </div>
      </div>
    </section>
  `;
}

function evidenceGateStatus(result) {
  const checks = result.evidence_checks || [];
  const recommendationChecks = checks.filter((check) => check.claim_type === "recommendation");
  const blocked = recommendationChecks.filter((check) => check.blocks_recommendation);
  const grounded = recommendationChecks.filter((check) => !check.blocks_recommendation);
  if (recommendationChecks.length && blocked.length === recommendationChecks.length) {
    return { label: "bloqueada", badge: "red", blocked, grounded, recommendationChecks };
  }
  if (blocked.length || Number(result.quality_metrics?.evidence_coverage_percent || 0) < 50) {
    return { label: "rebaixada", badge: "amber", blocked, grounded, recommendationChecks };
  }
  return { label: "aceita", badge: "green", blocked, grounded, recommendationChecks };
}

function renderEvidenceQualityGate(result) {
  const status = evidenceGateStatus(result);
  const metrics = result.quality_metrics || {};
  const sampleChecks = (result.evidence_checks || [])
    .filter((check) => check.claim_type === "recommendation" || check.blocks_recommendation)
    .slice(0, 4);
  return `
    <section class="decision-panel">
      <div class="decision-header">
        <div>
          <span class="decision-kicker">Gate de Qualidade de Evidências</span>
          <h3>Recomendação ${escapeHtml(status.label)}</h3>
        </div>
        <span class="badge ${status.badge}">${escapeHtml(status.label)}</span>
      </div>
      <div class="metric-row">
        <div><span>Fontes</span><strong>${Number(metrics.public_source_pages || result.source_pages?.length || 0)}</strong></div>
        <div><span>Lastro</span><strong>${Number(metrics.recommendation_groundedness_percent || 0)}%</strong></div>
        <div><span>Bloqueios</span><strong>${Number(metrics.blocked_evidence_checks || status.blocked.length || 0)}</strong></div>
      </div>
      <div class="gate-list">
        ${sampleChecks.length
          ? sampleChecks.map((check) => `
              <div class="gate-item ${check.blocks_recommendation ? "blocked" : "ok"}">
                <strong>${escapeHtml(check.blocks_recommendation ? "Bloqueio" : "Lastro")}</strong>
                <p>${escapeHtml(check.blocking_reason || check.note || check.claim || "")}</p>
              </div>
            `).join("")
          : "<p class='muted-copy'>Sem checks detalhados nesta execução.</p>"
        }
      </div>
    </section>
  `;
}

function wrapperRiskFactors(result) {
  const factors = [];
  const risk = Number(result.wrapper_risk_score || 0);
  const text = [
    result.classification,
    result.evidence_summary,
    result.briefing_markdown,
    ...(result.detected_gaps || []),
    ...(result.signals || []),
  ].join(" ").toLowerCase();
  if (risk >= 60 || text.includes("wrapper")) factors.push("Produto pode depender demais de uma camada fina sobre API externa.");
  if (text.includes("chatbot") || text.includes("interface")) factors.push("Descrição sugere interface conversacional ou camada de produto fácil de copiar.");
  if (!text.includes("dados propriet") && !text.includes("proprietary data")) factors.push("Ainda faltam sinais claros de dados proprietários.");
  if (!text.includes("workflow")) factors.push("Ainda faltam sinais de workflow operacional profundo.");
  if (text.includes("latencia") || text.includes("latência") || text.includes("inferencia") || text.includes("inferência")) factors.push("Há dor de produção onde NVIDIA pode ajudar com controle de inferência.");
  return factors.slice(0, 4);
}

function renderWrapperDisplacementMap(result) {
  const risk = Number(result.wrapper_risk_score || 0);
  const band = risk >= 65 ? "alto" : risk >= 40 ? "medio" : "baixo";
  const factors = wrapperRiskFactors(result);
  return `
    <section class="decision-panel">
      <div class="decision-header">
        <div>
          <span class="decision-kicker">Mapa de Risco Wrapper</span>
          <h3>Risco ${escapeHtml(band)} de comoditização</h3>
        </div>
        <span class="badge ${risk >= 65 ? "red" : risk >= 40 ? "amber" : "green"}">${risk}/100</span>
      </div>
      <div class="risk-path">
        <div>
          <strong>Sinais de risco</strong>
          <ul>${factors.map((factor) => `<li>${escapeHtml(factor)}</li>`).join("") || "<li>Sem sinais fortes de wrapper no contexto atual.</li>"}</ul>
        </div>
        <div>
          <strong>Caminho NVIDIA</strong>
          <ul>
            <li>Medir custo, latência e dependência de API externa.</li>
            <li>Testar a tecnologia recomendada em um fluxo pequeno.</li>
            <li>Adicionar governança, observabilidade e controle de produção.</li>
          </ul>
        </div>
      </div>
    </section>
  `;
}

function counterfactualItems(result) {
  const profileText = [
    result.evidence_summary,
    result.briefing_markdown,
    ...(result.detected_gaps || []),
    ...(result.signals || []),
  ].join(" ").toLowerCase();
  const categories = new Set((result.recommendations || result.top_tools || []).map((item) => item.category));
  const items = [];
  if (!categories.has("digital_twins") && !profileText.match(/3d|digital twin|simul|omniverse/)) {
    items.push("Não priorizar Omniverse agora: não há evidência de 3D, simulação ou digital twin.");
  }
  if (!categories.has("speech_ai") && !profileText.match(/voz|speech|audio|call center|transcri/)) {
    items.push("Não priorizar Riva agora: faltam sinais de voz, áudio ou atendimento falado.");
  }
  if (!categories.has("optimization") && !profileText.match(/rota|routing|scheduling|otimiz/)) {
    items.push("Não priorizar cuOpt ainda: não há problema operacional claro de rotas, scheduling ou alocação.");
  }
  if (!categories.has("data_processing") && !profileText.match(/etl|dataframe|analytics|dados em larga escala/)) {
    items.push("Não priorizar RAPIDS antes de confirmar volume de dados ou gargalo de pipeline.");
  }
  return items.slice(0, 3);
}

function renderCounterfactuals(result) {
  const items = counterfactualItems(result);
  return `
    <section class="decision-panel">
      <div class="decision-header">
        <div>
          <span class="decision-kicker">Contrafactual</span>
          <h3>O que não recomendar ainda</h3>
        </div>
        <span class="badge blue">${items.length || 0} checks</span>
      </div>
      <div class="counterfactual-list">
        ${items.length
          ? items.map((item) => `<p>${escapeHtml(item)}</p>`).join("")
          : "<p>Sem contraindicações fortes a partir dos sinais atuais.</p>"
        }
      </div>
    </section>
  `;
}

function demoPayload(scenario) {
  return {
    startup_name: scenario.payload.startup_name,
    website_url: scenario.payload.website_url || null,
    sector: scenario.payload.sector || null,
    description: scenario.payload.description || null,
    technical_gaps: scenario.payload.technical_gaps || [],
  };
}

function fillManualFormFromScenario(scenario) {
  $("#startupName").value = scenario.payload.startup_name || "";
  $("#websiteUrl").value = scenario.payload.website_url || "";
  $("#sector").value = scenario.payload.sector || "";
  $("#technicalGaps").value = (scenario.payload.technical_gaps || []).join(", ");
  $("#description").value = scenario.payload.description || "";
}

function renderDemoScenarios() {
  const container = $("#demoScenarios");
  if (!container) return;
  container.innerHTML = DEMO_SCENARIOS.map(
    (scenario, index) => `
      <article class="demo-card">
        <div class="demo-card-top">
          <div>
            <span class="decision-kicker">Cenário ${index + 1}</span>
            <h2>${escapeHtml(scenario.title)}</h2>
          </div>
          <span class="badge blue">${escapeHtml(scenario.badge)}</span>
        </div>
        <p>${escapeHtml(scenario.goal)}</p>
        <div class="demo-payload">
          <strong>${escapeHtml(scenario.payload.startup_name)}</strong>
          <span>${escapeHtml(scenario.payload.sector || "setor não informado")}</span>
        </div>
        <ul>
          ${scenario.what_to_show.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
        <div class="result-actions">
          <button class="secondary-button small-action" type="button" data-demo-action="load" data-demo-index="${index}">Carregar no formulário</button>
          <button class="primary-button small-action" type="button" data-demo-action="run" data-demo-index="${index}">Rodar cenário</button>
        </div>
      </article>
    `,
  ).join("");
}

function renderDemoResults() {
  const results = state.demoResults || [];
  $("#demoResultCount").textContent = `${results.length} execuções`;
  $("#demoEmpty").classList.toggle("hidden", results.length > 0);
  $("#demoResults").innerHTML = results.map((entry) => {
    const result = entry.result;
    const status = evidenceGateStatus(result);
    const timing = timingFromScores(result);
    const top = primaryRecommendation(result);
    return `
      <article class="demo-result-item">
        <div class="demo-result-top">
          <div>
            <strong>${escapeHtml(entry.scenario.title)}</strong>
            <span>${escapeHtml(result.startup_name || entry.scenario.payload.startup_name)}</span>
          </div>
          <span class="badge ${timingBadgeClass(timing)}">${escapeHtml(timing)}</span>
        </div>
        <div class="history-score-grid compact-scores">
          <div><span>AI-native</span><strong>${Number(result.ai_native_score || 0)}</strong></div>
          <div><span>NVIDIA fit</span><strong>${Number(result.nvidia_fit_score || 0)}</strong></div>
          <div><span>Risco wrapper</span><strong>${Number(result.wrapper_risk_score || 0)}</strong></div>
          <div><span>Gate</span><strong>${escapeHtml(status.label)}</strong></div>
        </div>
        <p>${escapeHtml(top?.next_action || "Coletar mais evidências antes de recomendar uma abordagem técnica forte.")}</p>
      </article>
    `;
  }).join("");
}

async function runDemoScenario(index, button = null) {
  const scenario = DEMO_SCENARIOS[index];
  if (!scenario) return null;
  if (button) setLoading(button, true, "Rodando");
  try {
    const result = await api("/analysis/startup", {
      method: "POST",
      body: JSON.stringify(demoPayload(scenario)),
    });
    state.demoResults = [
      ...state.demoResults.filter((entry) => entry.scenario.id !== scenario.id),
      { scenario, result },
    ];
    renderDemoResults();
    renderManualAnalysisResult(result);
    await loadHistory();
    showToast(`Demo concluída: ${scenario.title}.`);
    return result;
  } catch (error) {
    showToast(`Falha no cenário ${scenario.title}: ${error.message}`);
    return null;
  } finally {
    if (button) setLoading(button, false);
  }
}

async function runDemoSequence(event) {
  const button = event?.target?.closest("button") || $("#runDemoSequenceButton");
  state.demoResults = [];
  renderDemoResults();
  setLoading(button, true, "Rodando demo");
  try {
    for (let index = 0; index < DEMO_SCENARIOS.length; index += 1) {
      await runDemoScenario(index);
    }
    navigate("demo");
    showToast("Demo completa executada.");
  } finally {
    setLoading(button, false);
  }
}

function handleDemoClick(event) {
  const button = event.target.closest("[data-demo-action]");
  if (!button) return;
  const scenario = DEMO_SCENARIOS[Number(button.dataset.demoIndex)];
  if (!scenario) return;
  if (button.dataset.demoAction === "load") {
    fillManualFormFromScenario(scenario);
    navigate("analysis");
    showToast(`Formulário carregado: ${scenario.title}.`);
  }
  if (button.dataset.demoAction === "run") {
    runDemoScenario(Number(button.dataset.demoIndex), button);
  }
}

function renderManualAnalysisResult(result) {
  state.lastAnalysis = result;
  const runId = result.analysis_run_id || "";
  const filename = `${String(result.startup_name || "briefing").replace(/\s+/g, "_")}_briefing.md`;
  const searchPlan = renderSearchPlan(result.search_plan);
  const structuredProfile = renderStructuredProfile(result.structured_profile);
  const recommendationSummary = renderRecommendationSummary(result.recommendations);
  const angelThesisPanel = renderAngelThesis(result);
  const approachPlaybook = renderApproachPlaybook(result);
  const evidenceGate = renderEvidenceQualityGate(result);
  const wrapperMap = renderWrapperDisplacementMap(result);
  const counterfactuals = renderCounterfactuals(result);
  const persistedDownload = runId
    ? `
      <a class="secondary-button small-action" href="${API_BASE}/analysis/runs/${escapeHtml(runId)}/briefing.md">Baixar .md salvo</a>
      <a class="secondary-button small-action" href="${API_BASE}/analysis/runs/${escapeHtml(runId)}/briefing.pdf">Baixar PDF</a>
    `
    : "";
  $("#manualResult").classList.remove("hidden");
  $("#manualResult").innerHTML = `
    <strong>${escapeHtml(result.startup_name)}</strong><br />
    Classificação: ${escapeHtml(result.classification)}<br />
    NVIDIA fit: ${Number(result.nvidia_fit_score || 0)}<br />
    ID da análise: ${escapeHtml(runId || "não salvo")}
    <div class="decision-stack">
      ${angelThesisPanel}
      ${approachPlaybook}
      ${evidenceGate}
      ${wrapperMap}
      ${counterfactuals}
    </div>
    ${searchPlan}
    ${structuredProfile}
    ${recommendationSummary}
    <div class="result-actions">
      <button class="secondary-button small-action" type="button" data-action="copy-briefing">Copiar briefing</button>
      <button class="secondary-button small-action" type="button" data-action="download-current-briefing" data-filename="${escapeHtml(filename)}">Baixar .md atual</button>
      ${persistedDownload}
    </div>
  `;
}

function toolRow(tool) {
  const name = escapeHtml(tool.technology);
  const pct = Number(tool.fit_percent || 0);
  const source = isHttpUrl(tool.source_url)
    ? `<a href="${escapeHtml(tool.source_url)}" target="_blank" rel="noreferrer">${name}</a>`
    : `<span>${name}</span>`;
  return `
    <div class="tool-row">
      ${source}
      <div class="bar"><span style="width:${pct}%"></span></div>
      ${renderToolFitBadge(tool)}
    </div>
  `;
}

function renderSourceEvidenceCard(source) {
  const label = source.label || "Fonte";
  const host = source.host || "";
  const detail = source.detail || "";
  return `
    <article class="source-evidence-card">
      <div>
        <strong>${escapeHtml(label)}</strong>
        <span>${escapeHtml(host)}</span>
      </div>
      <p>${escapeHtml(detail)}</p>
      ${isHttpUrl(source.url) ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">Abrir fonte</a>` : ""}
    </article>
  `;
}

function renderNvidiaCitation(tool) {
  const summary = localizedTechSummary(tool.technology, tool.reason || "");
  return `
    <article class="nvidia-citation-card">
      <div class="result-item-title">
        <span>${escapeHtml(tool.technology)}</span>
        ${renderToolFitBadge(tool, "badge green fit-badge")}
      </div>
      <p>${escapeHtml(summary)}</p>
      <div class="citation-meta">
        <span>${escapeHtml(formatCategory(tool.category))}</span>
        <span>${escapeHtml(clippedText(tool.reason || "Recomendação gerada pelo fit entre perfil da startup e base NVIDIA.", 120))}</span>
      </div>
      ${isHttpUrl(tool.source_url) ? `<a class="link-button citation-source" href="${escapeHtml(tool.source_url)}" target="_blank" rel="noreferrer">Fonte NVIDIA</a>` : ""}
    </article>
  `;
}

function renderStartupCard(item, index) {
  const signals = (item.signals || [])
    .slice(0, 6)
    .map((signal) => `<span class="badge green">${escapeHtml(signal)}</span>`)
    .join("");
  const summarySignals = (item.signals || [])
    .slice(0, 3)
    .map((signal) => `<span class="badge green">${escapeHtml(signal)}</span>`)
    .join("");
  const tools = (item.top_tools || []).map(toolRow).join("");
  const links = [
    linkButton(item.website_url, "Site"),
    linkButton(item.github_url, "GitHub"),
    linkButton(item.source_url, "Fonte"),
  ]
    .filter(Boolean)
    .join("");
  const linkFallback = links || `<span class="badge">${escapeHtml(item.source || "fonte indisponível")}</span>`;
  const ai = Number(item.ai_native_score || 0);
  const fit = Number(item.nvidia_fit_score || 0);
  const risk = Number(item.wrapper_risk_score || 0);
  const opportunity = Number(item.opportunity_percent || 0);
  const timing = timingFromScores(item);

  return `
    <details class="startup-card">
      <summary class="card-summary">
        <div class="card-summary-main">
          <div class="card-rank">#${String(index + 1).padStart(2, "0")}</div>
          <div class="card-name">${escapeHtml(item.startup_name)}</div>
          <div class="card-meta">
            <span class="badge blue">${escapeHtml(item.sector)}</span>
            <span class="badge">${escapeHtml(formatStage(item.stage))}</span>
            <span class="badge ${timingBadgeClass(timing)}">${escapeHtml(timing)}</span>
            ${summarySignals}
          </div>
        </div>
        <div class="card-summary-side">
          <span class="opportunity fit-tooltip" role="button" tabindex="0" data-opportunity-index="${index}" aria-label="Explicar oportunidade ${opportunity}%" ${tooltipAttributes(`Por que ${opportunity}%?`, opportunityLines(item))}>
            <strong>${opportunity}%</strong>
          </span>
          <span class="card-expand">Detalhes</span>
        </div>
      </summary>
      <div class="card-dropdown">
        <div class="score-strip">
          <div>
            <div class="score-label">AI-native</div>
            <div class="score-value">${ai}</div>
            <div class="bar"><span style="width:${ai}%"></span></div>
          </div>
          <div>
            <div class="score-label">NVIDIA fit</div>
            <div class="score-value fit-tooltip" tabindex="0" aria-label="Detalhes do NVIDIA fit ${fit}" ${tooltipAttributes("NVIDIA fit", nvidiaFitLines(item))}>
              <span>${fit}</span>
            </div>
            <div class="bar"><span style="width:${fit}%"></span></div>
          </div>
          <div>
            <div class="score-label">Risco wrapper</div>
            <div class="score-value">${risk}</div>
            <div class="bar risk"><span style="width:${risk}%"></span></div>
          </div>
        </div>
        <div class="tool-list">${tools || "<span class='badge'>Sem ferramentas</span>"}</div>
        <div class="card-body"><p>${escapeHtml(item.evidence_summary || "")}</p></div>
        <div class="signals">${signals}</div>
        <div class="card-footer">
          <div class="card-links">${linkFallback}</div>
          <div class="card-actions">
            <button class="action-button primary" data-action="detail" data-index="${index}">Ver detalhes</button>
            <button class="action-button" data-action="evidence" data-index="${index}">Buscar evidências</button>
          </div>
        </div>
      </div>
    </details>
  `;
}

function renderRadar(items) {
  state.radarResults = items || [];
  $("#radarResultCount").textContent = `${state.radarResults.length} resultados`;
  $("#radarCards").innerHTML = state.radarResults.map(renderStartupCard).join("");
  $("#radarEmpty").classList.toggle("hidden", state.radarResults.length > 0);
}

function renderStartupSearchItem(item, index) {
  const signals = (item.signals || [])
    .slice(0, 5)
    .map((signal) => `<span class="badge green">${escapeHtml(signal)}</span>`)
    .join("");
  return `
    <article class="source-result">
      <div>
        <div class="result-item-title">
          <span>${escapeHtml(item.startup_name)}</span>
          <span class="badge blue">${escapeHtml(item.sector || "desconhecido")}</span>
        </div>
        <p>${escapeHtml(item.description || "")}</p>
        <div class="signals compact">${signals}</div>
      </div>
      <div class="source-actions">
        ${linkButton(item.website_url, "Site")}
        <button class="action-button primary" type="button" data-source-action="analyze" data-index="${index}">Analisar por nome</button>
      </div>
    </article>
  `;
}

function renderStartupSearchResults(items) {
  state.startupSearchResults = items || [];
  const container = $("#startupSearchResults");
  container.classList.toggle("hidden", state.startupSearchResults.length === 0);
  container.innerHTML = state.startupSearchResults.map(renderStartupSearchItem).join("");
}

function discoveryStatusLabel(status) {
  const labels = {
    new: "nova descoberta",
    enriched: "descoberta enriquecida",
    imported: "já no scout",
    needs_website_review: "revisar site",
    enrichment_failed: "enriquecimento falhou",
  };
  return labels[status] || "descoberta";
}

function renderRepertoireItem(item, index) {
  const signals = (item.signals || [])
    .slice(0, 5)
    .map((signal) => `<span class="badge green">${escapeHtml(signal)}</span>`)
    .join("");
  const needsReview = item.status === "needs_website_review";
  const reviewForm = needsReview
    ? `
      <form class="review-form" data-review-index="${index}">
        <input id="reviewWebsite-${index}" type="url" placeholder="https://site-oficial.com.br" required />
        <button class="action-button primary" type="submit">Salvar e enriquecer</button>
      </form>
    `
    : "";
  return `
    <article class="source-result">
      <div>
        <div class="result-item-title">
          <span>${escapeHtml(item.startup_name)}</span>
          <span class="badge blue">${Number(item.confidence || 0)}% · ${escapeHtml(discoveryStatusLabel(item.status))}</span>
        </div>
        <div class="result-meta">Descoberta recente capturada de notícia ou fonte pública. Revise e importe para o scout se fizer sentido.</div>
        <p>${escapeHtml(item.article_title || item.description || "")}</p>
        <div class="signals compact">${signals}</div>
        ${reviewForm}
      </div>
      <div class="source-actions">
        ${linkButton(item.article_url || item.source_url, "Notícia")}
        ${linkButton(item.website_url, "Site")}
      </div>
    </article>
  `;
}

function renderRepertoire(result) {
  const items = result?.results || [];
  state.repertoireResults = items;
  $("#repertoireMeta").textContent = `${result?.total ?? items.length} descobertas salvas`;
  const container = $("#repertoireResults");
  container.classList.toggle("hidden", items.length === 0);
  container.innerHTML = items.slice(0, 8).map(renderRepertoireItem).join("");
}

async function loadRepertoire() {
  try {
    const result = await api("/startup/repertoire");
    renderRepertoire(result);
  } catch (error) {
    showToast(`Falha ao carregar repertorio: ${error.message}`);
  }
}

async function refreshRepertoire() {
  const button = $("#refreshRepertoireButton");
  setLoading(button, true, "Atualizando");
  try {
    const result = await api("/startup/repertoire/refresh", {
      method: "POST",
      body: JSON.stringify({ max_items: 20 }),
    });
    renderRepertoire(result);
    showToast(`Repertorio atualizado: ${result.added} novas, ${result.total} salvas.`);
  } catch (error) {
    showToast(`Falha ao atualizar repertorio: ${error.message}`);
  } finally {
    setLoading(button, false);
  }
}

async function enrichRepertoire() {
  const button = $("#enrichRepertoireButton");
  setLoading(button, true, "Enriquecendo");
  try {
    const result = await api("/startup/repertoire/enrich", {
      method: "POST",
      body: JSON.stringify({ max_items: 10 }),
    });
    showToast(
      `Enriquecimento: ${result.enriched} ok, ${result.needs_review} para revisar.`,
    );
    await loadRepertoire();
    await runRadar();
  } catch (error) {
    showToast(`Falha ao enriquecer repertorio: ${error.message}`);
  } finally {
    setLoading(button, false);
  }
}

async function useRepertoire() {
  const button = $("#useRepertoireButton");
  setLoading(button, true, "Importando");
  try {
    const result = await api("/startup/repertoire/use", {
      method: "POST",
      body: JSON.stringify({ min_confidence: 50 }),
    });
    showToast(`Base ativa atualizada: ${result.imported} importadas, ${result.total_active} no total.`);
    await runRadar();
    await checkHealth();
  } catch (error) {
    showToast(`Falha ao usar repertorio: ${error.message}`);
  } finally {
    setLoading(button, false);
  }
}

async function reviewRepertoireItem(event) {
  event.preventDefault();
  const form = event.target.closest("form[data-review-index]");
  if (!form) return;
  const index = Number(form.dataset.reviewIndex);
  const item = state.repertoireResults[index];
  const input = $(`#reviewWebsite-${index}`);
  const button = form.querySelector("button");
  if (!item || !input?.value.trim()) return;

  setLoading(button, true, "Salvando");
  try {
    const result = await api("/startup/repertoire/review", {
      method: "POST",
      body: JSON.stringify({
        startup_name: item.startup_name,
        article_url: item.article_url || item.source_url || null,
        website_url: input.value.trim(),
        sector: item.sector || null,
        description: item.description || item.article_title || null,
        signals: item.signals || [],
        promote: true,
      }),
    });
    showToast(
      result.promoted
        ? "Descoberta revisada e adicionada na base ativa."
        : "Descoberta revisada.",
    );
    await loadRepertoire();
    await runRadar();
  } catch (error) {
    showToast(`Falha na revisão: ${error.message}`);
  } finally {
    setLoading(button, false);
  }
}

async function searchStartupSource(event) {
  event?.preventDefault();
  const query = $("#startupSearchQuery").value.trim();
  if (!query) {
    renderStartupSearchResults([]);
    return;
  }
  try {
    const result = await api("/startups/search", {
      method: "POST",
      body: JSON.stringify({ query, limit: 6 }),
    });
    renderStartupSearchResults(result.results || []);
    showToast(`Fonte: ${result.returned} de ${result.total_candidates} candidatas.`);
  } catch (error) {
    showToast(`Falha na busca de startups: ${error.message}`);
  }
}

async function analyzeStartupByName(item) {
  if (!item?.startup_name) return;
  try {
    const result = await api("/analysis/startup", {
      method: "POST",
      body: JSON.stringify({
        startup_name: item.startup_name,
        technical_gaps: (item.signals || []).slice(0, 3),
      }),
    });
    renderManualAnalysisResult(result);
    await loadHistory();
    navigate("analysis");
    showToast("Análise por nome concluída e salva.");
  } catch (error) {
    showToast(`Falha na análise por nome: ${error.message}`);
  }
}

async function runRadar(event) {
  event?.preventDefault();
  const button = $("#radarForm button");
  $("#radarError").classList.add("hidden");
  $("#radarLoading").classList.remove("hidden");
    setLoading(button, true, "Rodando");
  try {
    const result = await api("/startup/radar", {
      method: "POST",
      body: JSON.stringify({
        sector: $("#fSector").value.trim() || null,
        focus: $("#fTechFocus").value.trim() || null,
        stage: $("#fStage").value || null,
        limit: Number($("#fLimit").value || 8),
      }),
    });
    renderRadar(result.results || []);
    showToast(
      `Base ativa: ${result.returned} de ${result.total_candidates} candidatas ranqueadas. Para aumentar, use Buscar novidades e Adicionar ao scout.`,
    );
  } catch (error) {
    $("#radarError").textContent = error.message;
    $("#radarError").classList.remove("hidden");
    showToast(`Falha no scout: ${error.message}`);
  } finally {
    $("#radarLoading").classList.add("hidden");
    setLoading(button, false);
  }
}

function selectStartup(index) {
  state.selectedStartup = state.radarResults[index];
  if (!state.selectedStartup) return;
  renderDetail(state.selectedStartup);
  navigate("detail");
}

function renderDetail(item) {
  $("#detailEmpty").classList.add("hidden");
  $("#detailContent").classList.remove("hidden");
  $("#detailName").textContent = item.startup_name;
  $("#detailMeta").textContent = `${item.sector} | ${formatStage(item.stage)} | ${item.opportunity_percent}% oportunidade | ${timingFromScores(item)} | fontes ${Number(item.source_confidence || 0)}%`;
  $("#detailHeaderActions").innerHTML = [
    linkButton(item.website_url, "Site"),
    linkButton(item.github_url, "GitHub"),
    linkButton(item.source_url, "Fonte"),
  ]
    .filter(Boolean)
    .join("");

  $("#detailOverview").innerHTML = `
    <h2>Resumo</h2>
    <div class="detail-score-grid">
      <div><span>Oportunidade</span><strong>${Number(item.opportunity_percent || 0)}%</strong></div>
      <div><span>Fit NVIDIA</span><strong>${Number(item.nvidia_fit_score || 0)}</strong></div>
      <div><span>Risco wrapper</span><strong>${Number(item.wrapper_risk_score || 0)}</strong></div>
      <div><span>Confiança das fontes</span><strong>${Number(item.source_confidence || 0)}%</strong></div>
    </div>
    <p>${escapeHtml(item.evidence_summary || "")}</p>
    <p class="muted-copy">${escapeHtml(item.source_summary || "Sem resumo de fonte disponível.")}</p>
    <div class="decision-stack compact-stack">
      ${renderAngelThesis(item)}
      ${renderApproachPlaybook(item)}
      ${renderWrapperDisplacementMap(item)}
      ${renderCounterfactuals(item)}
    </div>
  `;
  $("#detailTools").innerHTML = `
    <h2>Recomendações NVIDIA citadas</h2>
    <div class="citation-list">
      ${(item.top_tools || []).map(renderNvidiaCitation).join("") || "<p class='muted-copy'>Sem recomendação NVIDIA forte para esta startup.</p>"}
    </div>
  `;
  $("#detailSignals").innerHTML = `
    <h2>Sinais técnicos</h2>
    <div class="signals">${(item.signals || []).map((signal) => `<span class="badge green">${escapeHtml(signal)}</span>`).join("")}</div>
  `;
  $("#detailSources").innerHTML = `
    <h2>Fontes citadas</h2>
    <div class="source-evidence-list">
      ${(item.source_evidence || []).map(renderSourceEvidenceCard).join("") || "<p class='muted-copy'>Nenhum link disponível nesta fonte.</p>"}
    </div>
  `;
}

async function searchEvidence(event) {
  event?.preventDefault();
  $("#evLoading").classList.remove("hidden");
  try {
    const result = await api("/startup/evidence/search", {
      method: "POST",
      body: JSON.stringify({
        startup_name: $("#evStartupName").value.trim() || null,
        analysis_run_id: $("#evRunId").value.trim() || null,
        query: $("#evQuery").value.trim() || "latência inferência modelo produção",
        limit: 8,
      }),
    });
    $("#evResults").innerHTML = (result.results || []).map(renderEvidenceItem).join("") || "<div class='empty-state'>Nenhuma evidência encontrada.</div>";
  } catch (error) {
    showToast(`Falha na busca de evidências: ${error.message}`);
  } finally {
    $("#evLoading").classList.add("hidden");
  }
}

function renderEvidenceItem(item) {
  const rerank = item.metadata?.rerank;
  const scoreLabel = rerank?.final_score ?? item.score ?? 0;
  const rerankMeta = rerank
    ? `
      <div class="result-meta">
        Rerank ${escapeHtml(rerank.provider || "hybrid")} ·
        vector ${Number(rerank.vector_score || 0).toFixed(2)} ·
        bm25 ${Number(rerank.bm25_score || 0).toFixed(2)} ·
        lexical ${Number(rerank.lexical_score || 0).toFixed(2)} ·
        domain ${Number(rerank.domain_score || 0).toFixed(2)}
      </div>
    `
    : "";
  return `
    <article class="result-item">
      <div class="result-item-title">
        <span>${escapeHtml(item.startup_name || item.product_name || "Result")}</span>
        <span class="badge green">${Number(scoreLabel || 0).toFixed(3)}</span>
      </div>
      ${rerankMeta}
      <p>${escapeHtml(item.chunk_text || "")}</p>
      ${isHttpUrl(item.source_url) ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">Abrir fonte</a>` : ""}
    </article>
  `;
}

async function ragSearch(event) {
  event?.preventDefault();
  try {
    const result = await api("/rag/search", {
      method: "POST",
      body: JSON.stringify({ query: $("#ragQuery").value.trim(), limit: 6 }),
    });
    $("#ragResults").innerHTML = (result.results || []).map(renderEvidenceItem).join("") || "<div class='empty-state'>Nenhum resultado.</div>";
  } catch (error) {
    showToast(`Falha no RAG: ${error.message}`);
  }
}

async function loadTechnologies() {
  try {
    const technologies = await api("/nvidia/technologies");
    $("#techCount").textContent = technologies.length;
    $("#technologyList").innerHTML = technologies
      .map(
        (item) => `
          <article class="tech-item">
            <strong>${escapeHtml(item.product_name)}</strong>
            <p>${escapeHtml(localizedTechSummary(item.product_name, item.summary))}</p>
              ${isHttpUrl(item.source_url) ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">Abrir fonte NVIDIA</a>` : ""}
          </article>
        `,
      )
      .join("");
  } catch (error) {
    showToast(`Falha ao carregar tecnologias: ${error.message}`);
  }
}

async function loadHistory() {
  try {
    const rows = await api("/analysis/runs?limit=20");
    state.historyRows = rows || [];
    renderHistoryRows();
  } catch (error) {
    showToast(`Falha ao carregar histórico: ${error.message}`);
  }
}

function filteredHistoryRows() {
  const query = ($("#historyQuery")?.value || "").trim().toLowerCase();
  const classification = $("#historyClassification")?.value || "";
  return (state.historyRows || []).filter((row) => {
    const searchable = [
      row.startup_name,
      row.sector,
      row.classification,
      row.created_at,
    ]
      .join(" ")
      .toLowerCase();
    return (
      (!classification || row.classification === classification)
      && (!query || searchable.includes(query))
    );
  });
}

function renderHistoryRows() {
  const rows = filteredHistoryRows();
  $("#historyRows").innerHTML = rows
    .map(
      (row) => `
        <tr class="history-row" data-history-id="${escapeHtml(row.analysis_run_id)}">
          <td>${escapeHtml(row.startup_name)}</td>
          <td>${escapeHtml(row.sector || "")}</td>
          <td><span class="badge blue">${escapeHtml(row.classification)}</span></td>
          <td>${Number(row.nvidia_fit_score || 0)}</td>
          <td>${Number(row.recommendations_count || 0)}</td>
          <td>${escapeHtml(row.created_at || "")}</td>
          <td>
            <button class="link-button" type="button" data-history-action="detail" data-run-id="${escapeHtml(row.analysis_run_id)}">Ver</button>
            <a class="link-button" href="${API_BASE}/analysis/runs/${escapeHtml(row.analysis_run_id)}/briefing.md">.md</a>
            <a class="link-button" href="${API_BASE}/analysis/runs/${escapeHtml(row.analysis_run_id)}/briefing.pdf">.pdf</a>
          </td>
        </tr>
      `,
    )
    .join("");
  $("#historyEmpty").classList.toggle("hidden", rows.length > 0);
  renderHistoryDetail(rows[0] || null);
}

function renderHistoryDetail(row) {
  const detail = $("#historyDetail");
  if (!row) {
    detail.classList.add("hidden");
    detail.innerHTML = "";
    return;
  }
  detail.classList.remove("hidden");
  detail.innerHTML = `
    <div class="history-detail-header">
      <div>
        <h2>${escapeHtml(row.startup_name)}</h2>
        <p>${escapeHtml(row.sector || "setor não informado")} · ${escapeHtml(row.created_at || "")}</p>
      </div>
      <span class="badge blue">${escapeHtml(row.classification)}</span>
    </div>
    <div class="history-score-grid">
      <div><span>AI-native</span><strong>${Number(row.ai_native_score || 0)}</strong></div>
      <div><span>NVIDIA fit</span><strong>${Number(row.nvidia_fit_score || 0)}</strong></div>
      <div><span>Risco wrapper</span><strong>${Number(row.wrapper_risk_score || 0)}</strong></div>
      <div><span>Recomendações</span><strong>${Number(row.recommendations_count || 0)}</strong></div>
    </div>
    <div class="history-meta">
      <span>ID da análise</span>
      <code>${escapeHtml(row.analysis_run_id)}</code>
      <span>Páginas coletadas</span>
      <strong>${Number(row.scraped_pages_count || 0)}</strong>
    </div>
    <div class="result-actions">
      <a class="secondary-button small-action" href="${API_BASE}/analysis/runs/${escapeHtml(row.analysis_run_id)}/briefing.md">Baixar .md</a>
      <a class="secondary-button small-action" href="${API_BASE}/analysis/runs/${escapeHtml(row.analysis_run_id)}/briefing.pdf">Baixar PDF</a>
      <button class="secondary-button small-action" type="button" data-history-action="evidence" data-run-id="${escapeHtml(row.analysis_run_id)}" data-startup-name="${escapeHtml(row.startup_name)}">Buscar evidências</button>
    </div>
  `;
}

function handleHistoryClick(event) {
  const control = event.target.closest("[data-history-action]");
  if (control) {
    const action = control.dataset.historyAction;
    if (action === "detail") {
      const row = state.historyRows.find(
        (item) => item.analysis_run_id === control.dataset.runId,
      );
      renderHistoryDetail(row);
    }
    if (action === "evidence") {
      $("#evStartupName").value = control.dataset.startupName || "";
      $("#evRunId").value = control.dataset.runId || "";
      $("#evQuery").value = "latência inferência modelo produção";
      navigate("evidence");
    }
    return;
  }

  if (event.target.closest("a, button")) {
    return;
  }
  const rowElement = event.target.closest(".history-row");
  if (rowElement) {
    renderHistoryDetail(
      state.historyRows.find(
        (item) => item.analysis_run_id === rowElement.dataset.historyId,
      ),
    );
  }
}

function handleHistoryFilter(event) {
  event?.preventDefault();
  renderHistoryRows();
}

async function handleManualResultAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const briefing = state.lastAnalysis?.briefing_markdown || "";
  if (!briefing) {
    showToast("Nenhum briefing disponível nesta sessão.");
    return;
  }
  if (button.dataset.action === "copy-briefing") {
    try {
      await navigator.clipboard.writeText(briefing);
      showToast("Briefing copiado.");
    } catch (_error) {
      showToast("Não foi possível copiar o briefing.");
    }
  }
  if (button.dataset.action === "download-current-briefing") {
    downloadTextFile(button.dataset.filename || "briefing.md", briefing);
  }
}

function splitGaps(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

async function analyzeStartup(event) {
  event?.preventDefault();
  const button = $("#analysisForm button");
  setLoading(button, true, "Analisando");
  try {
    const result = await api("/analysis/startup", {
      method: "POST",
      body: JSON.stringify({
        startup_name: $("#startupName").value.trim(),
        website_url: $("#websiteUrl").value.trim() || null,
        sector: $("#sector").value.trim() || null,
        description: $("#description").value.trim() || null,
        technical_gaps: splitGaps($("#technicalGaps").value),
      }),
    });
    renderManualAnalysisResult(result);
    await loadHistory();
    showToast("Análise concluída e salva.");
  } catch (error) {
    showToast(`Falha na análise: ${error.message}`);
  } finally {
    setLoading(button, false);
  }
}

function wireEvents() {
  $("#themeToggle")?.addEventListener("click", toggleTheme);
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.view)));
  $("#radarForm").addEventListener("submit", runRadar);
  $("#startupSearchForm").addEventListener("submit", searchStartupSource);
  $("#evidenceForm").addEventListener("submit", searchEvidence);
  $("#ragForm").addEventListener("submit", ragSearch);
  $("#analysisForm").addEventListener("submit", analyzeStartup);
  $("#demoScenarios").addEventListener("click", handleDemoClick);
  $("#runDemoSequenceButton").addEventListener("click", runDemoSequence);
  $("#manualResult").addEventListener("click", handleManualResultAction);
  $("#view-history").addEventListener("click", handleHistoryClick);
  $("#historyFilterForm").addEventListener("input", handleHistoryFilter);
  $("#historyFilterForm").addEventListener("submit", handleHistoryFilter);
  $("#refreshTechButton").addEventListener("click", loadTechnologies);
  $("#refreshHistoryButton").addEventListener("click", loadHistory);
  $("#refreshStatusButton").addEventListener("click", checkHealth);
  $("#refreshRepertoireButton").addEventListener("click", refreshRepertoire);
  $("#enrichRepertoireButton").addEventListener("click", enrichRepertoire);
  $("#useRepertoireButton").addEventListener("click", useRepertoire);
  $("#repertoireResults").addEventListener("submit", reviewRepertoireItem);
  document.addEventListener("mouseover", handleFitTooltipPointer);
  document.addEventListener("focusin", handleFitTooltipPointer);
  document.addEventListener("mouseout", handleFitTooltipLeave);
  document.addEventListener("focusout", handleFitTooltipLeave);
  window.addEventListener("scroll", handleFitTooltipReposition, true);
  window.addEventListener("resize", handleFitTooltipReposition);
  document.addEventListener("click", (event) => {
    const backdrop = event.target.closest(".score-explainer-backdrop");
    if (!backdrop) return;
    if (
      event.target.classList.contains("score-explainer-backdrop")
      || event.target.closest(".score-explainer-close")
    ) {
      closeOpportunityExplainer();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeOpportunityExplainer();
  });
  $("#radarCards").addEventListener("click", (event) => {
    const opportunityButton = event.target.closest("[data-opportunity-index]");
    if (opportunityButton) {
      event.preventDefault();
      event.stopPropagation();
      const item = state.radarResults[Number(opportunityButton.dataset.opportunityIndex)];
      if (item) openOpportunityExplainer(item);
      return;
    }
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const index = Number(button.dataset.index);
    if (button.dataset.action === "detail") selectStartup(index);
    if (button.dataset.action === "evidence") {
      const item = state.radarResults[index];
      $("#evStartupName").value = item?.startup_name || "";
      $("#evRunId").value = "";
      $("#evQuery").value = item?.signals?.slice(0, 3).join(" ") || "latência inferência";
      navigate("evidence");
    }
  });
  $("#radarCards").addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    const opportunityButton = event.target.closest("[data-opportunity-index]");
    if (!opportunityButton) return;
    event.preventDefault();
    event.stopPropagation();
    const item = state.radarResults[Number(opportunityButton.dataset.opportunityIndex)];
    if (item) openOpportunityExplainer(item);
  });
  $("#startupSearchResults").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-source-action]");
    if (!button) return;
    const item = state.startupSearchResults[Number(button.dataset.index)];
    if (button.dataset.sourceAction === "analyze") analyzeStartupByName(item);
  });
}

async function boot() {
  initTheme();
  wireEvents();
  renderDemoScenarios();
  renderDemoResults();
  try {
    await checkHealth();
    await Promise.all([loadTechnologies(), loadHistory(), loadRepertoire()]);
    await runRadar();
  } catch (error) {
    showToast(`API indisponível: ${error.message}`);
  }
}

boot();
