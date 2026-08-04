# Roadmap do Modulo NVIDIA Knowledge

O modulo `nvidia_knowledge` organiza conhecimento sobre tecnologias NVIDIA para
que o sistema consiga recomendar produtos, frameworks e caminhos tecnicos com
base em fontes confiaveis.

---

## Objetivo do Modulo

```txt
documentacao NVIDIA -> documents/chunks -> embeddings -> base consultavel
```

Esse modulo pode reutilizar ingestion, embeddings e RAG, mas com regras e
metadados especificos para conhecimento tecnico NVIDIA.

---

## Versoes Planejadas

| Versao | Status | Objetivo |
|---|---|---|
| NVIDIA Knowledge V1 | Implementado | Catalogo inicial de tecnologias |
| NVIDIA Knowledge V2 | Entregue (20/20 fontes processadas, 17/20 com conteudo) | Ingestao de fontes oficiais |
| NVIDIA Knowledge V3 | Futuro | Metadados tecnicos |
| NVIDIA Knowledge V4 | Futuro | Busca por caso de uso |

---

## NVIDIA Knowledge V1 - Catalogo Inicial

Status:

```txt
implementado
```

Entregaveis:

- entidade `NvidiaTechnology`;
- catalogo inicial de tecnologias;
- categoria, descricao e casos de uso;
- fonte oficial associada;
- contrato publico `NvidiaTechnologyCatalog`;
- rotas `GET /nvidia-knowledge/technologies` e
  `GET /nvidia-knowledge/technologies/{slug}`;
- filtros por categoria e busca textual simples.

Exemplos:

```txt
NVIDIA NIM
NVIDIA NeMo
NVIDIA Triton Inference Server
TensorRT-LLM
RAPIDS
Riva
CUDA
NVIDIA AI Enterprise
MONAI
```

Documento da entrega: `docs/nvidia_knowledge/nvidia_knowledge_v1_catalogo_inicial.md`.

---

## Extensao do catalogo V1 (entregue; nao e uma nova versao)

Status:

```txt
entregue
```

O brief original do case (secao 5.4) lista 16 tecnologias/programas; o
catalogo V1 cobria 10. Foram adicionadas as 8 que faltavam (ver
`docs/diagnostico_case_original_e_novas_prioridades.md`, secao 5):

```txt
NVIDIA Inception     <- prioridade maxima: e o PROGRAMA que o projeto
                         existe para alimentar (atrair/qualificar/nutrir
                         startups para o Inception). Categoria nova:
                         STARTUP_PROGRAM.
NeMo Guardrails       (categoria MODEL_TRAINING, junto com NeMo)
NVIDIA Clara          (categoria HEALTHCARE_AI, junto com MONAI)
cuDF                  (categoria DATA_SCIENCE, junto com RAPIDS)
cuML                  (categoria DATA_SCIENCE, junto com RAPIDS)
NVIDIA Omniverse      (categoria nova: ROBOTICS_SIMULATION)
NVIDIA Isaac          (categoria nova: ROBOTICS_SIMULATION)
NVIDIA Morpheus       (categoria nova: CYBERSECURITY)
```

Extensao de dados em `catalog_data.py` (`INITIAL_NVIDIA_TECHNOLOGIES`),
mesmo formato das 10 entradas que ja existiam, mais 3 valores novos em
`NvidiaTechnologyCategory` (`STARTUP_PROGRAM`, `ROBOTICS_SIMULATION`,
`CYBERSECURITY`) — sem mudanca de arquitetura nem migration (o catalogo e
estatico em codigo, nao tabela). Por isso fica registrado aqui como
extensao da V1, nao como V2 (que e sobre ingestao de documentacao real
via pipeline, um escopo bem maior — ver abaixo).

Testes novos: `test_catalog_includes_nvidia_inception_program`,
`test_catalog_includes_all_brief_items_added_this_round` (+2, total do
modulo: 7 unit).

---

## NVIDIA Knowledge V2 - Fontes Oficiais

Status:

```txt
fundacao source_type entregue
source registry entregue
submissao do registry para Orchestration V2 entregue
worker automatico de advance entregue (workers/orchestration_worker/)
primeira validacao real ponta a ponta entregue (2/8 fontes P0; ver
  docs/nvidia_knowledge/nvidia_knowledge_v2_primeira_validacao_real.md)
P0+P1+P2 completo: 20/20 fontes processadas, 17/20 com conteudo disponivel
  (ver CLAUDE.md, secao "Recent validation")
```

