from __future__ import annotations

from scraper.enrichment_pipeline import config
from scraper.enrichment_pipeline.graph import build_enrichment_graph, enrichment_graph
from scraper.enrichment_pipeline import main as enrichment_main
from scraper.enrichment_pipeline.identity import normalize_company_name, validate_source_identity
from scraper.enrichment_pipeline.nodes.ai_classification import ai_classification_node
from scraper.enrichment_pipeline.nodes.build_summary import build_evidence_summary
from scraper.enrichment_pipeline.nodes.brasil_company import (
    has_technology_activity,
    relevance_score,
    select_most_relevant,
    structure_with_groq,
    validate_company_match,
)
from scraper.enrichment_pipeline.nodes.cnpj_biz import (
    catalog_payload,
    extract_company_details,
    extract_search_results,
    scrape_and_upsert,
)
from scraper.enrichment_pipeline.nodes.candidate_url_loop import candidate_url_loop_node
from scraper.enrichment_pipeline.nodes.cnpj_lookup import lookup_cnpj, normalize_cnpj_payload
from scraper.enrichment_pipeline.nodes.description_generation import description_generation_node
from scraper.enrichment_pipeline.nodes.github_lookup import cross_validate_github_candidate, github_lookup_node
from scraper.enrichment_pipeline.nodes.llm_classify import normalize_classification
from scraper.enrichment_pipeline.nodes.source_discovery import build_discovery_query
from scraper.enrichment_pipeline.nodes.tech_signal_detection import tech_signal_detection_node
from scraper.enrichment_pipeline.nodes.update_supabase import (
    _prefer_stronger,
    build_result_payload,
    load_candidates,
    save_github_validation_result,
    save_enrichment_result,
    should_save_enrichment_result,
)
from scraper.enrichment_pipeline.nodes.validation_gate import validation_gate_node
from scraper.enrichment_pipeline.nodes import web_scrape


def test_config_parse_seconds_aceita_sufixo_s():
    assert config._parse_seconds_tuple("1, 2, 4S", (1.0, 2.0, 4.0)) == (1.0, 2.0, 4.0)


def test_normaliza_resposta_publica_cnpj_ws_ativa_e_inativa():
    payload = {
        "razao_social": "NOVA AI LTDA",
        "capital_social": "10000.00",
        "estabelecimento": {
            "situacao_cadastral": "Ativa",
            "data_inicio_atividade": "2025-03-01",
            "atividade_principal": {"id": "6201501", "descricao": "Software"},
            "cidade": {"nome": "Sao Paulo"},
            "estado": {"sigla": "SP"},
        },
    }
    active = normalize_cnpj_payload(payload, "11.222.333/0001-81")
    assert active["cnpj"] == "11222333000181"
    assert active["ativa"] is True
    assert active["municipio"] == "Sao Paulo"
    assert active["uf"] == "SP"
    assert active["cnae"] == "6201501"

    inactive = normalize_cnpj_payload({**payload, "estabelecimento": {**payload["estabelecimento"], "situacao_cadastral": "Baixada"}})
    assert inactive["ativa"] is False
    assert inactive["situacao"] == "BAIXADA"


def test_cnpj_search_400_por_nome_retorna_vazio(monkeypatch):
    class FakeResponse:
        status_code = 400

        def raise_for_status(self):
            raise AssertionError("raise_for_status nao deveria ser chamado para 400 na busca por nome")

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None, headers=None):
            return FakeResponse()

    monkeypatch.setenv("BRASIL_IO_API_TOKEN", "token-de-teste")
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.brasil_company.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.cnpj_biz.scrape_and_upsert",
        lambda _: [],
    )
    assert lookup_cnpj({"company_name": "Blips"}) == {}


def test_cnpj_search_429_por_nome_retorna_vazio_sem_erro(monkeypatch):
    class FakeResponse:
        status_code = 429

        def raise_for_status(self):
            raise AssertionError("429 deve ser tratado como indisponibilidade temporaria")

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None, headers=None):
            return FakeResponse()

    monkeypatch.setenv("BRASIL_IO_API_TOKEN", "token-de-teste")
    monkeypatch.setattr(config, "MAX_RETRIES", 1)
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.brasil_company.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.cnpj_biz.scrape_and_upsert",
        lambda _: [],
    )
    assert lookup_cnpj({"company_name": "Zanzar"}) == {}


def test_cnpj_biz_e_usado_quando_brasil_io_nao_encontra(monkeypatch):
    class FakeResponse:
        status_code = 400

        def raise_for_status(self):
            raise AssertionError("400 da busca deve retornar vazio")

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None, headers=None):
            return FakeResponse()

    monkeypatch.setenv("BRASIL_IO_API_TOKEN", "token-de-teste")
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.brasil_company.httpx.Client",
        FakeClient,
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.cnpj_biz.scrape_and_upsert",
        lambda _: [
            {
                "cnpj": "12381921000120",
                "razao_social": "Axenya Corretora de Seguros LTDA",
                "nome_fantasia": "Axenya",
                "situacao_cadastral": "Ativa",
                "municipio": "São Paulo",
                "estado": "SP",
                "cnae_principal": "66.22-3-00 - Corretores de seguros",
                "cnae_secundarias": None,
                "socios": None,
                "source_url": "https://cnpj.biz/12381921000120",
            }
        ],
    )

    result = lookup_cnpj({"company_name": "Axenya"})

    assert result["cnpj"] == "12381921000120"
    assert result["nome_fantasia"] == "Axenya"
    assert result["ativa"] is True
    assert result["fontes"] == ["cnpj.biz"]


