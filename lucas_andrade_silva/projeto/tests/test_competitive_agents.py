from agents.nvidia.competitive import agents
from agents.nvidia.competitive import search as competitive_search
from agents.nvidia.competitive.search import company_for_official_url


def test_official_domain_allowlist_rejects_third_parties():
    assert company_for_official_url("https://platform.openai.com/docs") == "OpenAI"
    assert company_for_official_url("https://www.ibm.com/products/watsonx-ai") == "IBM"
    assert company_for_official_url("https://nubank.com.br/empresas") == "Nubank"
    assert company_for_official_url("https://www.sap.com/products/erp.html") == "SAP"
    assert company_for_official_url("https://www.siemens.com/global/en.html") == "Siemens"
    assert company_for_official_url("https://www.itau.com.br/empresas") == "Itaú Unibanco"
    assert (
        company_for_official_url("https://www.einstein.br/especialidades")
        == "Hospital Israelita Albert Einstein"
    )
    assert company_for_official_url("https://openai.com.evil.test/product") is None
    assert company_for_official_url("https://medium.com/openai-product") is None


class _NoResultsDDGS:
    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def text(self, *_args, **_kwargs):
        raise competitive_search.DDGSException("No results found.")


def test_pricing_search_returns_none_when_ddgs_has_no_results(monkeypatch):
    monkeypatch.setattr(competitive_search, "DDGS", _NoResultsDDGS)
    monkeypatch.setattr(competitive_search, "_rate_limit", lambda: None)

    result = competitive_search.search_pricing_page(
        "Acme analytics",
        ("acme.test",),
    )

    assert result is None


def test_official_search_returns_empty_when_ddgs_has_no_results(monkeypatch):
    monkeypatch.setattr(competitive_search, "DDGS", _NoResultsDDGS)
    monkeypatch.setattr(competitive_search, "_rate_limit", lambda: None)

    result = competitive_search.search_official_candidates(
        "analytics platform",
        set(),
    )

    assert result == []


def test_official_search_uses_selected_company_domains(monkeypatch):
    queries = []

    def fake_search(query, max_results):
        queries.append((query, max_results))
        return [
            {
                "href": "https://nubank.com.br/empresas",
                "title": "Nubank para empresas",
                "body": "Conta e soluções de crédito para empresas.",
            }
        ]

    monkeypatch.setattr(competitive_search, "_search_text", fake_search)
    monkeypatch.setattr(competitive_search, "_rate_limit", lambda: None)

    result = competitive_search.search_official_candidates(
        "business credit platform",
        set(),
        ["Nubank"],
    )

    assert "site:nubank.com.br" in queries[0][0]
    assert "site:openai.com" not in queries[0][0]
    assert result[0]["company"] == "Nubank"


def test_official_search_tries_broader_query_after_empty_specific_query(
    monkeypatch,
):
    queries = []

    def fake_search(query, max_results):
        queries.append((query, max_results))
        if "business credit platform" not in query:
            return []
        return [
            {
                "href": "https://nubank.com.br/empresas",
                "title": "Nubank para empresas",
                "body": "Soluções de crédito para empresas.",
            }
        ]

    monkeypatch.setattr(competitive_search, "_search_text", fake_search)
    monkeypatch.setattr(competitive_search, "_rate_limit", lambda: None)

    result = competitive_search.search_official_candidates(
        [
            "business credit and equipment leasing platform",
            "business credit platform",
        ],
        set(),
        ["Nubank"],
    )

    assert len(queries) == 2
    assert result[0]["company"] == "Nubank"


def test_search_generator_selects_known_companies(monkeypatch):
    captured = {}

    def fake_call_json(_, payload):
        captured["payload"] = payload
        return {
            "search_string_gerada": "business credit and equipment leasing platform",
            "search_strings_geradas": [
                "business credit and equipment leasing platform",
                "business credit platform",
            ],
            "categoria_funcional": "crédito e aluguel de equipamentos",
            "empresas_candidatas": ["Nubank", "IBM", "Empresa inventada", "nubank"],
        }

    monkeypatch.setattr(agents, "call_json", fake_call_json)

    result = agents.search_string_generator_agent(
        {"servico_startup_analisado": "Crédito e aluguel de equipamentos."}
    )

    assert "Nubank" in captured["payload"]["empresas_referencia"]
    assert result["bigtech_empresas_candidatas"] == ["Nubank", "IBM"]
    assert result["search_strings_geradas"] == [
        "business credit and equipment leasing platform",
        "business credit platform",
    ]


