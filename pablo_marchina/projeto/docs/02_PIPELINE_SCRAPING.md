# 02 — Pipeline de Scraping e Coleta Pública

## Responsabilidade deste documento

Este documento descreve apenas a pipeline de busca/coleta pública: planejamento de fontes, governança, crawling/fetching, parsing, deduplicação, métricas e output bruto para extração. Ele não descreve RAG NVIDIA, recomendação ou frontend.

## Objetivo da pipeline de scraping

A pipeline de scraping deve coletar o máximo de informação pública útil para responder ao case:

- a startup realmente usa IA?
- o uso de IA é profundo ou superficial?
- há sinais de AI-native service?
- há produto, workflow, dados proprietários, clientes, funding, founders e stack?
- há lacunas que a NVIDIA pode resolver?

O output ideal não é “página baixada”; é **evidência pública governada**, rastreável e pronta para extração/validação.

## Entrada do subsistema

O scraping recebe do workflow:

```json
{
  "startup_name": "Nome da startup",
  "website_url": "https://site-oficial.com",
  "run_id": "workflow-ou-analysis-run-id",
  "search_plan": []
}
```

Quando `search_plan` ainda não existe, o nó `plan_search` cria o plano. Quando o review solicita mais evidência, `plan_missing_information` acrescenta fontes específicas para lacunas.

## Saída do subsistema

```json
{
  "raw_evidence": [
    {
      "url": "https://...",
      "source_url": "https://...",
      "text": "texto limpo extraído",
      "source_type": "official_site|news|directory|blog|job_post|founder_profile",
      "source_category": "official_website|funding_news|ecosystem_directory|jobs|media",
      "source_id": "...",
      "fetched_at": "ISO-8601",
      "status_code": 200,
      "content_hash": "...",
      "latency_ms": 123,
      "content_bytes": 12345,
      "extraction_status": "..."
    }
  ],
  "source_errors": [],
  "collection_metrics": {}
}
```

O subsistema termina aqui. A transformação em `startup_profile` e `validated_evidence` pertence a extração/validação posterior.

## Arquivos e módulos principais

| Arquivo/módulo | Responsabilidade |
|---|---|
| `src/agents/search_planner.py` | cria plano adaptativo de fontes |
| `src/agents/scraper_agent.py` | executa coleta simples ou governada |
| `src/scraping/http_collector.py` | coletor HTTP governado de produção |
| `src/scraping/fetcher.py` | fetch HTTP com `httpx` |
| `src/scraping/parser.py` | extração de texto limpo |
| `src/scraping/source_registry.py` | fontes habilitadas para produção |
| `src/scraping/domain_rate_limiter.py` | limite por domínio |
| `src/scraping/rate_limit_policy.py` | políticas de rate limit |
| `src/scraping/cache.py` | cache de coleta |
| `src/scraping/circuit_breaker.py` | proteção contra fontes instáveis |
| `src/scraping/content_quality.py` | qualidade de conteúdo |
| `src/scraping/fuzzy_dedup.py` | deduplicação semântica/fuzzy |
| `src/scraping/playwright_collector.py` | fallback browser/JS quando configurado |
| `src/scraping/firecrawl_collector.py` | coletor opcional Firecrawl quando API key existe |
| `src/scraping/rss_collector.py` | RSS |
| `src/scraping/pdf_collector.py` | PDFs |
| `src/scraping/youtube_collector.py` | vídeos/transcrições |
| `src/scraping/github_collector.py` | sinais de stack/código quando configurado |
| `src/scraping/scrapers/*` | scrapers específicos de diretórios/ecossistema |
| `src/sourcing/adaptive_source_planner.py` | cálculo de expected information gain e stop condition |

## Tecnologias usadas

| Tecnologia | Uso |
|---|---|
| `httpx` | fetching HTTP/2, timeout granular, connection pooling |
| BeautifulSoup | fallback de extração HTML |
| `trafilatura` | extração de texto principal |
| `selectolax` | parsing rápido |
| `readability-lxml` | extração article/readability |
| Playwright | páginas JS/dinâmicas quando coletor ativado |
| Firecrawl | extração/crawl externa opcional quando API key existe |
| Crawl4AI | dependência disponível para crawling/markdown limpo quando promovida |
| PyMuPDF/MarkItDown | leitura/extração de PDF quando coletor PDF ativado |
| feedparser | RSS |
| youtube-transcript-api | transcrições públicas de vídeos |
| rapidfuzz | deduplicação fuzzy |
| fake-useragent | user-agent realista |
| tenacity | retry/backoff |
| tldextract | normalização de domínio |
| diskcache | cache local |
| Pydantic | schemas de request/result |

