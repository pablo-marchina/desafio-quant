# RAG V2 - Resposta com Citacoes

Esta versao completa o primeiro ciclo RAG: alem de recuperar evidencias, o
modulo agora gera uma resposta curta e fundamentada com citacoes estruturadas.

## 1. Objetivo

```txt
pergunta -> RAG V1 recupera chunks -> Gemini responde -> citacoes por chunk
```

## 2. Componentes

```txt
apps/api/src/modules/rag
  application/public/answer_generator.py
  application/use_cases/answer_question.py
  infrastructure/llm/langchain_gemini_answer_generator.py
  presentation/routes.py
  presentation/schemas.py
```

Contratos publicos:

```txt
Retriever.search(SearchEvidenceInput) -> SearchEvidenceView
RagAnswerGenerator.generate(GenerateRagAnswerInput) -> RagAnswerView
```

## 3. Decisao Arquitetural

O adapter Gemini desta entrega fica em:

```txt
apps/api/src/modules/rag/infrastructure/llm
```

Ele nao fica em `agents`, porque a responsabilidade aqui nao e orquestrar um
grafo agentico. A responsabilidade e transformar evidencias recuperadas pelo
RAG em resposta citavel. Agents pode chamar RAG depois por contrato publico,
mas nao deve ser dono do provider de resposta do RAG.

## 4. Fluxo

```txt
POST /rag/answer {"query": "...", "limit": 5}
  -> AnswerQuestion
  -> Retriever.search recupera evidencias
  -> RagAnswerGenerator monta contexto
  -> Gemini gera saida estruturada
  -> validacao garante que toda citacao aponta para chunk existente
  -> API retorna answer, citations e evidences
```

## 5. API

```txt
POST /rag/answer
```

Entrada:

```json
{
  "query": "Como a startup usa IA?",
  "limit": 5
}
```

Saida:

```json
{
  "query": "Como a startup usa IA?",
  "answer": "A startup usa IA para automatizar analises operacionais...",
  "citations": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "source_url": "https://startup.example.com",
      "quote": "automatiza analises operacionais"
    }
  ],
  "evidences": [
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

## 6. Erros

```txt
400 -> pergunta vazia ou texto invalido para embedding
404 -> nenhuma evidencia recuperada
503 -> GEMINI_API_KEY ou servico de embedding nao configurado
502 -> LLM gerou resposta invalida ou citou chunk inexistente
```

## 7. Limites da V2

```txt
sem busca hibrida
sem reranking
sem persistencia de consultas RAG
sem filtros por startup
sem avaliacao automatica de qualidade da resposta
```

## 8. Validacao

```txt
test_answer_question.py
test_search_evidence.py
7 testes unitarios do modulo RAG passando
292 testes unitarios da suite de modulos passando
```

Observacao: testes de integracao ainda dependem de Postgres, Redis e Qdrant
locais ativos.

## 9. Proximo Passo

```txt
RAG V3/V4 - ja implementados; ver rag_v3_busca_hibrida.md e rag_v4_reranking.md
```