def test_scraper_stops_after_max_attempts():
    result = agents.bigtech_scraper_agent(
        {
            "search_string_gerada": "report generation SaaS",
            "bigtech_tentativas": agents.MAX_BIGTECH_ATTEMPTS,
            "bigtech_candidatos_testados": [],
            "dados_insuficientes": [],
        }
    )
    assert result["bigtech_validacao_status"] == "esgotado"
    assert result["bigtech_servico_validado"] is None
    assert result["dados_insuficientes"]


def test_validator_requires_explicit_positive_result(monkeypatch):
    monkeypatch.setattr(
        agents,
        "call_json",
        lambda *_: {"validado": False, "motivo": "modalidade API vs SaaS"},
    )
    result = agents.equivalence_validator_agent(
        {
            "servico_startup_analisado": "relatórios por API",
            "categoria_funcional": "geração de relatórios",
            "bigtech_tentativas": 1,
            "bigtech_candidato": {
                "candidato_url": "https://openai.com/product",
                "candidato_empresa": "OpenAI",
                "candidato_conteudo": {},
            },
        }
    )
    assert result["bigtech_validacao_status"] == "rejeitado"
    assert result["bigtech_servico_validado"] is None


def test_pricing_does_not_analyze_when_one_price_is_missing(monkeypatch):
    monkeypatch.setattr(agents, "search_pricing_page", lambda *_: None)
    monkeypatch.setattr(
        agents,
        "call_json",
        lambda *_: {
            "preco_startup": {"valor": "nao_disponivel", "fonte_url": None},
            "preco_bigtech": {
                "valor": "$10",
                "fonte_url": "https://openai.com/pricing",
            },
            "analise_custo_beneficio": "estimativa indevida",
        },
    )
    result = agents.pricing_agent(
        {
            "empresa": "Acme",
            "startup_url": "https://acme.test",
            "servico_startup_analisado": "relatórios SaaS",
            "bigtech_servico_validado": {
                "candidato_empresa": "OpenAI",
                "candidato_conteudo": {"titulo_produto": "Reports"},
            },
        }
    )
    assert result["analise_custo_beneficio"] == (
        "comparação de preço não disponível"
    )


def test_comparison_removes_points_with_invented_sources(monkeypatch):
    monkeypatch.setattr(
        agents,
        "call_json",
        lambda *_: {
            "pontos_fortes_startup": [
                {
                    "aspecto": "integração",
                    "evidencia": "alegação",
                    "fonte": "https://blog-terceiro.test",
                }
            ],
            "pontos_fortes_bigtech": [],
            "quem_entrega_mais_hoje": "startup",
            "justificativa": "fonte inválida",
        },
    )
    result = agents.comparison_agent(
        {
            "servico_startup_analisado": "SaaS",
            "startup_url": "https://acme.test",
            "pontos_fortes": [],
            "bigtech_servico_validado": {
                "candidato_url": "https://openai.com/product"
            },
        }
    )["comparacao_pontos_fortes_fracos"]
    assert result["pontos_fortes_startup"] == []
    assert result["quem_entrega_mais_hoje"] == "equivalente"


def test_comparison_never_adds_future_nvidia_to_startup(monkeypatch):
    monkeypatch.setattr(
        agents,
        "call_json",
        lambda *_: {
            "pontos_fortes_startup": [
                {
                    "aspecto": "NVIDIA IGX",
                    "evidencia": "Tractian com NVIDIA IGX teria menor latência",
                    "fonte": "https://tractian.com",
                }
            ],
            "pontos_fracos_startup": [],
            "pontos_fortes_bigtech": [],
            "pontos_fracos_bigtech": [],
            "quem_entrega_mais_hoje": "startup",
            "justificativa": "inclui arquitetura futura",
        },
    )
    result = agents.comparison_agent(
        {
            "empresa": "Tractian",
            "servico_startup_analisado": "monitoramento industrial atual",
            "startup_url": "https://tractian.com",
            "pontos_fortes": [
                {
                    "aspecto": "monitoramento",
                    "evidencia": "monitoramento industrial",
                    "fonte": "https://tractian.com",
                }
            ],
            "bigtech_servico_validado": {
                "candidato_url": "https://aws.amazon.com/product",
                "candidato_empresa": "Amazon",
            },
        }
    )["comparacao_pontos_fortes_fracos"]
    assert result["pontos_fortes_startup"] == []
    assert result["escopo_comparacao"].startswith("estado_atual")


