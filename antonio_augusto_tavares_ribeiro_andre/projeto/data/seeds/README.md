# Seeds de fontes (§9) — sourcing de startups AI-native BR

Listas de **fontes** usadas pelo sourcing (F1): de onde descobrir startups brasileiras
AI-native e quais canais podem ser coletados. Consumidas pelo `search_planner` (F2.3),
pelo crawler Scrapy (F1.6) e pela política de ToS (F1.15).

## Política (decisão travada — F1.15)

`robots.txt ≠ Termos de Uso`. Por isso cada fonte carrega uma **decisão explícita**:

- **Priorizar** sites/blogs/carreiras **oficiais** das startups + **notícias** (§9.2) → `policy: allow`.
- Diretórios/plataformas de dados (§9.1: Distrito, Cubo, StartSe, 100 Open Startups…) **só**
  com API pública/permissão → `policy: api_only`; sem isso, **não coletar** → `policy: deny`.
- Fonte sem permissão clara **não é coletada**. A allowlist/denylist aqui é a **intenção**
  declarada; a checagem vinculante (robots + rate limit) roda em runtime (F1.8) e a base legal
  por evidência é registrada na tabela `evidence` (F1.13).

> ⚠️ ToS/robots mudam. As anotações refletem uma avaliação de **2026-06**; reavaliar antes de
> coletar. Na dúvida, trate como `deny`.

## Schema de cada item (`sources:` em cada `.yaml`)

| campo | valores | significado |
|---|---|---|
| `id` | slug único | identificador estável |
| `name` | texto | nome da fonte |
| `url` | http(s) | URL canônica |
| `type` | `directory` \| `news` \| `program` | §9.1 diretório · §9.2 notícia · descoberta (acelerada/edital/comunidade) |
| `country` | `BR` \| `GLOBAL` | escopo geográfico |
| `policy` | `allow` \| `api_only` \| `deny` | decisão de coleta |
| `robots` | `allow` \| `disallow` \| `unknown` | leitura do `robots.txt` |
| `tos_scraping` | `permitted` \| `prohibited` \| `api_only` \| `unknown` | postura dos Termos de Uso |
| `legal_basis` | texto | base p/ coleta (dado público / interesse legítimo / API) |
| `notes` | texto | observações |

Arquivos: `directories.yaml` (§9.1) · `news.yaml` (§9.2) · `programs.yaml` (descoberta/§11).
Loader: `packages/scraping/seeds.py` (`load_sources()`, `allowlist()`, `denylist()`).