def test_cnpj_biz_extrai_busca_detalhes_e_payload():
    search_html = """
    <ul role="list">
      <li><a href="/12381921000120">Axenya</a></li>
      <li><a href="https://cnpj.biz/12381921000120">Duplicada</a></li>
      <li><a href="/00000000000191">Outra empresa</a></li>
    </ul>
    """
    assert extract_search_results(search_html) == [
        ("https://cnpj.biz/12381921000120", "12381921000120"),
        ("https://cnpj.biz/00000000000191", "00000000000191"),
    ]

    detail_html = """
    <main>
      <p><strong>CNPJ:</strong> 12.381.921/0001-20</p>
      <p><strong>Inscrição Estadual SP:</strong> 123.456.789.000</p>
      <p><strong>Razão Social:</strong> Axenya Corretora de Seguros LTDA</p>
      <p><strong>Nome Fantasia:</strong> Axenya</p>
      <p><strong>Data da Abertura:</strong> 22/07/2010</p>
      <p><strong>Porte:</strong> Sem Enquadramento</p>
      <p><strong>Natureza Jurídica:</strong> Sociedade Empresária Limitada</p>
      <p><strong>Capital Social:</strong> R$ 20.628.647,00</p>
      <p><strong>Situação:</strong> Ativa</p>
      <h2>Localização</h2>
      <p><strong>Logradouro:</strong> Rua Brejo Alegre, 93</p>
      <p><strong>Bairro:</strong> Brooklin Paulista</p>
      <p><strong>CEP:</strong> 04557-050</p>
      <p><strong>Município:</strong> São Paulo</p>
      <p><strong>Estado:</strong> São Paulo</p>
      <h2>Atividades - CNAES</h2>
      <p>Principal: 66.22-3-00 - Corretores e agentes de seguros</p>
      <h3>CNAEs Secundárias</h3>
      <p>66.29-1-00 - Atividades auxiliares dos seguros</p>
      <h2>Quadro de Sócios e Administradores</h2>
      <p>Nome: Maria Silva</p>
      <p>Qualificação: Sócio-Administrador</p>
      <h2>Contato</h2>
    </main>
    """
    company = extract_company_details(
        detail_html,
        cnpj="12381921000120",
        source_url="https://cnpj.biz/12381921000120",
    )
    assert company["cnpj"] == "12381921000120"
    assert company["founding_year"] == "2010"
    assert company["estado"] == "SP"
    assert company["capital_social"] == "20628647.00"
    assert company["cnae_principal"] == (
        "66.22-3-00 - Corretores e agentes de seguros"
    )
    assert company["cnae_secundarias"] == [
        {
            "codigo": "66.29-1-00",
            "descricao": "Atividades auxiliares dos seguros",
        }
    ]
    assert company["socios"] == [
        {"nome": "Maria Silva", "cargo": "Sócio-Administrador"}
    ]

    payload = catalog_payload(company)
    assert payload["candidate_id"] == "12381921000120"
    assert payload["company_name"] == "Axenya"
    assert payload["location"] == "São Paulo, SP"
    assert payload["validation_status"] == "Ativa"
    assert payload["enrichment_status"] == "scraped"
    assert payload["is_active"] is True
    assert payload["description"] == (
        "Capital Social: R$ 20628647.00 | Sócios: Maria Silva"
    )


def test_cnpj_biz_aguarda_e_faz_upsert(monkeypatch):
    search_html = """
    <ul role="list">
      <li><a href="/12381921000120">Axenya</a></li>
    </ul>
    """
    detail_html = """
    <p>Razão Social: Axenya Corretora de Seguros LTDA</p>
    <p>Nome Fantasia: Axenya</p>
    <p>Situação: Ativa</p>
    """

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return FakeResponse(
                search_html if "/procura/" in url else detail_html
            )

    class Query:
        def __init__(self, client, operation, payload=None):
            self.client = client
            self.operation = operation
            self.payload = payload

        def select(self, *_):
            self.operation = "select"
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def upsert(self, payload, **_):
            self.operation = "upsert"
            self.payload = payload
            return self

        def execute(self):
            if self.operation == "upsert":
                self.client.upserts.append(self.payload)
            return type("Result", (), {"data": []})()

    class FakeSupabase:
        def __init__(self):
            self.upserts = []

        def table(self, _):
            return Query(self, "")

    session = FakeSession()
    client = FakeSupabase()
    sleeps = []
    companies = scrape_and_upsert(
        "Axenya",
        session=session,
        supabase_client=client,
        sleep_fn=sleeps.append,
    )

    assert len(companies) == 1
    assert sleeps == [1]
    assert len(session.calls) == 2
    assert client.upserts[0]["candidate_id"] == "12381921000120"


def test_ranking_brasil_io_prefere_nome_exato_ativo_e_matriz():
    rows = [
        {
            "cnpj": "11111111000111",
            "nome_fantasia": "Nubank Serviços",
            "situacao": "BAIXADA",
            "tipo": "FILIAL",
        },
        {
            "cnpj": "18236120000158",
            "nome_fantasia": "Nubank",
            "situacao": "ATIVA",
            "tipo": "MATRIZ",
        },
    ]

    selected = select_most_relevant(rows, "Nubank")

    assert selected["cnpj"] == "18236120000158"
    assert relevance_score(rows[1], "Nubank") > relevance_score(
        rows[0], "Nubank"
    )


def test_validador_cnpj_rejeita_nome_parecido_mas_errado():
    row = {
        "cnpj": "00000000000191",
        "nome_fantasia": "MAISMAR",
        "razao_social": "MAISMAR TECNOLOGIA LTDA",
        "situacao": "ATIVA",
        "tipo": "MATRIZ",
        "cnae": "6201501",
        "cnae_descricao": "Desenvolvimento de programas de computador",
    }

    validation = validate_company_match(row, "MAISMEI")

    assert validation["accepted"] is False
    assert validation["reason"] == "nome_incompativel"
    assert select_most_relevant([row], "MAISMEI") is None


def test_validador_cnpj_aceita_nome_compativel_e_sinal_tecnologico():
    row = {
        "cnpj": "11222333000181",
        "nome_fantasia": "MAISMEI",
        "razao_social": "MAISMEI TECNOLOGIA LTDA",
        "situacao": "ATIVA",
        "tipo": "MATRIZ",
        "cnae": "6201501",
        "cnae_descricao": "Desenvolvimento de programas de computador",
    }

    validation = validate_company_match(row, "MAISMEI")

    assert validation["accepted"] is True
    assert validation["technology_activity"] is True
    assert has_technology_activity(row) is True


