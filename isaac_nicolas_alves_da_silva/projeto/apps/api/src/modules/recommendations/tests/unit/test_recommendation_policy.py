"""Testes da politica de match determinístico (domain/policies.py).

Os cenarios espelham o mapeamento de tecnologias NVIDIA documentado no
CLAUDE.md (ex: "LLMs in customer service -> NIM, NeMo, TensorRT-LLM").

Passo 3 do Briefing V4: score composto substituiu o ratio de keywords puro.
Testes que antes assertavam score == 1.0 (keyword ratio perfeito) agora
verificam ranges e comportamentos relativos — a logica de negocio e a mesma,
mas a escala numerica mudou.
"""

from uuid import uuid4

from apps.api.src.modules.recommendations.domain.policies import (
    EvidenceSignal,
    StartupAIContext,
    TechnologyCandidate,
    _compute_nivel,
    _compute_faltando,
    _composite_confidence,
    _evidence_signal_score,
    _workload_alignment,
    match_technologies,
    MIN_MATCH_SCORE,
    NIVEL_FORTE,
    NIVEL_HIPOTESE,
    NIVEL_MODERADA,
    NIVEL_EXPLORATORIA,
    WORKLOAD_ADMISSION_THRESHOLD,
)

NIM = TechnologyCandidate(
    slug="nvidia-nim",
    name="NVIDIA NIM",
    category="model_serving",
    use_cases=("servir LLMs e modelos generativos em producao",),
    keywords=("llm", "generative ai", "inference", "api", "deployment", "microservice"),
    complexity="low",
    supported_workloads={"nlp": 0.80, "speech": 0.50, "analytics": 0.40},
)
NEMO = TechnologyCandidate(
    slug="nvidia-nemo",
    name="NVIDIA NeMo",
    category="model_training",
    use_cases=("fine-tuning de modelos generativos",),
    keywords=("training", "fine tuning", "llm", "agent", "generative ai", "speech"),
    complexity="high",
    supported_workloads={"nlp": 0.90, "speech": 0.70, "mlops": 0.50},
)
RIVA = TechnologyCandidate(
    slug="riva",
    name="NVIDIA Riva",
    category="speech_ai",
    use_cases=("automatic speech recognition",),
    keywords=("speech", "asr", "tts", "voice", "translation", "conversational ai"),
    complexity="medium",
    supported_workloads={"speech": 0.99, "nlp": 0.40},
)
MONAI = TechnologyCandidate(
    slug="monai",
    name="MONAI",
    category="healthcare_ai",
    use_cases=("analise de imagens medicas",),
    keywords=("healthcare", "medical imaging", "monai", "segmentation", "radiology", "clinical ai"),
    complexity="high",
    supported_workloads={"vision": 0.95, "analytics": 0.30},
)
RAPIDS = TechnologyCandidate(
    slug="rapids",
    name="RAPIDS",
    category="data_science",
    use_cases=("acelerar pipelines de data science",),
    keywords=("data science", "analytics", "dataframe", "gpu", "pandas", "spark"),
    complexity="medium",
    supported_workloads={"analytics": 0.95, "recommendation": 0.75, "mlops": 0.60},
)
CUDF = TechnologyCandidate(
    slug="cudf",
    name="cuDF",
    category="data_science",
    use_cases=("acelerar processamento de dataframes",),
    keywords=("dataframe", "pandas", "gpu", "rapids", "etl", "data science"),
    complexity="low",
    supported_workloads={"analytics": 0.95, "recommendation": 0.55, "mlops": 0.50},
)
CUML = TechnologyCandidate(
    slug="cuml",
    name="cuML",
    category="data_science",
    use_cases=("acelerar machine learning classico",),
    keywords=("machine learning", "scikit-learn", "gpu", "rapids", "clustering"),
    complexity="low",
    supported_workloads={"analytics": 0.85, "recommendation": 0.70, "mlops": 0.70},
)
CATALOG = [NIM, NEMO, RIVA, MONAI, RAPIDS]


def test_llm_customer_service_profile_matches_nim_and_nemo() -> None:
    results = match_technologies(
        sector="LLM and generative AI",
        description=(
            "Provides inference API with simple deployment as microservice "
            "architecture."
        ),
        evidence_signals=[],
        technologies=CATALOG,
    )

    slugs = [result.technology.slug for result in results]
    assert "nvidia-nim" in slugs
    assert "nvidia-nemo" in slugs
    assert "riva" not in slugs
    assert "monai" not in slugs

    nim_result = next(result for result in results if result.technology.slug == "nvidia-nim")
    assert set(nim_result.matched_keywords) == set(NIM.keywords)
    # Com score composto, perfil-only sem ai_context: score esta em torno de 0.40-0.55
    assert nim_result.score > 0.30


