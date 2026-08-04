"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Priority = "high" | "medium" | "low";

interface Recommendation {
  nvidia_tech: string;
  technical_justification: string;
  business_justification: string;
  priority: Priority;
  complexity: Priority;
  next_action: string;
  evidence_used: string[];
}

interface BriefingReport {
  startup: {
    name: string;
    website: string | null;
    logo_url: string | null;
    sector: string | null;
    description: string | null;
    founding_year: number | null;
    hq_location: string | null;
    employee_count: number | null;
    classification: string | null;
    tech_stack: string[];
    founders: string[];
    funding_usd: number | null;
    funding_stage: string | null;
    investors: string[];
    products: string[];
    use_cases: string[];
    business_model: string | null;
    target_market: string | null;
    github_url: string | null;
    linkedin_url: string | null;
  };
  recommendations: Recommendation[];
  summary: string;
  generated_at: string;
}

interface DimensionScore {
  score: number;
  rationale: string;
}

interface StartupScore {
  startup_name: string;
  technical_fit: DimensionScore;
  ai_maturity: DimensionScore;
  market_potential: DimensionScore;
  strategic_value: DimensionScore;
  urgency: DimensionScore;
  total: number;
  tier: string;
  recommendation: string;
}

interface RankedStartup {
  position: number;
  startup_name: string;
  score: StartupScore;
  highlight: string;
  action: string;
}

interface RankingReport {
  ranked: RankedStartup[];
  strategic_summary: string;
  top_pick: string;
  quick_wins: string[];
  long_bets: string[];
}

interface DebateMove {
  agent: string;
  round_type: "opening" | "attack" | "rebuttal";
  argument: string;
}

interface DebateResult {
  startup_a: string;
  startup_b: string;
  model: string;
  rounds: DebateMove[];
  verdict: {
    winner: string;
    score_a: number;
    score_b: number;
    reasoning: string;
    nvidia_recommendation: string;
  };
}

const PRIORITY_COLOR: Record<Priority, string> = {
  high: "bg-green-500/20 text-green-400 border-green-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

const CLASSIFICATION_COLOR: Record<string, string> = {
  "AI-native": "bg-green-500/20 text-green-400 border-green-500/30",
  "AI-enabled": "bg-blue-500/20 text-blue-400 border-blue-500/30",
  "non-AI": "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

function RadarChart({ score, size = 90, showLabels = true }: { score: StartupScore; size?: number; showLabels?: boolean }) {
  const cx = size / 2, cy = size / 2, r = size * 0.38;
  const dims = [
    { label: "Técnico", value: score.technical_fit.score },
    { label: "IA", value: score.ai_maturity.score },
    { label: "Mercado", value: score.market_potential.score },
    { label: "Estratégia", value: score.strategic_value.score },
    { label: "Urgência", value: score.urgency.score },
  ];
  const n = dims.length;

  function pt(i: number, scale: number) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return { x: cx + r * Math.cos(a) * scale, y: cy + r * Math.sin(a) * scale };
  }

  function poly(scale: number) {
    return Array.from({ length: n }, (_, i) => pt(i, scale)).map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  }

  const color = score.total >= 80 ? "#22c55e" : score.total >= 65 ? "#3b82f6" : score.total >= 50 ? "#eab308" : "#71717a";
  const dataPoly = dims.map((d, i) => pt(i, d.value / 10)).map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
      {[0.33, 0.66, 1].map(l => (
        <polygon key={l} points={poly(l)} fill="none" stroke="#3f3f46" strokeWidth="0.5" />
      ))}
      {Array.from({ length: n }, (_, i) => {
        const outer = pt(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke="#3f3f46" strokeWidth="0.5" />;
      })}
      <polygon points={dataPoly} fill={color} fillOpacity="0.25" stroke={color} strokeWidth="1.2" />
      {showLabels && dims.map((d, i) => {
        const p = pt(i, 1.22);
        return (
          <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="middle" fontSize="6" fill="#71717a">
            {d.label} {d.value}
          </text>
        );
      })}
    </svg>
  );
}

function ScoreGauge({ score }: { score: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const id = setTimeout(() => setDisplay(score), 40);
    return () => clearTimeout(id);
  }, [score]);
  const arcLen = 78.54;
  const fill = (display / 100) * arcLen;
  const color = score >= 80 ? "#22c55e" : score >= 65 ? "#3b82f6" : score >= 50 ? "#eab308" : "#71717a";
  return (
    <svg viewBox="0 0 44 24" width="44" height="24" className="shrink-0">
      <path d="M 4 22 A 18 18 0 0 1 40 22" fill="none" stroke="#27272a" strokeWidth="4" strokeLinecap="round" />
      <path d="M 4 22 A 18 18 0 0 1 40 22" fill="none" stroke={color} strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={`${fill * 0.727} ${arcLen * 0.727}`}
        style={{ transition: "stroke-dasharray 0.85s cubic-bezier(0.4,0,0.2,1)" }} />
      <text x="22" y="21" textAnchor="middle" fontSize="9" fontWeight="bold" fill="white">{score}</text>
    </svg>
  );
}

const TIER_COLOR: Record<string, string> = {
  S: "bg-green-500/20 text-green-400 border-green-500/30",
  A: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  B: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  C: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

const SCORE_DIMS: { key: keyof StartupScore; label: string; weight: string }[] = [
  { key: "technical_fit",    label: "Fit Técnico",         weight: "30%" },
  { key: "ai_maturity",      label: "Maturidade IA",       weight: "25%" },
  { key: "market_potential", label: "Potencial de Mercado", weight: "20%" },
  { key: "strategic_value",  label: "Valor Estratégico",   weight: "15%" },
  { key: "urgency",          label: "Urgência",            weight: "10%" },
];

const ROUND_LABEL: Record<string, string> = {
  opening: "Abertura",
  attack: "Ataque",
  rebuttal: "Réplica",
};

const MODELS = [
  { key: "llama-3.3-70b", label: "Llama 3.3 70B", desc: "Default · fallback Groq" },
  { key: "deepseek-r1", label: "DeepSeek R1", desc: "Melhor raciocínio" },
  { key: "gemma-3-27b", label: "Gemma 3 27B", desc: "Bom em PT-BR" },
  { key: "qwen3-235b", label: "Qwen3 235B", desc: "Mais capaz" },
  { key: "mistral-7b", label: "Mistral 7B", desc: "Mais rápido" },
];

// ── ScoreView ─────────────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number }) {
  const color = value >= 8 ? "bg-green-500" : value >= 6 ? "bg-blue-500" : value >= 4 ? "bg-yellow-500" : "bg-zinc-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value * 10}%` }} />
      </div>
      <span className="text-xs text-zinc-400 w-4 text-right">{value}</span>
    </div>
  );
}

