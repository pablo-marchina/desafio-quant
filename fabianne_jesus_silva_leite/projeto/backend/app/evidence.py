import re

from app.schemas import (
    Evidence,
    EvidenceValidationReport,
    Gap,
    StartupProfile,
)
from collections import Counter
from urllib.parse import urlparse

AI_KEYWORDS = [
    "inteligência artificial",
    "inteligencia artificial",
    "ia generativa",
    "generative ai",
    "machine learning",
    "aprendizado de máquina",
    "aprendizado de maquina",
    "modelo de linguagem",
    "llm",
    "automação",
    "automacao",
    "agente de ia",
    "agentes de ia",
    "análise de documentos",
    "analise de documentos",
    "processamento de linguagem natural",
    "visão computacional",
    "visao computacional"
]

EVIDENCE_RULES = [
    {
        "category": "ai_product",
        "claim": "A fonte descreve IA como parte do produto ou serviço da startup.",
        "keywords": [
            "inteligência artificial",
            "inteligencia artificial",
            "agentes de ia",
            "agente de ia",
            "machine learning",
            "ia jurídica",
            "ia juridica",
        ],
    },
    {
        "category": "workflow_depth",
        "claim": "A fonte descreve IA integrada a um workflow operacional real.",
        "keywords": [
            "contencioso",
            "processos",
            "provas",
            "audiência",
            "audiencia",
            "defesa jurídica",
            "defesa juridica",
            "documentos internos",
            "sistemas internos",
            "workflow",
            "operação",
            "operacao",
        ],
    },
    {
        "category": "proprietary_data",
        "claim": "A fonte menciona dados internos, proprietários ou operacionais.",
        "keywords": [
            "dados proprietários",
            "dados proprietarios",
            "dados internos",
            "documentos internos",
            "informações internas",
            "informacoes internas",
            "dados reais da nossa operação",
            "dados reais da nossa operacao",
        ],
    },
    {
        "category": "governance_security",
        "claim": "A fonte menciona controles de governança, segurança ou validação humana.",
        "keywords": [
            "governança",
            "governanca",
            "rastreabilidade",
            "auditoria",
            "lgpd",
            "soc 2",
            "iso 27001",
            "iso 27701",
            "validação",
            "validacao",
            "revisão",
            "revisao",
            "zero retenção",
            "zero retencao",
            "criptografia",
        ],
    },
    {
        "category": "scale_traction",
        "claim": "A fonte apresenta sinais públicos de escala, tração ou operação empresarial.",
        "keywords": [
            "grandes empresas",
            "clientes",
            "centenas de milhares",
            "milhares de documentos",
            "rodada",
            "captação",
            "captacao",
            "valuation",
            "unicórnio",
            "unicornio",
            "escala",
        ],
    },
    {
        "category": "model_and_serving",
        "claim": "A fonte menciona sinais públicos sobre modelos, infraestrutura ou serving.",
        "keywords": [
            "llm",
            "modelo de linguagem",
            "inferência",
            "inferencia",
            "latência",
            "latencia",
            "triton",
            "tensorrt",
            "nim",
        ],
    },
]

def split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) >= 30
    ]


def find_sentences_with_keywords(
    text: str,
    keywords: list[str],
    limit: int = 5
) -> list[tuple[str, str]]:
    found = []
    used_sentences = set()

    for sentence in split_sentences(text):
        sentence_lower = sentence.lower()

        for keyword in keywords:
            if keyword in sentence_lower and sentence not in used_sentences:
                found.append((keyword, sentence))
                used_sentences.add(sentence)
                break

        if len(found) >= limit:
            break

    return found

def has_exact_keyword(sentence: str, keyword: str) -> bool:
    pattern = rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)"

    return re.search(pattern, sentence.casefold()) is not None

