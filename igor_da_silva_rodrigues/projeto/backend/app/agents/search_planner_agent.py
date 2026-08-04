from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


MATURITY_CLASSES = ("API-consumer", "AI-enabled", "AI-native", "Non-AI")

AI_TERMS = (
    "inteligência artificial",
    "machine learning",
    "deep learning",
    "IA",
    "LLM",
    "GPT",
    "modelo",
    "algoritmo",
    "automação inteligente",
)

VERTICAL_TERMS = {
    "financeiro": [
        "credit scoring",
        "análise preditiva",
        "modelo de risco",
        "algoritmo de crédito",
    ],
    "fintech": [
        "credit scoring",
        "análise preditiva",
        "modelo de risco",
        "algoritmo de crédito",
    ],
    "saúde": [
        "diagnóstico assistido",
        "análise de imagens médicas",
        "predição de risco",
        "triagem clínica",
    ],
    "healthtech": [
        "diagnóstico assistido",
        "análise de imagens médicas",
        "predição de risco",
        "triagem clínica",
    ],
    "educação": [
        "aprendizagem personalizada",
        "tutoria inteligente",
        "recomendação de conteúdo",
        "adaptive learning",
    ],
    "recursos humanos": [
        "people analytics",
        "matching de talentos",
        "recrutamento preditivo",
        "análise de performance",
    ],
    "hrtech": [
        "people analytics",
        "matching de talentos",
        "recrutamento preditivo",
        "análise de performance",
    ],
    "produtividade": [
        "automação de processos",
        "workflow inteligente",
        "RPA",
        "agentes de IA",
    ],
    "energia": [
        "previsão de demanda",
        "otimização energética",
        "smart grid",
        "manutenção preditiva",
    ],
    "agricultura e pecuária": [
        "agricultura de precisão",
        "previsão de safra",
        "visão computacional",
        "cadeia de suprimentos",
    ],
    "cibersegurança": [
        "detecção de anomalias",
        "threat intelligence",
        "segurança preditiva",
        "resposta automatizada",
    ],
    "biotecnologia": [
        "bioinformática",
        "descoberta de fármacos",
        "modelos biológicos",
        "análise genômica",
    ],
}


def planejar_busca_ia_startup(
    startup: dict[str, Any],
    contexto: str | None = None,
) -> dict[str, Any]:
    nome = _clean(startup.get("nome"))
    categoria = _clean(startup.get("categoria"))
    descricao = _clean(startup.get("descricao_curta"))
    site = _clean(startup.get("site_oficial") or startup.get("site"))
    plano_consultas = _gerar_plano_consultas(nome, categoria, site)

    return {
        "startup": nome,
        "site_oficial": site or None,
        "hipotese_maturidade": _gerar_hipotese_maturidade(categoria, descricao, contexto),
        "plano_consultas": plano_consultas,
        "tarefas": _gerar_tarefas_site_oficial(site) + _gerar_tarefas_scraper(plano_consultas),
        "fontes_prioritarias": _gerar_fontes_prioritarias(nome, site),
        "observacoes": _gerar_observacoes(categoria, descricao, site),
    }


def planejar_busca_ia_arquivo_curated(
    input_path: Path,
    startup_id_or_name: str,
) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    startups = payload.get("startups", [])
    selected = _selecionar_startup(startups, startup_id_or_name)
    if not selected:
        raise ValueError(f"Startup não encontrada: {startup_id_or_name}")
    return planejar_busca_ia_startup(selected)