def test_validador_cnpj_nome_forte_pode_passar_sem_cnae_tecnologico():
    row = {
        "cnpj": "12381921000120",
        "nome_fantasia": "Axenya",
        "razao_social": "Axenya Corretora de Seguros LTDA",
        "situacao": "ATIVA",
        "tipo": "MATRIZ",
        "cnae": "6622300",
        "cnae_descricao": "Corretores e agentes de seguros",
    }

    validation = validate_company_match(row, "Axenya")

    assert validation["accepted"] is True
    assert validation["technology_activity"] is False
    assert validation["reason"] == "nome_compativel_sem_sinal_tecnologico_cadastral"


def test_groq_nao_pode_alterar_fatos_oficiais():
    class FakeCompletions:
        def create(self, **kwargs):
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {
                                        "content": (
                                            '{"cnpj":"inventado",'
                                            '"setor_inferido":"Fintech",'
                                            '"usa_ia_potencialmente":true,'
                                            '"classificacao_ia":"AI_ENABLED",'
                                            '"justificativa_ia":"CNAE financeiro"}'
                                        )
                                    },
                                )()
                            },
                        )()
                    ]
                },
            )()

    groq = type(
        "Groq",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {"completions": FakeCompletions()},
            )()
        },
    )()
    official = {
        "cnpj": "18236120000158",
        "raw_data": {},
        "setor_inferido": None,
        "usa_ia_potencialmente": None,
        "classificacao_ia": "UNKNOWN",
        "justificativa_ia": None,
    }

    result = structure_with_groq(
        official, "Nubank", groq_client=groq
    )

    assert result["cnpj"] == "18236120000158"
    assert result["setor_inferido"] == "Fintech"
    assert result["classificacao_ia"] == "AI_ENABLED"


def test_web_scrape_fallback_para_bs4_quando_trafilatura_vazio(monkeypatch):
    monkeypatch.setattr(web_scrape, "_request_html", lambda url: "<html><body><main>Texto util sobre startup brasileira de IA com produto SaaS. " * 4)
    monkeypatch.setattr(web_scrape, "extract_with_trafilatura", lambda html, url: "")
    text = web_scrape.extract_text_from_url("https://example.com")
    assert "startup brasileira" in text


def test_source_discovery_query_mantem_contexto_brasil():
    assert build_discovery_query({"company_name": "Acme AI", "segment": "Fintech"}) == "Acme AI Fintech Brasil startup tecnologia"


def test_identity_validation_rejeita_homonima_estrangeira():
    candidate = {"company_name": "Finix", "description": "Startup brasileira de pagamentos com IA.", "segment": "Fintech"}
    source = {
        "url": "https://finix.ro",
        "source_type": "website",
        "origin": "ddg",
        "title": "Finix Romania",
        "snippet": "Romanian fintech platform",
        "raw_text": "Finix is a Romanian fintech company based in Bucharest.",
        "metadata": {},
    }
    result = validate_source_identity(candidate, source)
    assert result["classification"] == "WRONG_COMPANY"
    assert result["confidence"] < 80
    assert any(signal.startswith("foreign_tld:ro") for signal in result["negative_signals"])


def test_identity_validation_nao_aprova_homonima_us_sem_contexto_brasileiro():
    candidate = {
        "company_name": "Hakutaku",
        "description": "Startup brasileira de tecnologia.",
    }
    source = {
        "url": "https://hakutaku.us",
        "source_type": "website",
        "origin": "ddg",
        "title": "Hakutaku",
        "snippet": "Hakutaku software and digital services.",
        "raw_text": (
            "Hakutaku provides software and digital services for global customers."
        ),
        "metadata": {},
    }

    result = validate_source_identity(candidate, source)

    assert result["classification"] == "WRONG_COMPANY"
    assert result["should_update_database"] is False
    assert "foreign_tld:us" in result["negative_signals"]
    assert "brazil_context" not in result["matched_signals"]


def test_identity_validation_nome_igual_sem_pais_fica_apenas_possivel():
    result = validate_source_identity(
        {"company_name": "Acme"},
        {
            "url": "https://acme.com",
            "source_type": "website",
            "title": "Acme",
            "snippet": "Acme software platform",
            "raw_text": "Acme builds software products for companies.",
            "metadata": {},
        },
    )

    assert result["classification"] == "POSSIBLE_MATCH"
    assert result["should_update_database"] is False


def test_identity_validation_aceita_dominio_brasileiro_compativel():
    candidate = {"company_name": "Acme", "description": "Startup brasileira de analytics para RH.", "segment": "HRTech"}
    source = {
        "url": "https://acme.com.br",
        "source_type": "website",
        "origin": "candidate_field",
        "title": "Acme Brasil",
        "snippet": "Acme HR analytics platform",
        "raw_text": "A Acme e uma startup brasileira com plataforma de analytics para RH em Sao Paulo.",
        "metadata": {},
    }
    result = validate_source_identity(candidate, source)
    assert result["classification"] == "MATCH"
    assert result["confidence"] >= 80


def test_build_summary_usa_apenas_fontes_validadas():
    summary = build_evidence_summary({
        "candidate": {"company_name": "Acme", "source_url": "https://source.invalid"},
        "normalized_company_name": normalize_company_name("Acme"),
        "cnpj_data": {},
        "web_context": {"https://acme.com.br": "Startup brasileira de IA para varejo. " * 4},
        "validated_urls": ["https://acme.com.br"],
    })
    assert "Fontes validadas:" in summary
    assert "https://acme.com.br" in summary
    assert "descricao_original" not in summary


def test_tech_signal_detection_consolida_stack_e_ia():
    result = tech_signal_detection_node({
        "web_context": {"https://acme.com.br": "Python FastAPI React AWS OpenAI LangChain."},
        "github_profile": {"tech_stack": ["TypeScript"], "ai_integrations": ["PyTorch"], "repos": []},
        "gupy_profile": {"open_jobs_signals": ["Vaga pede Docker e Kubernetes."], "tech_stack": ["Docker"], "ai_integrations": []},
    })
    assert "Python" in result["tech_signals"]["tech_stack"]
    assert "FastAPI" in result["tech_signals"]["tech_stack"]
    assert "React" in result["tech_signals"]["tech_stack"]
    assert "AWS" in result["tech_signals"]["tech_stack"]
    assert "Docker" in result["tech_signals"]["tech_stack"]
    assert "OpenAI" in result["tech_signals"]["ai_integrations"]
    assert "LangChain" in result["tech_signals"]["ai_integrations"]
    assert "PyTorch" in result["tech_signals"]["ai_integrations"]


