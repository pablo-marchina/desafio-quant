import { useEffect, useMemo, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { StartupGrid } from "./components/StartupGrid";
import { DetailPanel } from "./components/DetailPanel";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { BriefingPanel } from "./components/BriefingPanel";
import { ChatPanel } from "./components/ChatPanel";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

function normalize(text) {
  return text.trim().toLowerCase();
}

function scoreBand(score) {
  if (score >= 85) return "85+";
  if (score >= 70) return "70-84";
  return "<70";
}

function slugify(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildBriefingDocument(startup) {
  const exportedAt = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "full",
    timeStyle: "short",
  }).format(new Date());

  const briefingBullets = startup.executiveBrief.bullets
    .map(
      (bullet) => `
        <article class="bullet-card">
          <h3>${escapeHtml(bullet.label)}</h3>
          <p>${escapeHtml(bullet.text)}</p>
        </article>`,
    )
    .join("");

  const recommendationCards = startup.recommendations
    .map(
      (recommendation) => `
        <article class="recommendation-card">
          <div class="card-head">
            <h3>${escapeHtml(recommendation.name)}</h3>
            <span>${escapeHtml(recommendation.confidence)}</span>
          </div>
          <p>${escapeHtml(recommendation.reason)}</p>
          <p><strong>Aderencia:</strong> ${escapeHtml(recommendation.adherence)}</p>
          <p><strong>Proximo passo:</strong> ${escapeHtml(recommendation.nextStep)}</p>
        </article>`,
    )
    .join("");

  const nextSteps = startup.nextSteps
    .map((step) => `<li>${escapeHtml(step)}</li>`)
    .join("");

  return `<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <title>Briefing - ${escapeHtml(startup.name)}</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fb;
        --panel: #ffffff;
        --text: #10203a;
        --muted: #5a6780;
        --line: #d5deee;
        --accent: #76b900;
        --accent-soft: #eef8d7;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        padding: 40px;
        background: linear-gradient(180deg, #eef3ff 0%, var(--bg) 100%);
        color: var(--text);
        font: 16px/1.6 Arial, sans-serif;
      }

      main {
        max-width: 960px;
        margin: 0 auto;
      }

      section {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 12px 30px rgba(16, 32, 58, 0.08);
      }

      h1, h2, h3, p {
        margin-top: 0;
      }

      .eyebrow {
        color: var(--accent);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 12px;
      }

      .hero-grid,
      .metrics-grid,
      .briefing-grid,
      .recommendation-grid {
        display: grid;
        gap: 16px;
      }

      .hero-grid,
      .metrics-grid {
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }

      .briefing-grid,
      .recommendation-grid {
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      }

      .metric-card,
      .bullet-card,
      .recommendation-card {
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 16px;
        background: #fbfcff;
      }

      .metric-card span,
      .exported-at {
        color: var(--muted);
      }

      .fit-badge {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: #335000;
        font-weight: 700;
      }

      .card-head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: baseline;
      }

      ul {
        padding-left: 20px;
        margin-bottom: 0;
      }
    </style>
  </head>
  <body>
    <main>
      <section>
        <p class="eyebrow">NVIDIA Startup AI Radar</p>
        <h1>${escapeHtml(startup.name)}</h1>
        <p>${escapeHtml(startup.summary)}</p>
        <p class="exported-at">Exportado em ${escapeHtml(exportedAt)}</p>
      </section>

      <section>
        <h2>Panorama geral</h2>
        <div class="hero-grid">
          <div>
            <p>${escapeHtml(startup.description)}</p>
          </div>
          <div>
            <span class="fit-badge">Fit NVIDIA ${escapeHtml(startup.nvidiaFit)}</span>
          </div>
        </div>
        <div class="metrics-grid">
          <div class="metric-card"><span>Segmento</span><h3>${escapeHtml(startup.segment)}</h3></div>
          <div class="metric-card"><span>Cidade</span><h3>${escapeHtml(startup.city)}</h3></div>
          <div class="metric-card"><span>Score AI-native</span><h3>${escapeHtml(startup.aiScore)}</h3></div>
          <div class="metric-card"><span>Status</span><h3>${escapeHtml(startup.validationStatus)}</h3></div>
        </div>
      </section>

      <section>
        <h2>Briefing executivo</h2>
        <p>${escapeHtml(startup.executiveBrief.summary)}</p>
        <div class="briefing-grid">${briefingBullets}</div>
      </section>

      <section>
        <h2>Recomendacoes NVIDIA</h2>
        <div class="recommendation-grid">${recommendationCards}</div>
      </section>

      <section>
        <h2>Proximos passos</h2>
        <ul>${nextSteps}</ul>
      </section>
    </main>
  </body>
</html>`;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Falha ao comunicar com a API.");
  }

  return response.json();
}

function upsertStartup(current, nextStartup) {
  const exists = current.some((startup) => startup.id === nextStartup.id);
  if (!exists) return [nextStartup, ...current];
  return current.map((startup) => (startup.id === nextStartup.id ? nextStartup : startup));
}

