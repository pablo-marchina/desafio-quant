# NVIDIA Knowledge V2 - Source Registry

Esta entrega registra as fontes que devem popular a base RAG NVIDIA.

## Objetivo

```txt
fontes oficiais/estrategicas -> registry -> url_ingestion_jobs NVIDIA Knowledge
```

O registry define quais URLs devem ser ingeridas, com prioridade, tipo de
fonte, tecnologia associada e tags. A camada executavel ja consegue submeter
essas URLs para Orchestration V2.

## Entregue

- entidade `NvidiaKnowledgeSource`;
- enums `NvidiaKnowledgeSourcePriority` (`p0`, `p1`, `p2`) e
  `NvidiaKnowledgeSourceType`;
- reposititorio estatico `StaticNvidiaKnowledgeSourceRepository`;
- contrato publico `NvidiaKnowledgeSourceRegistry`;
- caso de uso `ListNvidiaKnowledgeSources`;
- rota `GET /nvidia-knowledge/sources`;
- rota `POST /nvidia-knowledge/ingestion/jobs`;
- filtros por `priority`, `technology_slug` e `query`;
- DTO exposto com `document_source_type="nvidia_knowledge"`;
- caso de uso `SubmitNvidiaKnowledgeSources`;
- porta `NvidiaKnowledgeUrlIngestionSubmitter`;
- adaptador para `CreateUrlIngestionJob` de Orchestration V2;
- suporte a `limit` para executar lotes pequenos de fontes;
- testes garantindo cobertura dos slugs do catalogo.

## Fontes P0

```txt
NVIDIA Inception
NVIDIA NIM
NVIDIA NeMo
NeMo Guardrails
NVIDIA Triton Inference Server
TensorRT
TensorRT-LLM
NVIDIA AI Enterprise
```

## Fontes P1

```txt
RAPIDS
cuDF
cuML
NVIDIA Riva
NVIDIA Isaac
NVIDIA Omniverse
NVIDIA Clara
MONAI
NVIDIA Morpheus
```

## Fontes P2

```txt
CUDA Toolkit
Sequoia - AI Services
Emergence Capital - AI-Native Services Playbook
```

As fontes P2 de Sequoia e Emergence nao sao NVIDIA, mas fazem parte do
contexto estrategico do case para diferenciar AI-native services de wrappers
simples de LLM.

## Endpoint de Submissao

```txt
POST /nvidia-knowledge/ingestion/jobs
```

Body opcional:

```json
{
  "priority": "p0",
  "technology_slug": "nvidia-nim",
  "query": "inference",
  "limit": 2
}
```

Resposta:

```json
{
  "total": 2,
  "submitted": [
    {
      "source_slug": "nvidia-nim-docs",
      "title": "NVIDIA NIM Documentation",
      "url": "https://docs.nvidia.com/nim/",
      "priority": "p0",
      "technology_slug": "nvidia-nim",
      "url_ingestion_job_id": "..."
    }
  ]
}
```

Esta entrega cria jobs rastreaveis em `url_ingestion_jobs`. O avanco agora e'
automatico via `workers/orchestration_worker/` (fila `url_ingestion`), ver
`docs/orchestration/orchestration_v2_worker_automatico.md`; `POST
/url-ingestion/jobs/{job_id}/advance` continua disponivel so para destravar
manualmente um job que esgotou os retries automaticos.

## Proximo Passo

Rodar o executor de ingestao NVIDIA contra as fontes reais:

```txt
NvidiaKnowledgeSourceRegistry
-> url_ingestion_job (entregue)
-> advance automatico via worker (entregue)
-> ingestion com source_type=nvidia_knowledge
-> embedding job
-> RAG filtrado (validar fim a fim com fontes reais)
```

Pre-requisito entregue apos este registry: `ingestion_jobs.source_type`, para
que o job enfileirado preserve o tipo da fonte ate o `ingestion_worker`.