def test_cross_validation_github_exige_dois_criterios_objetivos():
    state = {
        "candidate": {"company_name": "Tractian", "segment": "manutencao preditiva industrial"},
        "validated_url": "https://tractian.com",
        "validated_source": {"raw_text": "manutencao preditiva industrial com sensores"},
    }
    source = {
        "url": "https://github.com/tractian",
        "metadata": {
            "organizacao_ou_owner": "tractian",
            "blog": "https://tractian.com",
            "descricao_repo": "predictive maintenance industrial sensors",
            "readme_trecho": "",
            "linguagens": ["Python"],
            "topicos": ["iot"],
        },
    }
    result = cross_validate_github_candidate(state, source)
    assert result["validado"] is True
    assert "dominio_presente" in result["criterios_atendidos"]
    assert "owner_corresponde_marca" in result["criterios_atendidos"]


def test_cross_validation_github_rejeita_nome_parecido_sem_conteudo():
    result = cross_validate_github_candidate(
        {
            "candidate": {"company_name": "Acme AI", "segment": "analytics para RH"},
            "validated_url": "https://acme.com.br",
            "validated_source": {"raw_text": "analytics para recursos humanos"},
        },
        {
            "url": "https://github.com/acme-labs",
            "metadata": {
                "organizacao_ou_owner": "acme-labs",
                "descricao_repo": "generic utilities",
                "readme_trecho": "open source helpers",
                "linguagens": ["Go"],
                "topicos": [],
            },
        },
    )
    assert result["validado"] is False


def test_github_lookup_limita_tentativas_e_nao_extrai_stack_sem_validacao(monkeypatch):
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup.config.MAX_GITHUB_VALIDATION_ATTEMPTS", 3)
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.github_lookup._search_org_candidates",
        lambda candidate: [
            {"url": f"https://github.com/wrong-{index}", "metadata": {"api_url": f"https://api.github.com/orgs/wrong-{index}"}}
            for index in range(4)
        ],
    )
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup._search_repo_candidates", lambda domain, tested_urls: [])
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.github_lookup._load_org_profile",
        lambda api_url: {"profile": {"login": api_url.rsplit("/", 1)[-1]}, "repos": [{"html_url": api_url, "description": "generic", "topics": [], "language": "Python", "owner": {"login": "wrong"}, "name": "repo"}]},
    )
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup._load_repo_readme", lambda owner, repo: "")
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup.extract_validated_github_stack", lambda repos: (_ for _ in ()).throw(AssertionError("nao deveria extrair stack")))
    result = github_lookup_node({
        "candidate": {"company_name": "Acme AI", "segment": "analytics para RH"},
        "validated_url": "https://acme.com.br",
        "validated_source": {"raw_text": "analytics para RH"},
        "errors": {},
        "validated_sources": [],
        "identity_evidence": {},
    })
    assert result["github_validacao_status"] == "esgotado"
    assert result["github_tentativas"] == 3
    assert result["github_repo_validado"] is None
    assert "github_repo_validado" in result["dados_insuficientes"]


def test_github_lookup_extrai_stack_so_apos_validacao(monkeypatch):
    repo = {"html_url": "https://github.com/tractian/api", "description": "industrial sensors", "topics": ["fastapi"], "language": "Python", "owner": {"login": "tractian"}, "name": "api"}
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup._search_org_candidates", lambda candidate: [{"url": "https://github.com/tractian", "metadata": {"api_url": "https://api.github.com/orgs/tractian"}}])
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup._search_repo_candidates", lambda domain, tested_urls: [])
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup._load_org_profile", lambda api_url: {"profile": {"login": "tractian", "blog": "https://tractian.com"}, "repos": [repo]})
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup._load_repo_readme", lambda owner, repo: "predictive maintenance industrial sensors tractian.com")
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.github_lookup.extract_validated_github_stack", lambda repos: (["Python", "fastapi"], [{"tecnologia": "fastapi", "fonte": "package.json", "repo_url": "https://github.com/tractian/api"}]))
    result = github_lookup_node({
        "candidate": {"company_name": "Tractian", "segment": "manutencao preditiva industrial"},
        "validated_url": "https://tractian.com",
        "validated_source": {"raw_text": "manutencao preditiva industrial sensores"},
        "errors": {},
        "validated_sources": [],
        "identity_evidence": {},
    })
    assert result["github_validacao_status"] == "confirmado"
    assert result["github_repo_validado"] == "https://github.com/tractian"
    assert result["github_profile"]["tech_stack"] == ["Python", "fastapi"]
    assert result["github_stack_evidence"][0]["fonte"] == "package.json"


def test_ai_classification_usa_taxonomia_rica_e_mapa_legado():
    result = ai_classification_node({
        "validated_sources": [{"url": "https://acme.com.br"}],
        "web_context": {"https://acme.com.br": "Plataforma de inteligencia artificial com LLM e agentes."},
        "ai_signals": ["OpenAI", "LLM"],
        "candidate": {"company_name": "Acme"},
        "identity_confidence_score": 90,
    })
    assert result["classification"]["ai_dependency_level"] == "AI_NATIVE"
    assert result["classification"]["ai_classification"] == "AI_NATIVE"
    assert result["classification"]["validation_status"] == "APPROVED"


def test_normalize_classification_nao_mantem_non_ai_com_evidencia_de_ia():
    result = normalize_classification(
        {"evidence_summary": "A empresa usa inteligencia artificial para automacao."},
        {
            "is_brazilian": True,
            "is_startup": True,
            "uses_ai_potentially": True,
            "ai_classification": "NON_AI",
            "validation_status": "REVIEW",
            "description": "Plataforma com IA para automacao.",
        },
    )

    assert result["ai_classification"] == "AI_ENABLED"
    assert result["uses_ai_potentially"] is True