def test_healthcare_profile_matches_monai_only() -> None:
    results = match_technologies(
        sector="Healthcare AI for medical imaging",
        description=(
            "Clinical AI platform for radiology segmentation using MONAI."
        ),
        evidence_signals=[],
        technologies=CATALOG,
    )

    slugs = [result.technology.slug for result in results]
    assert slugs == ["monai"]
    assert results[0].score > 0.30


def test_voice_profile_matches_riva_only() -> None:
    results = match_technologies(
        sector="Voice AI startup",
        description=(
            "Provides automatic speech recognition (asr), text-to-speech "
            "(tts), and voice translation for conversational ai assistants."
        ),
        evidence_signals=[],
        technologies=CATALOG,
    )

    slugs = [result.technology.slug for result in results]
    assert slugs == ["riva"]
    assert results[0].score > 0.30


def test_profile_without_ai_evidence_returns_no_matches() -> None:
    results = match_technologies(
        sector="Traditional retail",
        description="Sells shoes in physical stores.",
        evidence_signals=[],
        technologies=CATALOG,
    )

    assert results == []


def test_structured_analytics_profile_admits_rapids_family_without_literal_keywords() -> None:
    """P2: perfil analytics/tabular/producao deve admitir RAPIDS/cuDF/cuML."""

    results = match_technologies(
        sector="Pricing optimization",
        description="Processes millions of prices per day for pricing decisions.",
        ai_context=StartupAIContext(
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="unknown",
            has_operational_signal=True,
        ),
        evidence_signals=[],
        technologies=[RAPIDS, CUDF, CUML, NIM],
    )

    slugs = [result.technology.slug for result in results]
    assert "rapids" in slugs
    assert "cudf" in slugs
    assert "cuml" in slugs
    assert "nvidia-nim" not in slugs
    assert all(result.matched_keywords == () for result in results)
    assert all(
        "workload estruturado: analytics" in result.signal_origins
        for result in results
    )


def test_structured_analytics_profile_does_not_admit_non_data_categories_without_keywords() -> None:
    """Analytics estruturado nao deve virar speech/training sem sinal textual."""

    broad_riva = TechnologyCandidate(
        slug="riva",
        name="NVIDIA Riva",
        category="speech_ai",
        use_cases=("automatic speech recognition",),
        keywords=RIVA.keywords,
        complexity="medium",
        supported_workloads={"analytics": 0.80, "nlp": 0.80, "speech": 0.99},
    )
    broad_nemo = TechnologyCandidate(
        slug="nvidia-nemo",
        name="NVIDIA NeMo",
        category="model_training",
        use_cases=("fine-tuning de modelos generativos",),
        keywords=NEMO.keywords,
        complexity="high",
        supported_workloads={"analytics": 0.80, "nlp": 0.90},
    )

    results = match_technologies(
        sector="B2B sales intelligence",
        description="Processes company records and market data for sales teams.",
        ai_context=StartupAIContext(
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="unknown",
            has_operational_signal=True,
            profile_strength=0.75,
        ),
        evidence_signals=[],
        technologies=[broad_riva, broad_nemo, RAPIDS],
    )

    slugs = [result.technology.slug for result in results]
    assert "riva" not in slugs
    assert "nvidia-nemo" not in slugs
    assert "rapids" in slugs


def test_match_found_only_in_evidence_text_is_traceable() -> None:
    evidence_id = uuid4()
    results = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=evidence_id,
                text="our new generative ai inference api deployment as a microservice",
            )
        ],
        technologies=CATALOG,
    )

    assert len(results) == 1
    assert results[0].technology.slug == "nvidia-nim"
    assert results[0].evidence_ids == (evidence_id,)


def test_results_are_sorted_by_score_descending() -> None:
    results = match_technologies(
        sector="LLM and generative AI",
        description="Provides inference API with simple deployment as microservice.",
        evidence_signals=[],
        technologies=CATALOG,
    )

    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)


def test_operational_aliases_match_ai_infrastructure_signals() -> None:
    results = match_technologies(
        sector="AI infrastructure",
        description="",
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text="train fine-tune and deploy serverless inference workloads at scale",
            )
        ],
        technologies=CATALOG,
    )

    slugs = [result.technology.slug for result in results]
    assert "nvidia-nim" in slugs
    assert "nvidia-nemo" in slugs


