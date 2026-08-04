# Firecrawl Skill — NVIDIA Startup AI Radar

## Quando usar

Use esta skill sempre que for implementar, modificar ou depurar integrações com Firecrawl para busca web (Search) e extração de páginas (Scrape).

## Stack atual

| Provider | Uso | Classe |
|---|---|---|
| Firecrawl Search | Buscar startups brasileiras na web | `FirecrawlSearchAdapter` |
| Firecrawl Scrape | Extrair conteúdo de páginas de startups | `FirecrawlPageAdapter` |

## Dependências

- Pacote Python: `firecrawl-py` (já instalado no venv)
- SDK: `firecrawl.Firecrawl` — cliente unificado v2

## Configuração

Todas as variáveis vão no `.env` na raiz do repositório (gitignorado):

```env
RADAR_ENABLE_EXTERNAL_PROVIDERS=true
RADAR_SEARCH_PROVIDER=firecrawl
RADAR_PAGE_PROVIDER=firecrawl
FIRECRAWL_API_KEY=fc-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Safety Switch

Se `RADAR_ENABLE_EXTERNAL_PROVIDERS=false` (padrão), os adapters do Firecrawl levantam `ExternalProviderDisabledError` — não fazem chamadas de rede.

## API Key

- Criar conta em: https://www.firecrawl.dev/
- No dashboard, habilitar: **Scrape**, **Search**, **Crawl**
- API key fica visível após login
- **Nunca comitar a key no repositório** — usar `.env` local

## Como testar a integração

```powershell
$env:RADAR_ENABLE_EXTERNAL_PROVIDERS='true'
$env:FIRECRAWL_API_KEY='fc-...'
cd ai-agent-system
python -m pytest tests/test_provider_factory.py tests/test_provider_preflight.py -v
```

Teste end-to-end real:

```powershell
$env:PYTHONPATH='src'
$env:RADAR_ENABLE_EXTERNAL_PROVIDERS='true'
$env:RADAR_SEARCH_PROVIDER='firecrawl'
$env:RADAR_PAGE_PROVIDER='firecrawl'
$env:FIRECRAWL_API_KEY='fc-...'
python -c "
from radar.graph.builder import build_graph
result = build_graph().invoke({'query': 'startup brasileira de IA', 'collection_attempts': 0})
print('Sources:', len(result['sources']))
print('Classification:', result.get('classification'))
"
```

## Limitações conhecidas

- **Free tier**: 500 páginas/mês; alguns sites bloqueiam (ex: Bloomberg)
- Firecrawl pode não renderizar JavaScript pesado em certos sites → complementar com Playwright
- O resultado de `scrape_url` retorna `Document` (pydantic model), não dict — usar `.markdown`, `.raw_html`, `.metadata.title`

## Contrato FirecrawlSearchAdapter.search()

```python
client = Firecrawl(api_key=...)
response = client.search(query=plan.query, limit=10)
# response.web -> list[SearchResultWeb] | None
# response.news -> list[SearchResultNews] | None
# SearchResultWeb: .url, .title, .description
# SearchResultNews: .url, .title, .snippet, .date
```

## Contrato FirecrawlPageAdapter.fetch()

```python
client = Firecrawl(api_key=...)
doc = client.scrape_url(url=..., formats=["markdown", "rawHtml"], only_main_content=True)
# doc.markdown -> str
# doc.raw_html -> str
# doc.metadata.title -> str (via pydantic model)
```

## Arquivos relevantes

- `src/radar/scraping/adapters.py` — implementação dos adapters
- `src/radar/scraping/provider_factory.py` — fábrica que seleciona o adapter
- `src/radar/scraping/provider_preflight.py` — diagnóstico offline
- `src/radar/settings.py` — RadarSettings com env vars
- `.env` (gitignorado) — configuração local