def test_description_generation_so_gera_com_match():
    empty = description_generation_node({"validated_sources": [], "web_context": {}})
    assert empty["company_description"] == ""
    assert empty["enrichment_status"] == "insufficient_evidence"

    generated = description_generation_node({
        "candidate": {"company_name": "Acme", "location": "Sao Paulo"},
        "validated_sources": [{"url": "https://acme.com.br", "validation": {"classification": "MATCH"}}],
        "web_context": {"https://acme.com.br": "A Acme oferece plataforma de automacao para RH com IA."},
        "tech_signals": {"tech_stack": ["Python", "React"], "ai_integrations": ["OpenAI"]},
        "classification": {"ai_dependency_level": "AI_ENABLED"},
    })
    assert "Acme atua no Brasil." in generated["company_description"]
    assert "Python" in generated["company_description"]


def test_candidate_url_loop_para_no_primeiro_match(monkeypatch):
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.candidate_url_loop.extract_text_from_url",
        lambda url: {
            "https://wrong.example": "Empresa estrangeira errada.",
            "https://possible.example": "Contexto parcial da empresa.",
            "https://acme.com.br": "Acme Brasil startup brasileira de RH com plataforma de IA.",
        }[url],
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.candidate_url_loop.validate_source_identity",
        lambda candidate, source: {
            "https://wrong.example": {"classification": "WRONG_COMPANY", "confidence": 10, "reason": "wrong", "matched_signals": [], "negative_signals": [], "should_update_database": False},
            "https://possible.example": {"classification": "POSSIBLE_MATCH", "confidence": 40, "reason": "possible", "matched_signals": [], "negative_signals": [], "should_update_database": False},
            "https://acme.com.br": {"classification": "MATCH", "confidence": 91, "reason": "match", "matched_signals": ["brand_in_title"], "negative_signals": [], "should_update_database": True},
        }[str(source.get("url"))],
    )
    result = candidate_url_loop_node({
        "candidate": {"company_name": "Acme"},
        "source_candidates": [
            {"url": "https://wrong.example", "source_type": "website", "title": "Wrong"},
            {"url": "https://possible.example", "source_type": "website", "title": "Possible"},
            {"url": "https://acme.com.br", "source_type": "website", "title": "Acme"},
            {"url": "https://unused.example", "source_type": "website", "title": "Unused"},
        ],
        "errors": {},
    })
    assert result["validated_url"] == "https://acme.com.br"
    assert len(result["candidate_attempts"]) == 3
    assert result["candidate_attempts"][0]["decision"] == "rejected"
    assert result["candidate_attempts"][1]["decision"] == "continue"
    assert result["candidate_attempts"][2]["decision"] == "accepted"


def test_candidate_url_loop_nao_aprova_possible_match_acima_de_50(monkeypatch):
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.candidate_url_loop.extract_text_from_url",
        lambda url: "Contexto parcial mas suficiente.",
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.candidate_url_loop.validate_source_identity",
        lambda candidate, source: {
            "classification": "POSSIBLE_MATCH",
            "confidence": 61,
            "reason": "possible but acceptable",
            "matched_signals": [],
            "negative_signals": [],
            "should_update_database": False,
        },
    )
    result = candidate_url_loop_node({
        "candidate": {"company_name": "Acme"},
        "source_candidates": [
            {"url": "https://possible.example", "source_type": "website", "title": "Possible"},
            {"url": "https://unused.example", "source_type": "website", "title": "Unused"},
        ],
        "errors": {},
    })
    assert result["validated_url"] is None
    assert result["website_candidate"] == "https://possible.example"
    assert len(result["candidate_attempts"]) == 2
    assert result["candidate_attempts"][0]["decision"] == "continue"


def test_validation_gate_descarta_sem_fonte_confiavel():
    result = validation_gate_node({
        "candidate_attempts": [
            {"url_index": 1, "url": "https://acme.jobs.gupy.io", "classification": "POSSIBLE_MATCH", "confidence": 45, "reason": "possible", "decision": "continue"},
        ],
        "validated_sources": [],
        "rejected_urls": ["https://acme.ro | wrong company"],
        "identity_validation": {"classification": "INSUFFICIENT_EVIDENCE", "confidence": 65, "reason": "no reliable company-specific source found"},
        "identity_evidence": {"sources": []},
        "identity_confidence_score": 65,
        "discard_reason": "no_valid_source_found_after_10_urls",
        "is_active": False,
    })
    assert result["website_candidate"] == "https://acme.jobs.gupy.io"
    assert result["classification"]["validation_status"] == "DISCARDED"
    assert result["validated_url"] is None


def test_validation_gate_aprova_match_com_descricao_reliavel():
    result = validation_gate_node({
        "validated_sources": [
            {"url": "https://acme.com.br", "source_type": "website", "validation": {"classification": "MATCH", "confidence": 88}},
        ],
        "validated_url": "https://acme.com.br",
        "candidate_attempts": [{"url_index": 1, "url": "https://acme.com.br", "classification": "MATCH", "confidence": 88, "reason": "ok", "decision": "accepted"}],
        "company_description": "Descricao validada com fonte confiavel.",
        "identity_validation": {"classification": "MATCH", "confidence": 88, "reason": "ok"},
        "identity_confidence_score": 88,
    })
    assert result["classification"]["validation_status"] == "APPROVED"
    assert result["final_status"] == "APPROVED"
    assert result["validated_url"] == "https://acme.com.br"


