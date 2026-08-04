# NVIDIA Knowledge V2 - Primeira Validacao Real Ponta a Ponta

Esta entrega roda a ingestao de fontes reais da NVIDIA Knowledge V2 contra
infraestrutura local ativa (Postgres/Redis/Qdrant/Gemini) pela primeira vez,
e corrige 4 bugs que bloqueavam o fluxo completo
`URL -> scraping -> ingestion -> embeddings -> RAG`.

## Resultado

```txt
POST /nvidia-knowledge/ingestion/jobs (priority=p0) -> 8 fontes submetidas
nemo-framework-docs            completed
triton-inference-server-docs   completed
```

Confirmado via `GET /rag/search` (`source_type=nvidia_knowledge`): conteudo
real da documentacao NVIDIA (Triton, NeMo Framework) e recuperavel pela
busca hibrida. Primeira vez que isso funciona com dados reais neste
projeto — antes so havia testes com fakes/mocks.

## Bugs encontrados e corrigidos

### 1. Falso positivo no detector de captcha (`scraping`)

`technical_validator.py` fazia `"captcha" in lowered_html` — qualquer
pagina que so referencia uma lib de captcha no JS (GitHub, formularios de
login/abuso) era bloqueada mesmo sem desafio real. Corrigido: so bloqueia
quando o sinal vem acompanhado de pouco texto extraido (`< 500
caracteres`), mesmo padrao ja usado para detectar `javascript_required`.

### 2. Playwright quebrava dentro do worker (`scraping`)

Causa raiz confirmada: o Dramatiq substitui `sys.stdout`/`sys.stderr` por
um pipe entre processos (`StreamablePipe`, usado so para encaminhar logs
ao processo principal). Esse pipe tem `fileno()` valido, mas nao e' um
handle herdavel no Windows para o subprocesso que o Playwright cria
internamente (driver Node + Chromium) — falhava com `OSError: [Errno 9]
Bad file descriptor`. Corrigido: `PlaywrightScraper` restaura
`sys.__stdout__`/`sys.__stderr__` (os streams originais do processo)
durante o launch do driver/browser.

### 3. Validacao evidencial errada para fontes curadas (`scraping`)

O pipeline de scraping foi desenhado para validar "evidencia de que uma
startup usa IA" (deterministico + LLM + agente). Aplicado sem ajuste a
documentacao tecnica da propria NVIDIA, rejeitava paginas tecnicamente
perfeitas (ex: cuDF docs com `technical_score=1.0`, `text_score=0.93`)
porque elas nao "provam uso de IA por uma startup". Corrigido:
`source_type` agora trafega de `UrlIngestionJob` at e' `ScrapingJob`
(migration `7d4f2a9c6e83`); para qualquer `source_type != "startup_evidence"`,
`QualityScoringService` ignora a dimensao de evidencia
(`quality_score = technical*0.5 + text*0.5`) e a pipeline pula
LLM_REVIEW/AGENT_REVIEW inteiramente — fontes curadas pelo registry sao
aceitas por qualidade tecnica+textual, sem precisar "provar" nada sobre
IA.

### 4. Modelo de embedding descontinuado (`embeddings`)

`GEMINI_EMBEDDING_MODEL` apontava para `models/text-embedding-004`, que a
API do Gemini devolve 404 (`not found... or not supported for
embedContent`). Confirmado via `GET /v1beta/models` que o modelo nao
esta mais na lista de modelos com `embedContent` suportado. Trocado para
`models/gemini-embedding-001` (3072 dimensoes, validado com chamada real
antes de aplicar). Sem migracao de dados: a colecao Qdrant local estava
vazia, sem vetores no dimensionamento antigo para conciliar.

## Causa raiz dos resultados inconsistentes durante a validacao

Depois de corrigir os 4 bugs acima, a primeira rodada de teste do lote P0
(8 fontes) ainda mostrou 5 rejeicoes por "captcha" — aparentemente a
correcao 1 nao tinha pegado. Investigacao confirmou que **nao era um bug
de codigo**: reiniciar um worker via `kill` do lado WSL mata so o
processo wrapper; o processo real do Dramatiq (`venv/Scripts/python.exe`,
nativo Windows, mais o `WorkerProcess` filho via `multiprocessing`)
continuava vivo, orfao, consumindo da mesma fila Redis com codigo antigo
em memoria. Ao longo desta sessao de testes/correcoes, isso acumulou
~27 processos `python.exe` orfaos (alguns de mais de 1h atras), competindo
de forma nao deterministica com os workers novos pelas mesmas mensagens.

Corrigido localmente matando todos os processos `python.exe` direto pelo
lado Windows (`Get-Process python | Stop-Process -Force` via
`powershell.exe`) antes de reiniciar — sem isso, qualquer reinicio de
worker neste ambiente (Windows + WSL interop) pode deixar processos
antigos competindo com os novos silenciosamente.

## Limites e pendencias

```txt
6/8 fontes do lote P0 ainda nao foram re-tentadas com os workers
  realmente limpos (nemo-guardrails-github, nvidia-ai-enterprise,
  nvidia-inception, nim-docs, tensorrt-docs, tensorrt-llm-docs) -
  triton-inference-server-docs foi re-testada isoladamente e completou
  em ~40s, confirmando que as correcoes funcionam; as outras 5 fontes de
  captcha/rejeicao do lote original devem se comportar igual numa nova
  tentativa limpa

resolucao de hostname intermitente: docs.nvidia.com e docs.monai.io
  falharam com "nao foi possivel resolver o hostname" partindo do
  processo Python nativo do Windows, mesmo com DNS funcionando
  normalmente do lado WSL (confirmado via curl/getent). E' uma questao de
  rede/DNS do host Windows, fora do alcance de uma correcao de codigo -
  ficou para o usuario resolver no proprio ambiente

P1/P2 do registry (12 fontes) ainda nao foram submetidas
```

## Comando para reproduzir

```bash
# 1. Garantir Postgres/Redis/Qdrant ativos e GEMINI_API_KEY configurada
# 2. Matar processos python.exe orfaos (Windows) antes de reiniciar workers
powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"

# 3. Subir os 4 workers (cada um em processo separado)
venv/Scripts/python.exe workers/scraper_worker/run.py
venv/Scripts/python.exe workers/ingestion_worker/run.py
venv/Scripts/python.exe workers/embedding_worker/run.py
venv/Scripts/python.exe workers/orchestration_worker/run.py

# 4. Submeter o lote P0
curl -X POST localhost:8000/nvidia-knowledge/ingestion/jobs -d '{"priority": "p0"}'
```
