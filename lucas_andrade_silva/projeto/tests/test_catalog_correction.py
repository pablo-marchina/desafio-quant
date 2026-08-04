from __future__ import annotations

import scraper.enrichment_pipeline.catalog_correction as catalog_correction
from scraper.enrichment_pipeline.catalog_correction import (
    _cnpja_rate_limit,
    clean_company_name,
    correct_row,
    extract_name_from_description,
    find_official_website,
    normalize_cnpja_payload,
    rewrite_description_portuguese,
    _homepage,
    _host_matches_name,
    _is_news_or_social,
    _looks_bad_official_path,
    is_valid_company_name,
)


def test_clean_company_name_remove_lixo_inicial():
    assert clean_company_name("A Infiscal") == "Infiscal"
    assert clean_company_name("The Tools") == "Tools"
    assert clean_company_name("Essa Acme") == "Acme"


def test_is_valid_company_name_rejeita_lixo():
    assert not is_valid_company_name("thiago@darwinstartups.com")
    assert not is_valid_company_name("Menu")
    assert not is_valid_company_name("Principal")
    assert not is_valid_company_name("Solução A")
    assert is_valid_company_name("Cora")


def test_extract_name_from_description_prefere_nome_da_descricao():
    assert (
        extract_name_from_description("A Infiscal oferece automacao fiscal com IA.", "Empresa errada")
        == "Infiscal"
    )


def test_extract_name_from_description_usa_secao_web_quando_resumo_tem_nome_errado():
    description = """
    Candidato:
    - nome: Descomplica
    - descricao_original: nao informada
    Web:
    https://startups.com.br/noticia: Para a Cora, ser uma fintech focada em pequenas empresas e apenas uma parte da jornada.
    Sinais IA:
    - nenhum sinal verificavel encontrado
    """
    assert extract_name_from_description(description, "Descomplica") == "Cora"


def test_normalize_cnpja_payload_extrai_campos_principais():
    payload = {
        "data": [
            {
                "taxId": "11.222.333/0001-81",
                "founded": "2022-04-10",
                "address": {"city": "Sao Paulo", "state": "SP"},
                "mainActivity": {"code": "6201-5/01", "text": "Desenvolvimento de programas de computador"},
                "members": [{"name": "Maria Silva", "role": "Socio-administrador"}],
            }
        ]
    }
    result = normalize_cnpja_payload(payload)
    assert result["cnpj"] == "11222333000181"
    assert result["founding_year"] == "2022"
    assert result["location"] == "Sao Paulo, SP"
    assert result["cnae"] == "6201-5/01 - Desenvolvimento de programas de computador"
    assert result["socios"] == [{"name": "Maria Silva", "role": "Socio-administrador"}]


def test_rewrite_description_portuguese_so_quando_ingles():
    result = rewrite_description_portuguese(
        "Acme",
        "The company provides an AI platform for financial teams.",
        {"cnpj": "11222333000181", "founding_year": "2022", "location": "Sao Paulo, SP", "cnae": "6201 - Software"},
    )
    assert result is not None
    assert "CNPJ: 11222333000181" in result
    assert "Descricao original em ingles preservada" not in result
    assert "plataforma de IA" in result


def test_website_filters_bloqueiam_fontes_nao_oficiais_e_normalizam_home():
    assert _is_news_or_social("https://pt.wikipedia.org/wiki/Banco_Cora")
    assert _is_news_or_social("https://www.agoracupom.com.br/desconto/editora-sanar/")
    assert _looks_bad_official_path("https://www.revenawear.com/pages/security-privacy-policy")
    assert _homepage("https://www.revenawear.com/pages/security-privacy-policy") == "https://www.revenawear.com/"
    assert _host_matches_name("https://sanar.com.br/", "Sanar")
    assert not _host_matches_name("https://www.agoracupom.com.br/desconto/editora-sanar/", "Sanar")