## Classificação de fontes

O planner separa explicitamente:

| Tipo | Conta como fonte oficial? | Uso |
|---|---:|---|
| `official_site` | Sim | domínio provável ou website oficial da própria startup |
| `blog` | Parcialmente, se domínio da startup | sinais técnicos/produto |
| `job_post` | Parcialmente, se domínio da startup | stack, maturidade, contratação |
| `news` | Não | validação independente/funding/tração |
| `directory` | Não | ecossistema, aceleradoras, diretórios |
| `founder_profile` | Não | founders/experiência pública |
| `search_api` | Não | descoberta de URLs candidatas, nunca evidência direta |

Regra crítica:

> Diretórios, aceleradoras, resultados de busca e portais de notícia não podem satisfazer o gate de fonte oficial da startup.

## Planejamento adaptativo de fontes

`build_search_plan(startup_name)` gera candidatos com:

- URL;
- `source_type`;
- `is_official_source`;
- razão de coleta;
- expected information gain;
- marginal utility;
- custo estimado;
- latência estimada;
- compliance risk;
- fórmula de decisão.

### Fórmula de expected information gain

A fórmula registrada em `source_decision_trace` é:

```text
EIG = (authority*.25 + freshness*.15 + independence*.15 + novelty*.15
       + coverage*.15 + marginal*.15)
      - risk*.25 - cost*.10 - latency*.05
```

Interpretação:

- `authority`: confiabilidade esperada da fonte;
- `freshness`: probabilidade de conter informação recente;
- `independence`: independência em relação à startup;
- `novelty`: ganho esperado por ainda não cobrir aquele tipo de informação;
- `coverage`: cobertura esperada de categorias de fonte;
- `marginal`: evidência nova esperada;
- `risk`: risco de compliance/robots/login/paywall;
- `cost`: custo financeiro/API;
- `latency`: custo operacional.

## Estratégia de fontes

### Fontes oficiais prováveis

O planner tenta domínios derivados do nome:

```text
https://startup.com.br
https://www.startup.com.br
https://startup.com
https://www.startup.com
```

E recebe o `website_url` cadastrado quando disponível.

### Fontes independentes

Incluem portais, notícias, diretórios e ecossistema:

- StartSe;
- Distrito;
- Latitud;
- Cubo;
- ACE;
- Bossa;
- InovAtiva;
- Endeavor;
- Abstartups;
- Darwin;
- Liga Ventures;
- Open Startups;
- Exame;
- Valor;
- NeoFeed;
- Brazil Journal;
- Startups.com.br;
- PEGN;
- Mobile Time;
- Meio & Mensagem.

### Fontes técnicas

Quando disponíveis/configuradas:

- blog;
- engineering blog;
- careers/jobs;
- GitHub;
- docs;
- PDFs técnicos;
- vídeos/transcrições.

## Coleta governada

O caminho produtivo é `collect_governed_sources`. Ele usa:

- source records habilitados;
- search plan adaptativo;
- website oficial explícito;
- robots.txt;
- rate limit;
- compliance checks;
- cache;
- retries;
- circuit breaker;
- dedup;
- parser configurado;
- métricas de coleta.

## Compliance e bloqueios

Uma fonte pode ser bloqueada por:

- URL inválida;
- login/signin;
- paywall;
- robots.txt;
- alta taxa de falha;
- domínio instável;
- fonte não `production_enabled`;
- `production_blockers` no registry;
- tipo de coletor indisponível;
- API key ausente para coletor opcional.

## Robots.txt

O coletor possui `RobotsChecker` com:

- User-agent;
- Allow/Disallow;
- Crawl-delay;
- regra de caminho mais específico;
- cache de 24h.

Em produção, `robots_required=True` é usado nos source records críticos.

## Rate limit

A política considera:

- domínio;
- requests por segundo;
- crawl-delay;
- limite por source record;
- concorrência;
- backoff calibrado.

A intenção é maximizar evidência útil sem violar limites ou gerar comportamento agressivo.