def test_ai_native_maturity_level_boosts_implementation_viability() -> None:
    """ai_native recebe bonus na dimensao impl_viab — score deve ser maior."""

    results_native = match_technologies(
        sector=None,
        description=None,
        ai_maturity_level="ai_native",
        evidence_signals=[
            EvidenceSignal(evidence_id=uuid4(), text="fine-tune llm models")
        ],
        technologies=[NEMO],
    )
    results_enabled = match_technologies(
        sector=None,
        description=None,
        ai_maturity_level="ai_enabled",
        evidence_signals=[
            EvidenceSignal(evidence_id=uuid4(), text="fine-tune llm models")
        ],
        technologies=[NEMO],
    )

    assert results_native[0].technology.slug == "nvidia-nemo"
    assert results_native[0].score > results_enabled[0].score


def test_single_generic_keyword_is_not_enough_for_recommendation() -> None:
    results = match_technologies(
        sector=None,
        description=None,
        ai_maturity_level="ai_native",
        evidence_signals=[EvidenceSignal(evidence_id=uuid4(), text="platform")],
        technologies=[
            TechnologyCandidate(
                slug="nvidia-ai-enterprise",
                name="NVIDIA AI Enterprise",
                category="ai_platform",
                use_cases=("padronizar stack corporativa de IA",),
                keywords=(
                    "enterprise",
                    "platform",
                    "governance",
                    "deployment",
                    "support",
                    "infrastructure",
                ),
            )
        ],
    )

    assert results == []


def test_word_boundary_avoids_cross_language_false_positives() -> None:
    """Reproduz o bug real encontrado com https://dadosfera.com.br: o texto
    raspado em portugues continha "agentes"/"agente de ia" e "escale com ia",
    que batiam por substring puro nas keywords em ingles "agent" e no alias
    "scale" de "throughput" sem nenhuma relacao semantica real.
    """

    results = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text=(
                    "seu proprio agente de ia interpreta perguntas. agentes "
                    "autonomos com acesso a base de conhecimento. organize, "
                    "otimize e escale com ia."
                ),
            )
        ],
        technologies=CATALOG,
    )

    assert results == []


def test_word_boundary_still_matches_real_standalone_keywords() -> None:
    evidence_id = uuid4()
    results = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=evidence_id,
                text="we are building an llm-based ai agent platform for enterprise teams",
            )
        ],
        technologies=[NEMO],
    )

    assert len(results) == 1
    assert results[0].technology.slug == "nvidia-nemo"
    assert "agent" in results[0].matched_keywords
    assert "llm" in results[0].matched_keywords


def test_negative_training_context_does_not_create_nemo_match() -> None:
    """Frases de privacidade sobre nao treinar modelos nao sao sinal de NeMo."""

    results = match_technologies(
        sector="saas",
        description=(
            "B2B SaaS powered by generative AI API. "
            "No own model training and no own GPU infrastructure."
        ),
        ai_maturity_level="ai_enabled",
        ai_context=StartupAIContext(ai_workload_type="nlp", gpu_need="low"),
        evidence_signals=[],
        technologies=[NEMO],
    )

    assert results == []


def test_negative_training_context_is_reported_when_other_nemo_signals_match() -> None:
    evidence_id = uuid4()
    results = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=evidence_id,
                text="enterprise llm ai agent with no training on your data",
            )
        ],
        technologies=[NEMO],
    )

    assert len(results) == 1
    assert "training" not in results[0].matched_keywords
    assert any("training" in item for item in results[0].faltando)


def test_confidence_higher_with_strong_evidence_than_profile_only() -> None:
    """Match com evidencia de alta qualidade tem confianca maior que perfil puro."""

    high_conf_id = uuid4()
    results_with_evidence = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=high_conf_id,
                text="generative ai inference api deployment microservice",
                confidence_score=0.9,
            )
        ],
        technologies=[NIM],
    )
    results_profile_only = match_technologies(
        sector="LLM and generative AI inference API deployment microservice",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results_with_evidence) == 1
    assert len(results_profile_only) == 1
    assert results_with_evidence[0].confidence > results_profile_only[0].confidence


