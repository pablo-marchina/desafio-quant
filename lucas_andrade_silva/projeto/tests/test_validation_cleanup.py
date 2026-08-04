from scraper.validation_pipeline.cleanup import (
    clean_company_name, is_confirmed_non_ai, is_foreign_without_brazil,
    is_person_or_role, is_text_fragment, update_validation_record,
)


def base(**values):
    row = {"company_name": "Acme", "source_name": "startups.com.br", "source_url": "https://startups.com.br/a",
        "evidence_text": "Startup brasileira com produto digital.", "validation_status": "REVIEW",
        "is_valid_company": True, "is_brazilian": True, "is_startup": True,
        "uses_ai_potentially": None, "ai_classification": "UNKNOWN"}
    row.update(values)
    return row


def test_safe_article_correction():
    assert clean_company_name("A Billor") == "Billor"
    assert clean_company_name("A Jusfy") == "Jusfy"
    assert clean_company_name("A Sol Agora") == "Sol Agora"
    assert clean_company_name("A empresa anunciou resultados") == "A empresa anunciou resultados"


def test_fragments_and_roles():
    assert is_text_fragment(base(company_name="Hoje já possuem mais de 150 clientes."))
    assert is_text_fragment(base(company_name="Tel Aviv. A"))
    assert is_person_or_role(base(company_name="Diretora Executiva. A"))


def test_foreign_requires_explicit_evidence_and_no_brazil():
    assert is_foreign_without_brazil(base(evidence_text="Empresa fundada em Tel Aviv e sediada em Israel."))
    assert not is_foreign_without_brazil(base(evidence_text="Empresa fundada em Tel Aviv com operação no Brasil."))


def test_non_ai_is_conservative_and_strong_sources_are_protected():
    row = base(ai_classification="NON_AI", uses_ai_potentially=False,
        evidence_text=("Rede de lojas físicas de um varejista tradicional dedicada à venda presencial de alimentos e bebidas. " * 4))
    assert is_confirmed_non_ai(row)
    assert not is_confirmed_non_ai({**row, "source_name": "Cubo"})
    assert not is_confirmed_non_ai(base(ai_classification="NON_AI", uses_ai_potentially=False,
        evidence_text="Empresa brasileira sem detalhes suficientes."))


def test_approved_requires_ai_and_fragment_is_rejected():
    approved = base(validation_status="APPROVED", uses_ai_potentially=True, ai_classification="AI_ENABLED")
    assert update_validation_record(approved)["validation_status"] == "APPROVED"
    fragment = {**approved, "company_name": "jornadas de personalização e crédito"}
    result = update_validation_record(fragment)
    assert result["validation_status"] == "REJECTED"
    assert result["rejection_reason"] == "text_fragment"
