const apiUrlInput = document.querySelector("#apiUrl");
const apiStatus = document.querySelector("#apiStatus");
const checkApiButton = document.querySelector("#checkApiButton");
const themeToggleButton = document.querySelector("#themeToggleButton");
const discoveryForm = document.querySelector("#discoveryForm");
const marketQueryInput = document.querySelector("#marketQuery");
const marketCountryInput = document.querySelector("#marketCountry");
const marketMaxResultsInput = document.querySelector("#marketMaxResults");
const runDiscoveryButton = document.querySelector("#runDiscoveryButton");
const loadDiscoverySampleButton = document.querySelector("#loadDiscoverySampleButton");
const analysisForm = document.querySelector("#analysisForm");
const startupUrlInput = document.querySelector("#startupUrl");
const startupTitleInput = document.querySelector("#startupTitle");
const sourceTextInput = document.querySelector("#sourceText");
const runButton = document.querySelector("#runButton");
const loadSampleButton = document.querySelector("#loadSampleButton");
const copyBriefingButton = document.querySelector("#copyBriefingButton");
const downloadBriefingButton = document.querySelector("#downloadBriefingButton");
const printBriefingButton = document.querySelector("#printBriefingButton");
const reportEmailInput = document.querySelector("#reportEmail");
const emailBriefingButton = document.querySelector("#emailBriefingButton");
const emailStatus = document.querySelector("#emailStatus");
const discoveryOutput = document.querySelector("#discoveryOutput");
const profileOutput = document.querySelector("#profileOutput");
const maturityOutput = document.querySelector("#maturityOutput");
const radarOutput = document.querySelector("#radarOutput");
const gapsOutput = document.querySelector("#gapsOutput");
const recommendationsOutput = document.querySelector("#recommendationsOutput");
const briefingOutput = document.querySelector("#briefingOutput");

const sampleText =
  "MedAI automatiza fluxos de trabalho em saúde com agentes de IA e copilotos baseados em LLM. " +
  "A plataforma usa APIs da OpenAI e enfrenta pressão de latência.";

let currentBriefingTitle = "relatorio-nvidia-startup-ai-radar";
let currentBriefingMarkdown = "";
const systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
const themeStorageKey = "radarThemePreference";

const maturityLabels = {
  ai_native: "IA-native",
  ai_enabled: "IA aplicada",
  non_ai: "Sem sinais fortes de IA",
};

const priorityLabels = {
  high: "Alta",
  medium: "Média",
  low: "Baixa",
};

const complexityLabels = {
  high: "Alta",
  medium: "Média",
  low: "Baixa",
};

const evidenceBasisLabels = {
  evidence_backed: "Com evidência",
  inferred: "Inferido",
};

const scoreLabels = {
  ai_workflow_depth: "Profundidade do uso de IA",
  proprietary_data_advantage: "Vantagem de dados próprios",
  model_customization_or_evaluation: "Customização ou avaliação",
  production_deployment_maturity: "Maturidade em produção",
  automation_depth: "Profundidade da automação",
  vendor_dependency_risk: "Dependência de fornecedor",
  governance_readiness: "Governança",
  cost_latency_sensitivity: "Sensibilidade a custo/latência",
};

const gapLabels = {
  external_api_dependency: "Dependência de API externa",
  inference_latency_or_cost: "Custo ou latência de inferência",
  model_serving_maturity: "Maturidade de serving",
  agent_governance: "Governança de agentes",
  data_pipeline_scale: "Escala de dados",
  voice_ai_maturity: "Maturidade em voz",
  healthcare_production_readiness: "Prontidão para saúde em produção",
  robotics_or_simulation: "Robótica ou simulação",
  cybersecurity_ai: "IA para cibersegurança",
  general_ai_stack_gap: "Gap geral de stack de IA",
};

const signalLabels = {
  "AI agents": "Agentes de IA",
  "Computer vision": "Visão computacional",
  "Speech AI": "IA de voz",
  "Data pipeline": "Pipeline de dados",
  "External AI API": "API externa de IA",
};

