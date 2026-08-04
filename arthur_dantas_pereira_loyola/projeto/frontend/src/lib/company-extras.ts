// Mock-only extras: brand colors, contact info, growth/funding history.
// Kept here to avoid bloating the main mock-data file.

export interface CompanyContact {
  email: string;
  phone: string;
  website: string;
  linkedin: string;
  primaryName: string;
  primaryRole: string;
}

export interface GrowthPoint {
  month: string; // e.g. "2024-Q1"
  valuationM: number; // USD millions
  arrM: number; // ARR USD millions
  headcount: number;
}

export interface CompanyExtras {
  brandColor: string; // hex
  domain: string;
  contact: CompanyContact;
  growth: GrowthPoint[];
}

function genGrowth(seed: number, base: number): GrowthPoint[] {
  const quarters = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"];
  let v = base;
  let arr = base / 8;
  let hc = Math.round(base / 4);
  const out: GrowthPoint[] = [];
  for (let i = 0; i < quarters.length; i++) {
    const rand = (Math.sin(seed * (i + 1)) + 1) / 2; // 0..1
    const growth = 0.08 + rand * 0.18; // 8-26% q/q
    v = Math.round(v * (1 + growth));
    arr = +(arr * (1 + growth * 1.1)).toFixed(1);
    hc = Math.round(hc * (1 + growth * 0.4));
    out.push({ month: quarters[i], valuationM: v, arrM: arr, headcount: hc });
  }
  return out;
}

export const companyExtras: Record<string, CompanyExtras> = {
  neurabra: {
    brandColor: "#0EA5E9",
    domain: "neurabra.ai",
    contact: {
      email: "partnerships@neurabra.ai",
      phone: "+55 11 4002-8922",
      website: "https://neurabra.ai",
      linkedin: "https://linkedin.fictprofile/company/neurabra",
      primaryName: "Marina Tavares",
      primaryRole: "VP Engineering",
    },
    growth: genGrowth(1.3, 18),
  },
  "vortex-vision": {
    brandColor: "#8B5CF6",
    domain: "vortexvision.com.br",
    contact: {
      email: "contato@vortexvision.com.br",
      phone: "+55 48 3025-7711",
      website: "https://vortexvision.com.br",
      linkedin: "https://linkedin.fictprofile/company/vortex-vision",
      primaryName: "Rafael Kümmel",
      primaryRole: "CTO & Co-founder",
    },
    growth: genGrowth(2.1, 12),
  },
  agroflow: {
    brandColor: "#10B981",
    domain: "agroflow.farm",
    contact: {
      email: "comercial@agroflow.farm",
      phone: "+55 16 3621-4040",
      website: "https://agroflow.farm",
      linkedin: "https://linkedin.fictprofile/company/agroflow",
      primaryName: "Lucas Andrade",
      primaryRole: "Head of Data",
    },
    growth: genGrowth(0.7, 15),
  },
  "lumini-health": {
    brandColor: "#EC4899",
    domain: "luminihealth.com.br",
    contact: {
      email: "research@luminihealth.com.br",
      phone: "+55 51 3333-9090",
      website: "https://luminihealth.com.br",
      linkedin: "https://linkedin.fictprofile/company/lumini-health",
      primaryName: "Dra. Beatriz Lemos",
      primaryRole: "Chief Research Officer",
    },
    growth: genGrowth(3.4, 6),
  },
  "polyglot-voice": {
    brandColor: "#F59E0B",
    domain: "polyglotvoice.io",
    contact: {
      email: "hello@polyglotvoice.io",
      phone: "+55 21 4042-1180",
      website: "https://polyglotvoice.io",
      linkedin: "https://linkedin.fictprofile/company/polyglot-voice",
      primaryName: "Igor Mendes",
      primaryRole: "Founder & CEO",
    },
    growth: genGrowth(1.9, 9),
  },
  "quanta-logix": {
    brandColor: "#EF4444",
    domain: "quantalogix.com.br",
    contact: {
      email: "rfp@quantalogix.com.br",
      phone: "+55 41 3022-5500",
      website: "https://quantalogix.com.br",
      linkedin: "https://linkedin.fictprofile/company/quanta-logix",
      primaryName: "Patrícia Yamamoto",
      primaryRole: "Director of Engineering",
    },
    growth: genGrowth(4.2, 30),
  },
  "ferra-secure": {
    brandColor: "#0F172A",
    domain: "ferrasecure.io",
    contact: {
      email: "sales@ferrasecure.io",
      phone: "+55 31 4002-0707",
      website: "https://ferrasecure.io",
      linkedin: "https://linkedin.fictprofile/company/ferra-secure",
      primaryName: "Henrique Salles",
      primaryRole: "Head of Engineering",
    },
    growth: genGrowth(2.7, 11),
  },
  omnigen: {
    brandColor: "#76B900",
    domain: "omnigen.studio",
    contact: {
      email: "studios@omnigen.studio",
      phone: "+55 11 5040-3300",
      website: "https://omnigen.studio",
      linkedin: "https://linkedin.fictprofile/company/omnigen",
      primaryName: "Camila Vieira",
      primaryRole: "CTO & Co-founder",
    },
    growth: genGrowth(5.1, 5),
  },
};

export function getCompanyExtras(id: string, name?: string): CompanyExtras {
  return (
    companyExtras[id] ?? {
      brandColor: "#64748B",
      domain: (name || id).toLowerCase().replace(/[^a-z0-9]/g, "") + ".com.br",
      contact: {
        email: "contato@empresa.com",
        phone: "+55 00 0000-0000",
        website: "https://exemplo.com",
        linkedin: "https://linkedin.fictprofile/company/exemplo",
        primaryName: "—",
        primaryRole: "—",
      },
      growth: genGrowth(1, 10),
    }
  );
}

// Aggregate stats for the overview dashboard
export const sectorDistribution = [
  { name: "Fintech", value: 38 },
  { name: "Healthtech", value: 24 },
  { name: "Indústria", value: 21 },
  { name: "Agro", value: 18 },
  { name: "Cyber", value: 16 },
  { name: "Creative", value: 12 },
  { name: "Logística", value: 11 },
  { name: "CX/Voz", value: 9 },
];

export const regionDistribution = [
  { name: "SP", value: 92 },
  { name: "RJ", value: 41 },
  { name: "MG", value: 28 },
  { name: "RS", value: 24 },
  { name: "SC", value: 21 },
  { name: "PR", value: 18 },
  { name: "Outros", value: 24 },
];

export const pipelineFunnel = [
  { stage: "Identificadas", value: 248 },
  { stage: "Classificadas", value: 176 },
  { stage: "Com evidência forte", value: 112 },
  { stage: "Briefing pronto", value: 87 },
  { stage: "Contactadas", value: 42 },
  { stage: "Em negociação", value: 18 },
  { stage: "Contrato fechado", value: 7 },
];

export const weeklyActivity = [
  { week: "S-9", evidencias: 86, recomend: 14 },
  { week: "S-8", evidencias: 102, recomend: 19 },
  { week: "S-7", evidencias: 134, recomend: 22 },
  { week: "S-6", evidencias: 118, recomend: 28 },
  { week: "S-5", evidencias: 156, recomend: 31 },
  { week: "S-4", evidencias: 172, recomend: 35 },
  { week: "S-3", evidencias: 198, recomend: 42 },
  { week: "S-2", evidencias: 221, recomend: 48 },
  { week: "S-1", evidencias: 245, recomend: 56 },
];
