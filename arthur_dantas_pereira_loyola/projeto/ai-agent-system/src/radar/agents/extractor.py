from __future__ import annotations

import json
import re
from typing import Dict, Pattern

from radar.graph.progress import get_tracker
from radar.graph.state import RadarState
from radar.llm import EXTRACTION_PROMPT, run_llm_with_fallback
from radar.schemas import EvidenceClaim, SourceDocument, StartupProfile
from radar.settings import get_settings


SECTOR_PATTERNS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"sa[úu]de|health|healthcare|medical|cl[íi]nica", re.IGNORECASE), "Healthcare"),
    (re.compile(r"finan[cç]as|fintech|banking|pagamentos|finance", re.IGNORECASE), "Fintech"),
    (re.compile(r"agro|agricultura|farming|rural", re.IGNORECASE), "Agrotech"),
    (re.compile(r"educa[cç][ãa]o|learning|edtech|ensino|escola", re.IGNORECASE), "Edtech"),
    (re.compile(r"log[ií]stica|logistics|supply chain|frota", re.IGNORECASE), "Logistics"),
    (re.compile(r"vendas|sales|marketing|crm", re.IGNORECASE), "Sales & Marketing"),
    (re.compile(r"call.center|atendimento|customer.support|contact.center", re.IGNORECASE), "Customer Service"),
    (re.compile(r"jur[ií]dico|legal|law|advocacia", re.IGNORECASE), "Legal"),
    (re.compile(r"rob[oô]|robotics|automa[cç][ãa]o|autonomous", re.IGNORECASE), "Robotics"),
    (re.compile(r"voz|voice|speech|transcri[cç][ãa]o|asr|tts", re.IGNORECASE), "Voice AI"),
    (re.compile(r"data|analytics|business.intelligence|bi[^a-z]", re.IGNORECASE), "Data & Analytics"),
    (re.compile(r"seguran[cç]a|security|cyber|surveillance", re.IGNORECASE), "Cybersecurity"),
    (re.compile(r"jogos|gaming|game|entertainment|m[íi]dia", re.IGNORECASE), "Gaming & Media"),
]

FOUNDER_PATTERN = re.compile(
    r"(?:founder|ceo|cto|co-founder|fundador)[:\s]+([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+){1,3})",
    re.IGNORECASE,
)

FUNDING_PATTERNS: list[Pattern[str]] = [
    re.compile(r"raised\s+\$?([\d,.]+)\s*(million|m|billion|b)?", re.IGNORECASE),
    re.compile(r"(?:seed|series\s*[a-z]|s[ée]rie\s*[a-z])\s*(?:round|funding)?", re.IGNORECASE),
    re.compile(r"(?:us\$|r\$)\s*[\d,]+(?:\s*(?:mi|bi|m|b))?", re.IGNORECASE),
]

TECHNOLOGY_KEYWORDS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"tensorrt|tensor-rt|tensor.rt", re.IGNORECASE), "TensorRT-LLM"),
    (re.compile(r"triton\s+inference", re.IGNORECASE), "Triton Inference Server"),
    (re.compile(r"nemo|nemotron", re.IGNORECASE), "NeMo"),
    (re.compile(r"rapids\s+|cudf|cuml", re.IGNORECASE), "RAPIDS"),
    (re.compile(r"\bcuda\b(?![\w])", re.IGNORECASE), "CUDA"),
    (re.compile(r"omniverse", re.IGNORECASE), "Omniverse"),
    (re.compile(r"isaac\s+(sim|robot)", re.IGNORECASE), "Isaac"),
    (re.compile(r"clara", re.IGNORECASE), "Clara"),
    (re.compile(r"morpheus", re.IGNORECASE), "Morpheus"),
    (re.compile(r"\briva\b", re.IGNORECASE), "Riva"),
    (re.compile(r"nvidia\s+inception", re.IGNORECASE), "NVIDIA Inception"),
    (re.compile(r"ai\s+enterprise", re.IGNORECASE), "AI Enterprise"),
    (re.compile(r"\b(llm|llms)\b|large\s+language\s+model", re.IGNORECASE), "LLM"),
    (re.compile(r"langchain|langgraph", re.IGNORECASE), "LangChain/LangGraph"),
    (re.compile(r"rag|retrieval.augmented", re.IGNORECASE), "RAG"),
    (re.compile(r"vector\s+(database|store|db)|qdrant|chroma|pinecone", re.IGNORECASE), "Vector Database"),
    (re.compile(r"kubernetes|k8s|docker", re.IGNORECASE), "Container/Orch."),
    (re.compile(r"pytorch|tensorflow|jax", re.IGNORECASE), "ML Framework"),
    (re.compile(r"hugging.face|transformers", re.IGNORECASE), "Hugging Face"),
    (re.compile(r"on[ -]?prem(?:ise)?|edge\s+(?:deploy|infer)", re.IGNORECASE), "Edge/On-Prem"),
    (re.compile(r"gpu|inferencia|inference\s+(?:serv|optim)", re.IGNORECASE), "GPU Inference"),
]

