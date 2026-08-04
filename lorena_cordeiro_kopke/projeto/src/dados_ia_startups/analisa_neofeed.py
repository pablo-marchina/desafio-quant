from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SAIDA = _RAIZ / "data" / "jsons" / "neofeed"

_PALAVRAS_IA = re.compile(
    r'\b('
    r'IA|AI|intelig[eê]ncia artificial|artificial intelligence'
    r'|machine learning|deep learning|LLM|GPT|chatbot'
    r'|modelo preditivo|MLOps|data science|algoritmo'
    r'|automa[çc][ãa]o inteligente|rede neural|neural'
    r'|generativa|generativo|gen.?ai|copilot'
    r'|processamento de linguagem|NLP|computer vision'
    r'|reconhecimento de imagem|aprendizado de m[áa]quina'
    r')\b',
    re.IGNORECASE,
)


def _e_ia(titulo: str) -> bool:
    return bool(_PALAVRAS_IA.search(titulo))


def _carregar_mapa_empresas() -> dict[str, int]:
    rows = supabase.table("empresas").select("id, nome").execute().data
    return {r["nome"].strip().lower(): r["id"] for r in rows}


def _salvar_json(registros: list[dict]) -> None:
    _SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = _SAIDA / "neofeed.json"

    existentes: list[dict] = []
    if caminho.exists():
        existentes = json.loads(caminho.read_text(encoding="utf-8"))

    urls_existentes = {r["fonte_url"] for r in existentes if r.get("fonte_url")}
    novos = [r for r in registros if r.get("fonte_url") not in urls_existentes]

    caminho.write_text(
        json.dumps(existentes + novos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[json] {len(novos)} registro(s) novo(s) salvo(s) em {caminho}")


def _ja_checado(empresa_id: int) -> bool:
    resultado = (
        supabase.table("sinais_ia")
        .select("id")
        .eq("empresa_id", empresa_id)
        .eq("camada", "neofeed")
        .limit(1)
        .execute()
    )
    return len(resultado.data) > 0


def classificar(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    artigos: list[dict] = supabase.table("nomes_empresas").select("startup, titulo, url").execute().data
    if nome:
        artigos = [a for a in artigos if (a.get("startup") or "").strip().lower() == nome.strip().lower()]
    print(f"[info] {len(artigos)} artigo(s) carregado(s) do Supabase")

    mapa_empresas = _carregar_mapa_empresas()
    todos_registros: list[dict] = []

    for artigo in artigos:
        startup = artigo.get("startup") or ""
        empresa_id = mapa_empresas.get(startup.strip().lower())
        if not empresa_id:
            continue

        if atualizar_banco and _ja_checado(empresa_id):
            continue

        titulo = artigo.get("titulo") or ""
        url = artigo.get("url") or ""
        encontrado = _e_ia(titulo)

        if atualizar_banco:
            supabase.table("sinais_ia").insert({
                "empresa_id": empresa_id,
                "camada": "neofeed",
                "encontrado": encontrado,
                "evidencia": titulo if encontrado else None,
                "fonte_url": url or None,
            }).execute()

        todos_registros.append({
            "empresa_id": empresa_id,
            "nome_empresa": startup,
            "titulo": titulo,
            "fonte_url": url,
            "encontrado": encontrado,
            "coletado_em": datetime.now(timezone.utc).isoformat(),
        })

    if todos_registros:
        _salvar_json(todos_registros)

    positivos = sum(1 for r in todos_registros if r["encontrado"])
    print(f"[banco] {len(todos_registros)} registro(s) enviados ao Supabase — {positivos} com sinal de IA")
    print(f"[resumo] {positivos}/{len(artigos)} artigo(s) com sinal de IA no Neofeed")
    return [r for r in todos_registros if r["encontrado"]]


if __name__ == "__main__":
    classificar()