def test_bigtech_axis_summary_uses_description_cnae_and_validated_service(monkeypatch):
    captured = {}

    def fake_call_json(_, payload):
        captured["payload"] = payload
        return {
            "categoria_funcional": "plataforma SaaS de analytics preditivo",
            "equivalentes_big_tech": [
                {
                    "empresa": "Microsoft",
                    "produto": "Azure Machine Learning",
                    "como_resolve": "Treina e publica modelos preditivos.",
                }
            ],
            "vantagem_bigtech": "Escala e infraestrutura global.",
            "vantagem_startup": "Especializacao setorial e suporte local.",
            "risco_substituicao": "Médio - há equivalência funcional parcial.",
        }

    monkeypatch.setattr(agents, "call_json", fake_call_json)
    result = agents.bigtech_axis_summary_agent(
        {
            "empresa": "Axenya",
            "servico_startup_analisado": "Plataforma de saude com modelos preditivos.",
            "cnae": "6201-5/01 - Desenvolvimento de programas de computador",
            "categoria_funcional": "analytics preditivo em saude",
            "comparacao_pontos_fortes_fracos": {},
            "bigtech_servico_validado": {
                "candidato_empresa": "Microsoft",
                "candidato_url": "https://azure.microsoft.com/product",
                "candidato_conteudo": {"titulo_produto": "Azure Machine Learning"},
            },
        }
    )["comparacao_bigtechs_resumida"]

    assert captured["payload"]["startup"]["cnae"].startswith("6201")
    assert "Microsoft" in captured["payload"]["empresas_referencia"]
    assert result["categoria_funcional"] == "plataforma SaaS de analytics preditivo"
    assert result["equivalentes_big_tech"][0]["empresa"] == "Microsoft"
    assert result["risco_substituicao"].startswith("Médio")


def test_leverage_stops_without_delivery1_gap(monkeypatch):
    monkeypatch.setattr(
        agents,
        "call_json",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("não deve chamar o modelo")
        ),
    )
    result = agents.leverage_agent(
        {
            "gaps_identificados": [],
            "recomendacoes_nvidia": [
                {"gap": "latência", "produto": "NVIDIA IGX"}
            ],
            "comparacao_pontos_fortes_fracos": {
                "pontos_fortes_bigtech": [{"aspecto": "latência"}]
            },
            "dados_insuficientes": [],
        }
    )
    assert result["alavancagem_nvidia"] is None
    assert any("nenhum gap explícito" in item for item in result["dados_insuficientes"])


def test_synthesis_preserves_structured_agent_outputs():
    result = agents.competitive_synthesis_agent(
        {
            "empresa": "Tractian",
            "servico_startup_analisado": "monitoramento",
            "stack_atual": [],
            "pontos_fortes": [],
            "github_discovery": {"status": "esgotado", "tentativas": 3},
            "gaps_identificados": [],
            "recomendacoes_nvidia": [],
            "bigtech_validacao_status": "esgotado",
            "dados_insuficientes": ["sem equivalente"],
        }
    )["structured_output"]
    assert result["schema_version"] == "competitive-analysis/v1"
    assert result["startup_estado_atual"]["github_discovery"]["tentativas"] == 3
    assert result["entrega1"]["gaps_identificados"] == []
    assert result["dados_insuficientes"] == ["sem equivalente"]
    assert result["comparacao_competitiva"]["pesquisa"]["empresas_candidatas"] == []
    assert result["comparacao_competitiva"]["comparacao_bigtechs_resumida"][
        "categoria_funcional"
    ].startswith("sem equivalente direto relevante")
