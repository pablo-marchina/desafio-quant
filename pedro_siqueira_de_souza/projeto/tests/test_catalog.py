"""Testes do catálogo de produtos NVIDIA + motor de fit por regras."""
from recommender.catalog import MIN_FIT, score_products


def test_empresa_data_heavy_recebe_rapids_mesmo_non_ai():
    # "Abrir o fit": dado/infra pontua para Non-AI data-heavy.
    fits = score_products(
        "plataforma de análise de dados financeiros com etl e pandas",
        "fintech", "Non-AI",
    )
    techs = [f.tech for f in fits]
    assert "NVIDIA RAPIDS" in techs
    rapids = next(f for f in fits if f.tech == "NVIDIA RAPIDS")
    assert rapids.fit >= 50
    assert rapids.matched_signals  # registra QUAIS sinais casaram (auditável)


def test_empresa_genai_recebe_produtos_de_ia():
    fits = score_products("assistente com llm e rag para atendimento",
                          "Software/SaaS", "AI-native")
    techs = [f.tech for f in fits]
    assert any(t in techs for t in ("NVIDIA NIM", "NVIDIA NeMo", "NVIDIA API Catalog"))


def test_maturidade_modula_o_fit_de_genai():
    perfil = "assistente com llm e chatbot"
    nat = {f.tech: f.fit for f in score_products(perfil, None, "AI-native")}
    non = {f.tech: f.fit for f in score_products(perfil, None, "Non-AI")}
    # NIM (genAI) vale mais para AI-native do que para Non-AI.
    assert nat.get("NVIDIA NIM", 0) > non.get("NVIDIA NIM", 0)


def test_sem_sinais_nao_recomenda_nada():
    fits = score_products("padaria de bairro com pães artesanais", None, "Non-AI")
    assert fits == []  # nada casa -> não força recomendação


def test_respeita_top_k_e_min_fit():
    perfil = "assistente llm rag dados etl pandas voz fala robô saúde fraude"
    fits = score_products(perfil, None, "AI-native", top_k=3)
    assert len(fits) <= 3
    assert all(f.fit >= MIN_FIT for f in fits)
    assert fits == sorted(fits, key=lambda f: f.fit, reverse=True)


def test_setor_reforca_o_fit():
    # mesmo perfil, com e sem setor que o produto valoriza (Clara <- Saúde).
    perfil = "diagnóstico por imagem médica em hospitais"
    com = {f.tech: f.fit for f in score_products(perfil, "healthtech", "AI-native")}
    sem = {f.tech: f.fit for f in score_products(perfil, None, "AI-native")}
    assert com.get("NVIDIA Clara", 0) >= sem.get("NVIDIA Clara", 0)
