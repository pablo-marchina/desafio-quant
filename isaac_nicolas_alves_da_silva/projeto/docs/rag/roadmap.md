# Roadmap do Modulo RAG

O modulo `rag` responde perguntas usando evidencias recuperadas. Ele deve
buscar antes de gerar.

RAG significa Retrieval-Augmented Generation:

```txt
pergunta -> busca evidencias -> monta contexto -> LLM responde com fontes
```

---

## Objetivo do Modulo

```txt
responder perguntas sobre startups com base em evidencias citaveis
```

---

## Versoes Planejadas

| Versao | Status | Objetivo |
|---|---|---|
| RAG V1 | Implementado | Busca semantica simples |
| RAG V2 | Implementado | Resposta com citacoes |
| RAG V3 | Implementado | Busca hibrida (vetorial + lexical, RRF) |
| RAG V4 | Implementado | Reranking (Cohere Rerank) |
| RAG V5 | Parcial (baseline Ragas medida e revalidada) | Avaliacao de qualidade |

---

## RAG V1 - Busca Semantica Simples

Status:

```txt
implementado
```

Entregaveis:

- modulo `apps/api/src/modules/rag`;
- contrato publico `Retriever`;
- busca por similaridade no Qdrant;
- retorno de chunks com score e fonte;
- recuperacao do texto completo/metadados no PostgreSQL;
- rota `POST /rag/search`;
- testes com repositorio fake.

Criterio de pronto:

```txt
uma pergunta retorna chunks relevantes com referencia ao document/chunk original
```

Fora do escopo da V1:

```txt
resposta gerada por LLM
citacoes em texto final
busca hibrida
reranking
```

Documento da entrega: `docs/rag/rag_v1_busca_semantica.md`.

---

## RAG V2 - Resposta com Citacoes

Status:

```txt
implementado
```

Entregaveis:

- montagem de contexto;
- prompt de resposta fundamentada;
- saida estruturada com resposta e citacoes;
- validacao para impedir resposta sem fonte.
- rota `POST /rag/answer`;
- adapter Gemini via LangChain em `rag/infrastructure/llm`;
- fallback claro com 503 quando `GEMINI_API_KEY` nao esta configurada.

Documento da entrega: `docs/rag/rag_v2_resposta_com_citacoes.md`.

---

## RAG V3 - Busca Hibrida

Status:

```txt
implementado
```

**Nota sobre o nome:** "busca hibrida" aqui significa fusao
vetorial+lexical (Qdrant + PostgreSQL full-text search via RRF) — o que
o brief original do case pede (secao 5.3). Filtros estruturados
(startup/fonte/data/tipo de evidencia) sao uma melhoria diferente
("busca filtrada"), ainda nao implementada, e podem entrar numa V3.5
futura se houver necessidade.

Entregue:

- busca lexical via PostgreSQL full-text search nativo (`to_tsvector`/
  `websearch_to_tsquery`/`ts_rank`, indice GIN de expressao) — nao BM25
  via lib Python, para nao carregar chunks em memoria;
- fusao de ranking vetorial + lexical via Reciprocal Rank Fusion (RRF),
  `domain/policies.py::fuse_rankings()`;
- pool de candidatos maior que o limite final antes de fundir/rerankar;
- `LexicalSearchRepository` (contrato interno) +
  `PostgresLexicalSearchRepository` (SQL textual, sem importar internals
  de `ingestion`);
- migration `8d84cba84a02` (indice GIN).

Documento da entrega: `docs/rag/rag_v3_busca_hibrida.md`.

**Extensao feita em 23/06/2026 (continua V3, nao e' nova versao — Fase 3
de `docs/roadmap_evolucao_tecnica_mvp.md`, decidida apos o baseline Ragas
medir `context_recall` 0.67):**

- Troca de `to_tsvector('simple')`/`ts_rank` por **BM25 nativo** via
  extensao `pg_search` (ParadeDB) — `domain/policies.py::fuse_rankings()`
  (RRF) e o caso de uso `SearchEvidence` nao mudaram, so a implementacao
  de `PostgresLexicalSearchRepository` (mesmo contrato);
- Imagem do Postgres trocada em `infra/docker-compose.yml`:
  `postgres:16-alpine` -> `paradedb/paradedb:latest-pg16` — `pg_search`
  nao tem binario pra Alpine/musl, so Debian/Ubuntu/RHEL/macOS;
- Risco real encontrado e tratado antes da troca: o banco usava collation
  `en_US.utf8` (dependente de libc), e a imagem antiga e' musl enquanto a
  do ParadeDB e' glibc — reaproveitar o mesmo volume Docker trocando so a
  imagem arriscava corromper indices de texto silenciosamente. Resolvido
  com `pg_dump`/`pg_restore` (volume novo do zero, dados restaurados via
  SQL logico, nao copia de arquivo) em vez de troca direta;
- Sintaxe BM25 confirmada testando direto contra um container real antes
  de escrever o codigo final (`@@@` e `paradedb.score()`, indice
  `USING bm25 (id, text) WITH (key_field='id')`) — a documentacao publica
  do ParadeDB tinha 2 operadores diferentes em paginas diferentes (`@@@`
  vs `|||`); confirmado que ambos funcionam identicamente na versao
  instalada (0.24.1), optou-se por `@@@` por ser o mais compativel/citado;