def test_technical_source_increases_confidence_over_generic_website() -> None:
    """Docs/API/blog tecnico valem mais que landing page para confianca."""

    technical_id = uuid4()
    generic_id = uuid4()
    technical = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=technical_id,
                text="generative ai inference api deployment microservice",
                confidence_score=0.9,
                source_url="https://acme.ai/docs/api",
                evidence_type="documentation",
            )
        ],
        technologies=[NIM],
    )
    generic = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=generic_id,
                text="generative ai inference api deployment microservice",
                confidence_score=0.9,
                source_url="https://acme.ai/product",
                evidence_type="website",
            )
        ],
        technologies=[NIM],
    )

    assert technical[0].confidence > generic[0].confidence


def test_technical_evidence_type_counts_as_high_quality_source() -> None:
    """Evidence type technical tem peso alto mesmo fora de /docs."""

    technical = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text="generative ai inference api deployment microservice",
                confidence_score=0.9,
                source_url="https://jobs.lever.co/acme/data-engineer",
                evidence_type="technical",
            )
        ],
        technologies=[NIM],
    )
    generic = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text="generative ai inference api deployment microservice",
                confidence_score=0.9,
                source_url="https://acme.ai/about",
                evidence_type="website",
            )
        ],
        technologies=[NIM],
    )

    assert technical[0].confidence > generic[0].confidence


def test_confidence_is_lower_for_profile_only_match() -> None:
    """Match que veio so do perfil (setor/descricao) recebe confianca reduzida.

    Com a nova formula, source_quality=0 e evidence_depth=0 quando nao ha
    evidencias. A confianca fica abaixo do score composto.
    """

    results = match_technologies(
        sector="LLM and generative AI inference API deployment microservice",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    assert results[0].confidence < 0.5
    assert results[0].confidence < results[0].score


def test_confidence_reflects_multiple_evidence_sources() -> None:
    """Mais evidencias independentes → profundidade maior → confianca maior."""

    results_two_evid = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(evidence_id=uuid4(), text="llm inference api deployment microservice", confidence_score=0.8),
            EvidenceSignal(evidence_id=uuid4(), text="generative ai deployment", confidence_score=0.4),
        ],
        technologies=[NIM],
    )
    results_one_evid = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(evidence_id=uuid4(), text="llm inference api deployment microservice", confidence_score=0.8),
        ],
        technologies=[NIM],
    )

    assert len(results_two_evid) == 1
    assert len(results_one_evid) == 1
    # Mais evidencias independentes deve produzir maior confianca
    assert results_two_evid[0].confidence > results_one_evid[0].confidence


def test_signal_origins_identifies_profile_source() -> None:
    """signal_origins marca 'setor/descricao' quando a keyword bateu no perfil."""

    results = match_technologies(
        sector="llm inference api deployment microservice",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    origins = results[0].signal_origins
    assert any("setor/descrição" in o for o in origins)
    assert not any("evidência" in o for o in origins)


def test_signal_origins_identifies_evidence_source() -> None:
    """signal_origins marca a evidencia quando a keyword bateu so em evidencia."""

    eid = uuid4()
    results = match_technologies(
        sector=None,
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=eid,
                text="generative ai llm inference api deployment microservice",
            )
        ],
        technologies=[NIM],
    )

    assert len(results) == 1
    short = str(eid)[:8]
    assert any(f"evidência {short}" in o for o in results[0].signal_origins)
    assert not any("setor/descrição" in o for o in results[0].signal_origins)


def test_signal_origins_marks_both_when_keyword_hits_profile_and_evidence() -> None:
    """Keyword que bate no perfil E na evidencia aparece com as duas origens."""

    eid = uuid4()
    results = match_technologies(
        sector="llm inference api deployment microservice",
        description=None,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=eid,
                text="llm inference api deployment microservice",
            )
        ],
        technologies=[NIM],
    )

    assert len(results) == 1
    short = str(eid)[:8]
    llm_origin = next(o for o in results[0].signal_origins if o.startswith("llm:"))
    assert "setor/descrição" in llm_origin
    assert f"evidência {short}" in llm_origin


