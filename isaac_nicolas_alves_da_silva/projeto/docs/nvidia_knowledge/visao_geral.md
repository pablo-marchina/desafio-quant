# Módulo NVIDIA Knowledge — Visão Geral

## 1. Importância

O `nvidia_knowledge` é a fonte do "lado NVIDIA" da equação. Mantém o catálogo de
tecnologias/programas NVIDIA (NIM, Triton, TensorRT-LLM, RAPIDS, Riva, MONAI,
Clara, NVIDIA Inception, etc.) e um registry de fontes oficiais que são ingeridas
para o RAG. É contra esse catálogo que o motor de recomendações cruza o perfil da
startup, e é desse conteúdo ingerido que vêm as citações reais.

## 2. Fluxo

```txt
catálogo estático de tecnologias (em código, sem migration)
registry de fontes oficiais (20 fontes: docs NIM/Triton/NeMo/RAPIDS/...)
POST /nvidia-knowledge/ingestion/jobs
  -> cria url_ingestion_jobs com source_type=nvidia_knowledge
  -> scraping -> ingestion -> embeddings (NÃO entra em ANALYZING)
  -> conteúdo recuperável via /rag/search?source_type=nvidia_knowledge
GET /nvidia-knowledge/technologies, /technologies/{slug}, /sources
```

## 3. Estrutura de pastas

```txt
nvidia_knowledge/
  presentation/     GET technologies/sources, POST ingestion/jobs
  application/      use_cases; public/NvidiaTechnologyCatalog
  domain/           NvidiaTechnology (com supported_workloads/complexity), enums, registry
  infrastructure/   static_catalog/ (catalog_data.py), scraping_adapters/
  factories/
  tests/
```

## 4. Stack

```txt
catálogo estático em código    18 tecnologias/programas
(reuso) scraping/ingestion/embeddings   para ingerir as fontes oficiais
```

## 5. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Catálogo inicial de tecnologias (expandido para 18, inclui NVIDIA Inception) |
| V2 | Entregue | Ingestão de fontes oficiais (pipeline real): 20/20 processadas, 17/20 com conteúdo |

**Versão atual: V1 + V2.** 3 gaps sem fix de código possível agora (DNS
intermitente Windows-side em 2 fontes; rapids-docs exigiria Firecrawl). Detalhes
em `versoes/`; futuro (V3 metadados técnicos, V4 busca por caso de uso) em
`roadmap.md`.
