# Seraphim Scout

MVP inicial para uma plataforma de inteligência que usa Qdrant, RAG e uma API
FastAPI para mapear gaps técnicos de startups para tecnologias NVIDIA.

## Estado atual

- Qdrant local via Docker Compose.
- Postgres local via Docker Compose para histórico estruturado.
- Collections Qdrant: `nvidia_knowledge_base` e `startup_evidence`.
- API FastAPI em `apps/api/app` com interface visual em `http://localhost:8000/`.
- Interface web atual com header superior, navegação por abas, modo escuro,
  explicação clicável da porcentagem de oportunidade e CORS configurável para
  uso local seguro durante a demo.
- Ingestão seed e ingestão de 24 fontes oficiais NVIDIA.
- Busca vetorial recomendada com `sentence-transformers` local, sem custo de API.
- Fallback `hash` disponível para MVP offline simples, sem qualidade semântica real.
- Scraping de startup com mini-crawler: coleta a URL informada e links internos relevantes.
- Extração estruturada heurística de founders, funding, clientes, tecnologias
  e sinais de IA, com evidências e fontes quando disponíveis.
- Evidências de startup salvas no Qdrant para busca semântica posterior.
- Base ativa de startups no Postgres (`startup_catalog`), seedada por `data/startups_br.csv`.
- Repertório de descobertas no Postgres (`startup_discoveries`), com fallback CSV local.
- Descoberta de startups por adapters de fonte, com Startupi, Startups.com.br,
  Exame, Brazil Journal, StartSe, Endeavor, ACE e fallback genérico.
- Busca de startups por nome via `/startups/search`.
- Radar de startups candidatas com porcentagem de oportunidade para ferramentas NVIDIA.
- Análise de startup usa grafo formal com agentes separados e retorna
  `pipeline_trace` com etapas/agentes observáveis.
- Histórico na interface permite filtrar runs salvos, inspecionar detalhes,
  baixar briefing e abrir busca de evidências por `analysis_run_id`.
- Search Planner gera `search_plan` versionado com termos, fontes prioritárias
  e alvos de evidência.
- Recomendações NVIDIA incluem prioridade, complexidade de implementação e
  próxima ação sugerida como campos estruturados.
- RAG usa busca vetorial no Qdrant e reranking híbrido com BM25 formal,
  overlap lexical, frases, regras de domínio e qualidade da fonte.
- Evidence Validator rastreia fontes, motivos de bloqueio e remove recomendações
  fracas da análise final.
- Briefing inclui playbook de abordagem NVIDIA com timing sugerido, hipótese de
  valor, risco competitivo e pergunta de descoberta para a próxima conversa.
- Interface exibe diferenciais de decisão: playbook, Evidence Quality Gate,
  Wrapper Displacement Map, counterfactual e timing `quente/morno/exploratorio`
  nos cards do Radar.
- Aba Demo Mode roda os três cenários de apresentação: startup forte, risco
  wrapper e evidência fraca.
- Smoke test para validar RAG, ranking, Postgres e análise de startup.
- Testes unitários locais em `apps/api/tests`.
- Dockerfile da API e workflow de CI rodando `scripts/validate_mvp.py`.

## Estrutura do repositório

```text
apps/                  API FastAPI, frontend servido pela API e módulos do produto
scripts/               Scripts de operação, ingestão, checks e smoke test
docs/                  Documentação, protótipos e materiais de apoio
docker-compose.yml     Infra local: Qdrant e Postgres
requirements.txt       Dependências Python
README.md              Guia rápido para rodar o projeto
```

Dentro de `docs/`, os documentos de visão, status, guia pessoal, protótipo de
design e arquivos antigos ficam separados da raiz para deixar o projeto mais
fácil de navegar.

Para defender o projeto além do básico do case, veja
`docs/DIFERENCIAIS_ESTRATEGICOS.md`. Para preparar a apresentação, use
`docs/ROTEIRO_DEMO.md`; para checar a execução operacional antes da demo, use
`docs/DEMO_CHECKLIST.md`. Para ensaiar os cenários de diferencial, veja
`docs/DEMO_DIFERENCIAIS.md` ou use a aba `Demo Mode` na interface. Para revisar
o conjunto de mudanças antes de entrega ou commit, veja `docs/WORKTREE_REVIEW.md`.

## Como rodar

Requisito: Python 3.10+ instalado e disponível no terminal. Se o comando
`python --version` abrir a Microsoft Store, instale Python de verdade ou ajuste
os aliases de execução do Windows.