def test_missing_signals_lists_unmatched_catalog_keywords() -> None:
    """missing_signals contem as keywords do catalogo que nao encontraram sinal."""

    results = match_technologies(
        sector="llm generative ai inference",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    missing = results[0].missing_signals
    # "api", "deployment", "microservice" nao aparecem no perfil acima
    assert "api" in missing
    assert "deployment" in missing
    assert "microservice" in missing
    # keywords que bateram NAO devem aparecer em missing_signals
    assert "llm" not in missing
    assert "inference" not in missing


def test_missing_signals_is_empty_when_all_keywords_match() -> None:
    """Quando todas as keywords batem, missing_signals fica vazio."""

    results = match_technologies(
        sector="LLM and generative AI",
        description=(
            "Provides inference API with simple deployment as microservice architecture."
        ),
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    assert results[0].matched_keywords == NIM.keywords
    assert results[0].missing_signals == ()


def test_complexity_propagated_from_candidate() -> None:
    """complexity do TechnologyCandidate aparece no MatchResult via TechnologyCandidate."""

    nim_low = TechnologyCandidate(
        slug="nvidia-nim",
        name="NVIDIA NIM",
        category="model_serving",
        use_cases=("servir LLMs",),
        keywords=("llm", "inference"),
        complexity="low",
    )
    results = match_technologies(
        sector="llm inference",
        description=None,
        evidence_signals=[],
        technologies=[nim_low],
    )

    assert len(results) == 1
    assert results[0].technology.complexity == "low"


# ---------------------------------------------------------------------------
# Novos testes: score composto (passo 3, Briefing V4)
# ---------------------------------------------------------------------------


def test_score_breakdown_has_five_dimensions() -> None:
    """MatchResult.score_breakdown contem as 5 dimensoes do score composto."""

    results = match_technologies(
        sector="llm inference api deployment microservice generative ai",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    breakdown = results[0].score_breakdown
    assert set(breakdown.keys()) == {
        "workload_alignment",
        "evidence_signal",
        "startup_maturity",
        "keyword_prior",
        "implementation_viability",
    }
    for v in breakdown.values():
        assert 0.0 <= v <= 1.0


def test_workload_alignment_boosts_score_for_matching_workload() -> None:
    """Startup NLP com ai_context nlp → alinhamento alto com NIM (nlp=0.80)."""

    ctx_nlp = StartupAIContext(ai_workload_type="nlp")
    ctx_analytics = StartupAIContext(ai_workload_type="analytics")

    results_nlp = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        ai_context=ctx_nlp,
        evidence_signals=[],
        technologies=[NIM],
    )
    results_analytics = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        ai_context=ctx_analytics,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert results_nlp[0].score > results_analytics[0].score
    assert results_nlp[0].score_breakdown["workload_alignment"] == 0.80
    assert results_analytics[0].score_breakdown["workload_alignment"] == 0.40


def test_production_stage_increases_startup_maturity_score() -> None:
    """Startup em producao tem score de maturidade maior que startup em research."""

    ctx_prod = StartupAIContext(deployment_stage="production")
    ctx_research = StartupAIContext(deployment_stage="research")

    results_prod = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        ai_context=ctx_prod,
        evidence_signals=[],
        technologies=[NIM],
    )
    results_research = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        ai_context=ctx_research,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert results_prod[0].score > results_research[0].score
    assert results_prod[0].score_breakdown["startup_maturity"] == 0.85
    assert results_research[0].score_breakdown["startup_maturity"] == 0.25


def test_low_gpu_high_complexity_reduces_viability() -> None:
    """Startup com baixa necessidade de GPU + tech de alta complexidade = impl_viab 0.20."""

    ctx_low_gpu = StartupAIContext(gpu_need="low")
    high_complexity_tech = TechnologyCandidate(
        slug="nvidia-nemo",
        name="NVIDIA NeMo",
        category="model_training",
        use_cases=("fine-tuning",),
        keywords=("training", "fine tuning", "llm", "agent"),
        complexity="high",
    )
    results = match_technologies(
        sector="llm training fine tuning agent",
        description=None,
        ai_context=ctx_low_gpu,
        evidence_signals=[],
        technologies=[high_complexity_tech],
    )

    assert len(results) == 1
    assert results[0].score_breakdown["implementation_viability"] == 0.20


def test_high_gpu_high_complexity_maximizes_viability() -> None:
    """Startup com alta GPU + tech complexa = impl_viab 0.90 (fit perfeito)."""

    ctx_high_gpu = StartupAIContext(gpu_need="high")
    results = match_technologies(
        sector="llm training fine tuning agent generative ai speech",
        description=None,
        ai_context=ctx_high_gpu,
        evidence_signals=[],
        technologies=[NEMO],
    )

    assert len(results) == 1
    assert results[0].score_breakdown["implementation_viability"] == 0.90


def test_operational_signal_increases_confidence() -> None:
    """Startup em producao tem confianca maior que startup sem sinal operacional."""

    ctx_prod = StartupAIContext(deployment_stage="production")
    ctx_unknown = StartupAIContext()

    results_prod = match_technologies(
        sector=None,
        description=None,
        ai_context=ctx_prod,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text="llm generative ai inference api deployment microservice",
                confidence_score=0.7,
            )
        ],
        technologies=[NIM],
    )
    results_unknown = match_technologies(
        sector=None,
        description=None,
        ai_context=ctx_unknown,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text="llm generative ai inference api deployment microservice",
                confidence_score=0.7,
            )
        ],
        technologies=[NIM],
    )

    assert results_prod[0].confidence > results_unknown[0].confidence