def test_result_payload_separa_website_confirmado_e_candidato():
    payload = build_result_payload({
        "candidate": {"id": "abc", "company_name": "Acme", "source_url": "https://base.example/acme"},
        "cnpj_data": {"cnpj": "11222333000181"},
        "classification": {
            "validation_status": "APPROVED",
            "ai_classification": "AI_NATIVE",
            "ai_dependency_level": "AI_NATIVE",
            "ai_technology_focus": "Automation",
            "target_market": "Empresas",
            "key_milestones": None,
        },
        "company_description": "Descricao validada.",
        "website_candidate": "https://jobs.gupy.io/acme",
        "validated_url": "https://acme.com.br",
        "validated_sources": [
            {"url": "https://acme.com.br", "source_type": "website", "validation": {"classification": "MATCH", "confidence": 91}},
        ],
        "source_candidates": [
            {"url": "https://jobs.gupy.io/acme", "source_type": "gupy", "validation": {"classification": "POSSIBLE_MATCH", "confidence": 60}},
        ],
        "identity_evidence": {"sources": []},
        "tech_signals": {"tech_stack": ["Python"], "ai_integrations": ["OpenAI"]},
        "open_jobs_signals": ["Python", "Docker"],
        "identity_confidence_score": 91,
        "tech_confidence_score": 70,
        "enrichment_status": "enriched",
        "candidate_attempts": [{"url_index": 1, "url": "https://acme.com.br", "classification": "MATCH", "confidence": 91, "reason": "match", "decision": "accepted"}],
        "validated_urls": ["https://acme.com.br"],
        "candidate_urls": ["https://jobs.gupy.io/acme"],
        "rejected_urls": ["https://acme.ro | foreign"],
    })
    assert payload["website"] == "https://acme.com.br"
    assert payload["description"] == "Descricao validada."
    assert "website_candidate" not in payload
    assert "company_description" not in payload
    assert "github_org" not in payload
    assert "tech_stack" not in payload
    assert "ai_integrations" not in payload
    assert payload["cnpj"] == "11222333000181"
    assert payload["cnpj_data"] == {"cnpj": "11222333000181"}


def test_prefer_stronger_preserva_dado_confirmado():
    existing = {"website": "https://acme.com.br", "company_description": "forte", "website_confidence": 95, "identity_confidence_score": 95}
    incoming = {"website": "https://acme.example", "company_description": "fraca", "website_confidence": 62, "identity_confidence_score": 62}
    merged = _prefer_stronger(existing, incoming)
    assert merged["website"] == "https://acme.com.br"
    assert merged["company_description"] == "forte"


def test_build_result_payload_persiste_url_aprovada_com_possible_match():
    payload = build_result_payload({
        "candidate": {"id": "pm-1", "company_name": "Possible"},
        "classification": {"validation_status": "APPROVED"},
        "validated_url": "https://possible.com.br",
        "validated_sources": [
            {"url": "https://possible.com.br", "source_type": "website", "validation": {"classification": "POSSIBLE_MATCH", "confidence": 61}},
        ],
        "identity_confidence_score": 61,
        "enrichment_status": "needs_review",
    })
    assert payload["website"] == "https://possible.com.br"
    assert "validated_url" not in payload
    assert "website_confidence" not in payload
    assert "validated_urls" not in payload


def test_prefer_stronger_aceita_overwrite_quando_acima_do_threshold_de_aprovacao():
    existing = {"website": "https://acme-antiga.com.br", "website_confidence": 45, "identity_confidence_score": 45}
    incoming = {"website": "https://acme-nova.com.br", "website_confidence": 62, "identity_confidence_score": 62}
    merged = _prefer_stronger(existing, incoming)
    assert merged["website"] == "https://acme-nova.com.br"
    assert merged["website_confidence"] == 62


def test_load_candidates_usa_rest_do_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"id": "1", "company_name": "Acme"}]

    def fake_request(method, *, params=None, json=None, extra_headers=None, table=None):
        captured["method"] = method
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._request", fake_request)
    rows = load_candidates(limit=10, status="REVIEW")
    assert rows == [{"id": "1", "company_name": "Acme"}]
    assert captured["params"]["validation_status"] == "eq.REVIEW"


def test_load_candidates_fallback_para_postgres(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    captured = {}

    class FakeCursor:
        def __init__(self):
            self.rows = [{"id": "2", "company_name": "Beta"}]

        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return self.rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self, cursor_factory=None):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._pg_connect", lambda: FakeConnection())
    rows = load_candidates(limit=5, status=None)
    assert rows == [{"id": "2", "company_name": "Beta"}]
    assert "validation_status IN ('APPROVED', 'REVIEW')" in captured["sql"]


def test_save_enrichment_result_fallback_faz_upsert_na_tabela_separada(monkeypatch):
    captured = {}
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase.config.ENRICHMENT_RESULTS_TABLE", "startup_ai_radar_catalog")

    class FakeCursor:
        def __init__(self):
            self.mode = "columns"
            self.description = [("candidate_id",), ("website",), ("identity_confidence_score",)]

        def execute(self, sql, params=None):
            captured.setdefault("sql", []).append(sql)
            captured.setdefault("params", []).append(params)
            if "information_schema.columns" in sql:
                self.mode = "columns"
            elif sql.strip().startswith("SELECT * FROM startup_ai_radar_catalog"):
                self.mode = "select"
            elif sql.strip().startswith("INSERT INTO"):
                self.mode = "insert"

        def fetchall(self):
            if self.mode == "columns":
                return [
                    ("candidate_id",), ("company_name",), ("website",), ("description",), ("company_description",),
                    ("website_candidate",), ("website_confidence",), ("github_org",), ("linkedin_url",),
                    ("crunchbase_url",), ("gupy_url",), ("tech_stack",), ("ai_integrations",),
                    ("ai_dependency_level",), ("open_jobs_signals",), ("rejected_urls",), ("validated_urls",),
                    ("candidate_urls",), ("identity_evidence",), ("tech_confidence_score",),
                    ("identity_confidence_score",), ("enrichment_status",), ("cnpj",), ("founding_year",),
                    ("location",), ("ai_technology_focus",), ("target_market",), ("key_milestones",),
                    ("source_url",), ("validation_status",), ("last_enriched_at",), ("updated_at",),
                ]
            return []

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self, cursor_factory=None):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._pg_connect", lambda: FakeConnection())
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase.ensure_results_schema", lambda: None)
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._fetch_existing_result", lambda candidate_id: None)
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._fetch_existing_result_by_company_name", lambda company_name: None)
    save_enrichment_result({
        "candidate": {"id": "abc", "company_name": "Acme"},
        "cnpj_data": {},
        "classification": {"validation_status": "REVIEW", "ai_dependency_level": "INSUFFICIENT_EVIDENCE", "ai_classification": "UNKNOWN"},
        "identity_evidence": {"sources": [{"url": "https://acme.example"}]},
        "source_candidates": [{"url": "https://acme.example"}],
    })
    assert any("INSERT INTO startup_ai_radar_catalog" in sql for sql in captured["sql"])


