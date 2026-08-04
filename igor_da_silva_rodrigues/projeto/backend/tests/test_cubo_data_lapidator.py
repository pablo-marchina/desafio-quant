import json

from app.processing.cubo_data_lapidator import lapidar_dados_cubo


def test_lapidar_dados_remove_registro_sem_nome():
    payload = {"startups": [{"nome": "  "}, {"nome": "Clara", "pais": "Brasil"}]}

    resultado = lapidar_dados_cubo(payload)

    json_lapidado = resultado["JSON_LAPIDADO"]
    assert json_lapidado["metadados"]["total_bruto"] == 2
    assert json_lapidado["metadados"]["total_valido"] == 1
    assert len(json_lapidado["metadados"]["registros_removidos"]) == 1


def test_lapidar_dados_normaliza_textos_urls_e_preserva_raw():
    raw = {
        "nome": "  Clara Pagamentos  ",
        "site": "clara.com.br?utm_source=teste",
        "cidade": "sao paulo, sp",
        "estado": "",
        "pais": "",
        "categoria": " financeiro ",
        "descricao_curta": "  Plataforma   de gastos corporativos. ",
        "logo_url": "/logo.png",
        "link_perfil_cubo": "/startups-portfolio/clara",
    }

    resultado = lapidar_dados_cubo({"startups": [raw]})
    startup = resultado["JSON_LAPIDADO"]["startups"][0]

    assert startup["nome"] == "Clara Pagamentos"
    assert startup["site"] == "https://clara.com.br"
    assert startup["cidade"] == "Sao Paulo"
    assert startup["estado"] == "SP"
    assert startup["pais"] == "Brasil"
    assert startup["categoria"] == "Financeiro"
    assert startup["descricao_curta"] == "Plataforma de gastos corporativos."
    assert startup["logo_url"] == "https://cubo.itau/logo.png"
    assert startup["link_perfil_cubo"] == "https://cubo.itau/startups-portfolio/clara"
    assert startup["raw"] == raw
    assert startup["qualidade"]["score"] > 0.8


def test_lapidar_dados_marks_incomplete_and_low_quality():
    resultado = lapidar_dados_cubo({"startups": [{"nome": "Startup X"}]})
    startup = resultado["JSON_LAPIDADO"]["startups"][0]

    assert startup["qualidade"]["incompleto"] is True
    assert startup["qualidade"]["baixa_qualidade"] is False
    assert "Registro incompleto" in " ".join(startup["qualidade"]["alertas"])


def test_lapidar_dados_detects_suspicious_city_state():
    resultado = lapidar_dados_cubo(
        {
            "startups": [
                {
                    "nome": "Empresa Y",
                    "site": "https://empresa.example",
                    "cidade": "Sao Paulo",
                    "estado": "RJ",
                    "pais": "Brasil",
                    "categoria": "Fintech",
                }
            ]
        }
    )
    startup = resultado["JSON_LAPIDADO"]["startups"][0]

    assert startup["qualidade"]["score"] < 1.0
    assert any("Inconsistencia suspeita" in alerta for alerta in startup["qualidade"]["alertas"])


def test_lapidar_dados_accepts_current_scraper_shape():
    raw = {
        "id": "1",
        "nome": "AutoU",
        "segmento": "Produtividade",
        "descricao_curta": "IA para empresas.",
        "url_perfil": "https://cubo.itau/startups-portfolio/autou",
        "image_url": "https://img.example/autou.png",
    }

    resultado = lapidar_dados_cubo([raw])
    startup = resultado["JSON_LAPIDADO"]["startups"][0]

    assert startup["categoria"] == "Produtividade"
    assert startup["logo_url"] == "https://img.example/autou.png"
    assert startup["link_perfil_cubo"] == "https://cubo.itau/startups-portfolio/autou"
