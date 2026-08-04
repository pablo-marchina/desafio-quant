from __future__ import annotations

import requests

_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; pesquisa-academica/1.0)"


def consultar_cnpj(cnpj: str) -> dict | None:
    """Retorna os dados da BrasilAPI para o CNPJ ou None em caso de erro."""
    url = _URL.format(cnpj=cnpj)
    try:
        r = _SESSION.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"    [brasilapi] status {r.status_code} para CNPJ {cnpj}")
    except requests.RequestException as e:
        print(f"    [brasilapi] erro: {e}")
    return None


def nome_empresa(dados: dict) -> str:
    """Retorna nome fantasia ou razão social, em title case."""
    return ((dados.get("nome_fantasia") or "") or dados.get("razao_social", "")).title()


def situacao(dados: dict) -> str:
    return dados.get("descricao_situacao_cadastral", "").upper()


def atividades_principais(dados: dict) -> list[dict]:
    atividades = dados.get("atividade_principal", [])
    if isinstance(atividades, dict):
        return [atividades]
    return atividades