AI_MARKER_PATTERNS: list[Pattern[str]] = [
    re.compile(r"\b[Aa][Ii]\b"),                            # "AI" as word (English)
    re.compile(r"\b[Ii][Aa]\b"),                            # "IA" as word (Portuguese)
    re.compile(r"\bintelig[eê]ncia\s+artificial\b"),       # "inteligencia artificial"
    re.compile(r"\bartificial\s+intelligence\b"),           # "artificial intelligence"
    re.compile(r"\bllm\b|\bllms\b", re.IGNORECASE),        # "LLM"
    re.compile(r"\bmachine\s+learning\b", re.IGNORECASE),  # "machine learning"
    re.compile(r"\bagents?\b", re.IGNORECASE),              # "agent" or "agents"
    re.compile(r"\bautomation\b", re.IGNORECASE),           # "automation"
    re.compile(r"\bdeep\s+learning\b", re.IGNORECASE),      # "deep learning"
    re.compile(r"\bneural\s+network", re.IGNORECASE),       # "neural network"
    re.compile(r"\bGPT\b|\bgpt-|\bchatgpt\b", re.IGNORECASE), # "GPT", "GPT-*", "ChatGPT"
    re.compile(r"\bopenai\b", re.IGNORECASE),               # "OpenAI"
    re.compile(r"\bfine[ -]?tun(?:ing|ed)\b", re.IGNORECASE), # "fine-tuning", "finetuned"
]
TECH_MARKER_PATTERNS: list[Pattern[str]] = [
    re.compile(r"\bpipeline\b", re.IGNORECASE),
    re.compile(r"\bproduction\b", re.IGNORECASE),
    re.compile(r"\bevaluation\b", re.IGNORECASE),
    re.compile(r"\bworkflow\b", re.IGNORECASE),
    re.compile(r"\bdata\b", re.IGNORECASE),
]


