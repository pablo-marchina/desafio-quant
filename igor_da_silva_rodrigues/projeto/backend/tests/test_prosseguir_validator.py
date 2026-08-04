from app.processing.prosseguir_validator import validar_flags_prosseguir


def test_validar_flags_prosseguir_detects_falso_positivo():
    payload = {
        "startups": [
            {
                "nome": "Clara",
                "site": "https://clara.com.br",
                "cidade": None,
                "estado": None,
                "pais": "Brasil",
                "categoria": "Fintech",
                "descricao_curta": "Plataforma com inteligência artificial.",
                "qualidade": {"incompleto": False},
                "prosseguir": True,
            }
        ]
    }

    relatorio = validar_flags_prosseguir(payload)

    assert "Falsos positivos: 1" in relatorio
    assert "cidade ausente" in relatorio
    assert "estado ausente" in relatorio


def test_validar_flags_prosseguir_detects_falso_negativo():
    payload = [
        {
            "nome": "AutoU",
            "site": "https://autou.io",
            "cidade": "São Paulo",
            "estado": "SP",
            "pais": "Brasil",
            "categoria": "Deeptech",
            "descricao_curta": "Solução de machine learning para grandes empresas.",
            "qualidade": {"incompleto": False},
            "prosseguir": False,
        }
    ]

    relatorio = validar_flags_prosseguir(payload)

    assert "Falsos negativos: 1" in relatorio
    assert "machine learning" in relatorio


def test_validar_flags_prosseguir_marks_unconfirmed_ai_potential():
    payload = [
        {
            "nome": "Finboa",
            "site": "https://finboa.example",
            "cidade": "São Paulo",
            "estado": "SP",
            "pais": "Brasil",
            "categoria": "Fintech",
            "descricao_curta": "Plataforma financeira para empresas.",
            "qualidade": {"incompleto": False},
            "prosseguir": False,
        }
    ]

    relatorio = validar_flags_prosseguir(payload)

    assert "Potencial de IA não confirmado (requer revisão): 1" in relatorio
    assert "Finboa" in relatorio
    assert "Recomenda-se auditoria manual" in relatorio


def test_validar_flags_prosseguir_accepts_ai_description_outside_sector_list():
    payload = [
        {
            "nome": "OperAI",
            "site": "https://operai.example",
            "cidade": "Curitiba",
            "estado": "PR",
            "pais": "Brasil",
            "categoria": "Produtividade",
            "descricao_curta": "Automação inteligente com LLM para operações.",
            "qualidade": {"incompleto": False},
            "prosseguir": True,
        }
    ]

    relatorio = validar_flags_prosseguir(payload)

    assert "Flags corretas: 1" in relatorio
    assert "Nenhum alerta." in relatorio


def test_validar_flags_prosseguir_reports_high_confidence_when_all_correct():
    payload = [
        {
            "nome": "HealthAI",
            "site": "https://healthai.example",
            "cidade": "Recife",
            "estado": "PE",
            "pais": "Brasil",
            "categoria": "Healthtech",
            "descricao_curta": "Usa IA para triagem clínica.",
            "qualidade": {"incompleto": False},
            "prosseguir": True,
        }
    ]

    relatorio = validar_flags_prosseguir(payload)

    assert "Taxa de acerto: 100.00%" in relatorio
    assert "Alta confiabilidade" in relatorio