def build_evidences(
    clean_text: str,
    source_url: str
) -> tuple[list[Evidence], list[str]]:
    evidences = []
    ai_signals = set()
    category_counts = Counter()
    seen = set()

    for sentence in split_sentences(clean_text):
        sentence_lower = sentence.casefold()

        for keyword in AI_KEYWORDS:
            if has_exact_keyword(sentence_lower, keyword):
                ai_signals.add(keyword)

        for rule in EVIDENCE_RULES:
            category = rule["category"]

            if category_counts[category] >= 4:
                continue

            has_match = any(
                has_exact_keyword(sentence_lower, keyword)
                for keyword in rule["keywords"]
            )

            if not has_match:
                continue

            fingerprint = (category, sentence_lower)

            if fingerprint in seen:
                continue

            seen.add(fingerprint)
            category_counts[category] += 1

            evidences.append(
                Evidence(
                    claim=rule["claim"],
                    quote=sentence[:500],
                    source_url=source_url,
                    status="OBSERVADA",
                    confidence=0.95,
                    category=category,
                )
            )

    return evidences, sorted(ai_signals)

ALLOWED_STATUSES = {
    "OBSERVADA",
    "INFERIDA",
    "DESCONHECIDA",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def is_valid_public_url(url: str) -> bool:
    parsed = urlparse(url)

    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_evidences(
    evidences: list[Evidence]
) -> tuple[list[Evidence], EvidenceValidationReport]:
    valid_evidences = []
    seen_fingerprints = set()
    invalid_reasons = Counter()
    duplicate_count = 0

    for evidence in evidences:
        if not evidence.claim.strip():
            invalid_reasons["claim ausente"] += 1
            continue

        if len(evidence.quote.strip()) < 20:
            invalid_reasons["quote ausente ou curta"] += 1
            continue

        if not is_valid_public_url(evidence.source_url):
            invalid_reasons["source_url inválida"] += 1
            continue

        if evidence.status not in ALLOWED_STATUSES:
            invalid_reasons["status inválido"] += 1
            continue

        fingerprint = (
            evidence.category,
            evidence.source_url,
            normalize_text(evidence.quote),
        )

        if fingerprint in seen_fingerprints:
            duplicate_count += 1
            continue

        seen_fingerprints.add(fingerprint)
        valid_evidences.append(evidence)

    report = EvidenceValidationReport(
        total_received=len(evidences),
        valid_count=len(valid_evidences),
        duplicate_count=duplicate_count,
        invalid_count=sum(invalid_reasons.values()),
        invalid_reasons=[
            f"{reason}: {count}"
            for reason, count in invalid_reasons.items()
        ],
    )

    return valid_evidences, report


def build_startup_profile(
    evidences: list[Evidence]
) -> StartupProfile:
    grouped = {
        "ai_product": [],
        "workflow_depth": [],
        "proprietary_data": [],
        "governance_security": [],
        "scale_traction": [],
        "model_and_serving": [],
    }

    for evidence in evidences:
        if evidence.category in grouped:
            grouped[evidence.category].append(evidence)

    return StartupProfile(**grouped)


def build_gaps(profile: StartupProfile) -> list[Gap]:
    checks = [
        (
            "proprietary_data",
            profile.proprietary_data,
            "Não foram encontradas evidências públicas suficientes sobre dados internos, proprietários ou feedback loops.",
        ),
        (
            "governance_security",
            profile.governance_security,
            "Não foram encontradas evidências públicas suficientes sobre governança, auditoria, privacidade ou validação humana.",
        ),
        (
            "model_and_serving",
            profile.model_and_serving,
            "Não foram encontradas evidências públicas suficientes sobre modelos, serving, custo ou latência de inferência.",
        ),
        (
            "workflow_depth",
            profile.workflow_depth,
            "Não foram encontradas evidências públicas suficientes sobre integração da IA ao workflow operacional.",
        ),
    ]

    gaps = []

    for category, evidences, message in checks:
        if not evidences:
            gaps.append(
                Gap(
                    category=category,
                    status="DESCONHECIDA",
                    message=message,
                )
            )

    return gaps