def test_has_operational_signal_counts_as_production_for_confidence() -> None:
    """has_operational_signal=True equivale a sinal operacional mesmo sem stage."""

    ctx_with_signal = StartupAIContext(has_operational_signal=True)
    ctx_without = StartupAIContext()

    eid = uuid4()
    results_with = match_technologies(
        sector=None,
        description=None,
        ai_context=ctx_with_signal,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=eid,
                text="llm generative ai inference api deployment microservice",
            )
        ],
        technologies=[NIM],
    )
    results_without = match_technologies(
        sector=None,
        description=None,
        ai_context=ctx_without,
        evidence_signals=[
            EvidenceSignal(
                evidence_id=eid,
                text="llm generative ai inference api deployment microservice",
            )
        ],
        technologies=[NIM],
    )

    assert results_with[0].confidence > results_without[0].confidence


# ---------------------------------------------------------------------------
# Novos testes: nivel e faltando (passo 5, Briefing V4)
# ---------------------------------------------------------------------------


def test_compute_nivel_forte_when_score_and_confidence_are_high() -> None:
    assert _compute_nivel(score=0.65, confidence=0.60) == NIVEL_FORTE


def test_compute_nivel_moderada_when_score_moderate_and_confidence_meets_floor() -> None:
    assert _compute_nivel(score=0.45, confidence=0.30) == NIVEL_MODERADA


def test_compute_nivel_exploratoria_when_below_moderada_thresholds() -> None:
    assert _compute_nivel(score=0.30, confidence=0.15) == NIVEL_EXPLORATORIA


def test_compute_nivel_hipotese_prioritaria_when_score_high_but_confidence_low() -> None:
    assert _compute_nivel(score=0.70, confidence=0.20) == NIVEL_HIPOTESE


def test_compute_nivel_moderada_when_confidence_meets_but_score_below_forte() -> None:
    assert _compute_nivel(score=0.45, confidence=0.58) == NIVEL_MODERADA


def test_compute_faltando_empty_for_forte() -> None:
    faltando = _compute_faltando(
        nivel=NIVEL_FORTE,
        score_breakdown={},
        confidence=0.80,
        missing_signals=("speech",),
        evidence_count=2,
    )
    assert faltando == ()


def test_compute_faltando_suggests_evidence_for_exploratoria_with_low_evidence_signal() -> None:
    faltando = _compute_faltando(
        nivel=NIVEL_EXPLORATORIA,
        score_breakdown={"evidence_signal": 0.20, "keyword_prior": 0.60, "startup_maturity": 0.50, "workload_alignment": 0.50},
        confidence=0.30,
        missing_signals=(),
        evidence_count=0,
    )
    assert any("evidência" in item.lower() for item in faltando)


def test_compute_faltando_lists_missing_signals_for_exploratoria() -> None:
    faltando = _compute_faltando(
        nivel=NIVEL_EXPLORATORIA,
        score_breakdown={"evidence_signal": 0.25, "keyword_prior": 0.30, "startup_maturity": 0.50, "workload_alignment": 0.40},
        confidence=0.30,
        missing_signals=("tts", "asr"),
        evidence_count=0,
    )
    assert any("tts" in item or "asr" in item for item in faltando)


def test_compute_faltando_suggests_maturity_for_moderada() -> None:
    faltando = _compute_faltando(
        nivel=NIVEL_MODERADA,
        score_breakdown={"workload_alignment": 0.50, "startup_maturity": 0.50, "evidence_signal": 0.40},
        confidence=0.40,
        missing_signals=(),
        evidence_count=2,
    )
    assert any("produção" in item or "escala" in item for item in faltando)


def test_match_technologies_populates_nivel_in_results() -> None:
    """match_technologies deve retornar MatchResult com nivel preenchido."""

    results = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    assert results[0].nivel in {NIVEL_FORTE, NIVEL_MODERADA, NIVEL_EXPLORATORIA}


