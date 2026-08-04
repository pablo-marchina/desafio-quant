"""Ingere as documentações de tecnologias NVIDIA no Qdrant (Bloco 2).

Recria a coleção do zero e ingere as páginas oficiais de cada tecnologia.
É seguro rodar de novo: a coleção é zerada antes, evitando duplicatas.

Uso:
    uv run python scripts/ingest_nvidia.py
"""

from __future__ import annotations

import sys

from rag.ingestion import ingest_document, ingest_text
from rag.vector_store import COLLECTION_NAME, ensure_collection, get_client

# As 16 tecnologias NVIDIA (nome, URL oficial). URLs vindas do CLAUDE.md/TAP.
SOURCES = [
    # --- mínimo funcional original ---
    ("NVIDIA NIM", "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/"),
    ("NVIDIA NeMo", "https://www.nvidia.com/en-us/ai-data-science/products/nemo/"),
    ("NVIDIA Inception", "https://www.nvidia.com/en-us/startups/"),
    # --- demais tecnologias (P2: cobertura completa) ---
    ("NeMo Guardrails", "https://github.com/NVIDIA/NeMo-Guardrails"),
    ("NVIDIA Triton Inference Server", "https://developer.nvidia.com/triton-inference-server"),
    ("TensorRT-LLM", "https://github.com/NVIDIA/TensorRT-LLM"),
    ("NVIDIA RAPIDS", "https://rapids.ai/"),
    ("cuDF", "https://docs.rapids.ai/api/cudf/stable/"),
    ("cuML", "https://docs.rapids.ai/api/cuml/stable/"),
    ("CUDA", "https://developer.nvidia.com/cuda-toolkit"),
    ("NVIDIA Riva", "https://developer.nvidia.com/riva"),
    ("NVIDIA Omniverse", "https://www.nvidia.com/en-us/omniverse/"),
    ("NVIDIA Isaac", "https://developer.nvidia.com/isaac"),
    ("NVIDIA Clara", "https://www.nvidia.com/en-us/clara/"),
    ("NVIDIA Morpheus", "https://developer.nvidia.com/morpheus-cybersecurity"),
    ("NVIDIA AI Enterprise", "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/"),
]