1. Suba Qdrant e Postgres:

```powershell
docker compose up -d qdrant postgres
```

2. Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

O `.env` local recomendado usa o provider gratuito via `sentence-transformers`:

```powershell
NVIDIA_RADAR_QDRANT_URL=http://localhost:6333
NVIDIA_RADAR_NVIDIA_COLLECTION=nvidia_knowledge_base
NVIDIA_RADAR_STARTUP_COLLECTION=startup_evidence
NVIDIA_RADAR_DATABASE_URL=postgresql://nvidia_radar:nvidia_radar@localhost:5432/nvidia_radar
NVIDIA_RADAR_STARTUP_SOURCE_PATH=data/startups_br.csv
NVIDIA_RADAR_STARTUP_DISCOVERY_PATH=data/startup_discoveries.csv
NVIDIA_RADAR_STARTUP_DISCOVERY_SOURCE_URL=https://startupi.com.br/
NVIDIA_RADAR_STARTUP_DISCOVERY_SOURCE_URLS=https://startupi.com.br/,https://startupi.com.br/startups/,https://revistapegn.globo.com/startups/
NVIDIA_RADAR_EMBEDDING_PROVIDER=sentence_transformers
NVIDIA_RADAR_SENTENCE_TRANSFORMERS_MODEL=intfloat/multilingual-e5-small
NVIDIA_RADAR_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY=false
NVIDIA_RADAR_VECTOR_SIZE=384
NVIDIA_RADAR_VECTOR_DISTANCE=Cosine
NVIDIA_RADAR_RERANKER_PROVIDER=hybrid
NVIDIA_RADAR_CORS_ALLOW_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
```

Depois do primeiro download do modelo, você pode trocar
`NVIDIA_RADAR_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY` para `true` para rodar sem baixar
novamente.

Opcionalmente, proteja endpoints administrativos de ingestão, freshness e
curadoria de repertório com um token local:

```powershell
NVIDIA_RADAR_ADMIN_API_TOKEN=troque-este-token
```

Quando esse token estiver configurado, chamadas administrativas devem enviar
`X-Admin-Token: troque-este-token` ou `Authorization: Bearer troque-este-token`.

Opcionalmente, configure embeddings via OpenAI:

```powershell
NVIDIA_RADAR_EMBEDDING_PROVIDER=openai
NVIDIA_RADAR_OPENAI_API_KEY=sk-...
NVIDIA_RADAR_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
NVIDIA_RADAR_VECTOR_SIZE=1536
```

Para um smoke test puramente offline e mais simples, também existe o provider
`hash`, mas ele não substitui embeddings semânticos reais:

```powershell
NVIDIA_RADAR_EMBEDDING_PROVIDER=hash
NVIDIA_RADAR_VECTOR_SIZE=1536
```

Valide o provider ativo:

```powershell
python scripts/check_embedding_provider.py
```

O reranking padrão é `hybrid`: ele combina score vetorial, overlap lexical,
BM25 formal, frases relevantes, qualidade da fonte e regras de fit NVIDIA por
domínio. Para usar um reranker neural local opcional, configure:

```powershell
NVIDIA_RADAR_RERANKER_PROVIDER=cross_encoder
NVIDIA_RADAR_CROSS_ENCODER_RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
NVIDIA_RADAR_CROSS_ENCODER_RERANKER_LOCAL_FILES_ONLY=true
```

Se o modelo CrossEncoder não estiver disponível localmente, o sistema volta para
o reranking `hybrid` sem interromper a API.

O endpoint `/health` mostra a configuração ativa do reranker e retorna
`status: degraded` quando algum serviço externo, como Qdrant, estiver indisponível.
As respostas de `/rag/search` incluem `metadata.rerank`, e as recomendações de
`/analysis/startup` incluem `rerank_details` para explicar score final, score
vetorial, sinais lexicais e boost de domínio. A interface visual também mostra
esses sinais na busca RAG.

3. Rode a API:

```powershell
python -m uvicorn app.main:app --reload --app-dir apps/api
```

Abra a interface preferencialmente em:

```txt
http://127.0.0.1:8000/
```

Também é possível abrir o `index.html` por preview/Live Server, mas a API
precisa estar rodando em `http://127.0.0.1:8000` e a origem do preview precisa
estar em `NVIDIA_RADAR_CORS_ALLOW_ORIGINS`.

