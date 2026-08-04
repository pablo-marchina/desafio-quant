const ENGLISH_MARKERS = [
  " the ",
  " and ",
  " for ",
  " with ",
  " platform ",
  " company ",
  " hardware ",
  " software ",
  " expansion ",
  " is ",
  " that ",
  " banks ",
  " financial ",
  " technology ",
  " evidence "
];

const PHRASES: Array<[RegExp, string]> = [
  [/\bcloud-based\b/gi, "baseadas em nuvem"],
  [/\bnuvem-based\b/gi, "baseadas em nuvem"],
  [/\bcloud-centric\b/gi, "centrada em nuvem"],
  [/\bAPI-driven\b/gi, "orientada por APIs"],
  [/\bother financial institutions\b/gi, "outras instituições financeiras"],
  [/\baiming to modernize\b/gi, "visando modernizar"],
  [/\benable banks to provide banking\b/gi, "permitem que bancos ofereçam serviços bancários"],
  [/\bdoes not indicate a use\b/gi, "não indica uso"],
  [/\blegacy financial systems\b/gi, "sistemas financeiros legados"],
  [/\bissuer processing services\b/gi, "serviços de processamento para emissores"],
  [/\bemerging payment methods such as Pix\b/gi, "métodos de pagamento emergentes, como Pix"],
  [/\btechnology stack\b/gi, "stack tecnológica"],
  [/\bavailable evidence\b/gi, "evidência disponível"],
  [/\bhardware and software integration\b/gi, "integração de hardware e software"],
  [/\bexpansion plans to major Brazilian cities\b/gi, "planos de expansão para grandes cidades brasileiras"],
  [/\bartificial intelligence\b/gi, "inteligência artificial"],
  [/\bmachine learning\b/gi, "aprendizado de máquina"],
  [/\bcomputer vision\b/gi, "visão computacional"],
  [/\bpredictive analytics\b/gi, "análise preditiva"],
  [/\bdata platform\b/gi, "plataforma de dados"],
  [/\bsoftware platform\b/gi, "plataforma de software"],
  [/\bcloud infrastructure\b/gi, "infraestrutura em nuvem"],
  [/\bcustomer service\b/gi, "atendimento ao cliente"],
  [/\bhealthcare\b/gi, "saúde"],
  [/\bfinancial services\b/gi, "serviços financeiros"],
  [/\bmajor Brazilian cities\b/gi, "grandes cidades brasileiras"]
];

const WORDS: Record<string, string> = {
  and: "e",
  for: "para",
  with: "com",
  without: "sem",
  to: "para",
  in: "em",
  of: "de",
  the: "a",
  a: "uma",
  an: "uma",
  is: "é",
  are: "são",
  that: "que",
  while: "embora",
  other: "outras",
  or: "ou",
  not: "não",
  company: "empresa",
  startup: "startup",
  platform: "plataforma",
  product: "produto",
  service: "serviço",
  services: "serviços",
  develops: "desenvolve",
  modular: "modulares",
  based: "baseadas",
  banks: "bancos",
  bank: "banco",
  financial: "financeiras",
  finance: "financeira",
  institutions: "instituições",
  institution: "instituição",
  aiming: "visando",
  modernize: "modernizar",
  legacy: "legados",
  systems: "sistemas",
  offers: "oferece",
  apis: "APIs",
  enable: "permitem",
  issuer: "emissor",
  processing: "processamento",
  supports: "suporta",
  provide: "oferecer",
  banking: "serviços bancários",
  emerging: "emergentes",
  payment: "pagamento",
  methods: "métodos",
  such: "como",
  software: "software",
  hardware: "hardware",
  data: "dados",
  analytics: "analytics",
  integration: "integração",
  expansion: "expansão",
  plans: "planos",
  plan: "plano",
  cities: "cidades",
  city: "cidade",
  major: "grandes",
  brazilian: "brasileiras",
  brazil: "Brasil",
  operations: "operações",
  customers: "clientes",
  business: "negócio",
  management: "gestão",
  automation: "automação",
  intelligence: "inteligência",
  artificial: "artificial",
  predictive: "preditiva",
  models: "modelos",
  model: "modelo",
  solutions: "soluções",
  solution: "solução",
  development: "desenvolvimento",
  deployment: "implantação",
  monitoring: "monitoramento",
  security: "segurança",
  performance: "desempenho",
  infrastructure: "infraestrutura",
  cloud: "nuvem",
  centric: "centrada",
  driven: "orientada",
  available: "disponível",
  mobile: "mobile",
  app: "aplicativo",
  applications: "aplicações",
  application: "aplicação",
  evidence: "evidência",
  indicate: "indica",
  indicates: "indica",
  does: "",
  use: "uso",
  its: "seus",
  products: "produtos",
  their: "seus",
  pismo: "Pismo"
};

export function looksEnglish(value?: string | null) {
  const normalized = ` ${String(value || "").toLowerCase()} `;
  const markerHits = ENGLISH_MARKERS.filter((marker) => normalized.includes(marker)).length;
  const words = normalized.match(/\b[a-z][a-z-]*\b/g) || [];
  const dictionaryHits = words.filter((word) => WORDS[word] || word.includes("-based") || word.includes("-driven")).length;
  return markerHits >= 2 || dictionaryHits >= 5;
}

export function translateIfEnglish(value?: string | null) {
  const text = String(value || "").trim();
  if (!text || !looksEnglish(text)) return text;

  let translated = text;
  for (const [pattern, replacement] of PHRASES) {
    translated = translated.replace(pattern, replacement);
  }
  translated = translated.replace(/\b[A-Za-z][A-Za-z-]*\b/g, (word) => {
    const replacement = WORDS[word.toLowerCase()];
    if (!replacement) return word;
    return /^[A-Z]/.test(word)
      ? replacement.charAt(0).toUpperCase() + replacement.slice(1)
      : replacement;
  });
  return translated
    .replace(/\bBrasileiras fintech\b/g, "fintech brasileira")
    .replace(/\bfinanceiras instituições\b/g, "instituições financeiras")
    .replace(/\blegados financeira sistemas\b/g, "sistemas financeiros legados")
    .replace(/\bpara modernizar\b/g, "modernizar")
    .replace(/\ba disponível evidência\b/g, "a evidência disponível")
    .replace(/\ba available evidência\b/g, "a evidência disponível")
    .replace(/\s+/g, " ")
    .trim();
}