def test_save_enrichment_result_atualiza_linha_legada_por_company_name(monkeypatch):
    captured = {}
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase.config.ENRICHMENT_RESULTS_TABLE", "startup_ai_radar_catalog")

    class FakeCursor:
        def __init__(self):
            self.mode = "columns"
            self.description = [("candidate_id",), ("website",), ("identity_confidence_score",), ("id",)]

        def execute(self, sql, params=None):
            captured.setdefault("sql", []).append(sql)
            captured.setdefault("params", []).append(params)
            if "information_schema.columns" in sql:
                self.mode = "columns"

        def fetchall(self):
            if self.mode == "columns":
                return [
                    ("id",), ("candidate_id",), ("company_name",), ("validated_url",), ("website",),
                    ("website_confidence",), ("identity_confidence_score",), ("validation_status",),
                    ("enrichment_status",), ("updated_at",), ("last_enriched_at",),
                ]
            return []

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self, cursor_factory=None):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._pg_connect", lambda: FakeConnection())
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase.ensure_results_schema", lambda: None)
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._fetch_existing_result", lambda candidate_id: None)
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.nodes.update_supabase._fetch_existing_result_by_company_name",
        lambda company_name: {"id": "legacy-row-id", "candidate_id": "old-legacy-id", "company_name": company_name, "website_confidence": 10, "identity_confidence_score": 10},
    )
    save_enrichment_result({
        "candidate": {"id": "abc", "company_name": "Acme"},
        "classification": {"validation_status": "APPROVED"},
        "validated_url": "https://acme.com.br",
        "validated_sources": [{"url": "https://acme.com.br", "source_type": "website", "validation": {"classification": "MATCH", "confidence": 88}}],
        "identity_confidence_score": 88,
        "enrichment_status": "needs_review",
    })
    assert any(sql.startswith("UPDATE startup_ai_radar_catalog SET") for sql in captured["sql"])


def test_save_github_validation_result_persiste_apenas_confirmado(monkeypatch):
    captured = {}
    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase.ensure_results_schema", lambda: None)

    class FakeCursor:
        def __init__(self):
            self.mode = "columns"

        def execute(self, sql, params=None):
            captured.setdefault("sql", []).append(sql)
            captured.setdefault("params", []).append(params)
            if "information_schema.columns" in sql:
                self.mode = "columns"

        def fetchall(self):
            return [("empresa_id",), ("github_repo_url",), ("criterios_atendidos",), ("evidencia",), ("data_validacao",)]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self, cursor_factory=None):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scraper.enrichment_pipeline.nodes.update_supabase._pg_connect", lambda: FakeConnection())
    skipped = save_github_validation_result({
        "candidate": {"id": "abc", "company_name": "Acme"},
        "github_validacao_status": "rejeitado",
        "github_repo_validado": None,
    })
    saved = save_github_validation_result({
        "candidate": {"id": "abc", "company_name": "Acme"},
        "github_validacao_status": "confirmado",
        "github_repo_validado": "https://github.com/acme",
        "github_validacao_criterios": ["dominio_presente", "owner_corresponde_marca"],
        "github_validacao_evidencia": "dominio acme.com.br encontrado",
    })
    assert skipped is False
    assert saved is True
    assert any("INSERT INTO github_repository_validations" in sql for sql in captured["sql"])


def test_should_save_enrichment_result_permte_review_com_evidencia_de_identidade():
    assert should_save_enrichment_result({
        "candidate": {"id": "1"},
        "validated_sources": [],
        "identity_evidence": {"sources": [{"url": "https://acme.example"}]},
    }) == (True, None)
    assert should_save_enrichment_result({"candidate": {}}) == (False, "candidato sem id")
    assert should_save_enrichment_result({
        "candidate": {"id": "startup-123", "company_name": "Nubank"},
        "cnpj_data": {"cnpj": "18236120000158"},
    }) == (True, None)


def test_run_mescla_stream_aninhado_do_langgraph(monkeypatch, capsys, tmp_path):
    class FakeGraph:
        def stream(self, state):
            yield {"identity_validation": {"identity_validation": {"classification": "MATCH"}}}
            yield {"ai_classification": {"classification": {"validation_status": "APPROVED"}}}
            yield {"log_result": {"log_summary": {"total": 1, "APPROVED": 1, "MATCH": 1, "updated": False}}}

    monkeypatch.setattr(enrichment_main.config, "CHECKPOINT_PATH", tmp_path / "checkpoint.json")
    monkeypatch.setattr(enrichment_main, "load_candidates", lambda **kwargs: [{"id": "1", "company_name": "Acme"}])
    monkeypatch.setattr(enrichment_main, "enrichment_graph", FakeGraph())
    result = enrichment_main.run(dry_run=True, reset_checkpoint=True)
    captured = capsys.readouterr()
    assert result["total"] == 1
    assert result["APPROVED"] == 1
    assert "concluido: Acme (APPROVED)" in captured.err
    assert "company_name" in captured.out
    assert "validated_url" in captured.out