**Atualizacao 23/06/2026:** o "restante do lote P0 + P1/P2" que esta secao
listava como pendente ja foi concluido (`CLAUDE.md` confirma 20/20 fontes
processadas). Restam 3 gaps sem fix de codigo possivel agora:
`nvidia-nim-docs` e `monai-docs` (DNS intermitente do lado Windows, fora do
alcance de uma correcao de codigo), `rapids-docs` (esgotou BS4/Trafilatura/
Playwright — precisaria de Firecrawl real, ver secao de tecnologias
candidatas abaixo).

Fundacao entregue:

- `documents.source_type` com default `startup_evidence`;
- `ingestion_jobs.source_type` para o worker criar documentos NVIDIA sem
  perder contexto apos o enfileiramento;
- enum `DocumentSourceType` com `startup_evidence` e `nvidia_knowledge`;
- propagacao ingestion reader -> embeddings -> payload Qdrant;
- filtro opcional `source_type` em busca vetorial, busca lexical,
  `/rag/search` e `/rag/answer`;
- migrations `1d3e7f9a2b4c` e `2a7c9b8d1e5f`.

Registry de fontes entregue:

- entidade `NvidiaKnowledgeSource`;
- enums `NvidiaKnowledgeSourcePriority` e `NvidiaKnowledgeSourceType`;
- reposititorio estatico `StaticNvidiaKnowledgeSourceRepository`;
- contrato publico `NvidiaKnowledgeSourceRegistry`;
- caso de uso `ListNvidiaKnowledgeSources`;
- rota `GET /nvidia-knowledge/sources`;
- rota `POST /nvidia-knowledge/ingestion/jobs`;
- filtros por prioridade, tecnologia e busca textual;
- submissao em lote filtravel das fontes oficiais para `url_ingestion_jobs`;
- cobertura dos slugs atuais do catalogo NVIDIA;
- fontes P0/P1/P2 para Inception, NIM, NeMo, Guardrails, Triton,
  TensorRT/TensorRT-LLM, AI Enterprise, RAPIDS/cuDF/cuML, Riva, Isaac,
  Omniverse, Clara/MONAI, Morpheus, CUDA e contexto AI-native do case.

Entregaveis:

- pipeline para documentos NVIDIA;
- registro de URL oficial - entregue como source registry;
- submit inicial para Orchestration V2 - entregue via
  `POST /nvidia-knowledge/ingestion/jobs`;
- versionamento de documento;
- chunking de documentacao tecnica.

Proximo passo:

```txt
validar as seis fontes P0 restantes com workers limpos e executar P1/P2;
registrar taxa de sucesso, erros por dominio, custo e qualidade de recuperacao.
```

---

## NVIDIA Knowledge V3 - Metadados Tecnicos

Entregaveis:

- mapear tecnologia para caso de uso;
- maturidade da solucao;
- dependencia de hardware/software;
- perfil de startup recomendado.

---

## NVIDIA Knowledge V4 - Busca por Caso de Uso

Entregaveis:

- perguntar em linguagem natural;
- recuperar tecnologias NVIDIA relevantes;
- explicar fonte e motivo da recuperacao.

---

## Tecnologias candidatas (auditoria de codigo, 23/06/2026)

| Fraqueza confirmada | Tecnologia/abordagem | Serve a | Esforco |
|---|---|---|---|
| `rapids-docs` esgotou BS4/Trafilatura/Playwright (gap conhecido, sem fix de codigo possivel com as estrategias atuais) | implementar o client real do Firecrawl em `scraping` (hoje so comentado, ver roadmap do modulo `scraping`) como ultimo fallback pago | Fecha o ultimo gap corrigivel por codigo do V2 | Medio — depende da entrega de Firecrawl em `scraping`, nao e' trabalho deste modulo |
| Catalogo (`catalog_data.py`) e registry (`source_data.py`) sao 100% estaticos em codigo, sem checagem se a URL oficial ainda existe | script periodico simples de health-check (HTTP HEAD/GET) nas URLs do `NvidiaKnowledgeSourceRegistry`, logando (via `shared/logging`, ja existente) fontes que pararam de responder | Pre-requisito de qualidade para V3 (metadados tecnicos) — nao adianta mapear metadados de uma fonte que ja saiu do ar | Baixo — script simples, sem lib nova |
| V3 (metadados tecnicos) ainda nao tem nenhum mecanismo de extracao definido | reusar o Extraction Agent (`agents` V8) — ja extrai dados estruturados de evidencias via Gemini com schema Pydantic — em vez de escrever um parser novo so para documentacao NVIDIA | NVIDIA Knowledge V3 | Medio — e' reuso de contrato publico ja existente, nao tech nova |

Nao subir um scheduler dedicado (Airflow/Celery beat) so para o health-check
periodico: o projeto ja tem Dramatiq+Redis para tudo que precisa rodar
assincrono; um script simples disparado por cron do sistema operacional (ou
um actor Dramatiq com `cron`-like delay) resolve sem infra nova.