def test_match_technologies_forte_with_strong_context_and_evidence() -> None:
    """Startup com workload NLP, producao, alta GPU e boa evidencia → forte."""

    results = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        ai_maturity_level="ai_native",
        ai_context=StartupAIContext(
            ai_workload_type="nlp",
            deployment_stage="production",
            gpu_need="high",
            has_operational_signal=True,
        ),
        evidence_signals=[
            EvidenceSignal(
                evidence_id=uuid4(),
                text="llm generative ai inference api deployment microservice",
                confidence_score=0.9,
            ),
            EvidenceSignal(
                evidence_id=uuid4(),
                text="inference api generative ai deployment",
                confidence_score=0.8,
            ),
        ],
        technologies=[NIM],
    )

    assert len(results) == 1
    assert results[0].nivel == NIVEL_FORTE


def test_match_technologies_faltando_present_for_non_forte() -> None:
    """Recomendacao nao-forte deve ter faltando com pelo menos 1 sugestao."""

    results = match_technologies(
        sector="llm inference api",
        description=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    assert results[0].nivel != NIVEL_FORTE
    assert len(results[0].faltando) >= 1


def test_no_ai_context_uses_neutral_defaults() -> None:
    """Sem ai_context, todos os componentes sao neutros e o resultado e valido."""

    results = match_technologies(
        sector="llm generative ai inference api deployment microservice",
        description=None,
        ai_context=None,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    # workload_alignment=0.40, evidence_signal=0.20, startup_maturity=0.50,
    # keyword_prior=1.0, impl_viab=0.60
    # score = 0.35*0.40 + 0.25*0.20 + 0.15*0.50 + 0.15*1.0 + 0.10*0.60
    #       = 0.14 + 0.05 + 0.075 + 0.15 + 0.06 = 0.475 → 0.48
    assert 0.40 <= results[0].score <= 0.60


def test_workload_admission_admits_with_one_keyword_when_alignment_strong() -> None:
    """P2: uma startup com workload nlp + 1 keyword bate => NIM admitido."""

    nlp_context = StartupAIContext(
        ai_workload_type="nlp",
        deployment_stage="production",
        gpu_need="medium",
        has_operational_signal=True,
    )
    # NIM tem supported_workloads={"nlp": 0.80} => workload_aln=0.80 >= threshold
    # Startup so tem "llm" no setor (1 de 6 keywords) => sem a porta workload ficaria
    # bloqueado por MIN_MATCHED_KEYWORDS=2; com a porta, deve ser admitido
    results = match_technologies(
        sector="llm platform",
        description=None,
        ai_context=nlp_context,
        evidence_signals=[],
        technologies=[NIM],
    )

    assert len(results) == 1
    assert results[0].technology.slug == "nvidia-nim"
    assert results[0].matched_keywords == ("llm",)
    # Score com 1 keyword: keyword_prior=1/6=0.17, workload_aln=0.80
    # score = 0.35*0.80 + 0.25*0.20 + 0.15*0.85 + 0.15*0.17 + 0.10*0.55 ≈ 0.50
    assert results[0].score >= MIN_MATCH_SCORE


def test_workload_admission_does_not_admit_with_zero_keywords() -> None:
    """P2: mesmo com workload forte, zero keywords => nao admitido."""

    nlp_context = StartupAIContext(
        ai_workload_type="nlp",
        deployment_stage="production",
        gpu_need="medium",
    )
    # Startup sem nenhuma keyword do RIVA (speech/asr/tts/voice/translation/conversational ai)
    results = match_technologies(
        sector="data analytics platform",
        description="financial reporting and dashboards",
        ai_context=nlp_context,
        evidence_signals=[],
        technologies=[RIVA],
    )

    assert len(results) == 0


def test_workload_admission_does_not_admit_when_alignment_below_threshold() -> None:
    """P2: 1 keyword + workload_aln < 0.60 => nao admitido."""

    analytics_context = StartupAIContext(
        ai_workload_type="analytics",
        deployment_stage="production",
        gpu_need="low",
    )
    # NeMo tem supported_workloads={"analytics": nao definido -> 0.0} => nao atinge threshold
    # Com 1 keyword "llm" no setor, nao deve ser admitido
    results = match_technologies(
        sector="llm platform",
        description=None,
        ai_context=analytics_context,
        evidence_signals=[],
        technologies=[NEMO],  # NEMO nao suporta analytics bem
    )

    # Sem keyword suficiente e sem alinhamento de workload => zero resultados
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Novos testes: perfil estruturado como evidencia (profile_strength)
# ---------------------------------------------------------------------------


def test_evidence_signal_score_credits_profile_strength_without_matched_evidence() -> None:
    """Admitida so por perfil (sem evidencia casada): field_confidence alto do
    perfil de IA deve elevar o evidence_signal acima do piso historico 0.20,
    porque o perfil foi extraido de fonte real (field_evidence_ids)."""

    score = _evidence_signal_score(
        matched_evidence_ids=set(),
        evidence_signals=[],
        profile_strength=0.75,
    )

    assert score > 0.20
    assert score == round(0.9 * 0.75, 2)


def test_evidence_signal_score_keeps_floor_when_profile_strength_is_zero() -> None:
    score = _evidence_signal_score(
        matched_evidence_ids=set(),
        evidence_signals=[],
        profile_strength=0.0,
    )

    assert score == 0.20


def test_composite_confidence_profile_path_beats_old_floor() -> None:
    """Admitida por workload com perfil forte deve sair de ~0.29 para >= 0.55
    (forte), creditando profile_strength como prova indireta."""

    ai_context = StartupAIContext(
        ai_workload_type="analytics",
        deployment_stage="production",
        gpu_need="unknown",
        has_operational_signal=True,
        profile_strength=0.75,
    )

    confidence = _composite_confidence(
        evidence_signals=[],
        matched_evidence_ids=set(),
        keyword_prior=0.0,
        workload_aln=0.95,
        ai_context=ai_context,
    )

    assert confidence >= 0.55


def test_profile_only_with_missing_signals_is_not_promoted_to_forte() -> None:
    results = match_technologies(
        sector="Pricing optimization",
        description="Processes millions of prices per day for pricing decisions.",
        ai_context=StartupAIContext(
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="unknown",
            has_operational_signal=True,
            profile_strength=0.75,
        ),
        evidence_signals=[],
        technologies=[RAPIDS],
    )

    assert len(results) == 1
    assert results[0].matched_keywords == ()
    assert results[0].evidence_ids == ()
    assert results[0].missing_signals
    assert results[0].nivel == NIVEL_MODERADA
    assert results[0].faltando


def test_composite_confidence_falls_back_to_evidence_path_without_profile() -> None:
    """Sem profile_strength, o caminho de perfil nao deve superar o
    comportamento historico de perfil-only (confianca baixa)."""

    confidence = _composite_confidence(
        evidence_signals=[],
        matched_evidence_ids=set(),
        keyword_prior=0.0,
        workload_aln=0.40,
        ai_context=None,
    )

    assert confidence < 0.30


def test_workload_alignment_uses_secondary_workload_when_primary_does_not_align() -> None:
    """Driva/Econodata: workload primario 'analytics' nao alinha com NIM, mas
    o sinal secundario 'nlp' (copiloto/agente) detectado no texto deve fazer
    NIM alinhar mesmo assim."""

    ctx_primary_only = StartupAIContext(ai_workload_type="analytics")
    ctx_with_secondary = StartupAIContext(
        ai_workload_type="analytics", secondary_workloads=("nlp",)
    )

    score_primary_only = _workload_alignment(ctx_primary_only, NIM)
    score_with_secondary = _workload_alignment(ctx_with_secondary, NIM)

    assert score_with_secondary == NIM.supported_workloads["nlp"]
    assert score_with_secondary > score_primary_only


# ---------------------------------------------------------------------------
# Novo teste: Morpheus nao dispara mais por workload "analytics"
# ---------------------------------------------------------------------------


def test_morpheus_is_not_recommended_for_analytics_profile_without_security_signal() -> None:
    """Bug corrigido: Morpheus tinha supported_workloads={"analytics": 0.65},
    causando falso-positivo em qualquer startup de analytics/dados, sem
    nenhum sinal real de ciberseguranca. Agora so deve aparecer por keyword."""

    morpheus = TechnologyCandidate(
        slug="nvidia-morpheus",
        name="NVIDIA Morpheus",
        category="cybersecurity",
        use_cases=("detectar ameacas de seguranca em tempo real",),
        keywords=(
            "cybersecurity",
            "morpheus",
            "threat detection",
            "anomaly detection",
            "security",
            "incident response",
        ),
        complexity="high",
        supported_workloads={},
    )

    results = match_technologies(
        sector="Pricing optimization",
        description="Processes millions of prices per day for pricing decisions.",
        ai_context=StartupAIContext(
            ai_workload_type="analytics",
            deployment_stage="production",
            gpu_need="unknown",
            has_operational_signal=True,
            profile_strength=0.75,
        ),
        evidence_signals=[],
        technologies=[morpheus],
    )

    assert results == []