def test_run_pula_candidatos_processados_por_checkpoint(monkeypatch, tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text('{"processed":{"1":{"company_name":"Acme"}},"failed":{},"last_saved_at":null}', encoding="utf-8")

    class FakeGraph:
        def stream(self, state):
            yield {"log_result": {"log_summary": {"total": 1, "REVIEW": 1, "updated": False}}}

    monkeypatch.setattr(enrichment_main.config, "CHECKPOINT_PATH", checkpoint_path)
    monkeypatch.setattr(enrichment_main, "load_candidates", lambda **kwargs: [{"id": "1", "company_name": "Acme"}])
    monkeypatch.setattr(enrichment_main, "enrichment_graph", FakeGraph())
    result = enrichment_main.run(dry_run=False)
    assert result["total"] == 0
    assert result["skipped_by_checkpoint"] == 1


def test_run_dry_run_ignora_checkpoint_e_nao_altera_arquivo(monkeypatch, tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_text = '{"processed":{"1":{"company_name":"Acme"}},"failed":{},"last_saved_at":null}'
    checkpoint_path.write_text(checkpoint_text, encoding="utf-8")

    class FakeGraph:
        def stream(self, state):
            yield {"log_result": {"log_summary": {"total": 1, "REVIEW": 1, "updated": False}}}

    monkeypatch.setattr(enrichment_main.config, "CHECKPOINT_PATH", checkpoint_path)
    monkeypatch.setattr(enrichment_main, "load_candidates", lambda **kwargs: [{"id": "1", "company_name": "Acme"}])
    monkeypatch.setattr(enrichment_main, "enrichment_graph", FakeGraph())
    result = enrichment_main.run(dry_run=True)
    assert result["total"] == 1
    assert result["skipped_by_checkpoint"] == 0
    assert checkpoint_path.read_text(encoding="utf-8") == checkpoint_text


def _patch_graph_nodes(monkeypatch, evidence_url="https://acme.com.br"):
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.cnpj_lookup_node", lambda state: {"cnpj_data": {"cnpj": "11222333000181", "ativa": True, "uf": "SP", "situacao": "ATIVA", "razao_social": "ACME AI LTDA"}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.source_discovery_node", lambda state: {
        "source_candidates": [{"url": evidence_url, "source_type": "website", "origin": "candidate_field", "title": "Acme Brasil", "snippet": "startup brasileira", "raw_text": "Acme e uma startup brasileira com OpenAI, Python e React.", "metadata": {}}],
        "errors": {},
    })
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.candidate_url_loop_node", lambda state: {
        "source_candidates": [{"url": evidence_url, "source_type": "website", "validation": {"classification": "MATCH", "confidence": 91}}],
        "candidate_attempts": [{"url_index": 1, "url": evidence_url, "classification": "MATCH", "confidence": 91, "reason": "match", "decision": "accepted"}],
        "validated_source": {"url": evidence_url, "source_type": "website", "validation": {"classification": "MATCH", "confidence": 91}},
        "validated_sources": [{"url": evidence_url, "source_type": "website", "validation": {"classification": "MATCH", "confidence": 91}}],
        "validated_url": evidence_url,
        "rejected_sources": [],
        "identity_validation": {"classification": "MATCH", "confidence": 91, "should_update_database": True},
        "identity_evidence": {"sources": [{"url": evidence_url}]},
        "identity_confidence_score": 91,
        "candidate_urls": [evidence_url],
        "errors": {},
    })
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.github_lookup_node", lambda state: {"github_profile": {"login": "acme", "tech_stack": ["Python"], "ai_integrations": ["OpenAI"], "repos": []}, "validated_sources": state["validated_sources"], "identity_evidence": state["identity_evidence"], "errors": {}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.gupy_lookup_node", lambda state: {"gupy_profile": {"url": "https://acme.gupy.io", "open_jobs_signals": ["React", "Docker"], "tech_stack": ["React", "Docker"], "ai_integrations": []}, "validated_sources": state["validated_sources"], "identity_evidence": state["identity_evidence"], "errors": {}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.web_context_lookup_node", lambda state: {"web_context": {evidence_url: "A Acme e uma startup brasileira com plataforma de inteligencia artificial para RH."}, "raw_texts": {evidence_url: "A Acme e uma startup brasileira com plataforma de inteligencia artificial para RH."}, "evidence_urls": [evidence_url], "errors": {}})


def test_grafo_aprova_candidato_com_identidade_e_stack(monkeypatch):
    _patch_graph_nodes(monkeypatch)
    result = build_enrichment_graph().invoke({"candidate": {"id": "1", "company_name": "Acme AI"}, "dry_run": True, "errors": {}})
    assert result["identity_validation"]["classification"] == "MATCH"
    assert result["classification"]["validation_status"] == "APPROVED"
    assert result["company_description"]
    assert result["log_summary"]["MATCH"] == 1
    assert result["final_status"] == "APPROVED"


def test_grafo_mantem_review_quando_nao_ha_match(monkeypatch):
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.cnpj_lookup_node", lambda state: {"cnpj_data": {}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.source_discovery_node", lambda state: {"source_candidates": [{"url": "https://finix.ro", "source_type": "website", "origin": "ddg"}], "errors": {}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.candidate_url_loop_node", lambda state: {
        "source_candidates": [{"url": "https://finix.ro", "source_type": "website", "validation": {"classification": "WRONG_COMPANY", "confidence": 15}}],
        "candidate_attempts": [{"url_index": 1, "url": "https://finix.ro", "classification": "WRONG_COMPANY", "confidence": 15, "reason": "wrong company", "decision": "rejected"}],
        "validated_sources": [],
        "validated_url": None,
        "rejected_sources": [{"url": "https://finix.ro", "validation": {"classification": "WRONG_COMPANY", "confidence": 15, "reason": "wrong company"}}],
        "rejected_urls": ["https://finix.ro | wrong company"],
        "identity_validation": {"classification": "INSUFFICIENT_EVIDENCE", "confidence": 15, "should_update_database": False},
        "identity_evidence": {"sources": [{"url": "https://finix.ro"}]},
        "identity_confidence_score": 15,
        "discard_reason": "no_valid_source_found_after_10_urls",
        "is_active": False,
        "errors": {},
    })
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.github_lookup_node", lambda state: {"github_profile": {}, "validated_sources": state["validated_sources"], "identity_evidence": state["identity_evidence"], "errors": {}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.gupy_lookup_node", lambda state: {"gupy_profile": {}, "validated_sources": state["validated_sources"], "identity_evidence": state["identity_evidence"], "errors": {}})
    monkeypatch.setattr("scraper.enrichment_pipeline.graph.web_context_lookup_node", lambda state: {"web_context": {}, "raw_texts": {}, "evidence_urls": [], "errors": {}})
    result = build_enrichment_graph().invoke({"candidate": {"id": "2", "company_name": "Finix"}, "dry_run": True, "errors": {}})
    assert result["classification"]["validation_status"] == "DISCARDED"
    assert result["company_description"] == ""
    assert result["enrichment_status"] == "discarded"
