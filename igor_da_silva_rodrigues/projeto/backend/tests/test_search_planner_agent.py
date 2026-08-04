from app.agents.search_planner_agent import planejar_busca_ia_startup


def test_planejar_busca_ia_startup_generates_inception_plan_for_fintech():
    startup = {
        "nome": "Clara Pagamentos",
        "site": "https://clara.com.br",
        "categoria": "Financeiro",
        "descricao_curta": "Plataforma de gestão de gastos corporativos com automação.",
        "link_perfil_cubo": "https://cubo.itau/startups-portfolio/clara-pagamentos",
    }

    plano = planejar_busca_ia_startup(startup)

    assert plano["startup"] == "Clara Pagamentos"
    assert "Hipótese inicial" in plano["hipotese_maturidade"]
    assert "API-consumer" in plano["hipotese_maturidade"] or "AI-enabled" in plano["hipotese_maturidade"]
    assert len(plano["plano_consultas"]) >= 18
    assert len(plano["tarefas"]) == len(plano["plano_consultas"]) + 1
    assert len(plano["fontes_prioritarias"]) >= 3
    assert plano["fontes_prioritarias"][0]["fonte"] == "Site oficial"
    assert plano["tarefas"][0]["tipo"] == "acesso_direto"
    assert plano["tarefas"][0]["url"] == "https://clara.com.br"
    assert plano["tarefas"][0]["extrator"] == "firecrawl"


def test_planejar_busca_ia_startup_distributes_queries_across_seven_layers():
    startup = {
        "nome": "HealthAI",
        "site_oficial": "https://healthai.example",
        "categoria": "Healthtech",
        "descricao_curta": "Sistema para clínicas.",
    }

    plano = planejar_busca_ia_startup(startup)
    layers = {item["camada"] for item in plano["plano_consultas"]}

    assert layers == {1, 2, 3, 4, 5, 6, 7}
    assert any("diagnóstico assistido" in item["consulta"] for item in plano["plano_consultas"])
    assert "descrição curta não confirma IA" in plano["observacoes"]


def test_planejar_busca_ia_startup_prioritizes_layers_three_and_four():
    startup = {
        "nome": "OperAI",
        "site": "https://operai.example",
        "categoria": "Produtividade",
        "descricao_curta": "Automação inteligente com LLM para operações.",
    }

    plano = planejar_busca_ia_startup(startup)
    layer_3_4_count = sum(1 for item in plano["plano_consultas"] if item["camada"] in (3, 4))

    assert layer_3_4_count >= len(plano["plano_consultas"]) * 0.45
    assert any("API OpenAI" in item["consulta"] for item in plano["plano_consultas"])
    assert any("NVIDIA" in item["consulta"] for item in plano["plano_consultas"])
    assert any("custo de inferência" in item["consulta"] for item in plano["plano_consultas"])
    assert "AI-enabled" in plano["hipotese_maturidade"]


def test_planejar_busca_ia_startup_includes_english_queries():
    startup = {
        "nome": "DeepRisk",
        "site": "https://deeprisk.example",
        "categoria": "Fintech",
        "descricao_curta": "Motor de risco com dados transacionais.",
    }

    plano = planejar_busca_ia_startup(startup)
    queries = [item["consulta"] for item in plano["plano_consultas"]]

    assert any("PyTorch" in query or "TensorFlow" in query for query in queries)
    assert any("fine-tuning" in query for query in queries)
    assert any("technical report" in query for query in queries)
    assert any("site:deeprisk.example" in query for query in queries)


def test_planejar_busca_ia_startup_outputs_scraper_ready_tasks():
    startup = {
        "nome": "DeepRisk",
        "site": "https://deeprisk.example",
        "categoria": "Fintech",
        "descricao_curta": "Motor de risco com dados transacionais.",
    }

    plano = planejar_busca_ia_startup(startup)
    task = plano["tarefas"][1]
    site_task = next(item for item in plano["tarefas"] if item.get("consulta", "").startswith("site:"))

    assert task["id"].startswith("task_camada_")
    assert task["tipo"] == "busca_web"
    assert task["motor"] == "searxng"
    assert task["camada"] == plano["plano_consultas"][0]["camada"]
    assert task["objetivo"] == plano["plano_consultas"][0]["objetivo"]
    assert site_task["tipo"] == "busca_site"
    assert all(item["max_resultados"] == 8 for item in plano["tarefas"] if item["camada"] in (3, 4))


def test_planejar_busca_ia_startup_does_not_require_site():
    startup = {
        "nome": "SemSite",
        "categoria": "Edtech",
        "descricao_curta": "Plataforma educacional.",
    }

    plano = planejar_busca_ia_startup(startup)

    assert plano["startup"] == "SemSite"
    assert len(plano["plano_consultas"]) >= 18
    assert not any(item["consulta"].startswith("site:SemSite") for item in plano["plano_consultas"])
    assert plano["fontes_prioritarias"][0]["fonte"] == "LinkedIn"
