from radar.graph.builder import build_graph


def test_graph_generates_limited_briefing_when_evidence_is_weak() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup brasileira de IA", "collection_attempts": 0})

    assert result["briefing"].classification_label == "Inconclusivo"
    assert result.get("recommendations", []) == []
    assert result["review_required"] is True


def test_graph_preserves_source_urls() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup brasileira de IA", "collection_attempts": 0})

    assert result["sources"]
    assert str(result["sources"][0].url) == "https://www.nvidia.com/en-us/startups/"


def test_graph_recommends_only_after_minimum_evidence_is_validated() -> None:
    graph = build_graph()

    result = graph.invoke({"query": "startup validada com duas fontes de IA", "collection_attempts": 0})

    assert result["validation"].has_minimum_evidence is True
    assert result["classification"].label == "AI-Enabled"
    assert result["recommendations"]
    assert result["recommendations"][0].startup_evidence_ids == result["validation"].supporting_evidence_ids
    assert result["briefing"].recommendations == result["recommendations"]