Opcionalmente, rode a stack completa por Docker Compose:

```powershell
docker compose up --build
```

Nesse modo, a API fica em `http://localhost:8000/` e usa Qdrant/Postgres pelos
nomes internos do Compose.

4. Ingira fontes oficiais NVIDIA:

```powershell
python scripts/ingest_nvidia_official.py
```

Ou pela API:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/rag/ingest/nvidia/official `
  -ContentType "application/json" `
  -Body '{"reset_collection": true}'
```

5. Opcionalmente, ingira a base NVIDIA seed:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/rag/ingest/nvidia `
  -ContentType "application/json" `
  -Body '{"reset_collection": true}'
```

6. Busque recomendações:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/rag/search `
  -ContentType "application/json" `
  -Body '{"query": "startup usa LLM em atendimento e sofre com latência e custo de inferência", "limit": 5}'
```

7. Rode a validação local offline do MVP:

```powershell
python scripts/validate_mvp.py
```

Esse comando roda a suite Python, checa a sintaxe do JavaScript da interface e
executa `git diff --check`.

8. Rode os gates críticos de smoke e RAG quando a API e a infra estiverem no ar:

Pré-condições:

- Docker Desktop ativo.
- Qdrant e Postgres rodando.
- Migrations aplicadas.
- Base NVIDIA seed ou oficial ingerida.
- `/health` retornando `status: ok`.

Comandos recomendados:

```powershell
docker compose up -d qdrant postgres
python scripts/apply_migrations.py
python scripts/ingest_nvidia_seed.py --reset
python -m uvicorn app.main:app --reload --app-dir apps/api
```

Em outro terminal:

```powershell
python scripts/validate_mvp.py --with-smoke
python scripts/validate_mvp.py --with-rag-eval
```

O smoke valida `/health`, `/rag/search` para LLM, dados tabulares, cybersecurity,
agents/blueprints, otimização/logística e ambiente/containers, além de
`/startup/radar`, `/analysis/startup` com briefing, recomendações, histórico
Postgres e chunks da startup em `startup_evidence`.

Também é possível rodar os scripts separadamente:

```powershell
python scripts/smoke_rag.py
python scripts/evaluate_rag.py
```

Se algum serviço externo estiver fora, `/health` retorna `status: degraded` e os
scripts encerram com mensagem operacional indicando o que precisa subir.

9. Rode os testes unitários locais:

```powershell
python -m unittest discover -s apps\api\tests
```

10. Aplique migrations formais quando quiser versionar/atualizar o schema:

```powershell
python scripts/apply_migrations.py
```

11. Consulte o histórico salvo no Postgres:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/analysis/runs?limit=10
```

12. Busque evidências salvas de uma startup:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/startup/evidence/search `
  -ContentType "application/json" `
  -Body '{"query": "latência inferência modelo produção", "startup_name": "NeuralMed Brasil Demo", "limit": 5}'
```

13. Rode o radar de startups candidatas:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/startup/radar `
  -ContentType "application/json" `
  -Body '{"sector": "logistics", "focus": "rotas scheduling optimization", "limit": 5}'
```

14. Cheque freshness das fontes NVIDIA oficiais:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/rag/freshness/check `
  -ContentType "application/json" `
  -Body '{"max_sources": 8, "persist_results": true}'
```

15. Valide empiricamente as fontes de startups:

```powershell
python scripts/check_startup_sources.py --max-items 10
```

O relatório classifica cada fonte como `pass`, `warn` ou `fail` usando volume,
nomes válidos, duplicação, setor desconhecido e confiança média.

Para gerar um relatório JSON:

```powershell
python scripts/check_startup_sources.py --max-items 10 --json
```

Para usar como gate local/CI:

```powershell
python scripts/check_startup_sources.py --max-items 10 --fail-on-warning
```

## Endpoints iniciais

- `GET /health`
- `GET /nvidia/technologies`
- `POST /rag/ingest/nvidia`
- `POST /rag/ingest/nvidia/official`
- `POST /rag/freshness/check`
- `POST /rag/search`
- `POST /startups/search`
- `GET /startup/repertoire`
- `POST /startup/repertoire/refresh`
- `POST /startup/repertoire/use`
- `POST /startup/repertoire/enrich`
- `POST /startup/repertoire/review`
- `POST /analysis/startup`
- `GET /analysis/runs`
- `GET /analysis/runs/{analysis_run_id}/briefing`
- `GET /analysis/runs/{analysis_run_id}/briefing.md`
- `GET /analysis/runs/{analysis_run_id}/briefing.pdf`
- `POST /startup/evidence/search`
- `POST /startup/radar`

## Radar de startups

Com Postgres configurado, o radar usa a tabela `startup_catalog` como base ativa.
Na primeira subida, essa tabela é seedada a partir de `data/startups_br.csv`.
O CSV continua útil como seed/fallback auditável, mas a operação normal do
produto acontece no banco. O catálogo em `apps/api/app/startup_catalog.py` fica
apenas como fallback final se não houver banco nem CSV.

Para buscar uma startup pelo nome:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/startups/search `
  -ContentType "application/json" `
  -Body '{"query": "Loggi", "limit": 5}'
```