def _split_into_paragraphs(text: str) -> list[str]:
    cleaned = re.sub(r"\n{3,}", "\n\n", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    raw_chunks = re.split(r"\n\s*\n", cleaned)
    chunks = [c.strip() for c in raw_chunks]
    meaningful = [c for c in chunks if len(c) > 30]
    if not meaningful and chunks:
        candidate = " ".join(chunks).strip()
        if len(candidate) > 40:
            meaningful = [candidate]
    return meaningful


_IMAGE_PATTERN = re.compile(r"!\[.*?\]\(.*?\)")
_LINK_PATTERN = re.compile(r"\[.*?\]\(.*?\)")

_SEMANTIC_AI_PATTERNS: list[Pattern[str]] = [
    re.compile(r"\b[Aa][Ii]\b"),
    re.compile(r"\b[Ii][Aa]\b"),
    re.compile(r"\bintelig[eê]ncia\s+artificial\b"),
    re.compile(r"\bartificial\s+intelligence\b"),
    re.compile(r"\bllm\b|\bllms\b", re.IGNORECASE),
    re.compile(r"\bmachine\s+learning\b", re.IGNORECASE),
    re.compile(r"\bdeep\s+learning\b", re.IGNORECASE),
    re.compile(r"\bneural\s+network", re.IGNORECASE),
    re.compile(r"\bGPT\b|\bgpt-|\bchatgpt\b", re.IGNORECASE),
    re.compile(r"\bfine[ -]?tun(?:ing|ed)\b", re.IGNORECASE),
    re.compile(r"\bopenai\b", re.IGNORECASE),
    re.compile(r"\btransformers?\b", re.IGNORECASE),
]


def _is_image_heavy(text: str) -> bool:
    images = _IMAGE_PATTERN.findall(text)
    if not images:
        return False
    img_chars = sum(len(img) for img in images)
    return img_chars > len(text) * 0.5


def _is_navigation_ui(text: str) -> bool:
    links = _LINK_PATTERN.findall(text)
    if not links:
        return False
    link_chars = sum(len(link) for link in links)
    return link_chars > len(text) * 0.6


def _is_relevant_paragraph(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 30:
        return False
    if _is_image_heavy(stripped):
        return False
    if _is_navigation_ui(stripped):
        return False
    if any(p.search(text) for p in AI_MARKER_PATTERNS):
        return True
    if any(p.search(text) for p in TECH_MARKER_PATTERNS):
        return True
    return False


def extract_startups_and_claims(state: RadarState) -> tuple[list[StartupProfile], list[EvidenceClaim]]:
    sources = state.get("sources", [])
    query = state.get("query", "Unknown startup")
    known_name = state.get("startup_name")
    claims: list[EvidenceClaim] = []

    seen_texts: set[str] = set()
    for source in sources:
        if not source.text:
            continue
        paragraphs = _split_into_paragraphs(source.text)
        for paragraph in paragraphs:
            if not _is_relevant_paragraph(paragraph):
                continue
            claim_type = _infer_claim_type(paragraph)
            confidence = _infer_claim_confidence(source.source_type, claim_type)
            preview = paragraph[:500]
            dedup_key = preview.lower().strip()[:100]
            if dedup_key not in seen_texts:
                seen_texts.add(dedup_key)
                claims.append(
                    EvidenceClaim(
                        source_document_id=source.id,
                        text=preview,
                        claim_type=claim_type,
                        confidence=confidence,
                    )
                )

    profile = _build_profile(query, sources, claims, known_name)
    return [profile], claims


def _build_profile(
    query: str, sources: list[SourceDocument], claims: list[EvidenceClaim], known_name: str | None = None
) -> StartupProfile:
    all_text = " ".join(s.text for s in sources if s.text)

    tracker = get_tracker()
    settings = get_settings()
    if settings.enable_external_providers:
        try:
            if tracker:
                tracker.set_detail("extractor", "Extraindo dados via Groq LLM...")
            return _llm_extract(query, sources, claims, known_name)
        except Exception:
            if tracker:
                tracker.set_detail("extractor", "LLM falhou, usando extração por regex...")

    if tracker:
        tracker.set_detail("extractor", "Extraindo dados via regex e regras...")
    return _deterministic_extract(query, all_text, sources, claims, known_name)


def _llm_extract(
    query: str, sources: list[SourceDocument], claims: list[EvidenceClaim], known_name: str | None = None
) -> StartupProfile:
    combined_text = "\n\n---\n\n".join(
        f"[{s.source_type}] {s.title}\n{s.text[:2000]}"
        for s in sources if s.text
    )

    startup_hint = known_name or query
    result = run_llm_with_fallback(
        system_prompt=EXTRACTION_PROMPT,
        user_prompt=f"Startup: {startup_hint}\n\nCollected text:\n{combined_text[:8000]}",
    )

    parsed = _parse_llm_json(result)
    if parsed is None:
        raise ValueError("LLM returned invalid JSON for extraction")

    technologies = parsed.get("technologies") or []
    ai_claims = [c for c in claims if c.claim_type == "ai_usage"]
    sector = _text_or_none(parsed.get("sector"))
    startup_name = _text_or_none(parsed.get("name")) or known_name or query
    usage_summary = parsed.get("ai_usage_summary") or _summarize_ai_usage(ai_claims, technologies, sector)

    return StartupProfile(
        name=startup_name,
        sector=sector,
        product=parsed.get("product"),
        description="Perfil da startup montado a partir de evidencias publicas coletadas via LLM.",
        founders=parsed.get("founders") or [],
        funding=parsed.get("funding"),
        cited_technologies=technologies,
        ai_usage_summary=usage_summary,
        evidence_ids=[c.id for c in claims],
    )


def _deterministic_extract(
    query: str, all_text: str, sources: list[SourceDocument], claims: list[EvidenceClaim], known_name: str | None = None
) -> StartupProfile:
    sector = _extract_sector(all_text)
    product = _extract_product(all_text)
    founders = _extract_founders(all_text)
    funding = _extract_funding(all_text)
    technologies = _extract_technologies(all_text)

    ai_claims = [c for c in claims if c.claim_type == "ai_usage"]
    usage_summary = _summarize_ai_usage(ai_claims, technologies, sector)

    return StartupProfile(
        name=known_name or query,
        sector=sector,
        product=product,
        description="Perfil da startup montado a partir de evidencias publicas coletadas.",
        founders=founders,
        funding=funding,
        cited_technologies=technologies,
        ai_usage_summary=usage_summary,
        evidence_ids=[c.id for c in claims],
    )


def _text_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

def _parse_llm_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_sector(text: str) -> str | None:
    for pattern, sector in SECTOR_PATTERNS:
        if pattern.search(text):
            return sector
    return None


def _extract_product(text: str) -> str | None:
    product_match = re.search(
        r"(?:product|platform|solution|ferramenta|solu[cç][ãa]o|produto)[:\s]+([A-Z][A-Za-z0-9\s\-]{2,40}?)(?:\s+(?:foi|[eé]|para|que|,|\.|$))",
        text,
    )
    return product_match.group(1).strip() if product_match else None


def _extract_founders(text: str) -> list[str]:
    return list({m.group(1).strip() for m in FOUNDER_PATTERN.finditer(text)})


def _extract_funding(text: str) -> str | None:
    for pattern in FUNDING_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()[:100]
    return None


def _extract_technologies(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern, tech_name in TECHNOLOGY_KEYWORDS:
        if pattern.search(text) and tech_name not in seen:
            found.append(tech_name)
            seen.add(tech_name)
    return found


def _infer_claim_type(text: str) -> str:
    has_ai_marker = any(p.search(text) for p in AI_MARKER_PATTERNS)
    has_semantic_ai = any(p.search(text) for p in _SEMANTIC_AI_PATTERNS)
    if has_ai_marker and has_semantic_ai:
        return "ai_usage"
    if has_ai_marker:
        return "technology_signal"
    if any(p.search(text) for p in TECH_MARKER_PATTERNS):
        return "technology_signal"
    return "public_signal"


def _infer_claim_confidence(source_type: str, claim_type: str) -> float:
    base_confidence: Dict[str, float] = {
        "official_site": 0.7,
        "blog": 0.6,
        "careers": 0.55,
        "news": 0.55,
        "startup_directory": 0.5,
        "nvidia_documentation": 0.35,
        "other": 0.3,
    }
    base = base_confidence.get(source_type, 0.3)
    if claim_type == "ai_usage":
        return base
    if claim_type == "technology_signal":
        return max(base - 0.1, 0.0)
    return max(base - 0.2, 0.0)


def _summarize_ai_usage(
    ai_claims: list[EvidenceClaim],
    technologies: list[str],
    sector: str | None,
) -> str | None:
    if not ai_claims:
        return None
    tech_count = len(technologies)
    sector_info = f" no setor de {sector}" if sector else ""
    if tech_count >= 3:
        return (
            f"Evidencias indicam uso intensivo de IA{sector_info}, com "
            f"{tech_count} tecnologias citadas. Potencial perfil AI-Native."
        )
    if tech_count >= 1:
        return (
            f"Evidencias publicas mencionam uso de IA{sector_info}; "
            f"{tech_count} tecnologia(s) especifica(s) identificada(s)."
        )
    return (
        "Evidencias publicas mencionam uso de IA; "
        "dependente mais profunda de IA-native ainda requer validacao."
    )
