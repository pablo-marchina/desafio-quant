# NVIDIA Knowledge V2 - Fundacao `source_type`

Esta entrega prepara o backend para ingerir documentacao NVIDIA real sem
misturar esse corpus com evidencias coletadas de startups.

## Decisao

O escopo de recuperacao sera feito por `source_type`, nao por colecao Qdrant
separada.

Valores atuais:

```txt
startup_evidence
nvidia_knowledge
```

`startup_evidence` e o default para preservar o comportamento existente.

## Implementado

- `DocumentSourceType` no dominio de ingestion;
- `documents.source_type` com indice e default `startup_evidence`;
- `ingestion_jobs.source_type` com indice e default `startup_evidence`;
- migrations `1d3e7f9a2b4c` e `2a7c9b8d1e5f`;
- `IngestedDocumentSummary` e `ChunkRecord` propagando `source_type`;
- DTOs de embeddings carregando `source_type`;
- payload `source_type` no Qdrant;
- filtro opcional `source_type` em `VectorRepository.search`;
- filtro opcional `source_type` na busca lexical via `documents.source_type`;
- `SearchEvidenceInput` e `AnswerQuestionInput` aceitando `source_type`;
- requests/responses de `/rag/search` e `/rag/answer` expondo o campo.
- registry de fontes NVIDIA em `/nvidia-knowledge/sources`.

## Proximo Passo

Executar ingestao das fontes registradas:

```txt
fonte oficial -> scraping -> ingestion(source_type=nvidia_knowledge)
-> embeddings -> RAG filtrado por source_type=nvidia_knowledge
```

Isso fecha a base para o futuro Agents V10, o NVIDIA RAG Agent.
