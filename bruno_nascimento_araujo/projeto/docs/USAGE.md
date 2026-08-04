# Guia de Uso

[⬅ Voltar ao README](../README.md)

Todos os comandos abaixo assumem o ambiente virtual ativado e o `.env`
configurado (ver [SETUP.md](SETUP.md)). A ordem reflete a dependência real
entre as fases — pular uma etapa faz a próxima não encontrar dados.

## Índice

- [Fase 1 — Discovery (`main.py`)](#fase-1--discovery-mainpy)
- [Fase 2 — Deep Extraction (`phase2_main.py`)](#fase-2--deep-extraction-phase2_mainpy)
- [Vetorização de Startups (`phase2_vectorizer.py`)](#vetorização-de-startups-phase2_vectorizerpy)
- [Ingestão da Base NVIDIA (`ingest_nvidia_docs.py`)](#ingestão-da-base-nvidia-ingest_nvidia_docspy)
- [Fase 3 — Classificador (`classify_startup.py`)](#fase-3--classificador-classify_startuppy)
- [Fase 3 — RAG Agent (`query_nvidia_rag.py`)](#fase-3--rag-agent-query_nvidia_ragpy)
- [Fase 3 — Recomendação (`recommend_startup.py`)](#fase-3--recomendação-recommend_startuppy)
- [Fase 3 — Briefing (`brief_startup.py`)](#fase-3--briefing-brief_startuppy)
- [Fase 4 — Dashboard (`streamlit run`)](#fase-4--dashboard-streamlit-run)

## Fase 1 — Discovery (`main.py`)

Roda os 5 conectores diretos (Cubo Itaú, 100 Open Startups, ABRIA, Astella,
Monashees) em paralelo, mais a expansão de grafo (QFirst Open Search), e
persiste tudo em `startups_discovered` via upsert idempotente.

```bash
python main.py --migrate                     # só aplica migrações e sai
python main.py                               # pipeline completo (direta + busca aberta)
python main.py --no-open-search              # apenas os 5 conectores diretos
python main.py --dry-run --no-open-search    # testa os conectores SEM tocar o PostgreSQL
```

Conferir o resultado (idempotência: rodar 2x não duplica linhas):

```sql
SELECT source_name, status, count(*) FROM startups_discovered
GROUP BY source_name, status ORDER BY 1,2;
```

## Fase 2 — Deep Extraction (`phase2_main.py`)

Para cada startup em `startups_discovered`, descobre a URL (se ausente),
extrai conteúdo rico, divide em chunks e grava em `startups_content`.

```bash
python phase2_main.py --migrate                          # aplica 002_content.sql
python phase2_main.py --dry-run                          # extrai sem persistir (mostra ExtractedStartupData)
python phase2_main.py --batch-size 20                     # processa 20 por rodada (padrão: DEEP_SCAN_BATCH_SIZE)
python phase2_main.py --status high_priority              # prioriza startups marcadas high_priority
python phase2_main.py --status pending                    # pending_deep_scan + missing_url
python phase2_main.py --status missing_url                # só as que falharam por falta de URL
python phase2_main.py --status pending_deep_scan missing_url --batch-size 10   # múltiplos status + tamanho custom
```

O padrão (`--status all`, implícito) processa `pending_deep_scan` +
`high_priority`. Rode em várias rodadas até o log indicar
"Nenhum registro pendente" — cada rodada consome um lote e atualiza o
`status` de cada startup (`deep_scan_completed`, `deep_scan_failed` ou
`missing_url`).

## Vetorização de Startups (`phase2_vectorizer.py`)

Lê chunks de `startups_content` ainda não vetorizados (`is_embedded=FALSE`),
gera embeddings com `all-MiniLM-L6-v2` e grava na coleção Qdrant
`startup_chunks`.

```bash
python phase2_vectorizer.py --dry-run          # só conta quantos chunks estão pendentes
python phase2_vectorizer.py --limit 10         # processa no máximo 10 chunks (teste rápido)
python phase2_vectorizer.py --filter-ai        # processa só chunks com has_ai_signals=TRUE
python phase2_vectorizer.py --batch-size 64    # rodada completa (padrão: EMBED_BATCH_SIZE)
```

## Ingestão da Base NVIDIA (`ingest_nvidia_docs.py`)

Baixa as 18 URLs oficiais da NVIDIA (produtos, docs técnicas, READMEs do
GitHub), extrai texto (`trafilatura`, com fallback Crawl4AI para SPAs e fetch
direto de README para repositórios GitHub), divide em chunks com
`RecursiveCharacterTextSplitter` e vetoriza na coleção `nvidia_tech_knowledge`.
Mantém estado em `nvidia_ingest_state.json` para retomar caso seja
interrompido.

```bash
python ingest_nvidia_docs.py --dry-run         # lista as URLs pendentes sem baixar/escrever
python ingest_nvidia_docs.py --limit-urls 2    # testa com só as 2 primeiras URLs
python ingest_nvidia_docs.py                   # rodada completa (18 URLs)
python ingest_nvidia_docs.py --force           # reprocessa TODAS as URLs, mesmo já ingeridas
python ingest_nvidia_docs.py --batch-size 16   # chunks por lote de encode (padrão: 32)
```

## Fase 3 — Classificador (`classify_startup.py`)

Classifica uma startup (ou um lote) como `ai_native`, `ai_enabled` ou
`non_ai` com base nos chunks vetorizados, usando o fallback multi-provedor de
LLM.

```bash
python classify_startup.py --startup-id 1 --dry-run     # mostra prompt + resposta do LLM, não salva
python classify_startup.py --startup-id 1                # classifica e persiste em `classifications`
python classify_startup.py --batch-size 10                # classifica as 10 primeiras startups sem classificação
python classify_startup.py --startup-id 1 --reprocess     # força reclassificação mesmo já existindo
python classify_startup.py --startup-id 1 --model groq:llama3-8b-8192   # força um provedor específico
python classify_startup.py --startup-id 1 --model ollama:llama3.2:3b   # força Ollama local
```

Sem `--reprocess`, startups já classificadas são puladas (idempotência); com
`--batch-size`, até 5 startups são processadas em paralelo
(`asyncio.Semaphore(5)`).

## Fase 3 — RAG Agent (`query_nvidia_rag.py`)

Busca tecnologias NVIDIA relevantes — para uma startup (via transformação de
query pelo LLM) ou para uma pergunta livre (usado pelo chat do dashboard).

```bash
python query_nvidia_rag.py --startup-id 1 --dry-run                       # não grava no cache
python query_nvidia_rag.py --query "otimização de inferência de LLMs" --dry-run
python query_nvidia_rag.py --startup-id 1 --top-k 5                        # nº de chunks finais (padrão: 5)
python query_nvidia_rag.py --startup-id 1 --categories "Inferência,Dados"   # filtra por categoria no Qdrant
```

A saída no console mostra a query condensada, tempos de retrieval/reranking, e
o JSON completo dos chunks retornados (útil para integração/debug).

## Fase 3 — Recomendação (`recommend_startup.py`)

Cruza a classificação (Agente 1) com os chunks NVIDIA do RAG (Agente 2) e
heurísticas de setor para gerar recomendações técnicas priorizadas.

```bash
python recommend_startup.py --startup-id 1 --dry-run     # mostra as recomendações, não salva
python recommend_startup.py --startup-id 1                # gera e persiste em `recommendations`
python recommend_startup.py --batch-size 10                # as 10 primeiras startups classificadas sem recomendação
python recommend_startup.py --startup-id 1 --reprocess     # força regeração
```

Requer que a startup já tenha sido classificada
(`python classify_startup.py --startup-id 1` primeiro) — caso contrário, falha
com uma mensagem explícita.

## Fase 3 — Briefing (`brief_startup.py`)

Gera o relatório executivo em Markdown (resumo via LLM + seções
determinísticas), consolidando classificação e recomendações.

```bash
python brief_startup.py --startup-id 1 --dry-run          # mostra o Markdown no console, não salva
python brief_startup.py --startup-id 1                     # gera e persiste em `briefings`
python brief_startup.py --startup-id 1 --export-file       # também salva em reports/{id}_{nome}.md
python brief_startup.py --batch-size 10                     # lote de startups classificadas+recomendadas sem briefing
python brief_startup.py --startup-id 1 --reprocess          # força regeração
```

Requer classificação **e** recomendação já geradas para a startup.

## Fase 4 — Dashboard (`streamlit run`)

```bash
streamlit run dashboard/app.py
```

Páginas disponíveis:

- **Dashboard** (`views/home.py`) — métricas agregadas + lista de startups
  descobertas.
- **Detalhes da Startup** (`views/startup_detail.py`) — classificação,
  recomendações e briefing de uma startup específica, com botões para
  disparar `generate_recommendations` / `generate_briefing` sob demanda
  diretamente da UI (sem precisar rodar os CLIs manualmente) e exportar o
  briefing em Markdown.
- **Busca Inteligente** (`views/chat_rag.py`) — chat livre sobre a base de
  conhecimento NVIDIA, usando `run_rag(startup_id=None, query=...)` — não
  filtra por startup, é equivalente a `query_nvidia_rag.py --query "..."`.