const sectorLabels = {
  healthcare: "Saúde",
  finance: "Finanças",
  cybersecurity: "Cibersegurança",
  retail: "Varejo",
  education: "Educação",
  legal: "Jurídico",
  robotics: "Robótica",
};

function applyTheme(theme) {
  document.body.dataset.theme = theme;
  themeToggleButton.setAttribute(
    "aria-label",
    theme === "dark" ? "Alternar para modo claro" : "Alternar para modo noturno"
  );
  themeToggleButton.title = theme === "dark" ? "Modo claro" : "Modo noturno";
  localStorage.setItem(themeStorageKey, theme);
}

function preferredTheme() {
  const storedTheme = localStorage.getItem(themeStorageKey);
  if (storedTheme) {
    return storedTheme;
  }
  return systemThemeQuery.matches ? "dark" : "light";
}

function apiBaseUrl() {
  return apiUrlInput.value.replace(/\/$/, "");
}

async function postJson(path, body) {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

async function emailReport() {
  emailStatus.textContent = "";
  emailBriefingButton.disabled = true;
  emailBriefingButton.textContent = "Enviando...";

  try {
    const result = await postJson("/briefings/email", {
      to_email: reportEmailInput.value,
      subject: currentBriefingTitle,
      markdown: briefingOutput.textContent,
    });
    emailStatus.textContent = result.detail;
  } catch (error) {
    emailStatus.textContent =
      "Não foi possível enviar. Configure SMTP no backend ou baixe o relatório.";
  } finally {
    emailBriefingButton.disabled = false;
    emailBriefingButton.textContent = "Enviar por e-mail";
  }
}

async function checkApi() {
  setStatus("Verificando", "");
  try {
    const response = await fetch(`${apiBaseUrl()}/health`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const body = await response.json();
    setStatus(body.status === "ok" ? "API online" : "Erro na API", "ok");
  } catch (error) {
    setStatus("API offline", "error");
  }
}

function setStatus(text, state) {
  apiStatus.textContent = text;
  apiStatus.className = `status ${state}`;
}

function discoveryPayload() {
  return {
    query: marketQueryInput.value,
    country: marketCountryInput.value,
    max_results: Number(marketMaxResultsInput.value),
  };
}

function baseAnalysisPayload(extractedText) {
  return {
    url: startupUrlInput.value,
    title: startupTitleInput.value || null,
    extracted_text: extractedText,
  };
}

async function requestPayload() {
  const manualText = sourceTextInput.value.trim();
  if (manualText) {
    return baseAnalysisPayload(manualText);
  }

  runButton.textContent = "Coletando fonte...";
  const collectedText = await collectSourceTextFromUrl();
  const fallbackText = [
    startupTitleInput.value,
    startupUrlInput.value,
    "Análise solicitada a partir da URL pública da startup.",
  ]
    .filter(Boolean)
    .join(" ");

  return baseAnalysisPayload(collectedText || fallbackText);
}

async function collectSourceTextFromUrl() {
  try {
    const run = await postJson("/runs/analyze-url", {
      url: startupUrlInput.value,
      fetch: true,
    });
    const sourceDocument = run.source_document || {};
    const extractedText = String(sourceDocument.extracted_text || "").trim();
    const collectedTitle = String(sourceDocument.title || "").trim();

    if (collectedTitle && !startupTitleInput.value.trim()) {
      startupTitleInput.value = collectedTitle;
    }

    if (extractedText) {
      sourceTextInput.value = extractedText;
      return extractedText;
    }
  } catch (error) {
    return "";
  }

  return "";
}

async function runDiscovery(event) {
  event.preventDefault();
  runDiscoveryButton.disabled = true;
  runDiscoveryButton.textContent = "Buscando...";

  try {
    const discovery = await postJson("/runs/discovery", discoveryPayload());
    renderDiscovery(discovery);
  } catch (error) {
    discoveryOutput.textContent = `Busca falhou: ${error.message}`;
  } finally {
    runDiscoveryButton.disabled = false;
    runDiscoveryButton.textContent = "Buscar IAs relevantes";
  }
}

async function runAnalysis(event) {
  event.preventDefault();
  runButton.disabled = true;
  runButton.textContent = "Rodando...";

  try {
    const payload = await requestPayload();
    runButton.textContent = "Analisando...";
    const [profile, maturity, radar, gaps, recommendations, briefing] = await Promise.all([
      postJson("/extraction/startup-profile", payload),
      postJson("/classification/ai-maturity", payload),
      postJson("/radar/threat-opportunity", payload),
      postJson("/diagnostics/gaps", payload),
      postJson("/recommendations", payload),
      postJson("/briefings", payload),
    ]);

    renderProfile(profile);
    renderMaturity(maturity);
    renderRadar(radar);
    renderGaps(gaps);
    renderRecommendations(recommendations);
    currentBriefingTitle = briefing.title;
    currentBriefingMarkdown = briefing.markdown;
    renderBriefing(briefing.markdown);
  } catch (error) {
    renderBriefingMessage(`Análise falhou: ${error.message}`);
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Rodar análise";
  }
}

function renderDiscovery(discovery) {
  const visibleLinks = discovery.live_search_links.slice(0, 9);
  discoveryOutput.innerHTML =
    `<p>${escapeHtml(discovery.summary)}</p>` +
    `<h3>Empresas candidatas</h3>` +
    renderCandidates(discovery.candidates) +
    `<h3>Sinais para observar</h3>` +
    renderList(discovery.trend_signals) +
    `<h3>Consultas sugeridas</h3>` +
    renderList(discovery.suggested_queries) +
    `<h3>Fontes prioritárias</h3>` +
    renderList(discovery.source_targets) +
    `<h3>Links de busca atuais</h3>` +
    `<ul class="link-list">${visibleLinks
      .map(
        (link) =>
          `<li><a href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">` +
          `${escapeHtml(link.label)}</a></li>`
      )
      .join("")}</ul>` +
    `<h3>Critérios de priorização</h3>` +
    renderList(discovery.evaluation_checklist) +
    `<h3>Próximas ações</h3>` +
    renderList(discovery.next_actions);

  discoveryOutput.querySelectorAll("[data-load-candidate]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.getAttribute("data-load-candidate"));
      loadCandidate(discovery.candidates[index]);
    });
  });
}

function renderCandidates(candidates) {
  if (!candidates.length) {
    return "<p>Nenhuma candidata encontrada para essa busca.</p>";
  }

  return `<div class="candidate-grid">${candidates
    .map(
      (candidate, index) =>
        `<article class="candidate-card">` +
        `<div class="candidate-header">` +
        `<div><h4>${escapeHtml(candidate.name)}</h4>` +
        `<span>${escapeHtml(candidate.sector)}</span></div>` +
        `<button type="button" data-load-candidate="${index}">Analisar</button>` +
        `</div>` +
        `<p>${escapeHtml(candidate.why_relevant)}</p>` +
        `<div class="score-row compact">` +
        metricPill("Ranking", candidate.rank_score) +
        metricPill("Wrapper", candidate.wrapper_risk) +
        metricPill("Fit NVIDIA", candidate.nvidia_fit) +
        metricPill("Urgência", candidate.urgency) +
        `<span>${candidate.evidence_count} evidência(s)</span>` +
        `</div>` +
        renderChipGroup("Sinais IA-native", candidate.ai_native_signals.map(readableSignal)) +
        renderChipGroup("Oportunidade NVIDIA", candidate.nvidia_opportunity) +
        `<div class="source-row">${candidate.source_urls
          .map(
            (url) =>
              `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Fonte</a>`
          )
          .join("")}</div>` +
        `</article>`
    )
    .join("")}</div>`;
}

function loadCandidate(candidate) {
  startupUrlInput.value = candidate.website;
  startupTitleInput.value = candidate.name;
  sourceTextInput.value = candidate.analysis_text;
  renderBriefingMessage(
    `Empresa carregada: ${candidate.name}. Clique em "Rodar análise" para gerar o relatório completo.`
  );
  runButton.scrollIntoView({ behavior: "smooth", block: "center" });
  runButton.focus({ preventScroll: true });
}

function renderList(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderProfile(profile) {
  const sectorText = profile.sectors.map(readableSector).join(", ") || "Nenhum";
  const signalText = profile.technology_signals.map(readableSignal).join(", ") || "Nenhum";
  const rows = [
    ["Nome", profile.name || "Desconhecido"],
    ["Website", profile.website],
    ["Setores", sectorText],
    ["Sinais", signalText],
    ["Evidências", String(profile.evidence_claims.length)],
  ];
  profileOutput.innerHTML = rows
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
}

function renderMaturity(maturity) {
  const scoreLines = Object.entries(maturity.scores)
    .map(([key, value]) => renderScoreBar(readableScore(key), value))
    .join("");
  maturityOutput.innerHTML =
    `<div class="result-title"><strong>${escapeHtml(readableMaturity(maturity.label))}</strong>` +
    `<span>${formatPercent(maturity.confidence)} confiança</span></div>` +
    `<p>${escapeHtml(maturity.explanation)}</p>` +
    `<div class="score-stack">${scoreLines}</div>`;
}

function renderRadar(radar) {
  const scores = [
    ["Risco de wrapper", radar.wrapper_risk],
    ["Defensibilidade", radar.defensibility],
    ["Fit NVIDIA", radar.nvidia_fit],
    ["Urgência", radar.outreach_urgency],
  ];
  radarOutput.innerHTML =
    scores
      .map(
        ([label, value]) =>
          `<div class="radar-score"><span>${escapeHtml(label)}</span>` +
          `<strong>${formatPercent(value)}</strong>${renderMiniBar(value)}</div>`
      )
      .join("") +
    `<p>${escapeHtml(radar.summary)}</p>` +
    renderChipGroup(
      "Foco recomendado",
      radar.recommended_focus.map((item) =>
        item === "Wrapper-risk reduction" ? "Redução de risco de wrapper" : item
      )
    );
}

function renderGaps(report) {
  if (!report.gaps.length) {
    gapsOutput.innerHTML = `<li><p>${escapeHtml(report.summary)}</p></li>`;
    return;
  }

  gapsOutput.innerHTML = report.gaps
    .map(
      (gap) =>
        `<li><div class="result-title"><b>${escapeHtml(readableGap(gap.gap_type))}</b>` +
        `<span>${escapeHtml(readablePriority(gap.priority))}</span></div>` +
        `<div class="meta">${escapeHtml(readableEvidenceBasis(gap.evidence_basis))} · ` +
        `${formatPercent(gap.confidence)} confiança</div>` +
        `<p>${escapeHtml(gap.rationale)}</p>` +
        `<p class="next-action">${escapeHtml(gap.suggested_action)}</p></li>`
    )
    .join("");
}

function renderRecommendations(report) {
  if (!report.recommendations.length) {
    recommendationsOutput.innerHTML = `<li><p>${escapeHtml(report.summary)}</p></li>`;
    return;
  }

  recommendationsOutput.innerHTML = report.recommendations
    .map(
      (recommendation) =>
        `<li><div class="result-title"><b>${escapeHtml(recommendation.technology_name)}</b>` +
        `<span>${escapeHtml(readablePriority(recommendation.priority))}</span></div>` +
        `<div class="meta">Complexidade ${escapeHtml(readableComplexity(recommendation.complexity))} · ` +
        `${escapeHtml(readableGap(recommendation.gap_type))}</div>` +
        `<p>${escapeHtml(recommendation.technical_rationale)}</p>` +
        `<p class="next-action">${escapeHtml(recommendation.next_action)}</p></li>`
    )
    .join("");
}

function renderBriefing(markdown) {
  briefingOutput.innerHTML = markdownToHtml(markdown);
}

function renderBriefingMessage(message) {
  currentBriefingMarkdown = message;
  briefingOutput.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
}

function markdownToHtml(markdown) {
  const lines = String(markdown).split("\n");
  let html = "";
  let isListOpen = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (isListOpen) {
        html += "</ul>";
        isListOpen = false;
      }
      continue;
    }

    if (trimmed.startsWith("# ")) {
      if (isListOpen) {
        html += "</ul>";
        isListOpen = false;
      }
      html += `<h1>${escapeHtml(trimmed.slice(2))}</h1>`;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      if (isListOpen) {
        html += "</ul>";
        isListOpen = false;
      }
      html += `<h2>${escapeHtml(trimmed.slice(3))}</h2>`;
      continue;
    }

    if (trimmed.startsWith("### ")) {
      if (isListOpen) {
        html += "</ul>";
        isListOpen = false;
      }
      html += `<h3>${escapeHtml(trimmed.slice(4))}</h3>`;
      continue;
    }

    if (trimmed.startsWith("- ")) {
      if (!isListOpen) {
        html += "<ul>";
        isListOpen = true;
      }
      html += `<li>${escapeHtml(trimmed.slice(2))}</li>`;
      continue;
    }

    if (isListOpen) {
      html += "</ul>";
      isListOpen = false;
    }
    html += `<p>${escapeHtml(trimmed)}</p>`;
  }

  if (isListOpen) {
    html += "</ul>";
  }

  return html;
}

function renderScoreBar(label, value) {
  const normalized = normalizedScore(value);
  return (
    `<div class="score-bar">` +
    `<div><span>${escapeHtml(label)}</span><strong>${formatPercent(normalized)}</strong></div>` +
    `<i style="--value:${normalized * 100}%"></i>` +
    `</div>`
  );
}

function renderMiniBar(value) {
  return `<i class="mini-bar" style="--value:${normalizedScore(value) * 100}%"></i>`;
}

function metricPill(label, value) {
  return `<span>${escapeHtml(label)} ${formatPercent(value)}</span>`;
}

function renderChipGroup(label, items) {
  const validItems = items.filter(Boolean);
  if (!validItems.length) {
    return "";
  }
  return (
    `<div class="chip-group"><b>${escapeHtml(label)}</b><div>` +
    validItems.map((item) => `<span>${escapeHtml(item)}</span>`).join("") +
    `</div></div>`
  );
}

function readableMaturity(value) {
  return maturityLabels[value] || value;
}

function readablePriority(value) {
  return priorityLabels[value] || value;
}

function readableComplexity(value) {
  return complexityLabels[value] || value;
}

function readableEvidenceBasis(value) {
  return evidenceBasisLabels[value] || value;
}

function readableScore(value) {
  return scoreLabels[value] || value;
}

function readableGap(value) {
  return gapLabels[value] || value;
}

function readableSignal(value) {
  return signalLabels[value] || value;
}

function readableSector(value) {
  return sectorLabels[value] || value;
}

function normalizedScore(value) {
  const number = Number(value);
  if (Number.isNaN(number)) {
    return 0;
  }
  return Math.max(0, Math.min(number, 1));
}

function formatPercent(value) {
  return `${Math.round(normalizedScore(value) * 100)}%`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadSampleButton.addEventListener("click", () => {
  startupUrlInput.value = "https://medai.example";
  startupTitleInput.value = "MedAI";
  sourceTextInput.value = sampleText;
});

loadDiscoverySampleButton.addEventListener("click", () => {
  marketQueryInput.value = "IA generativa para saúde";
  marketCountryInput.value = "Brasil";
  marketMaxResultsInput.value = "10";
});

copyBriefingButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(currentBriefingMarkdown || briefingOutput.textContent);
  copyBriefingButton.textContent = "Copiado";
  setTimeout(() => {
    copyBriefingButton.textContent = "Copiar";
  }, 1200);
});

downloadBriefingButton.addEventListener("click", () => {
  const markdown = currentBriefingMarkdown || briefingOutput.textContent;
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${slugify(currentBriefingTitle)}.md`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
});

printBriefingButton.addEventListener("click", () => {
  window.print();
});

function slugify(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "briefing";
}

checkApiButton.addEventListener("click", checkApi);
themeToggleButton.addEventListener("click", () => {
  applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
});
systemThemeQuery.addEventListener("change", (event) => {
  if (!localStorage.getItem(themeStorageKey)) {
    applyTheme(event.matches ? "dark" : "light");
  }
});
emailBriefingButton.addEventListener("click", emailReport);
discoveryForm.addEventListener("submit", runDiscovery);
analysisForm.addEventListener("submit", runAnalysis);
applyTheme(preferredTheme());
checkApi();