def _gerar_hipotese_maturidade(
    categoria: str,
    descricao: str,
    contexto: str | None,
) -> str:
    lower_description = descricao.lower()
    category_hint = f"Na categoria {categoria}, " if categoria else "Pelo perfil disponível, "

    if any(term.lower() in lower_description for term in ("llm", "modelo", "machine learning", "ia", "inteligência artificial")):
        return (
            f"Hipótese inicial: AI-enabled. {category_hint}a descrição já contém sinais de IA, mas ainda é preciso confirmar se a startup usa modelos próprios, APIs externas ou infraestrutura otimizada."
        )

    if any(term.lower() in lower_description for term in ("automação", "dados", "algoritmo", "predição", "analytics")):
        return (
            f"Hipótese inicial: API-consumer ou AI-enabled. {category_hint}há sinais indiretos de automação ou dados, então o plano deve buscar evidências de stack, modelos e maturidade operacional."
        )

    extra = f" Contexto adicional considerado: {contexto}" if contexto else ""
    return (
        "Hipótese inicial: Non-AI ou API-consumer. Os dados fornecidos ainda não comprovam uso real de IA; a investigação deve procurar evidências explícitas antes de qualquer classificação positiva."
        + extra
    )


def _gerar_plano_consultas(nome: str, categoria: str, site: str) -> list[dict[str, Any]]:
    dominio = _dominio(site)
    termos_vertical = _termos_vertical(categoria)

    consultas: list[dict[str, Any]] = []
    consultas.extend(_camada_1(nome))
    consultas.extend(_camada_2(nome, termos_vertical))
    consultas.extend(_camada_3(nome))
    consultas.extend(_camada_4(nome))
    consultas.extend(_camada_5(nome))
    consultas.extend(_camada_6(nome, dominio))
    consultas.extend(_camada_7(nome))

    return _dedupe_consultas(consultas)