# Descrições curadas de CASO DE USO (uma por tecnologia). O texto usa as mesmas
# palavras que a query monta a partir do perfil da startup ("indicada para startups
# que ..."), pra a tecnologia certa competir na busca por significado. A fonte é a
# própria URL oficial (rastreável). Baseadas na tabela do motor de recomendação
# (CLAUDE.md). Nome DEVE bater com o de SOURCES (a URL é buscada de lá).
USE_CASES = [
    ("NVIDIA Inception",
     "Programa da NVIDIA para startups: créditos de nuvem e GPU, suporte técnico, "
     "treinamento, descontos em hardware, conexão com investidores e apoio de "
     "go-to-market. Indicado para qualquer startup de IA, em estágio inicial ou de "
     "crescimento, que queira acelerar com o apoio da NVIDIA."),
    ("NVIDIA NIM",
     "Microserviços de inferência para colocar modelos de IA em produção rapidamente, "
     "com APIs prontas e otimizadas. Indicado para startups que consomem LLMs ou modelos "
     "via API e querem escalar, reduzir custo e latência, ou hospedar modelos próprios."),
    ("NVIDIA NeMo",
     "Plataforma para treinar, customizar (fine-tuning) e avaliar modelos generativos e "
     "LLMs com dados próprios. Indicado para startups que querem modelo próprio, "
     "fine-tuning, ou construir agentes e modelos de linguagem e de fala."),
    ("NeMo Guardrails",
     "Controle de comportamento e segurança de assistentes e agentes de IA (evitar "
     "respostas indevidas, manter no escopo, reduzir alucinação). Indicado para startups "
     "com chatbots, agentes conversacionais ou LLMs em atendimento que precisam de "
     "governança, confiabilidade e conformidade."),
    ("NVIDIA Triton Inference Server",
     "Serving de múltiplos modelos de IA em produção, com alto desempenho e uso eficiente "
     "de GPU. Indicado para startups que sofrem com latência de inferência, servem muitos "
     "modelos, ou precisam escalar inferência em tempo real."),
    ("TensorRT-LLM",
     "Otimização de inferência de LLMs: menor latência, maior throughput e menor custo por "
     "token. Indicado para startups que rodam LLMs em produção e sofrem com custo ou "
     "latência de inferência."),
    ("NVIDIA RAPIDS",
     "Aceleração de pipelines de dados e analytics em GPU (ETL, ciência de dados e machine "
     "learning sobre grandes volumes). Indicado para startups que processam grandes volumes "
     "de dados tabulares, telemetria, dados de sensores, logs ou big data."),
    ("cuDF",
     "Processamento de dataframes em GPU, como o pandas porém acelerado. Indicado para "
     "startups que manipulam grandes tabelas e dataframes, ETL e transformação de dados "
     "em escala."),
    ("cuML",
     "Machine learning clássico acelerado em GPU (regressão, clustering, árvores), como um "
     "scikit-learn acelerado. Indicado para startups que treinam modelos de ML sobre dados "
     "tabulares ou de sensores em grande volume."),
    ("CUDA",
     "Plataforma de programação paralela em GPU, base de toda a stack acelerada da NVIDIA. "
     "Indicado para startups que desenvolvem algoritmos próprios de alto desempenho ou "
     "precisam de computação intensiva em GPU."),
    ("NVIDIA Riva",
     "Reconhecimento de fala (ASR) e síntese de voz (TTS) em tempo real, com qualidade de "
     "produção. Indicado para startups que atuam com voz, call center, atendimento por "
     "telefone, transcrição de áudio, assistentes de voz ou cobrança por ligação."),
    ("NVIDIA Omniverse",
     "Simulação 3D, gêmeos digitais (digital twins) e colaboração em mundos virtuais. "
     "Indicado para startups de simulação, indústria, arquitetura, gêmeos digitais ou "
     "robótica que precisam de ambientes 3D."),
    ("NVIDIA Isaac",
     "Plataforma para robótica: simulação, percepção e autonomia de robôs. Indicado para "
     "startups de robótica, automação industrial, drones ou veículos autônomos."),
    ("NVIDIA Clara",
     "Plataforma de IA para saúde e ciências da vida: imagens médicas, genômica e "
     "dispositivos clínicos. Indicado para startups de saúde, healthtech, diagnóstico por "
     "imagem, telemedicina ou biotecnologia."),
    ("NVIDIA Morpheus",
     "Framework de cibersegurança com IA acelerada: detecção de ameaças, anomalias e "
     "fraudes em grandes volumes de dados de rede. Indicado para startups de cibersegurança, "
     "detecção de fraude ou análise de segurança."),
    ("NVIDIA AI Enterprise",
     "Plataforma empresarial para rodar IA em produção com suporte, segurança e escala. "
     "Indicado para startups que precisam levar IA a produção de forma robusta, com "
     "governança e suporte corporativo."),
]

def main() -> int:
    client = get_client()

    # Zera a coleção para um estado limpo (evita duplicatas ao re-rodar).
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    ensure_collection(client)

    total = 0
    fracas: list[tuple[str, str]] = []  # (tecnologia, motivo) das que não renderam
    for technology, url in SOURCES:
        print(f"Ingerindo {technology}...")
        try:
            n = ingest_document(client, technology, url)
        except Exception as e:  # noqa: BLE001 — uma URL ruim não pode abortar o lote
            print(f"  [ERRO] {type(e).__name__}: {e}")
            fracas.append((technology, "erro no fetch"))
            continue
        print(f"  {n} chunks inseridos")
        total += n
        if n == 0:
            fracas.append((technology, "0 chunks"))

    # Ingere as descrições curadas de caso de uso (1 chunk cada), citando a URL oficial.
    # É o que faz a tecnologia certa por setor competir com as páginas genéricas.
    url_by_tech = dict(SOURCES)
    print("\nIngerindo casos de uso (curadoria interna, citando a pagina oficial)...")
    for technology, texto in USE_CASES:
        src = url_by_tech.get(technology, "curadoria interna")
        n = ingest_text(client, technology, texto, source_url=src)
        total += n
        print(f"  {technology}: +{n} chunk(s) de caso de uso")

    print(f"\n[OK] Ingestao concluida: {total} chunks de {len(SOURCES)} tecnologias.")
    if fracas:
        print("\n[ATENCAO] Tecnologias sem conteudo aproveitavel (revisar a fonte):")
        for tech, motivo in fracas:
            print(f"  - {tech} ({motivo})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
