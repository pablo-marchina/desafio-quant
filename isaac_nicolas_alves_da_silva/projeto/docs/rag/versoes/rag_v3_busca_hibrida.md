# RAG V3 — Busca Hibrida (Vetorial + Lexical)

Esta versao adiciona busca lexical (full-text search nativo do
PostgreSQL) ao lado da busca vetorial (Qdrant) ja existente, fundindo os
dois rankings via Reciprocal Rank Fusion (RRF). Fecha a primeira metade
do Entregavel 3 do case original ("busca hibrida: busca vetorial + busca
lexical").

## 1. Objetivo

```txt
pergunta -> candidatos vetoriais (Qdrant) + candidatos lexicais (Postgres) -> fusao RRF -> evidencias
```

Extensao posterior para NVIDIA Knowledge V2:

```txt
SearchEvidenceInput.source_type
AnswerQuestionInput.source_type
filtro vetorial por payload source_type
filtro lexical por documents.source_type
```

O filtro e opcional. Sem ele, o comportamento historico permanece: buscar em
todo o corpus disponivel.

## 2. Por que PostgreSQL full-text search, nao uma lib Python de BM25

O brief recomenda BM25, mas o projeto ja trata PostgreSQL como fonte de
verdade e evita dependencia nova quando o banco resolve. Uma lib como
`rank-bm25` exigiria carregar todos os chunks em memoria Python a cada
busca — nao escala. `to_tsvector('simple', text) @@
websearch_to_tsquery('simple', :query)` + `ts_rank` faz o mesmo papel
(ranking lexical por relevancia) usando o indice GIN de expressao criado
na migration, sem dependencia nova.

Config `'simple'` (nao `'portuguese'` nem `'english'`): o conteudo
coletado mistura PT-BR (sites/noticias brasileiras) e ingles (docs
oficiais, fontes internacionais). `'simple'` so tokeniza e faz lowercase,
sem stemming nem lista de stopwords de um idioma especifico — evita
favorecer um idioma sobre o outro.

## 3. Leitura cross-modulo sem importar internals

`chunks` e tabela de `ingestion`. `rag` le essa tabela via SQL textual
(`infrastructure/database/postgres_lexical_search_repository.py`), mesmo
padrao de `ingestion/infrastructure/database/postgres_scraping_result_reader.py`
(que ja le `scraping_results`, de `scraping`, da mesma forma) — nunca
importa `ChunkModel`.

## 4. Fusao por Reciprocal Rank Fusion (RRF)

Vetorial (Qdrant, cosine 0-1) e lexical (`ts_rank`, escala arbitraria) nao
sao comparaveis por valor. RRF usa so a posicao de cada item em cada
ranking: `score = soma de 1/(k+posicao)` por ranking em que o item
aparece (k=60). Um chunk que aparece nos dois rankings acumula pontuacao
— e o sinal que torna a fusao hibrida util (recupera o que a busca
vetorial perderia por sinonimos/paráfrase, e o que a lexical perderia por
match exato de termos tecnicos/nomes proprios).

Funcao pura `fuse_rankings()` em `domain/policies.py` (primeiro arquivo
de domain deste modulo alem de `exceptions.py`) — sem import de
framework, testada isoladamente.

## 5. Pool de candidatos maior que o limite final

`SearchEvidenceInput.limit` (default 5) e o numero final de resultados.
Para a fusao ter material para trabalhar, `SearchEvidence` busca
`max(limit * 4, 20)` candidatos de cada fonte antes de fundir e cortar —
constantes `CANDIDATE_POOL_MULTIPLIER`/`MIN_CANDIDATE_POOL` em
`application/use_cases/search_evidence.py`.

## 6. Mudanca de comportamento: `score` agora e o score RRF

Antes (V2), `EvidenceChunkView.score` era o cosine score do Qdrant.
Agora e o score RRF da fusao — escala diferente (nao e mais 0-1 cosine).
Decisao deliberada: manter o cosine original seria enganoso para chunks
encontrados so pela busca lexical (que nunca tiveram cosine score), e
expor dois campos de score (um por fonte) complicaria o contrato publico
sem necessidade clara.

## 7. Migration

`8d84cba84a02`: `CREATE INDEX ix_chunks_text_fts ON chunks USING GIN
(to_tsvector('simple', text))` — indice de expressao, sem coluna nova.

## 8. Validacao

Testes novos:

```txt
test_fuse_rankings.py                  5 testes (RRF puro)
test_search_evidence.py (atualizado)   +4 testes (fusao, item em ambas
                                        as fontes rankeia primeiro, sem
                                        reranker, com reranker fake)
tests/integration/test_postgres_lexical_search_repository.py   1 teste
```

## 9. Limites conhecidos

```txt
'simple' config nao faz stemming - "treinar" e "treinamento" sao termos
  diferentes para o indice (trade-off aceito pela mistura de idiomas)

filtro estruturado atual cobre apenas source_type; filtros por startup, data
  ou taxonomia tecnica ainda nao existem
```

## 10. Proximo passo

```txt
RAG V4 - reranking (entregue junto, ver docs/rag/rag_v4_reranking.md)
```
