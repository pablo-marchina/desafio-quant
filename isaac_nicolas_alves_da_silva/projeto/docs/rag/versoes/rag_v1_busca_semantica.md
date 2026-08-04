# RAG V1 - Busca Semantica Simples

Esta versao cria o modulo `rag` e entrega a primeira recuperacao de evidencias
citaveis sobre chunks ja vetorizados.

## 1. Objetivo

```txt
pergunta -> embedding da pergunta -> Qdrant -> chunks com texto e fonte
```

## 2. Componentes

```txt
apps/api/src/modules/rag
  domain/exceptions.py
  application/dto.py
  application/public/retriever.py
  application/use_cases/search_evidence.py
  factories/rag_factory.py
  presentation/routes.py
  presentation/schemas.py
```

Contrato publico:

```txt
Retriever.search(SearchEvidenceInput) -> SearchEvidenceView
```

## 3. Fluxo

```txt
POST /rag/search {"query": "...", "limit": 5}
  -> SearchEvidence
  -> GenerateChunkEmbedding gera vetor da pergunta
  -> VectorRepository.search busca chunks no Qdrant
  -> IngestedDocumentReader recupera texto dos chunks no PostgreSQL
  -> API retorna chunk_id, document_id, source_url, text e score
```

## 4. API

```txt
POST /rag/search
```

Saida:

```json
{
  "query": "Como a startup usa IA?",
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "source_url": "https://startup.example.com",
      "text": "Trecho recuperado...",
      "score": 0.87
    }
  ]
}
```

## 5. Limites da V1

```txt
sem LLM de resposta
sem busca hibrida
sem reranking
sem persistencia de consultas
sem filtros por startup
```

## 6. Validacao

```txt
test_search_evidence.py
292 testes unitarios passando na suite unitaria completa
```

## 7. Proximo Passo

```txt
RAG V2 - implementado em docs/rag/rag_v2_resposta_com_citacoes.md
```
