from app.schemas import ClassificationResult, ScoreReason


WORKFLOW_KEYWORDS = [
    "jurídico",
    "juridico",
    "legal",
    "processos",
    "documentos",
    "operações",
    "operacoes",
    "clientes",
    "empresas",
    "plataforma",
    "workflow",
    "automação",
    "automacao"
]

SCALE_KEYWORDS = [
    "escala",
    "volume",
    "milhares",
    "milhões",
    "milhoes",
    "empresas",
    "clientes",
    "corporativo",
    "enterprise",
    "latência",
    "latencia",
    "performance"
]

NVIDIA_OPPORTUNITY_KEYWORDS = [
    "inteligência artificial",
    "inteligencia artificial",
    "machine learning",
    "llm",
    "modelo",
    "documentos",
    "dados",
    "latência",
    "latencia",
    "escala",
    "governança",
    "governanca",
    "privacidade",
    "automação",
    "automacao"
]


def calculate_scores(
    clean_text: str,
    ai_signals: list[str]
) -> ClassificationResult:
    text_lower = clean_text.lower()
    reasons = []

    ai_native_score = 0
    wrapper_risk_score = 50
    nvidia_opportunity_score = 0

    workflow_matches = [
        keyword
        for keyword in WORKFLOW_KEYWORDS
        if keyword in text_lower
    ]

    scale_matches = [
        keyword
        for keyword in SCALE_KEYWORDS
        if keyword in text_lower
    ]

    nvidia_matches = [
        keyword
        for keyword in NVIDIA_OPPORTUNITY_KEYWORDS
        if keyword in text_lower
    ]

    if ai_signals:
        ai_native_score += 35
        wrapper_risk_score -= 15

        reasons.append(
            ScoreReason(
                criterion="IA no produto",
                points=35,
                reason="Foram encontrados sinais públicos de IA no conteúdo analisado."
            )
        )

    if len(ai_signals) >= 3:
        ai_native_score += 15
        wrapper_risk_score -= 10

        reasons.append(
            ScoreReason(
                criterion="Diversidade de sinais de IA",
                points=15,
                reason="A fonte apresenta mais de um tipo de sinal relacionado a IA."
            )
        )

    if workflow_matches:
        ai_native_score += 20
        wrapper_risk_score -= 10

        reasons.append(
            ScoreReason(
                criterion="Profundidade de workflow",
                points=20,
                reason=(
                    "Foram encontrados sinais de integração com "
                    "processos, documentos ou operações."
                )
            )
        )

    if scale_matches:
        ai_native_score += 10

        reasons.append(
            ScoreReason(
                criterion="Produção e escala",
                points=10,
                reason=(
                    "A fonte apresenta sinais públicos de clientes, "
                    "escala, volume ou operação corporativa."
                )
            )
        )

    if nvidia_matches:
        points = min(40, len(nvidia_matches) * 5)
        nvidia_opportunity_score += points

        reasons.append(
            ScoreReason(
                criterion="Aderência a tecnologias NVIDIA",
                points=points,
                reason=(
                    "Foram encontrados sinais de dados, modelos, "
                    "escala, IA, documentos ou automação."
                )
            )
        )

    if ai_signals:
        nvidia_opportunity_score += 25

        reasons.append(
            ScoreReason(
                criterion="Maturidade de IA",
                points=25,
                reason=(
                    "A startup apresenta sinais públicos de uso "
                    "de IA no produto ou operação."
                )
            )
        )

    if workflow_matches:
        nvidia_opportunity_score += 15

        reasons.append(
            ScoreReason(
                criterion="Dor de negócio",
                points=15,
                reason=(
                    "O conteúdo sugere uma aplicação de IA "
                    "conectada a um workflow real."
                )
            )
        )

    ai_native_score = min(ai_native_score, 100)
    wrapper_risk_score = max(min(wrapper_risk_score, 100), 0)
    nvidia_opportunity_score = min(nvidia_opportunity_score, 100)

    if ai_native_score >= 50:
        category = "AI-native"
    elif ai_native_score >= 20:
        category = "AI-enabled"
    else:
        category = "Non-AI ou evidência insuficiente"

    return ClassificationResult(
        category=category,
        ai_native_score=ai_native_score,
        wrapper_risk_score=wrapper_risk_score,
        nvidia_opportunity_score=nvidia_opportunity_score,
        score_reasons=reasons
    )