function ScoreView({ score }: { score: StartupScore }) {
  return (
    <div className="space-y-4">
      {/* Total */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="space-y-2">
                <p className="text-xs text-zinc-500 uppercase tracking-wider">Score de Fit NVIDIA</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-black text-zinc-100">{score.total}</span>
                  <span className="text-zinc-600">/100</span>
                </div>
                <Badge className={`text-sm border px-3 py-0.5 ${TIER_COLOR[score.tier]}`}>Tier {score.tier}</Badge>
              </div>
              <RadarChart score={score} size={160} />
            </div>
          </div>
          {score.recommendation && <p className="text-zinc-400 text-sm mt-4">{score.recommendation}</p>}
        </CardContent>
      </Card>

      {/* Dimensões */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="pt-5 space-y-4">
          {SCORE_DIMS.map(({ key, label, weight }) => {
            const dim = score[key] as DimensionScore;
            return (
              <div key={key} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-400">{label}</span>
                  <span className="text-xs text-zinc-600">{weight}</span>
                </div>
                <ScoreBar value={dim.score} />
                <p className="text-xs text-zinc-600 leading-relaxed">{dim.rationale}</p>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

// ── ScoreSidebar ──────────────────────────────────────────────────────────────

const DIM_LABELS: Record<string, { label: string; weight: string }> = {
  technical_fit:    { label: "Fit Técnico",          weight: "30%" },
  ai_maturity:      { label: "Maturidade IA",        weight: "25%" },
  market_potential: { label: "Potencial de Mercado", weight: "20%" },
  strategic_value:  { label: "Valor Estratégico",    weight: "15%" },
  urgency:          { label: "Urgência",             weight: "10%" },
};

function ScoreSidebar({ score }: { score: StartupScore }) {
  const [open, setOpen] = useState<string | null>(null);
  const dims = [
    { key: "technical_fit",    data: score.technical_fit },
    { key: "ai_maturity",      data: score.ai_maturity },
    { key: "market_potential", data: score.market_potential },
    { key: "strategic_value",  data: score.strategic_value },
    { key: "urgency",          data: score.urgency },
  ];
  const color = score.total >= 80 ? "#22c55e" : score.total >= 65 ? "#3b82f6" : score.total >= 50 ? "#eab308" : "#71717a";

  return (
    <div className="space-y-3 sticky top-4">
      {/* radar + totais */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="pt-4 pb-3 flex flex-col items-center gap-2">
          <RadarChart score={score} size={90} />
          <div className="flex items-baseline gap-1.5">
            <span className="text-3xl font-black text-zinc-100">{score.total}</span>
            <span className="text-zinc-600 text-sm">/100</span>
          </div>
          <Badge className={`text-xs border px-3 ${TIER_COLOR[score.tier]}`}>Tier {score.tier}</Badge>
        </CardContent>
      </Card>

      {/* dimensões expansíveis */}
      <div className="space-y-1.5">
        {dims.map(({ key, data }) => {
          const { label, weight } = DIM_LABELS[key];
          const isOpen = open === key;
          const barW = `${data.score * 10}%`;
          return (
            <button key={key} onClick={() => setOpen(isOpen ? null : key)}
              className="w-full text-left rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors overflow-hidden">
              <div className="px-3 py-2.5 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-300">{label}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-600">{weight}</span>
                    <span className="text-sm font-bold" style={{ color }}>{data.score}</span>
                    <span className="text-zinc-700 text-xs">{isOpen ? "▲" : "▼"}</span>
                  </div>
                </div>
                {/* barra */}
                <div className="h-1 rounded-full bg-zinc-800 overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: barW, backgroundColor: color }} />
                </div>
              </div>
              {isOpen && (
                <div className="px-3 pb-3 pt-0">
                  <p className="text-xs text-zinc-400 leading-relaxed">{data.rationale}</p>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── EcosystemGraph ────────────────────────────────────────────────────────────

const ECO_PRIORITY_COLOR: Record<string, string> = {
  high: "#22c55e", medium: "#3b82f6", low: "#71717a",
};

function wrapLabel(text: string, maxChars = 14): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > maxChars) { lines.push(cur.trim()); cur = w; }
    else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 3);
}

interface SynergyPoint { title: string; detail: string; }
interface SynergyResult {
  has_synergy: boolean;
  synergy_points: SynergyPoint[];
  integration_opportunity: string;
  no_synergy_reason: string;
}

function EcosystemGraph({ report, peers }: { report: BriefingReport; peers: BriefingReport[] }) {
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ kind: "tech" | "peer"; id: string } | null>(null);
  const [synergyCache, setSynergyCache] = useState<Record<string, SynergyResult | "loading" | "error">>({});
  const selectedTech = selected?.kind === "tech" ? selected.id : null;
  const selectedPeer = selected?.kind === "peer" ? selected.id : null;

  const myRecs = report.recommendations ?? [];
  const myRecMap = new Map(myRecs.map(r => [r.nvidia_tech, r]));
  const myNvidiaTechSet = new Set(myRecs.map(r => r.nvidia_tech));

  // Só techs recomendadas para a startup atual
  const allTechIds = myRecs.map(r => r.nvidia_tech);

  const W = 900, H = 600, CX = 450, CY = 300;
  const R_TECH = 130, R_PEER = 250;

  const techNodes = allTechIds.map((id, i) => {
    const angle = (2 * Math.PI * i) / Math.max(allTechIds.length, 1) - Math.PI / 2;
    const rec = myRecMap.get(id)!;
    return { id, angle, rec,
      x: CX + R_TECH * Math.cos(angle),
      y: CY + R_TECH * Math.sin(angle),
    };
  });
  const techById = Object.fromEntries(techNodes.map(t => [t.id, t]));

  const allNvidiaLower = new Set(allTechIds.map(t => t.toLowerCase()));

  const rawPeers = peers.map(peer => {
    const peerRecTechs = new Set((peer.recommendations ?? []).map(r => r.nvidia_tech));
    const connectedTechs = techNodes.filter(t => peerRecTechs.has(t.id));
    if (connectedTechs.length === 0) return null;
    const avgAngle = connectedTechs.reduce((s, t) => s + t.angle, 0) / connectedTechs.length;
    const extraTechs = (peer.startup.tech_stack ?? [])
      .filter(t => !allNvidiaLower.has(t.toLowerCase()))
      .slice(0, 3);
    return { name: peer.startup.name, logo: peer.startup.logo_url, idealAngle: avgAngle, connectedTechs: connectedTechs.map(t => t.id), extraTechs };
  }).filter(Boolean) as { name: string; logo: string | null; idealAngle: number; connectedTechs: string[]; extraTechs: string[] }[];

  // Spread peers that are too close angularly (min gap ~0.3 rad ≈ 17°)
  const MIN_GAP = 0.3;
  const sorted = [...rawPeers].sort((a, b) => a.idealAngle - b.idealAngle);
  for (let pass = 0; pass < 5; pass++) {
    for (let i = 1; i < sorted.length; i++) {
      const gap = sorted[i].idealAngle - sorted[i - 1].idealAngle;
      if (gap < MIN_GAP) {
        const mid = (sorted[i].idealAngle + sorted[i - 1].idealAngle) / 2;
        sorted[i - 1] = { ...sorted[i - 1], idealAngle: mid - MIN_GAP / 2 };
        sorted[i]     = { ...sorted[i],     idealAngle: mid + MIN_GAP / 2 };
      }
    }
  }

  const peerNodes = sorted
    .filter(p => {
      const s = synergyCache[p.name];
      // exclude only when synergy explicitly returned false; keep while loading/unknown
      return !(s && s !== "loading" && s !== "error" && !s.has_synergy);
    })
    .map(p => ({
      ...p,
      x: CX + R_PEER * Math.cos(p.idealAngle),
      y: CY + R_PEER * Math.sin(p.idealAngle),
    })) as {
    name: string; logo: string | null; x: number; y: number;
    connectedTechs: string[]; extraTechs: string[];
  }[];

  const svgRef = useRef<SVGSVGElement>(null);
  const panRef = useRef({ x: 0, y: 0 });
  const zoomRef = useRef(1);

  // Sync refs so wheel handler (non-React closure) stays current
  useEffect(() => { panRef.current = pan; }, [pan]);
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);

  // Non-passive wheel listener — prevents page scroll inside graph area
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const rect = el.getBoundingClientRect();
      const ox = e.clientX - rect.left;
      const oy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.12 : 0.88;
      const z = zoomRef.current;
      const p = panRef.current;
      const next = Math.min(8, Math.max(0.15, z * factor));
      setPan({ x: ox - (ox - p.x) * (next / z), y: oy - (oy - p.y) * (next / z) });
      setZoom(next);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, []);

  // Auto-fit: center startup + NVIDIA tech ring fills ~60% of container on mount
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    const scaleX = width / W;
    const scaleY = height / H;
    const baseScale = Math.min(scaleX, scaleY);
    const fitZoom = Math.min(2, (Math.min(width, height) * 0.38) / (R_TECH * baseScale * W / width));
    const cx = CX * baseScale;
    const cy = CY * baseScale;
    setPan({ x: width / 2 - cx * fitZoom, y: height / 2 - cy * fitZoom });
    setZoom(fitZoom);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.startup.name]);

  // Pre-fetch synergy for all peers so the graph can filter out no-synergy ones
  useEffect(() => {
    for (const peer of peers) {
      const name = peer.startup.name;
      if (synergyCache[name]) continue;
      setSynergyCache(c => ({ ...c, [name]: "loading" }));
      fetch("http://localhost:8000/synergy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: report, peer }),
      })
        .then(r => r.json())
        .then((res: SynergyResult) => setSynergyCache(c => ({ ...c, [name]: res })))
        .catch(() => setSynergyCache(c => ({ ...c, [name]: "error" })));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.startup.name, peers.length]);

  function onMouseDown(e: React.MouseEvent) { setDragging(true); setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y }); }
  function onMouseMove(e: React.MouseEvent) { if (!dragging) return; setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }); }
  function onMouseUp() { setDragging(false); }

  function applyZoom(factor: number) {
    const el = svgRef.current;
    const rect = el?.getBoundingClientRect();
    const ox = rect ? rect.width / 2 : 0;
    const oy = rect ? rect.height / 2 : 0;
    const z = zoomRef.current;
    const p = panRef.current;
    const next = Math.min(8, Math.max(0.15, z * factor));
    setPan({ x: ox - (ox - p.x) * (next / z), y: oy - (oy - p.y) * (next / z) });
    setZoom(next);
  }

  const dimAll = hovered !== null;

  function techDim(id: string) {
    if (!dimAll) return false;
    // dim if not directly connected to hovered tech/peer
    if (hovered === id) return false;
    const hoveredPeer = peerNodes.find(p => p.name === hovered);
    if (hoveredPeer) return !hoveredPeer.connectedTechs.includes(id);
    return true;
  }
  function peerDim(name: string) {
    if (!dimAll) return false;
    const peer = peerNodes.find(p => p.name === name)!;
    if (hovered === name) return false;
    return !peer.connectedTechs.includes(hovered ?? "");
  }

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        style={{ cursor: dragging ? "grabbing" : "grab", display: "block", minHeight: 480 }}
        onMouseDown={onMouseDown} onMouseMove={onMouseMove}
        onMouseUp={onMouseUp} onMouseLeave={onMouseUp}
      >
        <defs>
          <radialGradient id="eco-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#a78bfa" stopOpacity="0" />
          </radialGradient>
          <clipPath id="eco-clip-center"><circle cx={CX} cy={CY} r={30} /></clipPath>
          {peerNodes.map(pn => (
            <clipPath key={`clip-${pn.name}`} id={`eco-clip-${pn.name.replace(/\s/g, "")}`}>
              <circle cx={pn.x} cy={pn.y} r={16} />
            </clipPath>
          ))}
        </defs>

        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
          <circle cx={CX} cy={CY} r={80} fill="url(#eco-glow)" />

          {/* edges: center → NVIDIA techs */}
          {techNodes.map(tn => {
            const color = ECO_PRIORITY_COLOR[tn.rec.priority ?? "low"];
            return (
              <line key={`mine-${tn.id}`} x1={CX} y1={CY} x2={tn.x} y2={tn.y}
                stroke={color} strokeWidth={tn.rec?.priority === "high" ? 2.5 : 1.5}
                opacity={techDim(tn.id) ? 0.05 : 0.55}
                style={{ transition: "opacity 0.2s" }}
              />
            );
          })}

          {/* edges: peer → their NVIDIA techs */}
          {peerNodes.map(pn =>
            pn.connectedTechs.map(tid => {
              const tn = techById[tid];
              if (!tn) return null;
              return (
                <line key={`${pn.name}-${tid}`}
                  x1={tn.x} y1={tn.y} x2={pn.x} y2={pn.y}
                  stroke="#3f3f46" strokeWidth={1} strokeDasharray="5 4"
                  opacity={peerDim(pn.name) && techDim(tid) ? 0.04 : 0.3}
                  style={{ transition: "opacity 0.2s" }}
                />
              );
            })
          )}

          {/* central node — startup (roxo para diferenciar das techs NVIDIA verdes) */}
          <circle cx={CX} cy={CY} r={40} fill="#1a1625" stroke="#7c3aed" strokeWidth={2.5} />
          <circle cx={CX} cy={CY} r={44} fill="none" stroke="#7c3aed" strokeWidth={0.5} strokeOpacity={0.3} />
          {report.startup.logo_url
            ? <image href={report.startup.logo_url} x={CX - 22} y={CY - 22} width={44} height={44} clipPath="url(#eco-clip-center)" />
            : <text x={CX} y={CY} textAnchor="middle" dominantBaseline="middle" fill="#a78bfa" fontSize={18} fontWeight="bold">{report.startup.name.charAt(0)}</text>
          }
          <text x={CX} y={CY + 58} textAnchor="middle" fill="#c4b5fd" fontSize={10} fontWeight="600">{report.startup.name}</text>

          {/* NVIDIA tech ring */}
          {techNodes.map(tn => {
            const isSelected = selectedTech === tn.id;
            const color = ECO_PRIORITY_COLOR[tn.rec.priority ?? "low"];
            const dim = techDim(tn.id) && !isSelected;
            const lines = wrapLabel(tn.id, 13);
            return (
              <g key={tn.id}
                onMouseEnter={() => setHovered(tn.id)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => setSelected(isSelected ? null : { kind: "tech", id: tn.id })}
                style={{ cursor: "pointer", opacity: dim ? 0.15 : 1, transition: "opacity 0.2s" }}
              >
                {isSelected && <circle cx={tn.x} cy={tn.y} r={33} fill="none" stroke={color} strokeWidth={1} strokeOpacity={0.4} />}
                <circle cx={tn.x} cy={tn.y} r={27} fill={isSelected ? "#111" : "#1c1c1e"}
                  stroke={color} strokeWidth={isSelected ? 2.5 : 1.8} />
                {lines.map((line, li) => (
                  <text key={li} x={tn.x} textAnchor="middle" dominantBaseline="middle"
                    fill={isSelected ? "#fff" : "#e4e4e7"}
                    fontSize={6.5} fontWeight="500"
                    y={tn.y + (li - (lines.length - 1) / 2) * 8}
                  >{line}</text>
                ))}
                <circle cx={tn.x + 24} cy={tn.y - 24} r={4} fill={color} />
                {hovered === tn.id && !isSelected && (
                  <g style={{ pointerEvents: "none" }}>
                    <rect x={tn.x - 55} y={tn.y - 44} width={110} height={14} rx={3} fill="#27272a" stroke={color} strokeWidth={0.8} />
                    <text x={tn.x} y={tn.y - 34} textAnchor="middle" fill="#d4d4d8" fontSize={6.5}>clique para ver contribuição</text>
                  </g>
                )}
              </g>
            );
          })}

          {/* peer startup nodes */}
          {peerNodes.map(pn => {
            const dim = peerDim(pn.name);
            const isSel = selectedPeer === pn.name;
            return (
              <g key={pn.name}
                onMouseEnter={() => setHovered(pn.name)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => {
                  if (isSel) { setSelected(null); return; }
                  setSelected({ kind: "peer", id: pn.name });
                  if (!synergyCache[pn.name]) {
                    setSynergyCache(c => ({ ...c, [pn.name]: "loading" }));
                    const peerReport = peers.find(p => p.startup.name === pn.name);
                    if (peerReport) {
                      fetch("http://localhost:8000/synergy", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ target: report, peer: peerReport }),
                      })
                        .then(r => r.json())
                        .then((res: SynergyResult) => setSynergyCache(c => ({ ...c, [pn.name]: res })))
                        .catch(() => setSynergyCache(c => ({ ...c, [pn.name]: "error" })));
                    }
                  }
                }}
                style={{ opacity: dim ? 0.12 : 1, transition: "opacity 0.2s", cursor: "pointer" }}
              >
                {isSel && <circle cx={pn.x} cy={pn.y} r={26} fill="none" stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="4 3" />}
                <circle cx={pn.x} cy={pn.y} r={20} fill={isSel ? "#1a1625" : "#1c1c1e"}
                  stroke={isSel ? "#7c3aed" : hovered === pn.name ? "#71717a" : "#3f3f46"}
                  strokeWidth={isSel ? 2 : 1.2} />
                {pn.logo
                  ? <image href={pn.logo} x={pn.x - 12} y={pn.y - 12} width={24} height={24} clipPath={`url(#eco-clip-${pn.name.replace(/\s/g, "")})`} />
                  : <text x={pn.x} y={pn.y} textAnchor="middle" dominantBaseline="middle" fill={isSel ? "#c4b5fd" : "#71717a"} fontSize={9} fontWeight="600">{pn.name.charAt(0)}</text>
                }
                <text x={pn.x} y={pn.y + 30} textAnchor="middle" fill={isSel ? "#c4b5fd" : "#52525b"} fontSize={7.5} fontWeight="500">{pn.name}</text>
                {!isSel && pn.extraTechs.map((tech, ti) => (
                  <text key={tech} x={pn.x} y={pn.y + 41 + ti * 9} textAnchor="middle" fill="#3f3f46" fontSize={6}>· {tech}</text>
                ))}
                {hovered === pn.name && !isSel && (
                  <g style={{ pointerEvents: "none" }}>
                    <rect x={pn.x - 60} y={pn.y - 28} width={120} height={14} rx={3} fill="#27272a" stroke="#52525b" strokeWidth={0.8} />
                    <text x={pn.x} y={pn.y - 18} textAnchor="middle" fill="#a1a1aa" fontSize={6.5}>clique para ver sinergias</text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Painel de contribuição — aparece ao clicar em tech NVIDIA */}
      {selectedTech && (() => {
        const tn = techNodes.find(t => t.id === selectedTech);
        const rec = tn?.rec;
        if (!tn || !rec) return null;
        const color = ECO_PRIORITY_COLOR[rec.priority ?? "low"];
        const peersUsing = peerNodes.filter(p => p.connectedTechs.includes(selectedTech));

        // Contexto da startup pra enriquecer a explicação
        const relevantUseCases = (report.startup.use_cases ?? []).slice(0, 3);
        const relevantProducts = (report.startup.products ?? []).slice(0, 2);

        return (
          <div className="border-t border-zinc-800 p-4 animate-in fade-in slide-in-from-bottom-2 duration-200">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full shrink-0 mt-1" style={{ backgroundColor: color }} />
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-0.5">
                    Como contribui para <span className="text-violet-400">{report.startup.name}</span>
                  </p>
                  <h3 className="text-base font-semibold" style={{ color }}>{selectedTech}</h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-medium border" style={{ color, borderColor: color, background: `${color}15` }}>
                  {rec.priority === "high" ? "Alta" : rec.priority === "medium" ? "Média" : "Baixa"} prioridade
                </span>
              </div>
              <button onClick={() => setSelected(null)} className="text-zinc-600 hover:text-zinc-300 text-lg leading-none transition-colors">×</button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {/* Justificativa técnica */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 col-span-1">
                <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Contribuição técnica</p>
                <p className="text-zinc-300 text-xs leading-relaxed">{rec.technical_justification}</p>
                {relevantUseCases.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-zinc-800">
                    <p className="text-[9px] text-zinc-600 uppercase tracking-wider mb-1.5">Casos de uso que {selectedTech} endereça</p>
                    {relevantUseCases.map(u => (
                      <div key={u} className="flex items-start gap-1.5 mb-1">
                        <span style={{ color }} className="text-[9px] mt-0.5 shrink-0">▸</span>
                        <span className="text-zinc-400 text-[10px] leading-snug">{u}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Valor de negócio */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 col-span-1">
                <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Valor de negócio</p>
                <p className="text-zinc-300 text-xs leading-relaxed">{rec.business_justification}</p>
                {relevantProducts.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-zinc-800">
                    <p className="text-[9px] text-zinc-600 uppercase tracking-wider mb-1.5">Produtos que se beneficiam</p>
                    {relevantProducts.map(p => (
                      <div key={p} className="flex items-start gap-1.5 mb-1">
                        <span className="text-blue-400 text-[9px] mt-0.5 shrink-0">▸</span>
                        <span className="text-zinc-400 text-[10px] leading-snug">{p}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Próximo passo + validação de pares */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 col-span-1">
                {rec.next_action && (
                  <>
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Próximo passo</p>
                    <p className="text-zinc-300 text-xs leading-relaxed">{rec.next_action}</p>
                  </>
                )}
                {peersUsing.length > 0 && (
                  <div className={rec.next_action ? "mt-3 pt-2 border-t border-zinc-800" : ""}>
                    <p className="text-[9px] text-zinc-600 uppercase tracking-wider mb-1.5">Validação — também usam {selectedTech}</p>
                    {peersUsing.map(p => (
                      <div key={p.name} className="flex items-center gap-1.5 mb-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-zinc-600 shrink-0" />
                        <span className="text-zinc-500 text-[10px]">{p.name}</span>
                      </div>
                    ))}
                    <p className="text-[9px] text-zinc-600 mt-1.5">Sinal de mercado: outras startups do ecossistema já adotam esta tech.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Painel de sinergias — aparece ao clicar em startup par */}
      {selectedPeer && (() => {
        const pn = peerNodes.find(p => p.name === selectedPeer);
        if (!pn) return null;
        const synergy = synergyCache[selectedPeer];
        const sharedNvidiaNames = pn.connectedTechs;

        return (
          <div className="border-t border-zinc-800 p-4 animate-in fade-in slide-in-from-bottom-2 duration-200">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-violet-500 shrink-0 mt-1" />
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-0.5">
                    Como contribui para <span className="text-violet-400">{report.startup.name}</span>
                  </p>
                  <h3 className="text-base font-semibold text-violet-300">{selectedPeer}</h3>
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="text-zinc-600 hover:text-zinc-300 text-lg leading-none transition-colors">×</button>
            </div>

            {synergy === "loading" && (
              <div className="flex items-center gap-2 py-6 justify-center text-zinc-500 text-xs">
                <div className="w-4 h-4 border border-violet-500 border-t-transparent rounded-full animate-spin" />
                Analisando sinergia com IA...
              </div>
            )}

            {synergy === "error" && (
              <p className="text-red-400 text-xs py-4 text-center">Erro ao gerar análise. Tente clicar novamente.</p>
            )}

            {synergy && synergy !== "loading" && synergy !== "error" && !synergy.has_synergy && (
              <div className="py-4 text-center">
                <p className="text-zinc-500 text-xs">{synergy.no_synergy_reason || `Sinergia não identificada entre ${selectedPeer} e ${report.startup.name}.`}</p>
              </div>
            )}

            {synergy && synergy !== "loading" && synergy !== "error" && synergy.has_synergy && (
              <div className="space-y-3">
                {/* Pontos de sinergia gerados por IA */}
                <div className="grid grid-cols-2 gap-3">
                  {synergy.synergy_points.map((sp, i) => (
                    <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                      <p className="text-[10px] font-semibold text-violet-300 uppercase tracking-wider mb-1.5">{sp.title}</p>
                      <p className="text-zinc-300 text-[11px] leading-relaxed">{sp.detail}</p>
                    </div>
                  ))}
                </div>
                {/* Integração NVIDIA + oportunidade */}
                <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3 flex flex-col gap-2">
                  {synergy.integration_opportunity && (
                    <div>
                      <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">Oportunidade de integração</p>
                      <p className="text-zinc-300 text-[11px] leading-relaxed">{synergy.integration_opportunity}</p>
                    </div>
                  )}
                  {sharedNvidiaNames.length > 0 && (
                    <div className="pt-2 border-t border-zinc-800">
                      <p className="text-[9px] text-zinc-600 uppercase tracking-wider mb-1">Ponto de integração NVIDIA</p>
                      <div className="flex flex-wrap gap-1">
                        {sharedNvidiaNames.map(t => (
                          <span key={t} className="px-1.5 py-0.5 rounded bg-green-950/40 border border-green-800/30 text-[9px] text-green-400">{t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {!synergy && (
              <div className="flex items-center gap-2 py-6 justify-center text-zinc-600 text-xs">
                <div className="w-4 h-4 border border-zinc-700 border-t-transparent rounded-full animate-spin" />
                Carregando análise...
              </div>
            )}
          </div>
        );
      })()}

      <div className="px-4 py-2.5 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-600">
        <div className="flex items-center gap-5">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-violet-500" /> Startup analisada</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500" /> NVIDIA · alta prioridade</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500" /> NVIDIA · média/baixa</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-800 border border-blue-600" style={{ borderStyle: "dashed" }} /> NVIDIA · só pares</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => applyZoom(1.25)} className="w-6 h-6 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm leading-none transition-colors flex items-center justify-center">+</button>
          <span className="text-zinc-600 text-xs w-10 text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={() => applyZoom(0.8)} className="w-6 h-6 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm leading-none transition-colors flex items-center justify-center">−</button>
          <button onClick={() => {
            const el = svgRef.current;
            if (!el) return;
            const { width, height } = el.getBoundingClientRect();
            const baseScale = Math.min(width / W, height / H);
            const fitZoom = Math.min(2, (Math.min(width, height) * 0.38) / (R_TECH * baseScale * W / width));
            setPan({ x: width / 2 - CX * baseScale * fitZoom, y: height / 2 - CY * baseScale * fitZoom });
            setZoom(fitZoom);
          }} className="ml-1 text-zinc-600 hover:text-zinc-400 transition-colors">Resetar</button>
        </div>
      </div>
    </div>
  );
}

// ── StartupDetail ─────────────────────────────────────────────────────────────

function StartupDetail({ report, score, peers }: { report: BriefingReport; score: StartupScore | null; peers: BriefingReport[] }) {
  return (
    <Tabs defaultValue="recommendations">
      <TabsList className="bg-zinc-900 border border-zinc-800">
        <TabsTrigger value="overview" className="data-[state=active]:bg-zinc-800">Visão Geral</TabsTrigger>
        <TabsTrigger value="recommendations" className="data-[state=active]:bg-zinc-800">
          Recomendações ({report.recommendations?.length ?? 0})
        </TabsTrigger>
        <TabsTrigger value="ecosystem" className="data-[state=active]:bg-zinc-800">
          Relações {peers.length > 0 ? `(${peers.length})` : ""}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="overview" className="mt-4 space-y-4">

        {/* Main grid: conteúdo + score */}
        <div className="grid grid-cols-[1fr_200px] gap-4 items-start">
          <div className="space-y-4">

            {/* Sobre + meta stats inline */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
              {(report.startup.description || report.summary) && (
                <>
                  <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Sobre</p>
                  <p className="text-zinc-200 text-sm leading-relaxed">{report.startup.description || report.summary}</p>
                </>
              )}
              {/* stat chips inline — só renderiza se tiver algum */}
              {(report.startup.founding_year || report.startup.hq_location || report.startup.employee_count || report.startup.funding_usd || report.startup.funding_stage || report.startup.business_model || report.startup.target_market) && (
                <div className="pt-2 border-t border-zinc-800 flex flex-wrap gap-2">
                  {report.startup.founding_year && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-300">
                      {report.startup.founding_year}
                    </span>
                  )}
                  {report.startup.hq_location && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-300">
                      {report.startup.hq_location}
                    </span>
                  )}
                  {report.startup.employee_count && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-300">
                      ~{report.startup.employee_count.toLocaleString("pt-BR")} pessoas
                    </span>
                  )}
                  {(report.startup.funding_usd || report.startup.funding_stage) && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-green-500/10 border border-green-500/20 text-xs text-green-400">
                      {report.startup.funding_stage && <span>{report.startup.funding_stage}</span>}
                      {report.startup.funding_usd && <span className="font-semibold">USD {(report.startup.funding_usd / 1_000_000).toFixed(1)}M</span>}
                    </span>
                  )}
                  {report.startup.business_model && (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-400">
                      {report.startup.business_model}
                    </span>
                  )}
                  {report.startup.target_market && (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-400">
                      {report.startup.target_market}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Produtos & Casos de Uso */}
            {((report.startup.products?.length ?? 0) > 0 || (report.startup.use_cases?.length ?? 0) > 0) && (
              <div className="grid grid-cols-2 gap-3">
                {(report.startup.products?.length ?? 0) > 0 && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2.5">Produtos</p>
                    <div className="space-y-1.5">
                      {(report.startup.products ?? []).map(p => (
                        <div key={p} className="flex items-start gap-2">
                          <span className="text-green-500 text-xs mt-0.5 shrink-0">▸</span>
                          <span className="text-zinc-300 text-xs leading-snug">{p}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {(report.startup.use_cases?.length ?? 0) > 0 && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2.5">Casos de Uso</p>
                    <div className="space-y-1.5">
                      {(report.startup.use_cases ?? []).map(u => (
                        <div key={u} className="flex items-start gap-2">
                          <span className="text-blue-400 text-xs mt-0.5 shrink-0">▸</span>
                          <span className="text-zinc-300 text-xs leading-snug">{u}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Stack tecnológica */}
            {(report.startup.tech_stack?.length ?? 0) > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2.5">Stack Tecnológica</p>
                <div className="flex flex-wrap gap-1.5">
                  {(report.startup.tech_stack ?? []).map(t => (
                    <Badge key={t} variant="outline" className="text-xs border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-zinc-100 transition-colors cursor-default">{t}</Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Fundadores + Investidores */}
            {((report.startup.founders?.length ?? 0) > 0 || (report.startup.investors?.length ?? 0) > 0) && (
              <div className="grid grid-cols-2 gap-3">
                {(report.startup.founders?.length ?? 0) > 0 && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2.5">Fundadores</p>
                    <div className="space-y-1.5">
                      {(report.startup.founders ?? []).map(f => (
                        <div key={f} className="flex items-center gap-2">
                          <div className="w-5 h-5 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-[9px] text-zinc-400 shrink-0 font-medium">
                            {f.charAt(0).toUpperCase()}
                          </div>
                          <span className="text-zinc-300 text-xs">{f}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {(report.startup.investors?.length ?? 0) > 0 && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2.5">Investidores</p>
                    <div className="space-y-1.5">
                      {(report.startup.investors ?? []).map(inv => (
                        <div key={inv} className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
                          <span className="text-zinc-400 text-xs">{inv}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Links externos */}
            {(report.startup.website || report.startup.github_url || report.startup.linkedin_url) && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center gap-3">
                <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider shrink-0">Links</p>
                <div className="flex gap-2 flex-wrap">
                  {report.startup.website && (
                    <a href={report.startup.website} target="_blank" rel="noreferrer"
                      className="px-3 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs transition-colors border border-zinc-700">
                      Site oficial
                    </a>
                  )}
                  {report.startup.github_url && (
                    <a href={report.startup.github_url} target="_blank" rel="noreferrer"
                      className="px-3 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs transition-colors border border-zinc-700">
                      GitHub
                    </a>
                  )}
                  {report.startup.linkedin_url && (
                    <a href={report.startup.linkedin_url} target="_blank" rel="noreferrer"
                      className="px-3 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs transition-colors border border-zinc-700">
                      LinkedIn
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* Briefing NVIDIA */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 border-l-2 border-l-green-500/60">
              <p className="text-[10px] font-medium text-green-500/80 uppercase tracking-wider mb-2">Briefing Executivo NVIDIA</p>
              <p className="text-zinc-300 text-sm leading-relaxed">{report.summary}</p>
            </div>

          </div>

          {/* Score sidebar */}
          {score && <ScoreSidebar score={score} />}
        </div>
      </TabsContent>


      <TabsContent value="recommendations" className="space-y-3 mt-4">
        {(report.recommendations?.length ?? 0) === 0 && (
          <p className="text-zinc-500 text-sm">Nenhuma recomendação gerada. Reanalise a startup para obter sugestões de tecnologias NVIDIA.</p>
        )}
        {(report.recommendations ?? []).map((rec, i) => (
          <Card key={i} className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-100">{rec.nvidia_tech}</span>
                <div className="flex gap-2">
                  <Badge className={`text-xs border ${PRIORITY_COLOR[rec.priority]}`}>
                    {{ high: "alta", medium: "média", low: "baixa" }[rec.priority] ?? rec.priority}
                  </Badge>
                  <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400">
                    complexidade {{ high: "alta", medium: "média", low: "baixa" }[rec.complexity] ?? rec.complexity}
                  </Badge>
                </div>
              </div>
              <p className="text-zinc-300 text-sm">{rec.technical_justification}</p>
              <p className="text-zinc-500 text-sm">{rec.business_justification}</p>
              {rec.next_action && (
                <div className="pt-2 border-t border-zinc-800">
                  <p className="text-xs text-zinc-400">{rec.next_action}</p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </TabsContent>

      <TabsContent value="ecosystem" className="mt-4">
        {(report.recommendations?.length ?? 0) === 0 ? (
          <p className="text-zinc-500 text-sm">Sem recomendações geradas — reanalise para ver o grafo de relações.</p>
        ) : (
          <EcosystemGraph report={report} peers={peers} />
        )}
      </TabsContent>
    </Tabs>
  );
}

// ── DebateView ────────────────────────────────────────────────────────────────

function DebateView({ result, nameA, nameB }: { result: DebateResult; nameA: string; nameB: string }) {
  const [expanded, setExpanded] = useState(false);
  const rounds = ["opening", "attack", "rebuttal"] as const;

  return (
    <div className="space-y-4">
      <Card className="bg-zinc-900 border-green-900/40 border">
        <CardContent className="pt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-center flex-1">
              <p className="font-bold text-zinc-100">{nameA}</p>
              <p className={`text-5xl font-black mt-1 ${result.verdict.winner === nameA ? "text-green-400" : "text-zinc-600"}`}>
                {result.verdict.score_a}
              </p>
            </div>
            <div className="text-zinc-700 text-lg font-bold px-4">VS</div>
            <div className="text-center flex-1">
              <p className="font-bold text-zinc-100">{nameB}</p>
              <p className={`text-5xl font-black mt-1 ${result.verdict.winner === nameB ? "text-green-400" : "text-zinc-600"}`}>
                {result.verdict.score_b}
              </p>
            </div>
          </div>
          <div className="text-center">
            <Badge className="bg-green-500/20 text-green-400 border border-green-500/30 px-4 py-1">
              Vencedor: {result.verdict.winner}
            </Badge>
          </div>
          <div className="pt-3 border-t border-zinc-800 space-y-2">
            <p className="text-zinc-300 text-sm leading-relaxed">{result.verdict.reasoning}</p>
          </div>
          <button
            onClick={() => setExpanded(v => !v)}
            className="w-full text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-800 rounded-md py-2 transition-colors"
          >
            {expanded ? "▲ Ocultar transcrição" : "▼ Ver debate completo"}
          </button>
        </CardContent>
      </Card>

      {expanded && rounds.map((round) => {
        const movesA = result.rounds.filter(m => m.agent === nameA && m.round_type === round);
        const movesB = result.rounds.filter(m => m.agent === nameB && m.round_type === round);
        return (
          <div key={round}>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">{ROUND_LABEL[round]}</p>
            <div className="grid grid-cols-2 gap-4">
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-500">{nameA}</CardTitle></CardHeader>
                <CardContent><p className="text-zinc-300 text-sm leading-relaxed">{movesA[0]?.argument || "—"}</p></CardContent>
              </Card>
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader className="pb-2"><CardTitle className="text-xs text-zinc-500">{nameB}</CardTitle></CardHeader>
                <CardContent><p className="text-zinc-300 text-sm leading-relaxed">{movesB[0]?.argument || "—"}</p></CardContent>
              </Card>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── CompareTab ────────────────────────────────────────────────────────────────

function ModelSelect({ value, onChange, label, accentClass }: {
  value: string; onChange: (v: string) => void; label: string; accentClass: string;
}) {
  return (
    <div className="space-y-1.5">
      <p className={`text-xs font-medium ${accentClass}`}>{label}</p>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-zinc-800 border border-zinc-700 rounded-md text-zinc-300 text-xs px-3 py-2 focus:outline-none focus:ring-1 focus:ring-zinc-600 cursor-pointer"
      >
        {MODELS.map(m => (
          <option key={m.key} value={m.key}>{m.label} — {m.desc}</option>
        ))}
      </select>
    </div>
  );
}

function DropZone({ label, report, accentClass, onDrop, onClear, dragOver, onDragOver, onDragLeave }: {
  label: string;
  report: BriefingReport | null;
  accentClass: string;
  onDrop: (e: React.DragEvent) => void;
  onClear: () => void;
  dragOver: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
}) {
  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      className={`rounded-xl border-2 border-dashed transition-colors min-h-[110px] p-4 ${
        dragOver ? "border-zinc-500 bg-zinc-800/60" : "border-zinc-800 bg-zinc-900/40"
      }`}
    >
      <p className={`text-xs font-medium mb-3 ${accentClass}`}>{label}</p>
      {report ? (
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <p className="font-semibold text-zinc-100 text-sm">{report.startup.name}</p>
            {report.startup.sector && <p className="text-zinc-500 text-xs">{report.startup.sector}</p>}
            {report.startup.classification && (
              <Badge className={`text-xs border ${CLASSIFICATION_COLOR[report.startup.classification] ?? PRIORITY_COLOR.low}`}>
                {report.startup.classification}
              </Badge>
            )}
          </div>
          <button onClick={onClear} className="text-zinc-600 hover:text-zinc-400 text-lg leading-none mt-0.5">×</button>
        </div>
      ) : (
        <p className="text-zinc-700 text-sm text-center pt-3">Arraste uma startup aqui</p>
      )}
    </div>
  );
}

function CompareTab({ history }: { history: BriefingReport[] }) {
  const [pickA, setPickA] = useState<string>("");
  const [pickB, setPickB] = useState<string>("");
  const [modelA, setModelA] = useState("llama-3.3-70b");
  const [modelB, setModelB] = useState("deepseek-r1");
  const [judgeModel, setJudgeModel] = useState("llama-3.3-70b");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DebateResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<"A" | "B" | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);

  const reportA = history.find(r => r.startup.name === pickA) ?? null;
  const reportB = history.find(r => r.startup.name === pickB) ?? null;

  function handleDrop(slot: "A" | "B") {
    return (e: React.DragEvent) => {
      e.preventDefault();
      const name = e.dataTransfer.getData("startup");
      if (!name) return;
      if (slot === "A") { if (pickB !== name) setPickA(name); }
      else { if (pickA !== name) setPickB(name); }
      setDragOver(null);
    };
  }

  async function runDebate() {
    if (!reportA || !reportB) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("http://localhost:8000/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_a: reportA, report_b: reportB, model_a: modelA, model_b: modelB, judge_model: judgeModel }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Erro");
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }

  if (history.length < 2) {
    return <div className="text-center py-16 text-zinc-600">Analise pelo menos 2 startups para comparar.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Drop zones */}
      <div className="grid grid-cols-2 gap-4">
        <DropZone label="Startup A" report={reportA} accentClass="text-green-400"
          onDrop={handleDrop("A")} onClear={() => setPickA("")}
          dragOver={dragOver === "A"}
          onDragOver={e => { e.preventDefault(); setDragOver("A"); }}
          onDragLeave={() => setDragOver(null)} />
        <DropZone label="Startup B" report={reportB} accentClass="text-blue-400"
          onDrop={handleDrop("B")} onClear={() => setPickB("")}
          dragOver={dragOver === "B"}
          onDragOver={e => { e.preventDefault(); setDragOver("B"); }}
          onDragLeave={() => setDragOver(null)} />
      </div>

      {/* Startup cards (draggable) */}
      <div>
        <p className="text-xs text-zinc-600 mb-3">Arraste para os slots acima</p>
        <div className="grid grid-cols-2 gap-3">
          {history.map(r => {
            const inSlot = r.startup.name === pickA || r.startup.name === pickB;
            return (
              <div
                key={r.startup.name}
                draggable
                onDragStart={e => { e.dataTransfer.setData("startup", r.startup.name); setDragging(r.startup.name); }}
                onDragEnd={() => setDragging(null)}
                className={`rounded-lg border p-3 cursor-grab active:cursor-grabbing select-none transition-all ${
                  inSlot ? "border-zinc-700 opacity-40" : dragging === r.startup.name ? "opacity-50 border-zinc-600" : "border-zinc-800 bg-zinc-900 hover:border-zinc-600"
                }`}
              >
                <div className="flex items-start justify-between">
                  <p className="font-medium text-zinc-100 text-sm">{r.startup.name}</p>
                  {r.startup.classification && (
                    <Badge className={`text-xs border ${CLASSIFICATION_COLOR[r.startup.classification] ?? PRIORITY_COLOR.low}`}>
                      {r.startup.classification}
                    </Badge>
                  )}
                </div>
                {r.startup.sector && <p className="text-zinc-600 text-xs mt-1">{r.startup.sector}</p>}
                <p className="text-zinc-500 text-xs mt-1.5 line-clamp-1">{r.startup.description || r.summary}</p>
              </div>
            );
          })}
        </div>
      </div>

      <Separator className="bg-zinc-800" />

      {/* Model selectors */}
      <div className="grid grid-cols-3 gap-4">
        <ModelSelect value={modelA} onChange={setModelA} label="Agente A" accentClass="text-green-400" />
        <ModelSelect value={modelB} onChange={setModelB} label="Agente B" accentClass="text-blue-400" />
        <ModelSelect value={judgeModel} onChange={setJudgeModel} label="Juiz" accentClass="text-zinc-400" />
      </div>

      <Button onClick={runDebate} disabled={!pickA || !pickB || loading}
        className="w-full bg-green-600 hover:bg-green-500 text-black font-semibold">
        {loading ? "Debatendo..." : "Iniciar Debate"}
      </Button>
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading && (
        <div className="text-center py-10 space-y-3">
          <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-zinc-400 text-sm">Agentes formando crenças, desejos e intenções...</p>
          <p className="text-zinc-600 text-xs">Abertura → Ataque → Réplica → Veredicto</p>
        </div>
      )}

      {result && <DebateView result={result} nameA={result.startup_a} nameB={result.startup_b} />}
    </div>
  );
}

// ── BatchPage ─────────────────────────────────────────────────────────────────

type BatchStatus = "pending" | "running" | "done" | "error";

interface BatchRow {
  name: string;
  status: BatchStatus;
  score?: number;
  tier?: string;
  error?: string;
}

function BatchPage({ model, onComplete }: {
  model: string;
  onComplete: (report: BriefingReport, score: StartupScore) => void;
}) {
  const [input, setInput] = useState("");
  const [queue, setQueue] = useState<string[]>([]);
  const [rows, setRows] = useState<BatchRow[]>([]);
  const [running, setRunning] = useState(false);

  function addToQueue() {
    const name = input.trim();
    if (!name || queue.includes(name)) return;
    setQueue(prev => [...prev, name]);
    setInput("");
  }

  function removeFromQueue(name: string) {
    setQueue(prev => prev.filter(n => n !== name));
  }

  async function start() {
    if (!queue.length) return;
    setRows(queue.map(name => ({ name, status: "pending" })));
    setRunning(true);

    const res = await fetch("http://localhost:8000/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ startups: queue, model }),
    });

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    setRows(queue.map(name => ({ name, status: "running" })));

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      for (const line of text.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));
        if (data.done) { setRunning(false); break; }
        setRows(prev => prev.map(r =>
          r.name === data.startup_name
            ? { name: r.name, status: data.success ? "done" : "error", score: data.score?.total, tier: data.score?.tier, error: data.error }
            : r
        ));
        if (data.success && data.report && data.score) onComplete(data.report, data.score);
      }
    }
    setRunning(false);
  }

  const done = rows.filter(r => r.status === "done").length;
  const errors = rows.filter(r => r.status === "error").length;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-zinc-100">Análise em lote</h1>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="pt-6 space-y-4">
          {/* Input + Adicionar */}
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addToQueue()}
              placeholder="Nome da startup"
              disabled={running}
              className="bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 h-10"
            />
            <Button onClick={addToQueue} disabled={running || !input.trim()} variant="outline"
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 h-10 px-4 shrink-0">
              Adicionar
            </Button>
          </div>

          {/* Fila de chips */}
          {queue.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {queue.map(name => (
                <div key={name} className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-800 border border-zinc-700 text-sm text-zinc-200">
                  {name}
                  {!running && (
                    <button onClick={() => removeFromQueue(name)} className="text-zinc-600 hover:text-zinc-300 text-base leading-none ml-0.5">×</button>
                  )}
                </div>
              ))}
            </div>
          )}

          <Button onClick={start} disabled={running || queue.length === 0}
            className="w-full bg-green-600 hover:bg-green-500 text-black font-semibold">
            {running ? `Analisando... (${done}/${rows.length})` : `Pesquisar Lote${queue.length > 0 ? ` (${queue.length})` : ""}`}
          </Button>
        </CardContent>
      </Card>

      {/* Progresso */}
      {rows.length > 0 && (
        <div className="space-y-2">
          <div className="flex gap-4 text-xs text-zinc-600 px-1">
            <span>{done} concluídas</span>
            {errors > 0 && <span className="text-red-400">{errors} erros</span>}
            {running && <span className="text-zinc-500">{rows.filter(r => r.status === "running").length} em andamento</span>}
          </div>
          {rows.map(r => (
            <div key={r.name} className="flex items-center gap-3 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800">
              <div className="shrink-0">
                {r.status === "pending" && <div className="w-2 h-2 rounded-full bg-zinc-700" />}
                {r.status === "running" && <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />}
                {r.status === "done"    && <div className="w-2 h-2 rounded-full bg-green-400" />}
                {r.status === "error"   && <div className="w-2 h-2 rounded-full bg-red-400" />}
              </div>
              <span className="flex-1 text-sm text-zinc-200">{r.name}</span>
              {r.status === "done" && r.score !== undefined && r.tier && (
                <div className="flex items-center gap-2">
                  <Badge className={`text-xs border ${TIER_COLOR[r.tier]}`}>Tier {r.tier}</Badge>
                  <ScoreGauge score={r.score} />
                </div>
              )}
              {r.status === "error"   && <span className="text-xs text-red-400 truncate max-w-48">{r.error}</span>}
              {r.status === "running" && <span className="text-xs text-zinc-600">analisando...</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── StartupCard ───────────────────────────────────────────────────────────────

function StartupCard({ report, score: initialScore, model, onScore, onClick }: {
  report: BriefingReport;
  score: StartupScore | null;
  model: string;
  onScore: (s: StartupScore) => void;
  onClick: () => void;
}) {
  const [score, setScore] = useState<StartupScore | null>(initialScore);
  const [fetching, setFetching] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);

  useEffect(() => {
    if (score || fetching) return;
    setFetching(true);
    fetch("http://localhost:8000/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report, model }),
    })
      .then(r => r.ok ? r.json() : null)
      .then((s: StartupScore | null) => {
        if (s) { setScore(s); onScore(s); }
      })
      .catch(() => {})
      .finally(() => setFetching(false));
  }, []);

  const r = report;
  return (
    <Card className="group bg-zinc-900/80 border-zinc-800 cursor-pointer card-hover hover:border-zinc-600/60 backdrop-blur-sm" onClick={onClick}>
      <CardContent className="pt-5 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            {r.startup.logo_url && !logoFailed
              ? <img src={r.startup.logo_url} alt=""
                  className="w-8 h-8 rounded object-contain bg-white p-0.5 transition-transform duration-200 group-hover:scale-110"
                  onError={() => setLogoFailed(true)} />
              : <div className="w-8 h-8 rounded bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-bold text-zinc-300 transition-colors group-hover:border-zinc-500">
                  {r.startup.name[0].toUpperCase()}
                </div>
            }
            <span className="font-semibold text-zinc-100 group-hover:text-white transition-colors">{r.startup.name}</span>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            {r.startup.classification && (
              <Badge className={`text-xs border transition-opacity group-hover:opacity-100 ${CLASSIFICATION_COLOR[r.startup.classification] ?? PRIORITY_COLOR.low}`}>
                {r.startup.classification}
              </Badge>
            )}
            {fetching
              ? <div className="w-4 h-4 rounded-full border border-zinc-700 border-t-zinc-400 animate-spin" />
              : score && <ScoreGauge score={score.total} />}
          </div>
        </div>
        {r.startup.sector && <p className="text-zinc-500 text-xs group-hover:text-zinc-400 transition-colors">{r.startup.sector}</p>}
        <p className="text-zinc-400 text-sm line-clamp-2 group-hover:text-zinc-300 transition-colors">{r.startup.description || r.summary}</p>
        <div className="flex items-center justify-between pt-1">
          <div className="flex gap-1 flex-wrap">
            {r.startup.tech_stack.slice(0, 3).map(t => (
              <Badge key={t} variant="outline" className="text-xs border-zinc-700 text-zinc-500 hover:border-zinc-500 hover:text-zinc-400 transition-colors cursor-default">{t}</Badge>
            ))}
            {r.startup.tech_stack.length > 3 && <span className="text-xs text-zinc-600">+{r.startup.tech_stack.length - 3}</span>}
          </div>
          <span className="text-xs text-zinc-600 group-hover:text-zinc-500 transition-colors">{r.recommendations.length} recomendações</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── RankingPage ───────────────────────────────────────────────────────────────

function RankingPage({ scores, model }: { scores: Record<string, StartupScore>; model: string }) {
  const [ranking, setRanking] = useState<RankingReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scoreList = Object.values(scores);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/rank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scores: scoreList, model }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Erro");
      setRanking(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }

  if (scoreList.length === 0) {
    return <div className="text-center py-16 text-zinc-600">Analise startups primeiro para gerar ranking.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Ranking NVIDIA Inception</h1>
          <p className="text-zinc-500 text-sm mt-1">{scoreList.length} startups com score calculado</p>
        </div>
        <Button onClick={generate} disabled={loading} className="bg-green-600 hover:bg-green-500 text-black font-semibold">
          {loading ? "Gerando..." : ranking ? "Regerar" : "Gerar Ranking"}
        </Button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading && (
        <div className="text-center py-16 space-y-3">
          <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-zinc-400 text-sm">Agente ranker analisando portfólio...</p>
        </div>
      )}

      {ranking && (
        <div className="space-y-6">
          {/* Sumário estratégico */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-5 space-y-3">
              <p className="text-zinc-300 text-sm leading-relaxed">{ranking.strategic_summary}</p>
              <div className="flex gap-4 pt-2 border-t border-zinc-800">
                {ranking.quick_wins.length > 0 && (
                  <div>
                    <p className="text-xs text-zinc-600 mb-1">Ganhos rápidos</p>
                    <div className="flex gap-1.5 flex-wrap">
                      {ranking.quick_wins.map(n => (
                        <Badge key={n} className="text-xs border bg-green-500/10 text-green-400 border-green-500/30">{n}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {ranking.long_bets.length > 0 && (
                  <div>
                    <p className="text-xs text-zinc-600 mb-1">Apostas de longo prazo</p>
                    <div className="flex gap-1.5 flex-wrap">
                      {ranking.long_bets.map(n => (
                        <Badge key={n} className="text-xs border bg-yellow-500/10 text-yellow-400 border-yellow-500/30">{n}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Lista rankeada */}
          <div className="space-y-3">
            {ranking.ranked.map((r, idx) => (
              <Card key={r.position}
                className={`group border card-hover animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both ${r.startup_name === ranking.top_pick ? "bg-zinc-900 border-green-900/40 hover:border-green-700/50" : "bg-zinc-900/80 border-zinc-800 hover:border-zinc-600/60"}`}
                style={{ animationDelay: `${idx * 60}ms` }}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start gap-4">
                    {/* posição */}
                    <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-black border transition-colors ${
                      r.position === 1 ? "border-green-500/60 text-green-400 bg-green-500/10" :
                      r.position === 2 ? "border-blue-500/40 text-blue-400 bg-blue-500/10" :
                      r.position === 3 ? "border-yellow-500/40 text-yellow-400 bg-yellow-500/10" :
                      "border-zinc-700 text-zinc-400"
                    }`}>
                      {r.position}
                    </div>
                    {/* info */}
                    <div className="flex-1 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-zinc-100">{r.startup_name}</span>
                        {r.startup_name === ranking.top_pick && (
                          <Badge className="text-xs border bg-green-500/20 text-green-400 border-green-500/30">Top Pick</Badge>
                        )}
                        <Badge className={`text-xs border ${TIER_COLOR[r.score.tier]}`}>Tier {r.score.tier} · {r.score.total}</Badge>
                      </div>
                      <p className="text-zinc-400 text-sm">{r.highlight}</p>
                      {r.action && <p className="text-zinc-500 text-xs">{r.action}</p>}
                    </div>
                    {/* gauge */}
                    <ScoreGauge score={r.score.total} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── TechGraph ──────────────────────────────────────────────────────────────────

const W = 1000, H = 720, CX = 500, CY = 360, R = 230, NODE_R = 5, LABEL_PAD = 14;
const SUB_R = 110;

function TechGraph({ history }: { history: BriefingReport[] }) {
  const [techs, setTechs] = useState<string[]>([]);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  // pan / zoom
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const dragging = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);

  const onMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    dragging.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
  }, [pan]);

  const onMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!dragging.current) return;
    setPan({
      x: dragging.current.panX + (e.clientX - dragging.current.startX),
      y: dragging.current.panY + (e.clientY - dragging.current.startY),
    });
  }, []);

  const onMouseUp = useCallback(() => { dragging.current = null; }, []);

  const onWheel = useCallback((e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.91;
    setZoom(z => Math.min(4, Math.max(0.25, z * factor)));
  }, []);

  useEffect(() => {
    fetch("http://localhost:8000/techs")
      .then(r => r.json())
      .then((d: { techs: string[] }) => setTechs(d.techs))
      .catch(() => {});
  }, []);

  // map: tech -> startups using it
  const techStartups = new Map<string, string[]>();
  for (const r of history) {
    for (const rec of r.recommendations) {
      const list = techStartups.get(rec.nvidia_tech) ?? [];
      if (!list.includes(r.startup.name)) list.push(r.startup.name);
      techStartups.set(rec.nvidia_tech, list);
    }
  }
  const usedTechs = new Set(techStartups.keys());

  const N = techs.length;
  if (N === 0) return (
    <div className="text-center py-16 text-zinc-600">Carregando tecnologias...</div>
  );

  const pts = techs.map((_, i) => {
    const angle = (2 * Math.PI * i) / N - Math.PI / 2;
    return { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle), angle };
  });

  const polygonPoints = pts.map(p => `${p.x},${p.y}`).join(" ");

  // compute startup subgraph nodes for selected tech
  const subNodes: { name: string; x: number; y: number }[] = [];
  if (selected !== null) {
    const idx = techs.indexOf(selected);
    if (idx >= 0) {
      const techAngle = pts[idx].angle;
      const startups = techStartups.get(selected) ?? [];
      const spread = Math.min(Math.PI * 0.55, (startups.length + 1) * 0.28);
      startups.forEach((s, j) => {
        const offset = startups.length === 1 ? 0 : -spread / 2 + (spread / (startups.length - 1 || 1)) * j;
        const a = techAngle + offset;
        subNodes.push({
          name: s,
          x: pts[idx].x + (SUB_R + 10) * Math.cos(a),
          y: pts[idx].y + (SUB_R + 10) * Math.sin(a),
        });
      });
    }
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800">
        <span className="text-xs text-zinc-500">
          {N} tecnologias · <span className="text-green-400">{usedTechs.size} utilizadas</span>
          {selected && <span className="ml-3 text-zinc-400">· <span className="text-green-300">{selected}</span> — clique novamente para fechar</span>}
        </span>
      </div>
      <svg width={W} height={H} className="block mx-auto cursor-grab active:cursor-grabbing select-none"
        onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}
        onWheel={onWheel}
        onClick={(e) => { if ((e.target as SVGElement).tagName === "svg") setSelected(null); }}>
        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`} style={{ transformOrigin: `${CX}px ${CY}px` }}>
        {/* polygon outline */}
        <polygon points={polygonPoints} fill="none" stroke="#27272a" strokeWidth={1} />
        {/* spokes — NVIDIA center to each tech */}
        {pts.map((p, i) => (
          <line key={i} x1={CX} y1={CY} x2={p.x} y2={p.y}
            stroke={selected === techs[i] ? "#4ade80" : "#2d4a3e"}
            strokeWidth={selected === techs[i] ? 1.5 : 0.8} opacity={0.7} />
        ))}
        {/* NVIDIA central node */}
        <circle cx={CX} cy={CY} r={28} fill="#0a1a10" stroke="#22c55e" strokeWidth={2} />
        <circle cx={CX} cy={CY} r={22} fill="#052e16" stroke="#16a34a" strokeWidth={1} />
        <text x={CX} y={CY - 5} textAnchor="middle" dominantBaseline="middle"
          fontSize={11} fontWeight="700" fill="#4ade80" letterSpacing="0.5">NVIDIA</text>
        <text x={CX} y={CY + 9} textAnchor="middle" dominantBaseline="middle"
          fontSize={8} fontWeight="400" fill="#16a34a">Inception</text>

        {/* subgraph edges */}
        {selected && subNodes.map(sn => {
          const idx = techs.indexOf(selected);
          const tp = pts[idx];
          return (
            <line key={sn.name}
              x1={tp.x} y1={tp.y} x2={sn.x} y2={sn.y}
              stroke="#4ade80" strokeWidth={1.5} opacity={0.5} strokeDasharray="4 3"
            />
          );
        })}

        {/* subgraph startup nodes */}
        {subNodes.map(sn => {
          const dx = sn.x - (selected ? pts[techs.indexOf(selected)].x : CX);
          const dy = sn.y - (selected ? pts[techs.indexOf(selected)].y : CY);
          const angle = Math.atan2(dy, dx);
          const lx = sn.x + Math.cos(angle) * 12;
          const ly = sn.y + Math.sin(angle) * 12;
          const anchor = Math.abs(dx) < 10 ? "middle" : dx > 0 ? "start" : "end";
          const baseline = Math.abs(dy) < 8 ? "middle" : dy > 0 ? "hanging" : "auto";
          const r = history.find(h => h.startup.name === sn.name);
          return (
            <g key={sn.name}>
              {r?.startup.logo_url
                ? <>
                    <defs>
                      <clipPath id={`clip-${sn.name.replace(/\s/g,"")}`}>
                        <circle cx={sn.x} cy={sn.y} r={14} />
                      </clipPath>
                    </defs>
                    <circle cx={sn.x} cy={sn.y} r={14} fill="#fff" stroke="#4ade80" strokeWidth={1.5} />
                    <image href={r.startup.logo_url} x={sn.x - 12} y={sn.y - 12} width={24} height={24}
                      clipPath={`url(#clip-${sn.name.replace(/\s/g,"")})`} preserveAspectRatio="xMidYMid meet" />
                  </>
                : <circle cx={sn.x} cy={sn.y} r={7} fill="#1e3a2f" stroke="#4ade80" strokeWidth={1.5} />
              }
              <text x={lx} y={ly} fontSize={10.5} fontWeight="500"
                fill="#86efac" textAnchor={anchor} dominantBaseline={baseline}>
                {sn.name}
              </text>
            </g>
          );
        })}

        {/* tech nodes + labels */}
        {techs.map((name, i) => {
          const { x, y, angle } = pts[i];
          const used = usedTechs.has(name);
          const isSel = selected === name;
          const isHov = hovered === name;
          const lx = x + Math.cos(angle) * LABEL_PAD;
          const ly = y + Math.sin(angle) * LABEL_PAD;
          const dx = x - CX;
          const anchor = Math.abs(dx) < 10 ? "middle" : dx > 0 ? "start" : "end";
          const dy2 = y - CY;
          const baseline = Math.abs(dy2) < 8 ? "middle" : dy2 > 0 ? "hanging" : "auto";
          return (
            <g key={name}
              onMouseEnter={() => setHovered(name)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => setSelected(isSel ? null : name)}
              className="cursor-pointer">
              <circle cx={x} cy={y} r={NODE_R + (isSel ? 4 : isHov ? 3 : 0)}
                fill={isSel ? "#22c55e" : isHov ? "#16a34a" : used ? "#166534" : "#3f3f46"}
                stroke={isSel ? "#86efac" : used ? "#4ade80" : "#52525b"}
                strokeWidth={isSel ? 2.5 : 1}
              />
              <text x={lx} y={ly}
                fontSize={isSel ? 12 : isHov ? 11.5 : 10.5}
                fontWeight={isSel || used ? "600" : "400"}
                fill={isSel ? "#dcfce7" : isHov ? "#bbf7d0" : used ? "#86efac" : "#52525b"}
                textAnchor={anchor} dominantBaseline={baseline}>
                {name}
              </text>
            </g>
          );
        })}
        </g>
      </svg>
      <div className="flex items-center gap-3 px-4 py-1.5 border-t border-zinc-800 text-xs text-zinc-600">
        <span>Scroll para zoom</span>
        <span>·</span>
        <span>Arrastar para mover</span>
        <button onClick={() => { setPan({ x: 0, y: 0 }); setZoom(1); }}
          className="ml-auto hover:text-zinc-400 transition-colors">Resetar</button>
      </div>
    </div>
  );
}

// ── Sidebar nav item ──────────────────────────────────────────────────────────

function NavItem({ id, label, active, count, onClick }: {
  id: string; label: string; active: boolean; count?: number; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left pl-2.5 pr-3 py-2 rounded-r-md text-sm flex items-center justify-between transition-all duration-150 ${
        active ? "nav-active text-zinc-100" : "nav-inactive text-zinc-500 hover:text-zinc-200"
      }`}
    >
      <span className="font-medium">{label}</span>
      {count !== undefined && count > 0 && (
        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium transition-colors ${
          active ? "bg-green-500/20 text-green-400" : "bg-zinc-800 text-zinc-500"
        }`}>
          {count}
        </span>
      )}
    </button>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const [startupName, setStartupName] = useState("");
  const [urls, setUrls] = useState("");
  const [model, setModel] = useState("llama-3.3-70b");
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [history, setHistory] = useState<BriefingReport[]>([]);
  const [scores, setScores] = useState<Record<string, StartupScore>>({});
  const [selected, setSelected] = useState<BriefingReport | null>(null);
  const [page, setPage] = useState<"analyze" | "startups" | "compare" | "ranking" | "graph">("analyze");
  const [analyzeMode, setAnalyzeMode] = useState<"single" | "batch">("single");

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("radar-history");
    const savedHistory: BriefingReport[] = saved ? JSON.parse(saved) : [];
    if (savedHistory.length) setHistory(savedHistory);
    const savedScores: Record<string, StartupScore> = JSON.parse(localStorage.getItem("radar-scores") || "{}");
    if (Object.keys(savedScores).length) setScores(savedScores);

    // auto-calcular scores pendentes em background
    const pending = savedHistory.filter(r => !savedScores[r.startup.name]);
    if (!pending.length) return;
    (async () => {
      const updated = { ...savedScores };
      for (const r of pending) {
        try {
          const res = await fetch("http://localhost:8000/score", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report: r, model: "llama-3.3-70b" }),
          });
          if (res.ok) {
            const s: StartupScore = await res.json();
            updated[r.startup.name] = s;
            setScores({ ...updated });
            localStorage.setItem("radar-scores", JSON.stringify(updated));
          }
        } catch { /* ignora */ }
      }
    })();
  }, []);

  async function analyze() {
    setLoading(true);
    setError(null);
    setLoadingMsg("Coletando dados e extraindo perfil...");
    try {
      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          startup_name: startupName,
          urls: urls.split("\n").map((u) => u.trim()).filter(Boolean),
          model,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Erro desconhecido");
      const result: BriefingReport = await res.json();
      const updated = [result, ...history.filter(h => h.startup.name !== result.startup.name)];
      setHistory(updated);
      localStorage.setItem("radar-history", JSON.stringify(updated));
      setSelected(result);
      setPage("startups");

      // score em background
      setLoadingMsg("Calculando score de fit NVIDIA...");
      try {
        const scoreRes = await fetch("http://localhost:8000/score", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ report: result, model }),
        });
        if (scoreRes.ok) {
          const score: StartupScore = await scoreRes.json();
          const updatedScores = { ...scores, [result.startup.name]: score };
          setScores(updatedScores);
          localStorage.setItem("radar-scores", JSON.stringify(updatedScores));
        }
      } catch { /* score é opcional */ }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao analisar startup");
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">

      {/* Sidebar */}
      <aside className="w-52 shrink-0 border-r border-zinc-800/80 flex flex-col bg-zinc-950/95 backdrop-blur-sm">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-zinc-800/80">
          <div className="flex items-center gap-2.5">
            <img src="/logo.svg" alt="Logo" className="w-10 h-10 shrink-0" />
            <div>
              <p className="font-bold text-sm leading-tight tracking-tight">Startup Radar</p>
              <p className="text-zinc-500 text-xs">Inception · Brazil</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-4 space-y-0.5">
          <NavItem id="analyze" label="Analisar" active={page === "analyze"} onClick={() => setPage("analyze")} />
          <NavItem id="startups" label="Startups" active={page === "startups"} count={history.length} onClick={() => { setPage("startups"); setSelected(null); }} />
          <NavItem id="compare" label="Comparar" active={page === "compare"} onClick={() => setPage("compare")} />
          <NavItem id="ranking" label="Ranking" active={page === "ranking"} count={Object.keys(scores).length || undefined} onClick={() => setPage("ranking")} />
          <NavItem id="graph" label="Grafo" active={page === "graph"} onClick={() => setPage("graph")} />
        </nav>

        {/* Startups recentes na sidebar */}
        {history.length > 0 && (
          <div className="px-2 py-3 border-t border-zinc-800/80">
            <p className="text-xs text-zinc-600 px-2 mb-1.5 uppercase tracking-wider font-medium">Recentes</p>
            {history.slice(0, 5).map(r => {
              const isActive = selected?.startup.name === r.startup.name && page === "startups";
              return (
                <button
                  key={r.startup.name}
                  onClick={() => { setSelected(r); setPage("startups"); }}
                  className={`w-full text-left px-2 py-1.5 rounded text-xs transition-all duration-150 truncate flex items-center gap-1.5 group ${
                    isActive ? "text-green-400 bg-zinc-900" : "text-zinc-500 hover:text-zinc-200 hover:bg-zinc-900/50"
                  }`}
                >
                  <span className={`w-1 h-1 rounded-full shrink-0 transition-all duration-150 ${isActive ? "bg-green-400 shadow-[0_0_4px_rgba(74,222,128,0.6)]" : "bg-zinc-700 group-hover:bg-zinc-500"}`} />
                  {r.startup.name}
                </button>
              );
            })}
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div key={page} className={`mx-auto px-8 py-8 space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both ${page === "graph" ? "max-w-6xl" : "max-w-3xl"}`}>

          {/* PAGE: Analisar */}
          {page === "analyze" && (
            <>
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-zinc-100">Analisar</h1>
                <div className="flex rounded-md border border-zinc-700 overflow-hidden">
                  {(["single", "batch"] as const).map(m => (
                    <button key={m} onClick={() => setAnalyzeMode(m)}
                      className={`px-4 py-1.5 text-xs font-medium transition-colors ${
                        analyzeMode === m ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
                      }`}>
                      {m === "single" ? "Individual" : "Em lote"}
                    </button>
                  ))}
                </div>
              </div>

              {analyzeMode === "single" ? (
                <>
                  <Card className="bg-zinc-900 border-zinc-800">
                    <CardContent className="pt-6 space-y-4">
                      <div className="flex gap-3">
                        <Input
                          value={startupName}
                          onChange={(e) => setStartupName(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && analyze()}
                          placeholder="Ex: Neoway, Horus, Take Blip"
                          className="bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 h-10"
                        />
                        <Button onClick={analyze} disabled={!mounted || loading || !startupName}
                          className="bg-green-600 hover:bg-green-500 text-black font-semibold px-6 transition-all duration-200 hover:shadow-[0_0_20px_rgba(34,197,94,0.4)] disabled:opacity-40 disabled:shadow-none">
                          {loading ? "Analisando..." : "Analisar"}
                        </Button>
                      </div>
                      <div className="space-y-1.5">
                        <p className="text-xs text-zinc-500">Modelo</p>
                        <div className="flex flex-wrap gap-2">
                          {MODELS.map((m) => (
                            <button key={m.key} onClick={() => setModel(m.key)}
                              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-all duration-150 ${
                                model === m.key
                                  ? "border-green-500 bg-green-500/10 text-green-400 shadow-[0_0_12px_rgba(34,197,94,0.2)]"
                                  : "border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300 hover:bg-zinc-700/50"
                              }`}>
                              {m.label}
                              <span className="ml-1.5 text-zinc-600">{m.desc}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                      <details>
                        <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">URLs manuais (opcional)</summary>
                        <textarea value={urls} onChange={(e) => setUrls(e.target.value)}
                          placeholder={"https://startup.com\nhttps://github.com/startup"} rows={2}
                          className="mt-2 w-full rounded-md bg-zinc-800 border border-zinc-700 text-zinc-100 placeholder:text-zinc-600 p-3 text-sm focus:outline-none focus:ring-1 focus:ring-green-500" />
                      </details>
                      {error && <p className="text-red-400 text-sm">{error}</p>}
                    </CardContent>
                  </Card>
                  {loading && (
                    <div className="text-center py-16 space-y-3">
                      <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin mx-auto" />
                      <p className="text-zinc-400 text-sm">{loadingMsg}</p>
                    </div>
                  )}
                </>
              ) : (
                <BatchPage
                  model={model}
                  onComplete={(report, score) => {
                    setHistory(prev => {
                      const updated = [report, ...prev.filter(h => h.startup.name !== report.startup.name)];
                      localStorage.setItem("radar-history", JSON.stringify(updated));
                      return updated;
                    });
                    setScores(prev => {
                      const updated = { ...prev, [report.startup.name]: score };
                      localStorage.setItem("radar-scores", JSON.stringify(updated));
                      return updated;
                    });
                  }}
                />
              )}
            </>
          )}

          {/* PAGE: Startups */}
          {page === "startups" && (
            <>
              {history.length === 0 ? (
                <div className="text-center py-16 text-zinc-600">Nenhuma startup analisada ainda.</div>
              ) : selected ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <button onClick={() => setSelected(null)} className="text-zinc-500 hover:text-zinc-300 text-sm">← Voltar</button>
                    <Separator orientation="vertical" className="h-4 bg-zinc-700" />
                    <h2 className="font-bold text-lg">{selected.startup.name}</h2>
                    {selected.startup.classification && (
                      <Badge className={`text-xs border ${CLASSIFICATION_COLOR[selected.startup.classification] ?? PRIORITY_COLOR.low}`}>
                        {selected.startup.classification}
                      </Badge>
                    )}
                    {selected.startup.sector && <span className="text-zinc-500 text-sm">{selected.startup.sector}</span>}
                  </div>
                  <StartupDetail report={selected} score={scores[selected.startup.name] ?? null} peers={history.filter(r => r.startup.name !== selected.startup.name)} />
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <h1 className="text-xl font-bold text-zinc-100">Startups analisadas</h1>
                    {history.some(r => !scores[r.startup.name]) && (
                      <span className="text-xs text-zinc-600 animate-pulse">calculando scores...</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {history.map((r, i) => (
                      <StartupCard
                        key={i}
                        report={r}
                        score={scores[r.startup.name] ?? null}
                        model={model}
                        onScore={s => {
                          setScores(prev => {
                            const updated = { ...prev, [r.startup.name]: s };
                            localStorage.setItem("radar-scores", JSON.stringify(updated));
                            return updated;
                          });
                        }}
                        onClick={() => setSelected(r)}
                      />
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {/* PAGE: Comparar */}
          {page === "compare" && (
            <>
              <h1 className="text-xl font-bold text-zinc-100">Debate adversarial</h1>
              <CompareTab history={history} />
            </>
          )}

          {/* PAGE: Ranking */}
          {page === "ranking" && (
            <RankingPage scores={scores} model={model} />
          )}

          {/* PAGE: Grafo */}
          {page === "graph" && (
            <>
              <h1 className="text-xl font-bold text-zinc-100">Grafo de tecnologias</h1>
              <TechGraph history={history} />
            </>
          )}

        </div>
      </main>
    </div>
  );
}