A análise manual também usa essa fonte: se você enviar apenas
`startup_name`, a API tenta resolver setor, site e descrição automaticamente
antes de rodar scraping, RAG e briefing.

Na interface web, cada card do Radar exibe uma porcentagem de oportunidade.
Ao clicar nessa porcentagem, abre um resumo em linguagem simples explicando:

- o que a porcentagem significa;
- a fórmula resumida;
- o papel de `NVIDIA fit`, fit das ferramentas, sinais públicos e risco
  wrapper;
- os valores usados para aquela startup especifica.

## Atualização de repertório

A tela Radar tem dois botões para evoluir a base de startups:

- `Atualizar repertório`: busca notícias recentes nas fontes configuradas em
  `NVIDIA_RADAR_STARTUP_DISCOVERY_SOURCE_URLS` e salva descobertas em
  `startup_discoveries` no Postgres. Por padrão, usa adapters para Startupi,
  Startups.com.br, Exame, Brazil Journal, StartSe, Endeavor e ACE, com fallback
  genérico para novas URLs jornalísticas.
- `Enriquecer descobertas`: tenta localizar site oficial a partir da notícia,
  raspa evidências públicas e melhora descrição, sinais e confiança.
- Revisão manual: quando uma descoberta fica como `needs_website_review`, a
  tela permite informar o site oficial, salvar, enriquecer e promover para a
  base ativa.
- `Usar buscas já feitas`: promove as descobertas salvas para
  `startup_catalog`, que é a base ativa usada pelo radar e pela busca por nome.

As fontes iniciais são Startupi, Startups.com.br, Exame, Brazil Journal,
StartSe, Endeavor e ACE. As descobertas são mantidas separadas antes da
importação para permitir auditoria, deduplicação e revisão de site oficial.

## Demo de análise de startup

Depois de ingerir a base oficial, rode:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/analysis/startup `
  -ContentType "application/json" `
  -Body '{
    "startup_name": "NeuralMed Brasil Demo",
    "sector": "healthcare",
    "description": "Startup brasileira usa IA generativa, LLM e dados clínicos para automatizar atendimento e triagem médica em produção no Brasil.",
    "technical_gaps": ["latência de inferência", "governança de IA", "dependência de API externa"]
  }'
```

Quando a análise é salva no Postgres, o briefing pode ser exportado em Markdown
ou PDF. O PDF usa um layout executivo simples, com cabeçalho, seções, paginação
e rodapé:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8000/analysis/runs/SEU_RUN_ID/briefing.md `
  -OutFile briefing.md

Invoke-RestMethod `
  -Uri http://localhost:8000/analysis/runs/SEU_RUN_ID/briefing.pdf `
  -OutFile briefing.pdf
```

## Próximo passo

Agora que testes de API com mocks, migrations formais, freshness com reingestão
seletiva, CI, Dockerfile, exportação Markdown/PDF, grafo formal de agentes,
Evidence Validator bloqueante, métricas de qualidade, adapters de fontes,
CORS configurável e token administrativo opcional existem, os próximos passos
são automatizar freshness por scheduler, plugar bases comerciais ou internas de
startups, refatorar os módulos maiores em rotas/componentes menores e garantir
que o ambiente de demo tenha `langgraph` instalado caso a avaliação exija
execução nominal pela biblioteca.

## Fontes NVIDIA adicionais

A base oficial também inclui itens atuais do ecossistema NVIDIA que são úteis
para startups: NVIDIA API Catalog, NVIDIA AI Blueprints, NVIDIA Nemotron,
NVIDIA Dynamo, NVIDIA Cosmos, NVIDIA cuOpt, NVIDIA AI Workbench e NVIDIA NGC.
