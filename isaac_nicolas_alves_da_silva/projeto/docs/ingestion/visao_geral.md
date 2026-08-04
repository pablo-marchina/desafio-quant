# Módulo Ingestion — Visão Geral

## 1. Importância

O `ingestion` transforma o conteúdo bruto aprovado pelo scraping em unidades
prontas para embedding: limpa o texto, cria um `Document` normalizado e o quebra
em `Chunk`s. É a ponte entre "texto coletado" e "vetor pesquisável". Sem chunks
bem formados, a busca semântica e o RAG perdem qualidade.

## 2. Fluxo

```txt
POST /ingestion/jobs
  -> cria IngestionJob (1-para-1 com scraping_result)
  -> ingestion_worker busca o ScrapingResult
  -> TextCleaner normaliza (CRLF, chars de controle, linhas em branco)
  -> cria Document (clean_text + word_count + source_type)
  -> TextChunker quebra em chunks (~2000 chars, overlap 200; respeita parágrafo > sentença > palavra)
  -> marca o job como completed
```

## 3. Estrutura de pastas

```txt
ingestion/
  presentation/     POST/GET de jobs
  application/      TextCleaner, TextChunker, use cases; public/IngestedDocumentReader
  domain/           IngestionJob, Document, Chunk (status transitions)
  infrastructure/   database/ (PostgresIngestedDocumentReader, ScrapingResultReader)
  factories/
  tests/
```

## 4. Stack

```txt
(sem lib externa)   chunking/cleaning manual hoje
SQLAlchemy async    persistência
Dramatiq + Redis    fila "ingestion"
```

Candidata: `langchain_text_splitters` para chunking estrutural (ver `roadmap.md`).

## 5. Comunicação

```txt
embeddings -> ingestion (IngestedDocumentReader.list_chunks_by_document_id)
rag        -> ingestion (IngestedDocumentReader)
```

## 6. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | TextCleaner, TextChunker, Document, Chunk, worker, contrato público |
| V4 | Entregue | Worker assíncrono (alinhado ao padrão dos demais módulos) |

**Versão atual: V1 + V4.** Extensões posteriores adicionaram
`list_chunks_by_document_id()` e `clean_text` ao contrato público sem mudar a
versão. Futuro (V2/V3/V5) em `roadmap.md`.