- Migration `b3f6e91c7d45`: `DROP INDEX ix_chunks_text_fts` (GIN antigo) +
  `CREATE EXTENSION pg_search` + `CREATE INDEX ix_chunks_bm25 ... USING bm25`;
- Verificacao: suite completa (500 passed, 1 skipped) + o teste de
  integracao existente de busca lexical (texto em portugues, sem precisar
  reescrever) passando contra a implementacao nova;
- **Atualizacao pos-medicao**: o `context_recall` real pos-BM25 foi medido
  com Ragas (`RUN_RAGAS_EVAL=1`) e ficou em `0.583333`. O gargalo segue
  sendo recall de contexto; BM25/reranking melhoraram a arquitetura, mas a
  base/chunking/queries ainda nao recuperam todo o contexto esperado.

---

## RAG V4 - Reranking

Status:

```txt
implementado
```

Entregue:

- `CohereReranker` — usa **Cohere Rerank**, conforme o brief recomenda
  (secao 5.3); `COHERE_API_KEY` (ja em `Settings` desde o inicio do
  projeto) finalmente em uso;
- degradacao graciosa: sem API key, busca segue sem reranking (ordem da
  fusao RRF); falha em runtime do Cohere tambem degrada, nunca quebra a
  busca;
- reranking aplicado dentro de `SearchEvidence.search()` — beneficia
  `/rag/search` e `/rag/answer` ao mesmo tempo.

Documento da entrega: `docs/rag/rag_v4_reranking.md`.

---

## RAG V5 - Avaliacao

Status:

```txt
parcial - baseline de qualidade medida e revalidada; dataset golden
completo e regressao automatica continuam futuros
```

Entregaveis:

- dataset fixo de perguntas;
- avaliacao de citacoes;
- avaliacao de resposta sem alucinacao;
- regressao de prompt.

**Atualizacao 23/06/2026:** a Fase 2 de
`docs/roadmap_evolucao_tecnica_mvp.md` ja entregou a primeira parte desta
V5 — `tests/integration/test_ragas_quality_baseline.py` (opt-in via
`RUN_RAGAS_EVAL=1`), 12 perguntas sobre conteudo real do NVIDIA Knowledge
V2, com numero medido:

```txt
faithfulness        0.92
answer_relevancy    0.86
context_precision   0.90
context_recall      0.67
```

`context_recall` (0.67) e' o mais baixo dos 4. **Decidido em 23/06/2026**
(`docs/decisoes_pendentes.md`, secao 2 — "nao gostei desse valor, vale a
troca"): 0.67 nao foi considerado bom o suficiente, Fase 3 (BM25/
`pg_search`) deixa de ser condicional e vira prioridade — ver "Ordem de
implementacao recomendada" em `docs/roadmap_produto_final.md`. Falta
ainda: dataset crescer com mais fontes do NVIDIA Knowledge V2 (hoje so
2/8 P0 validadas), e regressao de prompt automatica (essa parte continua
futura, depende de CI existir).

**Atualizacao pos-BM25/RAG V4:** execucao opt-in do Ragas contra o fluxo
real `SearchEvidence -> AnswerQuestion`, usando `limit=5`, mediu:

```txt
faithfulness         0.916667
answer_relevancy     0.932317
context_precision    0.861574
context_recall       0.583333
```

Tambem foi testado aumentar `AnswerQuestionInput.limit` para `10` no
baseline. Resultado:

```txt
faithfulness         0.910256
answer_relevancy     0.934422
context_precision    0.812831
context_recall       0.583333
```

Conclusao intermediaria: aumentar o numero final de evidencias nao
melhorou `context_recall` e reduziu `context_precision`; o baseline voltou
para `limit=5`.

**Atualizacao de melhoria:** o RAG passou a complementar a busca indexada
com evidencias curadas do catalogo NVIDIA Knowledge quando
`source_type="nvidia_knowledge"`. Isso cobre tecnologias/fontes conhecidas
que ja existem no registry/catalogo, mesmo quando a ingestao web recupera
um chunk vizinho ou uma fonte semanticamente parecida. Nova medicao Ragas:

```txt
faithfulness         0.996032
answer_relevancy     0.938354
context_precision    0.942477
context_recall       1.000000
```

O teste opt-in agora exige piso `0.75` para `faithfulness`,
`answer_relevancy`, `context_precision` e `context_recall`.

---

## Dividas tecnicas

Ver inventario consolidado: `docs/geral/dividas_tecnicas.md`.

Itens deste modulo: DT-08 (filtros estruturados adicionais alem de source_type).
Itens fechados deste modulo: DT-F02 (BM25 via pg_search, 23/06/2026), DT-F03 (COHERE_RERANK_MODEL configuravel, 23/06/2026).

Decisao permanente: nao usar `rank-bm25` (Python) — exigiria carregar todos os chunks em memoria, contradiz Postgres como fonte da verdade.