def _gerar_tarefas_scraper(plano_consultas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tarefas = []
    for index, item in enumerate(plano_consultas, start=1):
        camada = item["camada"]
        tarefas.append(
            {
                "id": f"task_camada_{camada}_{index}",
                "tipo": "busca_site" if item["consulta"].startswith("site:") else "busca_web",
                "consulta": item["consulta"],
                "motor": "searxng",
                "max_resultados": 8 if camada in (3, 4) else 5,
                "camada": camada,
                "objetivo": item["objetivo"],
            }
        )
    return tarefas


def _gerar_tarefas_site_oficial(site: str) -> list[dict[str, Any]]:
    if not site:
        return []
    return [
        {
            "id": "task_site_oficial_1",
            "tipo": "acesso_direto",
            "url": site,
            "extrator": "firecrawl",
            "max_profundidade": 2,
            "max_paginas_relacionadas": 6,
            "camada": 6,
            "objetivo": "Coletar conteúdo do site oficial e páginas internas relevantes para evidências de produto, tecnologia, cases, segurança e carreiras.",
        }
    ]


def _camada_1(nome: str) -> list[dict[str, Any]]:
    return [
        _consulta(f'"{nome}" "inteligência artificial"', "Detectar menções explícitas a IA em materiais públicos.", 1),
        _consulta(f'"{nome}" "machine learning"', "Detectar menções explícitas a machine learning.", 1),
        _consulta(
            f'"{nome}" ("deep learning" OR "redes neurais" OR "transformers")',
            "Encontrar sinais de técnicas avançadas de IA.",
            1,
        ),
    ]


def _camada_2(nome: str, termos_vertical: list[str]) -> list[dict[str, Any]]:
    selected_terms = termos_vertical[:4] or [
        "análise preditiva",
        "recomendação",
        "automação inteligente",
        "modelo de decisão",
    ]
    return [
        _consulta(
            f'"{nome}" "{term}"',
            "Investigar sinal indireto de IA aplicado ao problema de negócio da startup.",
            2,
        )
        for term in selected_terms[:3]
    ]


def _camada_3(nome: str) -> list[dict[str, Any]]:
    return [
        _consulta(
            f'"{nome}" ("API OpenAI" OR "ChatGPT" OR "Gemini" OR "Azure AI" OR "AWS AI")',
            "Detectar dependência de APIs externas de IA, sinal típico de API-consumer.",
            3,
        ),
        _consulta(
            f'"{nome}" ("modelo próprio" OR "modelo proprietário" OR "treinamos nosso")',
            "Identificar desenvolvimento de modelos próprios, sinal de AI-enabled ou AI-native.",
            3,
        ),
        _consulta(
            f'"{nome}" ("GPU" OR "NVIDIA" OR "CUDA" OR "TensorRT")',
            "Buscar evidência de uso direto de infraestrutura acelerada ou stack NVIDIA.",
            3,
        ),
        _consulta(
            f'"{nome}" ("PyTorch" OR "TensorFlow" OR "JAX" OR "ONNX")',
            "Detectar frameworks de desenvolvimento de modelos.",
            3,
        ),
        _consulta(
            f'"{nome}" ("fine-tuning" OR "fine tuning" OR "transfer learning")',
            "Identificar adaptação de modelos existentes para casos próprios.",
            3,
        ),
        _consulta(
            f'"{nome}" ("Triton" OR "RAPIDS" OR "NeMo" OR "TensorRT-LLM")',
            "Buscar sinais de adoção de componentes da stack NVIDIA para produção de IA.",
            3,
        ),
    ]


def _camada_4(nome: str) -> list[dict[str, Any]]:
    return [
        _consulta(
            f'"{nome}" ("custo" OR "custo computacional" OR "custo de inferência") ("IA" OR "modelo")',
            "Detectar dor de custo computacional que pode ser resolvida com otimização NVIDIA.",
            4,
        ),
        _consulta(
            f'"{nome}" ("latência" OR "tempo real") ("machine learning" OR "deep learning")',
            "Identificar requisitos de baixa latência e inferência em tempo real.",
            4,
        ),
        _consulta(
            f'"{nome}" ("escalabilidade" OR "escalar") ("IA" OR "modelo")',
            "Buscar sinais de dificuldade para escalar sistemas de IA.",
            4,
        ),
        _consulta(
            f'"{nome}" ("privacidade de dados" OR "LGPD") ("machine learning" OR "IA")',
            "Detectar exigências de privacidade, governança e proteção de dados.",
            4,
        ),
        _consulta(
            f'"{nome}" ("governança de IA" OR "explicabilidade" OR "auditoria")',
            "Encontrar sinais de necessidade de governança, explicabilidade e auditoria.",
            4,
        ),
        _consulta(
            f'"{nome}" ("avaliação de modelo" OR "monitoramento de modelo" OR "MLOps")',
            "Verificar maturidade operacional em avaliação, monitoramento e MLOps.",
            4,
        ),
        _consulta(
            f'"{nome}" ("dependência de fornecedor" OR "vendor lock-in")',
            "Detectar risco de dependência de fornecedor de IA, oportunidade para arquitetura mais controlada.",
            4,
        ),
        _consulta(
            f'"{nome}" ("GPU" OR "aceleração" OR "inferência otimizada") ("custo" OR "escala")',
            "Buscar necessidade de aceleração computacional para reduzir custo ou aumentar escala.",
            4,
        ),
    ]


def _camada_5(nome: str) -> list[dict[str, Any]]:
    return [
        _consulta(
            f'"{nome}" ("data scientist" OR "machine learning engineer" OR "MLOps engineer")',
            "Encontrar sinais organizacionais de equipe técnica especializada em IA.",
            5,
        ),
        _consulta(
            f'"{nome}" (vaga OR contratação) ("machine learning" OR "deep learning")',
            "Investigar vagas que revelem stack, senioridade e uso real de IA.",
            5,
        ),
    ]


def _camada_6(nome: str, dominio: str | None) -> list[dict[str, Any]]:
    consultas = [
        _consulta(
            f'"{nome}" site:github.com',
            "Encontrar repositórios, SDKs ou projetos públicos relacionados à startup.",
            6,
        ),
        _consulta(
            f'"{nome}" (whitepaper OR paper OR "technical report") ("deep learning" OR "machine learning")',
            "Buscar conteúdo técnico em inglês sobre modelos, arquitetura ou pesquisa.",
            6,
        ),
    ]
    if dominio:
        consultas.extend(
            [
                _consulta(
                    f'site:{dominio} ("machine learning" OR "deep learning" OR "modelo")',
                    "Investigar conteúdo técnico no próprio domínio da startup.",
                    6,
                ),
                _consulta(
                    f'site:{dominio} blog ("GPU" OR "inference" OR "training")',
                    "Buscar posts técnicos em inglês sobre treinamento, inferência ou GPU.",
                    6,
                ),
            ]
        )
    return consultas


def _camada_7(nome: str) -> list[dict[str, Any]]:
    return [
        _consulta(f'"{nome}" site:neofeed.com.br', "Verificar menções em portal brasileiro de negócios e tecnologia.", 7),
        _consulta(f'"{nome}" site:braziljournal.com', "Verificar cobertura de mercado, rodadas e estratégia.", 7),
    ]


def _gerar_fontes_prioritarias(nome: str, site: str) -> list[dict[str, str]]:
    dominio = _dominio(site)
    fontes = []
    if dominio:
        fontes.append(
            {
                "fonte": "Site oficial",
                "razao": "Fonte primária para validar produto, tecnologia, blog, documentação e páginas de carreira.",
                "instrucao": f"Testar sitemap/RSS e buscar em site:{dominio} por IA, machine learning, modelo, GPU, inferência, blog e carreiras.",
            }
        )

    fontes.extend(
        [
            {
                "fonte": "LinkedIn",
                "razao": "Perfis, posts e vagas revelam stack, senioridade técnica e existência de times de dados ou IA.",
                "instrucao": f"Buscar '{nome}' AND ('data scientist' OR 'ML engineer' OR 'MLOps' OR 'GPU') em páginas públicas e snippets.",
            },
            {
                "fonte": "GitHub",
                "razao": "Repositórios públicos podem revelar frameworks, SDKs, integrações e maturidade técnica.",
                "instrucao": f"Buscar '{nome}' e domínio oficial em github.com e na API pública de busca de repositórios.",
            },
            {
                "fonte": "Portais brasileiros de startups",
                "razao": "NeoFeed, Brazil Journal, Distrito, Exame e Startups.com.br ajudam a validar evidências com fontes externas.",
                "instrucao": f"Executar consultas site: para portais brasileiros e coletar menções a IA, produto, tecnologia, rodada e escala.",
            },
        ]
    )
    return fontes


def _gerar_observacoes(categoria: str, descricao: str, site: str) -> str:
    termos = _termos_vertical(categoria)
    observacoes = [
        "O Scraper Agent deve coletar apenas evidências públicas e registrar URL, título, trecho, data de coleta e camada da consulta.",
        "A classificação final não deve ser inferida só por linguagem comercial; exigir evidência técnica, organizacional ou de produto.",
        "Camadas 3 e 4 têm maior peso porque indicam maturidade técnica e dores que a stack NVIDIA pode resolver.",
    ]
    if site:
        observacoes.append("No site oficial, priorizar sitemap, blog, produto, tecnologia, documentação e carreiras.")
    if termos:
        observacoes.append("Termos verticais usados no plano: " + ", ".join(termos[:4]) + ".")
    if not any(term.lower() in descricao.lower() for term in AI_TERMS):
        observacoes.append("A descrição curta não confirma IA; tratar qualquer classificação positiva como hipótese até validação.")
    return " ".join(observacoes)


def _consulta(consulta: str, objetivo: str, camada: int) -> dict[str, Any]:
    return {"consulta": consulta, "objetivo": objetivo, "camada": camada}


def _termos_vertical(categoria: str) -> list[str]:
    categoria_key = categoria.lower()
    for key, terms in VERTICAL_TERMS.items():
        if key in categoria_key:
            return terms
    return []


def _dominio(site: str) -> str | None:
    if not site:
        return None
    parsed = urlparse(site if "://" in site else f"https://{site}")
    return parsed.netloc.replace("www.", "") if parsed.netloc else None


def _selecionar_startup(
    startups: list[dict[str, Any]],
    startup_id_or_name: str,
) -> dict[str, Any] | None:
    needle = startup_id_or_name.lower()
    for startup in startups:
        if startup.get("startup_id", "").lower() == needle:
            return startup
        if startup.get("nome", "").lower() == needle:
            return startup
    return None


def _dedupe_consultas(consultas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for item in consultas:
        key = item["consulta"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()
