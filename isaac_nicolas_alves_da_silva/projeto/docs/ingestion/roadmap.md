# Roadmap do Modulo Ingestion

O modulo `ingestion` transforma `scraping_results` aprovados em documentos e
chunks limpos, rastreaveis e prontos para embeddings.

Ele nao faz scraping e nao gera embedding. A responsabilidade dele e preparar o
texto.

---

## Objetivo do Modulo

```txt
scraping_results -> documents -> chunks
```

O scraping salva conteudo bruto aprovado. A ingestion limpa, normaliza, divide
e cria uma base textual confiavel para busca semantica.

---

## Versoes Planejadas

| Versao | Status | Objetivo |
|---|---|---|
| Ingestion V1 | Implementado | Documents e chunks no PostgreSQL |
| Ingestion V2 | Futuro | Limpeza textual mais forte |
| Ingestion V3 | Futuro | Deduplicacao e versionamento |
| Ingestion V4 | Implementado | Worker assincrono |
| Ingestion V5 | Futuro | Reprocessamento e auditoria |

---

## Ingestion V1 - Documents e Chunks

Objetivo:

```txt
transformar scraping_results em documents e chunks persistidos
```

Entregaveis:

- modulo `apps/api/src/modules/ingestion`;
- entidades `IngestionJob`, `Document`, `Chunk`;
- contrato publico para ler resultados aprovados do scraping;
- servicos de dominio `TextCleaner` e `TextChunker`;
- caso de uso `ExecuteIngestionJob`;
- models SQLAlchemy;
- migration Alembic;
- repositorios PostgreSQL;
- testes unitarios e integracao.

Criterio de pronto:

```txt
um scraping_result aprovado gera um Document e varios Chunks rastreaveis
```

Documento da entrega: `docs/ingestion/ingestion_v1_documents_e_chunks.md`.

---

## Ingestion V2 - Limpeza Textual

Objetivo:

```txt
melhorar qualidade dos textos antes de embedding
```

Entregaveis:

- remover menus, rodapes e boilerplate residual;
- normalizar espacos e quebras de linha;
- detectar idioma;
- preservar titulo, URL e metadados;
- marcar trechos de baixa qualidade.

---

## Ingestion V3 - Deduplicacao e Versionamento

Objetivo:

```txt
evitar documentos duplicados e controlar mudancas de conteudo
```

Entregaveis:

- hash por documento limpo;
- hash por chunk;
- historico de versoes;
- politica de atualizacao quando a mesma URL mudar;
- relacao entre document original e versoes.

---

## Ingestion V4 - Worker Assincrono

Objetivo:

```txt
executar ingestion fora da API
```

Entregaveis:

- `workers/ingestion_worker`;
- fila `ingestion`;
- mensagem somente com `ingestion_job_id`;
- dispatcher no modulo `ingestion`;
- retry/backoff para falhas recuperaveis.

Entregue junto da V1 para manter simetria com os demais modulos baseados em
jobs.

---

## Ingestion V5 - Reprocessamento

Objetivo:

```txt
permitir reprocessar documentos quando a regra de limpeza ou chunking mudar
```

Entregaveis:

- versao do algoritmo de chunking;
- versao do algoritmo de limpeza;
- job de reprocessamento;
- auditoria de chunks antigos e novos;
- integracao futura com embeddings para reembedding.

---

## Fronteiras

O modulo `ingestion` pode depender de contratos publicos do scraping para ler
resultados aprovados.

Ele nao deve importar infraestrutura interna do scraping.

Ele nao deve chamar Qdrant diretamente. Qdrant pertence ao modulo de embeddings
ou retrieval.

---

## Dividas tecnicas

Ver inventario consolidado: `docs/geral/dividas_tecnicas.md`.

Itens deste modulo: DT-07 (dedup de Document por hash).
Itens fechados deste modulo: DT-F08 (cache de embedding por content_hash, 23/06/2026), DT-F10 (TextChunker via LangChain RecursiveCharacterTextSplitter, 28/06/2026).