export default function App() {
  const [searchTerm, setSearchTerm] = useState("");
  const [segmentFilter, setSegmentFilter] = useState("Todos");
  const [scoreFilter, setScoreFilter] = useState("Todos");
  const [statusFilter, setStatusFilter] = useState("Todos");
  const [cityFilter, setCityFilter] = useState("Todos");
  const [selectedStartupId, setSelectedStartupId] = useState(null);
  const [startups, setStartups] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [isLoadingStartups, setIsLoadingStartups] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const loadStartups = async () => {
      try {
        const data = await apiRequest("/api/startups");
        setStartups(data);
        if (data.length > 0) {
          setSelectedStartupId(data[0].id);
        }
      } catch (error) {
        setErrorMessage(error.message);
      } finally {
        setIsLoadingStartups(false);
      }
    };

    loadStartups();
  }, []);

  const selectedStartup = useMemo(
    () => startups.find((startup) => startup.id === selectedStartupId) ?? null,
    [selectedStartupId, startups],
  );

  const segments = useMemo(
    () => ["Todos", ...new Set(startups.map((startup) => startup.segment))],
    [startups],
  );
  const cities = useMemo(
    () => ["Todos", ...new Set(startups.map((startup) => startup.city))],
    [startups],
  );

  const filteredStartups = useMemo(() => {
    return startups.filter((startup) => {
      const matchesSearch =
        searchTerm === "" ||
        normalize(startup.name).includes(normalize(searchTerm)) ||
        normalize(startup.summary).includes(normalize(searchTerm));
      const matchesSegment = segmentFilter === "Todos" || startup.segment === segmentFilter;
      const matchesScore = scoreFilter === "Todos" || scoreBand(startup.aiScore) === scoreFilter;
      const matchesStatus =
        statusFilter === "Todos" || startup.validationStatus === statusFilter;
      const matchesCity = cityFilter === "Todos" || startup.city === cityFilter;

      return matchesSearch && matchesSegment && matchesScore && matchesStatus && matchesCity;
    });
  }, [cityFilter, scoreFilter, searchTerm, segmentFilter, startups, statusFilter]);

  const handleAnalyze = async () => {
    const startupName = searchTerm.trim();
    if (!startupName) {
      window.alert("Digite o nome da startup para iniciar a analise.");
      return;
    }

    setIsAnalyzing(true);
    setErrorMessage("");
    try {
      const result = await apiRequest("/api/startups/analyze", {
        method: "POST",
        body: JSON.stringify({ startup_name: startupName }),
      });
      setStartups((current) => upsertStartup(current, result));
      setSelectedStartupId(result.id);
      setChatMessages([]);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleExport = () => {
    if (!selectedStartup) {
      window.alert("Selecione uma startup para exportar o briefing.");
      return;
    }

    const documentContent = buildBriefingDocument(selectedStartup);
    const blob = new Blob([documentContent], {
      type: "text/html;charset=utf-8",
    });
    const url = window.URL.createObjectURL(blob);
    const link = window.document.createElement("a");

    link.href = url;
    link.download = `briefing-${slugify(selectedStartup.name)}.html`;
    window.document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleCopyBriefing = async () => {
    if (!selectedStartup) return;

    const briefingText = [
      selectedStartup.executiveBrief.summary,
      ...selectedStartup.executiveBrief.bullets.map(
        (bullet) => `${bullet.label}: ${bullet.text}`,
      ),
    ].join("\n");

    try {
      await navigator.clipboard.writeText(briefingText);
      window.alert("Briefing copiado para a area de transferencia.");
    } catch {
      window.alert("Nao foi possivel copiar o briefing neste navegador.");
    }
  };

  const handleSendMessage = async (input) => {
    if (!input.trim() || !selectedStartup || isSendingChat) return;

    const userMessage = { id: Date.now(), role: "user", text: input };
    setChatMessages((current) => [...current, userMessage]);
    setIsSendingChat(true);

    try {
      const reply = await apiRequest("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          startup_id: selectedStartup.id,
          startup_name: selectedStartup.name,
          message: input,
        }),
      });
      setChatMessages((current) => [
        ...current,
        { id: Date.now() + 1, role: "assistant", text: reply.answer, sources: reply.sources },
      ]);
    } catch (error) {
      setChatMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          text: `Nao foi possivel responder agora: ${error.message}`,
        },
      ]);
    } finally {
      setIsSendingChat(false);
    }
  };

  return (
    <div className="app-shell">
      <Header
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        onExport={handleExport}
        onAnalyze={handleAnalyze}
        isAnalyzing={isAnalyzing}
        isExportDisabled={!selectedStartup}
      />
      {errorMessage ? <div className="feedback-banner error">{errorMessage}</div> : null}
      {isLoadingStartups ? (
        <div className="feedback-banner">Carregando analises disponiveis...</div>
      ) : null}
      <div className="dashboard-layout">
        <Sidebar
          startups={startups}
          selectedStartupId={selectedStartup?.id ?? ""}
          onSelectStartup={setSelectedStartupId}
          segmentFilter={segmentFilter}
          onSegmentFilterChange={setSegmentFilter}
          scoreFilter={scoreFilter}
          onScoreFilterChange={setScoreFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          cityFilter={cityFilter}
          onCityFilterChange={setCityFilter}
          segments={segments}
          cities={cities}
        />
        <main className="dashboard-main">
          <StartupGrid
            startups={filteredStartups}
            selectedStartupId={selectedStartup?.id ?? ""}
            onSelectStartup={setSelectedStartupId}
          />
          <DetailPanel startup={selectedStartup} />
          <section className="content-grid bottom-grid">
            <RecommendationPanel startup={selectedStartup} />
            <BriefingPanel
              startup={selectedStartup}
              onExport={handleExport}
              onCopy={handleCopyBriefing}
            />
          </section>
          <ChatPanel
            messages={chatMessages}
            onSendMessage={handleSendMessage}
            isSending={isSendingChat}
            disabled={!selectedStartup}
          />
        </main>
      </div>
    </div>
  );
}
