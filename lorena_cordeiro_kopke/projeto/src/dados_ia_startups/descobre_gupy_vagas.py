from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TERMOS_IA = [
    # IA / ML genérico
    "inteligência artificial", "machine learning", "aprendizado de máquina",
    "deep learning", "llm", "nlp", "mlops", "modelo de linguagem",
    "processamento de linguagem natural", "visão computacional", "computer vision",
    "rede neural", "neural network", "reinforcement learning",
    "generative ai", "ia generativa", "foundation model",
    # Dados
    "dados", "data science", "data scientist", "cientista de dados",
    "engenheiro de dados", "data engineer", "analista de dados",
    "data analyst", "analytics", "big data", "business intelligence",
    "pipeline de dados", "feature engineering", "engenharia de dados",
    "arquiteto de dados", "data architect", "data platform",
    "data mesh", "data lake", "data warehouse", "dbt", "airflow", "spark",
    # Automação / produto
    "automação inteligente", "rpa", "process mining",
    "recomendação", "recommendation", "personalização",
    "detecção de fraude", "fraud detection", "previsão", "forecast",
    "otimização", "scoring", "propensão",
    # Infra / engenharia
    "mlflow", "kubeflow", "sagemaker", "vertex ai", "databricks",
    "inferência", "treinamento de modelos", "feature store",
    # Abreviações soltas (com espaço para evitar falso positivo)
    " ia ", " ai ", " ml ", " bi ",
]

_SAIDA = _RAIZ / "data" / "jsons" / "gupy_vagas"


def _contem_termo_ia(texto: str) -> str | None:
    """Retorna o primeiro termo encontrado ou None."""
    texto_lower = texto.lower()
    for termo in _TERMOS_IA:
        if termo in texto_lower:
            return termo
    return None


def _buscar_vagas(subdominio: str, debug: bool = False) -> list[dict]:
    """Extrai vagas do __NEXT_DATA__ embutido na homepage do Gupy."""
    url = f"https://{subdominio}.gupy.io"
    try:
        r = _SESSION.get(url, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        if debug:
            print(f"      [debug] erro ao acessar {url}: {e}")
        return []

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        r.text,
        re.DOTALL,
    )
    if not match:
        if debug:
            print(f"      [debug] __NEXT_DATA__ não encontrado em {url}")
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        if debug:
            print(f"      [debug] erro ao parsear JSON de {url}")
        return []

    jobs = data.get("props", {}).get("pageProps", {}).get("jobs", [])
    if debug:
        print(f"      [debug] {len(jobs)} vaga(s) encontrada(s) na página")

    return jobs


def pesquisar(debug: bool = False, nome: str | None = None) -> None:
    query = supabase.table("empresas").select("id, nome, gupy_subdominio").not_.is_("gupy_subdominio", "null")
    if nome:
        query = query.eq("nome", nome)
    rows = query.execute().data
    empresas = [
        {"empresa_id": r["id"], "nome": r["nome"], "gupy_subdominio": r["gupy_subdominio"]}
        for r in rows
    ]
    print(f"[info] {len(empresas)} empresa(s) com gupy_subdominio no Supabase\n")

    todos_registros: list[dict] = []

    for empresa in empresas:
        empresa_id = empresa["empresa_id"]
        nome = empresa["nome"]
        subdominio = empresa["gupy_subdominio"]

        print(f"[→] {nome}  ({subdominio}.gupy.io)")

        vagas = _buscar_vagas(subdominio, debug=debug)
        vagas_ia: list[dict] = []

        for vaga in vagas:
            titulo = vaga.get("title", "")
            departamento = vaga.get("department", "") or ""
            texto_completo = f"{titulo} {departamento}"
            termo = _contem_termo_ia(texto_completo)

            if termo:
                job_id = vaga.get("id")
                fonte_url = f"https://{subdominio}.gupy.io/job/{job_id}" if job_id else None
                vagas_ia.append({
                    "empresa_id": empresa_id,
                    "nome_empresa": nome,
                    "titulo_vaga": titulo,
                    "departamento": departamento,
                    "fonte_url": fonte_url,
                    "termo_encontrado": termo,
                    "encontrado": True,
                    "coletado_em": datetime.now(timezone.utc).isoformat(),
                })

        if vagas_ia:
            for item in vagas_ia:
                supabase.table("sinais_ia").insert({
                    "empresa_id": empresa_id,
                    "camada": "gupy_vagas",
                    "encontrado": True,
                    "evidencia": item["titulo_vaga"],
                    "fonte_url": item["fonte_url"],
                }).execute()
            print(f"    [✓] {len(vagas_ia)} vaga(s) com sinal de IA")
            todos_registros.extend(vagas_ia)
        else:
            supabase.table("sinais_ia").insert({
                "empresa_id": empresa_id,
                "camada": "gupy_vagas",
                "encontrado": False,
                "evidencia": None,
                "fonte_url": f"https://{subdominio}.gupy.io",
            }).execute()
            print(f"    [✗] {len(vagas)} vaga(s) no total, nenhuma com sinal de IA")
            todos_registros.append({
                "empresa_id": empresa_id,
                "nome_empresa": nome,
                "titulo_vaga": None,
                "departamento": None,
                "fonte_url": f"https://{subdominio}.gupy.io",
                "termo_encontrado": None,
                "encontrado": False,
                "coletado_em": datetime.now(timezone.utc).isoformat(),
            })

        time.sleep(1)

    if todos_registros:
        _SAIDA.mkdir(parents=True, exist_ok=True)
        caminho = _SAIDA / "gupy_vagas_ia.json"
        existentes: list[dict] = []
        if caminho.exists():
            existentes = json.loads(caminho.read_text(encoding="utf-8"))
        urls_existentes = {r.get("fonte_url") for r in existentes if r.get("fonte_url")}
        novos = [r for r in todos_registros if r.get("fonte_url") not in urls_existentes]
        caminho.write_text(
            json.dumps(existentes + novos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[json] {len(novos)} registro(s) salvo(s) em {caminho}")

    positivos = len({r["empresa_id"] for r in todos_registros if r["encontrado"]})
    print(f"\n[resumo] {positivos}/{len(empresas)} empresa(s) com vaga de IA no Gupy")


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv
    pesquisar(debug=debug)
