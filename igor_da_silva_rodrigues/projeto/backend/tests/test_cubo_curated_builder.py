from app.processing.cubo_curated_builder import construir_curated_cubo_de_payload


def test_construir_curated_cubo_deduplicates_by_domain_and_preserves_aliases():
    payload = {
        "startups": [
            _startup("Alice", "https://alice.com.br", score=0.7),
            _startup("Alice Saude", "https://www.alice.com.br", score=0.9),
        ]
    }

    resultado = construir_curated_cubo_de_payload(payload)

    assert resultado["metadados"]["total_entrada"] == 2
    assert resultado["metadados"]["total_curado"] == 1
    empresa = resultado["startups"][0]
    assert empresa["nome"] == "Alice Saude"
    assert empresa["aliases"] == ["Alice"]
    assert empresa["dominio"] == "alice.com.br"
    assert empresa["qualidade"]["merged_from_count"] == 2


def test_construir_curated_cubo_keeps_different_companies():
    payload = {
        "startups": [
            _startup("Alice", "https://alice.com.br"),
            _startup("Brisa", "https://brisa.com.br"),
        ]
    }

    resultado = construir_curated_cubo_de_payload(payload)

    assert resultado["metadados"]["total_curado"] == 2


def test_construir_curated_cubo_builds_agent_friendly_shape():
    payload = {
        "startups": [
            {
                **_startup("Clara", "https://clara.com.br", score=0.95),
                "link_perfil_cubo": "https://cubo.itau/startups-portfolio/clara",
            }
        ]
    }

    resultado = construir_curated_cubo_de_payload(payload)
    empresa = resultado["startups"][0]

    assert empresa["startup_id"].startswith("cubo_clara_com_br_")
    assert empresa["qualidade"]["status"] == "boa"
    assert empresa["decisao_pipeline"]["prosseguir"] is True
    assert {"tipo": "site_oficial", "url": "https://clara.com.br"} in empresa["fontes"]
    assert {"tipo": "cubo_perfil", "url": "https://cubo.itau/startups-portfolio/clara"} in empresa["fontes"]


def test_construir_curated_cubo_marks_missing_fields_in_decision():
    payload = {"startups": [_startup("SemCidade", "https://semcidade.com.br", cidade=None, estado=None)]}

    resultado = construir_curated_cubo_de_payload(payload)
    decisao = resultado["startups"][0]["decisao_pipeline"]

    assert decisao["prosseguir"] is False
    assert "cidade ausente" in decisao["motivos"]
    assert "estado ausente" in decisao["motivos"]


def _startup(nome, site, score=0.9, cidade="São Paulo", estado="SP"):
    return {
        "nome": nome,
        "site": site,
        "cidade": cidade,
        "estado": estado,
        "pais": "Brasil",
        "categoria": "Fintech",
        "descricao_curta": "Empresa com IA.",
        "logo_url": None,
        "link_perfil_cubo": f"https://cubo.itau/startups-portfolio/{nome.lower()}",
        "qualidade": {
            "score": score,
            "alertas": [],
        },
        "raw": {"nome": nome},
    }
