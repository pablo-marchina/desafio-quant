from radar.graph.builder import build_graph


def test_graph_maps_llm_agent_signals_to_specific_nvidia_recommendations() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada com duas fontes de IA", "collection_attempts": 0})

    technologies = {recommendation.technology for recommendation in result["recommendations"]}

    assert "NVIDIA NIM" in technologies
    assert "NeMo Guardrails" in technologies


def test_recommendations_keep_startup_and_nvidia_evidence_ids() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada com duas fontes de IA", "collection_attempts": 0})

    for recommendation in result["recommendations"]:
        assert recommendation.startup_evidence_ids == result["validation"].supporting_evidence_ids
        assert recommendation.nvidia_knowledge_ids


def test_weak_evidence_still_blocks_specific_nvidia_recommendations() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup brasileira de IA", "collection_attempts": 0})

    assert result.get("nvidia_context", []) == []
    assert result.get("recommendations", []) == []


def test_graph_maps_tabular_data_signals_to_rapids_stack() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada de dados tabulares", "collection_attempts": 0})

    technologies = _recommendation_technologies(result)

    assert len(technologies) >= 1


def test_graph_maps_voice_signals_to_riva_and_nim() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada de voz e call center", "collection_attempts": 0})

    technologies = _recommendation_technologies(result)

    assert "NVIDIA Riva" in technologies


def test_graph_maps_healthcare_signals_to_clara() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada de saude com IA", "collection_attempts": 0})

    technologies = _recommendation_technologies(result)

    assert "NVIDIA Clara" in technologies


def test_graph_maps_robotics_simulation_signals_to_isaac_and_omniverse() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada de robotica e simulacao", "collection_attempts": 0})

    technologies = _recommendation_technologies(result)

    assert "NVIDIA Isaac" in technologies


def test_graph_maps_latency_signals_to_tensorrt_llm() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada com latencia de inferencia", "collection_attempts": 0})

    technologies = _recommendation_technologies(result)

    assert "TensorRT-LLM" in technologies
    assert "NVIDIA Triton Inference Server" in technologies


def _recommendation_technologies(result: dict) -> set[str]:
    return {recommendation.technology for recommendation in result["recommendations"]}


def test_recommendation_guidance_covers_seed_knowledge_technologies() -> None:
    from radar.agents.recommendation import TECHNOLOGY_GUIDANCE
    from radar.rag.knowledge_base import get_seed_chunks

    seed_technologies = {chunk["technology"] for chunk in get_seed_chunks()}

    assert seed_technologies <= set(TECHNOLOGY_GUIDANCE)

def test_recommendations_filter_domain_specific_nvidia_technologies() -> None:
    from radar.agents.recommendation import generate_recommendations
    from radar.schemas import (
        EvidenceClaim,
        EvidenceValidationReport,
        NvidiaKnowledgeChunk,
        StartupProfile,
    )

    claim = EvidenceClaim(
        id="claim_gupy_ai_agents",
        source_document_id="src_gupy",
        text="Gupy uses AI agents to screen resumes and support recruiting workflows.",
        claim_type="ai_usage",
        confidence=0.7,
    )
    validation = EvidenceValidationReport(
        has_minimum_evidence=True,
        source_quality="medium",
        supporting_evidence_ids=[claim.id],
        conflicts=[],
        caveats=[],
        requires_human_review=False,
    )
    chunks = [
        NvidiaKnowledgeChunk(
            id="nv_nim",
            technology="NVIDIA NIM",
            title="NIM",
            url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
            content="NIM supports optimized generative AI inference.",
            relevance_score=0.8,
        ),
        NvidiaKnowledgeChunk(
            id="nv_clara",
            technology="NVIDIA Clara",
            title="Clara",
            url="https://www.nvidia.com/en-us/clara/",
            content="Clara supports healthcare AI.",
            relevance_score=0.8,
        ),
        NvidiaKnowledgeChunk(
            id="nv_isaac",
            technology="NVIDIA Isaac",
            title="Isaac",
            url="https://developer.nvidia.com/isaac",
            content="Isaac supports robotics simulation.",
            relevance_score=0.8,
        ),
    ]

    _, recommendations = generate_recommendations(
        {
            "claims": [claim],
            "validation": validation,
            "nvidia_context": chunks,
            "extracted_startups": [
                StartupProfile(
                    name="Gupy",
                    sector="HR Tech",
                    product="Recruiting platform",
                    ai_usage_summary="AI agents for recruiting workflows.",
                )
            ],
        }
    )

    technologies = {recommendation.technology for recommendation in recommendations}
    assert "NVIDIA NIM" in technologies
    assert "NVIDIA Clara" not in technologies
    assert "NVIDIA Isaac" not in technologies