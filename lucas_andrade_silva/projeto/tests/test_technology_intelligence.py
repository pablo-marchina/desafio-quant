from scraper.api.services.technology_intelligence_service import (
    TechnologyIntelligenceService,
)
from scraper.market_intelligence.agent import (
    _validated_report,
    build_queries,
    source_matches_company,
)


def test_queries_cover_required_market_intelligence_sources():
    queries = build_queries("Acme AI", "acme.ai")
    text = " ".join(queries)
    assert "Gupy" in text
    assert "LinkedIn" in text
    assert "GitHub" in text
    assert "StackShare" in text
    assert "AWS GCP Azure" in text
    assert "OpenAI LLM" in text


def test_report_drops_claims_without_real_evidence_ids():
    evidence = [
        {
            "id": "S1",
            "url": "https://jobs.acme.ai/backend",
            "titulo": "Backend Engineer",
        }
    ]
    report = _validated_report(
        {
            "perfil_geral": {
                "resumo": "Acme vende software.",
                "evidencias": ["S1"],
            },
            "infraestrutura_backend": [
                {
                    "tecnologia": "Python",
                    "uso_provavel": "Backend",
                    "certeza": "Média",
                    "evidencias": ["S1"],
                },
                {
                    "tecnologia": "Kubernetes",
                    "uso_provavel": "Infra",
                    "certeza": "Alta",
                    "evidencias": ["S99"],
                },
            ],
            "frontend_mobile": [],
            "ia_operacional_interna": [],
            "ia_produto_core": [],
            "nivel_certeza": {
                "classificacao": "Média",
                "justificativa": "Uma vaga oficial.",
            },
        },
        evidence,
    )
    assert [item["tecnologia"] for item in report["infraestrutura_backend"]] == [
        "Python"
    ]
    assert report["fontes"] == evidence


def test_source_identity_accepts_company_domain_and_rejects_namesake():
    assert source_matches_company(
        {"url": "https://careers.acme.ai/job", "content": ""},
        "Acme AI",
        "acme.ai",
    )
    assert not source_matches_company(
        {
            "url": "https://example.com/job",
            "title": "Another company",
            "content": "Python and React",
        },
        "Acme AI",
        "acme.ai",
    )


def test_service_persists_structured_report():
    class FakeAgent:
        def analyze(self, startup, progress):
            progress(95)
            return {"schema_version": "technology-intelligence/v1"}

    class FakeStartupService:
        updated = None

        def update_startup(self, startup_id, data):
            self.updated = (startup_id, data)

    startup_service = FakeStartupService()
    service = TechnologyIntelligenceService(startup_service, FakeAgent())
    report = service.analyze(
        {"id": "startup-1", "company_name": "Acme"}, lambda _: None
    )
    assert report["schema_version"] == "technology-intelligence/v1"
    assert startup_service.updated == (
        "startup-1",
        {"technology_intelligence": report},
    )