## Fetching HTTP

`src/scraping/fetcher.py` usa:

- `httpx.Client` com HTTP/2;
- timeout padrão;
- redirect follow;
- connection pooling;
- user-agent;
- proxy via env quando existe;
- headers condicionais `If-None-Match` e `If-Modified-Since`;
- detecção de status 304;
- captura de ETag/Last-Modified;
- warning de content-type.

## Parsing de texto

Ordem de parser:

1. `readability-lxml`;
2. `trafilatura`;
3. `selectolax`;
4. BeautifulSoup.

Regra:

- o primeiro parser que gera texto suficientemente longo é usado;
- fallback ocorre automaticamente;
- conteúdo vazio gera erro de extração.

## Deduplicação

A pipeline deduplica por:

- URL;
- hash de conteúdo;
- duplicate result no collector;
- fuzzy dedup para textos muito similares.

Saída duplicada pode ser registrada com `extraction_status=duplicate_skipped` para auditoria.

## Coleta adaptativa por lacunas

Quando human review retorna `request_more_evidence`, o grafo chama `plan_missing_information`. Esse nó adiciona fontes direcionadas:

| Lacuna | Fonte alvo |
|---|---|
| founders/company profile | `/about`, `/sobre` |
| clientes/cases | `/customers`, `/cases` |
| profundidade técnica | `/blog`, `/engineering` |
| stack/equipe | `/careers`, `/jobs` |
| funding/notícias | portais de notícia |

Esse comportamento substitui o loop incorreto de voltar direto para score sem novas evidências.

## Métricas de coleta

O coletor produz:

- `attempted_sources_count`;
- `fetched_sources_count`;
- `blocked_sources_count`;
- `failed_sources_count`;
- `robots_blocked_count`;
- `compliance_blocked_count`;
- `duplicate_count`;
- `total_latency_ms`;
- `median_latency_ms`;
- `total_content_bytes`;
- `extraction_success_rate`;
- `fetch_success_rate`.

## Gates mínimos recomendados

Para considerar que uma startup está pronta para downstream:

```text
mínimo 5 fontes tentadas
mínimo 3 fontes úteis
mínimo 2 ou 3 categorias de fonte
mínimo 1 fonte oficial real
máximo 25% erro de coleta
zero fonte genérica contada como oficial
```

Esses valores são configuráveis via `.env`:

```env
SCRAPING_MIN_RAW_EVIDENCE=5
SCRAPING_MIN_DISTINCT_SOURCES=3
SCRAPING_MIN_SOURCE_CATEGORIES=2
SCRAPING_MIN_OFFICIAL_SOURCES=1
SCRAPING_MAX_ERROR_RATE=0.25
```

## Output esperado para o case

A coleta deve tentar obter informação para:

- descrição da empresa;
- produto;
- setor;
- clientes/cases;
- funding/investidores;
- founders;
- sinais de IA;
- sinais AI-native;
- sinais de wrapper LLM;
- stack técnica;
- vagas e maturidade de engenharia;
- sinais de escala;
- riscos ou contradições.

## O que não deve acontecer

- usar Google Search HTML como evidência;
- contar diretório como `official_site`;
- emitir recomendação downstream com apenas uma fonte fraca;
- ignorar robots/paywall/login;
- esconder erros de fonte;
- coletar fonte opcional sem API key configurada;
- usar dados fake/mock em produção.

## Validação específica

```bash
pytest -q tests/unit/test_scraper_agent.py
pytest -q tests/unit/test_adaptive_source_planner.py
pytest -q tests/unit/test_source_registry.py
pytest -q tests/integration/test_http_collector_governed.py
pytest -q tests/evals/test_scraping_baseline.py
```

## Critérios de aceite

| Critério | Aceite |
|---|---|
| Planejamento | Search plan contém fontes oficiais, independentes e técnicas |
| Fonte oficial | Apenas domínio da startup ou canal próprio conta como oficial |
| Governança | Robots/rate limit/compliance ativos |
| Parsing | Texto limpo extraído com fallback |
| Erros | Erros aparecem em `source_errors`, não são ocultados |
| Métricas | Collection metrics preenchidas |
| Adaptividade | `request_more_evidence` gera fontes novas e específicas |
| Output | `raw_evidence` contém texto, URL, tipo, hash e timestamp |