def test_find_official_website_ignora_primeiro_homonimo_sem_contexto_brasileiro(monkeypatch):
    class FakeDDGS:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def text(self, query, max_results):
            assert "empresa brasileira" in query
            return [
                {
                    "href": "https://hakutaku.us",
                    "title": "Hakutaku",
                    "body": "Hakutaku software and digital services.",
                },
                {
                    "href": "https://hakutaku.com.br",
                    "title": "Hakutaku Brasil",
                    "body": "A Hakutaku e uma empresa brasileira de tecnologia.",
                },
            ]

    monkeypatch.setattr(catalog_correction, "DDGS", FakeDDGS)
    monkeypatch.setattr(catalog_correction, "_rate_limit", lambda: None)

    assert find_official_website("Hakutaku") == "https://hakutaku.com.br"


def test_find_official_website_nao_usa_fallback_sem_identidade_brasileira(monkeypatch):
    class FakeDDGS:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def text(self, query, max_results):
            return [
                {
                    "href": "https://hakutaku.us",
                    "title": "Hakutaku",
                    "body": "Hakutaku software and digital services.",
                }
            ]

    monkeypatch.setattr(catalog_correction, "DDGS", FakeDDGS)
    monkeypatch.setattr(catalog_correction, "_rate_limit", lambda: None)

    assert "encontrado" in find_official_website("Hakutaku")


def test_cnpja_rate_limit_usa_janela_propria(monkeypatch):
    sleeps = []
    times = iter([5.0, 20.0])
    monkeypatch.setattr(catalog_correction.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(catalog_correction.time, "sleep", lambda value: sleeps.append(value))
    monkeypatch.setattr(catalog_correction, "_last_cnpja_request_at", 0.0)
    _cnpja_rate_limit()
    assert sleeps == [15.0]


def test_correct_row_respeita_campos_editaveis(monkeypatch):
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.catalog_correction.search_cnpj",
        lambda name: {
            "cnpj": "11222333000181",
            "founding_year": "2022",
            "location": "Sao Paulo, SP",
            "socios": [{"name": "Maria Silva"}],
            "cnae": "6201 - Software",
        },
    )
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.catalog_correction.find_official_website",
        lambda name: "https://acme.ai",
    )
    result = correct_row({
        "id": "nao-mexer",
        "candidate_id": "1",
        "company_name": "A Empresa errada",
        "description": "A Acme oferece automacao com IA.",
        "cnpj": None,
        "source_url": "nao-mexer",
        "created_at": "nao-mexer",
    })
    assert result["company_name"] == "Acme"
    assert result["website"] == "https://acme.ai"
    assert result["cnpj"] == "11222333000181"
    assert "id" not in result
    assert "source_url" not in result
    assert "created_at" not in result


def test_correct_row_nao_envia_company_name_quando_nome_invalido(monkeypatch):
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.catalog_correction.find_official_website",
        lambda name: "não encontrado",
    )
    result = correct_row({
        "candidate_id": "2",
        "company_name": "Menu",
        "description": "Menu principal de navegacao sem nome confiavel de empresa.",
        "cnpj": "11222333000181",
    })
    assert "company_name" not in result


def test_correct_row_nao_troca_nome_valido_por_web_contaminada(monkeypatch):
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.catalog_correction.find_official_website",
        lambda name: "https://igti.example",
    )
    result = correct_row({
        "candidate_id": "3",
        "company_name": "IGTI",
        "description": "Web: https://example.com: A GetHome oferece uma solucao para moradia. Sinais IA:",
        "cnpj": "11222333000181",
    })
    assert result["company_name"] == "IGTI"


def test_correct_row_troca_produto_por_empresa_quando_frase_comeca_com_empresa(monkeypatch):
    monkeypatch.setattr(
        "scraper.enrichment_pipeline.catalog_correction.find_official_website",
        lambda name: "https://aimirim.ai",
    )
    result = correct_row({
        "candidate_id": "4",
        "company_name": "Tupana",
        "description": "Aimirim, sediada em Uberlandia, oferece a plataforma Tupana, que integra sensores IoT e inteligencia artificial.",
        "cnpj": "11222333000181",
    })
    assert result["company_name"] == "Aimirim"
