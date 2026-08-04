# RAG V4 — Reranking

Esta versao adiciona reranking via Cohere Rerank sobre as evidencias ja
fundidas pela busca hibrida (RAG V3). Fecha a segunda metade do
Entregavel 3 do case original.

## 1. Objetivo

```txt
evidencias fundidas (RRF) + pergunta -> Cohere Rerank -> top N reordenado
```

## 2. Cohere Rerank, conforme o brief pede

`COHERE_API_KEY` ja existia em `Settings` desde o inicio do projeto
(documentado em CLAUDE.md), mas nunca tinha sido usado. `cohere>=5.0,<6`
adicionado a `requirements.txt`. `CohereReranker`
(`infrastructure/reranking/cohere_reranker.py`) usa
`cohere.AsyncClient.rerank(model=, query=, documents=, top_n=)` —
assinatura confirmada contra o SDK 5.21.1 instalado.

## 3. Degradacao graciosa, diferente do padrao Gemini

Todo servico Gemini deste projeto levanta erro 503 quando a API key esta
ausente (`AgentServiceUnavailableError`, `EmbeddingServiceUnavailableError`,
etc.) porque, sem LLM, a operacao **nao pode** ser concluida (ex: gerar
uma resposta). Reranking e diferente: a busca hibrida (V3) ja funciona
sem ele. Por isso:

```txt
sem COHERE_API_KEY -> RagFactory.create_reranker() devolve None ->
  SearchEvidence usa a ordem da fusao RRF direto, sem erro

com COHERE_API_KEY mas Cohere fora do ar / erro inesperado ->
  CohereReranker captura a excecao, loga (logger.warning com
  exc_info=True) e devolve a ordem recebida (evidences[:top_n]) -> busca
  nunca falha por causa do reranker
```

## 4. Onde o reranking acontece

Dentro de `SearchEvidence.search()` (RAG V3), nao em `AnswerQuestion`.
`/rag/search` e `/rag/answer` compartilham o mesmo `Retriever`
(`SearchEvidence`), entao colocar o reranking ali beneficia os dois
endpoints sem duplicar logica. Fluxo completo:

```txt
busca vetorial (pool) + busca lexical (pool)
  -> fuse_rankings() (RRF)
  -> carrega texto completo via ingestion
  -> reranker.rerank(query, evidences, top_n=limit) se configurado
  -> senao, corta para `limit` direto
```

## 5. Validacao

Testes novos: cobertos junto com RAG V3 em `test_search_evidence.py`
(`test_search_evidence_without_reranker_keeps_fused_order`,
`test_search_evidence_uses_reranker_when_configured`).

Sem teste dedicado para `CohereReranker` chamando a API real — mesmo
padrao dos demais wrappers de LLM/API externa deste projeto (Gemini via
LangChain tambem nao tem teste unitario que chame a API de fato).

## 6. Limites conhecidos

```txt
sem teste automatizado contra a API real da Cohere (custo + necessidade
  de chave real); validar manualmente com COHERE_API_KEY configurada
  antes de depender disso em produção

modelo fixo (rerank-v3.5) - sem configuracao de modelo via env var ainda
```

## 7. Proximo passo

```txt
Com RAG V3+V4 entregues, o Entregavel 3 do case esta completo. Proximos
itens do diagnostico (docs/diagnostico_case_original_e_novas_prioridades.md,
secao 8): os 3 agentes LangGraph que faltam (NVIDIA RAG, Recommendation,
Briefing), Startups V2, ou Frontend.
```
