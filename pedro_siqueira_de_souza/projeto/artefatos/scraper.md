# Scraper Agent — guia didático

> Como o NVISION descobre startups nas fontes públicas, por que foi construído
> assim e o que cada decisão ensina. Documento de aprendizado:
> o foco é **expor a mecânica**, não escondê-la.

---

## 1. Onde o Scraper entra no pipeline

O Scraper é a **segunda estação** do grafo LangGraph, logo depois do Search
Planner:

```
query → search_planner → scraper → (extractor → classifier → ...)
```

- **Recebe** do estado (`RadarState`): `sources` (domínios escolhidos pelo
  Search Planner) e `search_terms`.
- **Entrega** ao estado: `raw_startups` — uma lista de startups **cruas**
  (ainda não estruturadas), que o Extractor Agent vai enriquecer depois.

O Scraper é deliberadamente **"burro"**: ele só *descobre e coleta*. Toda a
inteligência (estruturar, classificar, validar) fica nos agentes seguintes.
Essa separação de responsabilidades mantém cada peça simples e testável.

---

## 2. A ferramenta: Scrapling (e como difere do scraping tradicional)

Adotamos o [**Scrapling**](https://github.com/D4Vinci/Scrapling) como scraper
principal — um framework que unifica numa lib só o que normalmente exigiria
quatro ferramentas especializadas.

### A divergência: stack tradicional × Scrapling

O scraping "clássico" monta um **pipeline de ferramentas especializadas**, cada
uma resolvendo uma etapa:

| Etapa | Ferramenta tradicional | O que faz |
|---|---|---|
| Baixar HTML estático | `requests` / `httpx` | GET puro, sem executar JS |
| Renderizar JS | Playwright / Selenium | sobe um navegador e roda o JavaScript |
| Parsear o HTML | BeautifulSoup / lxml | navega o DOM e extrai os dados |
| Orquestrar crawl | Scrapy | agenda requisições, paraleliza, segue links |

O custo dessa abordagem é a **costura manual**: você decide a cada fonte se
precisa de navegador, instancia a ferramenta certa, passa o HTML de uma para a
outra, e trata anti-bot/fingerprint por conta própria.

O **Scrapling** colapsa essas quatro camadas atrás de **uma única API**, e
acrescenta o que a stack tradicional não dá de graça:

- **Três fetchers no mesmo contrato** (`Fetcher` estático, `DynamicFetcher` com
  navegador, `StealthyFetcher` anti-bot) — trocar de estático para render JS é
  trocar a função chamada, não a biblioteca nem o parsing.
- **Fingerprint TLS realista** já no fetch estático — o `requests` puro entrega
  um fingerprint de bot que muitos sites barram; o Scrapling imita um navegador
  de verdade sem precisar subir um.
- **Bypass anti-bot/Cloudflare** embutido (`StealthyFetcher`), que no fluxo
  tradicional exigiria plugins de stealth configurados à mão.
- **Seletores adaptativos**: o parsing é o mesmo objeto do fetch (sem passar o
  HTML para uma lib separada), e os seletores toleram pequenas mudanças de
  layout em vez de quebrarem no primeiro `<div>` que muda de lugar.

Em resumo: a stack tradicional **expõe cada camada** (mais controle, mais código
de cola); o Scrapling **integra as camadas** (menos código, mais robustez de
fábrica), ao custo de abstrair os detalhes de baixo nível. Por isso este
documento detalha o que acontece por baixo — para que a abstração não vire
caixa-preta. Mantivemos `playwright`/`beautifulsoup4`/`trafilatura` no
`pyproject.toml` como referência e para fases futuras (notícias/enriquecimento).

### Os três fetchers — a decisão de cada requisição

A regra de ouro: **sempre tente o mais barato primeiro.**

| Fetcher | O que faz | Custo | Quando usar |
|---|---|---|---|
| `Fetcher` (estático) | HTTP puro com fingerprint TLS | ⚡ barato | HTML já vem pronto no servidor |
| `DynamicFetcher` | abre navegador real e roda o JS | 🐢 médio | site SPA (conteúdo só aparece após o JS) |
| `StealthyFetcher` | navegador + bypass anti-bot/Cloudflare | 🐌 caro | reservado para quando uma fonte bloquear |

> Como saber qual usar? Abra o site, veja o **código-fonte** (Ctrl+U) e procure
> o dado que você quer. Está no HTML cru → estático. Só aparece no
> "Inspecionar" → dinâmico (precisa de navegador).

---

## 3. A arquitetura: adapters por fonte

Cada site tem um HTML próprio, mas o agente não pode conhecer o HTML de cada
um — senão vira um monstro impossível de manter. A solução é o **padrão de
adapter**: cada fonte tem seu arquivo, e todos expõem a **mesma interface**.

```
scraping/
├── base.py        # RawStartup (contrato de saída) + SourceAdapter (contrato)
├── fetch.py       # fetch_static / fetch_dynamic (a "costura" trocada nos testes)
├── search.py      # busca o site oficial via DuckDuckGo (usado no enriquecimento)
├── registry.py    # mapa  domínio → adapter
├── wow.py         # ┐
├── openstartups.py# │ um adapter por fonte
├── anjos.py       # │ (cada um implementa discover())
└── latitud.py     # ┘
```

E o nó do agente vive em `agents/scraper.py`.

### O contrato (`base.py`)

```python
class RawStartup(BaseModel):
    name: str
    source: str                    # domínio (ex.: "wow.ac")
    source_url: str                # página onde foi encontrada
    detail_url: str | None = None  # link de detalhe / site oficial, se houver
    sector: str | None = None      # dica de setor, quando a fonte fornece

class SourceAdapter:
    domain: str
    def discover(self) -> list[RawStartup]: ...
```

### O nó (`agents/scraper.py`)

O nó é **agnóstico de fonte**. Ele só itera:

```python
for dominio in state["sources"]:
    adapter = get_adapter(dominio)
    if adapter is None:
        continue                  # fonte sem adapter ainda → ignora com aviso
    try:
        coletadas += adapter.discover()
    except Exception:
        ...                       # erro POR FONTE: uma quebrada não derruba as outras
```

**Por que isso importa:** adicionar uma fonte nova = criar um arquivo +
uma linha no `registry.py`. O nó, o estado e o grafo **não mudam**. Provamos
isso na prática: passamos de 1 para 4 fontes sem tocar no núcleo.

---

## 4. As 4 fontes — e a "caixa de ferramentas" de scraping

A maior lição do projeto: **scraping não é uma técnica, é várias.** Cada fonte
escondia os dados de um jeito diferente e exigiu uma abordagem própria.

| Fonte | Fetcher | Sinal extraído | Técnica |
|---|---|---|---|
| **wow.ac** | dinâmico | `<img alt="Nome">` no grid | render JS + alt |
| **openstartups.net** | dinâmico | tabela `rank \| logo \| nome \| setor` | render JS + tabela (traz setor!) |
| **anjosdobrasil.net** | **estático** | `<img alt="Nome">` | HTTP puro + alt (o mais barato) |
| **latitud.com** | dinâmico | links externos → domínio | derivar nome do domínio (+ site oficial) |

Detalhe instrutivo de cada uma:

- **WOW** — provou *por que o fetcher dinâmico existe*: o HTML estático trazia
  só 4 cases; o grid completo (~194 startups) só apareceu após o JS rodar.
- **100 Open Startups** — a fonte mais rica: tabela estruturada que entrega o
  **setor de graça** (FinTechs, HealthTechs...). Por isso `RawStartup` ganhou
  o campo opcional `sector`.
- **Anjos** — provou que *nem tudo precisa de navegador*: é estático, então usa
  `fetch_static`. Reforça a regra "comece pelo barato".
- **Latitud** — uma técnica totalmente diferente: o site (Framer) não tem nome
  em texto nem API, mas os links apontam para os **sites oficiais das
  investidas**. Derivamos o nome do domínio e ganhamos o `detail_url` de
  brinde (o alvo de enriquecimento "Grupo B").

---

## 5. Os becos sem saída (lição igualmente valiosa)

Nem toda fonte é raspável. Documentar *por quê* é parte do aprendizado.

| Fonte | Por que não deu | É limite de quê? |
|---|---|---|
| **Darwin** | nomes só existem *dentro das imagens* dos logos (`alt` = `logo-33.png`) | da **fonte** — nenhum scraper de HTML resolve; só OCR |
| **Bossa Invest** | portfólio num widget JetEngine/Elementor; a API REST do WordPress expõe o post type mas com dados vazios | da **técnica** — exigiria engenharia reversa do widget |
| **StartupBase** | domínio não resolve (DNS) — descontinuado | da **fonte** — fora do ar |

> A diferença entre "limite da fonte" e "limite da técnica" é o insight central:
> a Bossa *parecia* impossível com render de HTML, mas a investigação da API
> REST mostrou que o problema era a **técnica escolhida**, não a fonte. Já a
> Darwin é impossível para qualquer scraper de HTML — o dado simplesmente não é
> texto.

### A caixa de ferramentas completa (mapa mental)

```
Renderizar HTML  → site mostra a lista no DOM            ✅ usado (4 fontes)
API JSON/REST    → SPA busca dados de um endpoint        ⚠️ investigado (Bossa)
Sitemap          → site lista páginas de detalhe         ◻️ não usado ainda
OCR              → nome só dentro de imagem               ❌ fora de escopo (Darwin)
Notícias (busca) → menções públicas a startups            ⏸️ adiado (pós-v1)
```

---

## 6. Como testar

**Ao vivo** (abre rede/navegador, imprime no terminal):

```bash
uv run python -m scraping.wow           # dinâmico
uv run python -m scraping.openstartups  # dinâmico, com setor
uv run python -m scraping.anjos         # estático
uv run python -m scraping.latitud       # dinâmico, com site oficial
```

**Offline** (sem rede, HTML salvo nas fixtures — rápido e determinístico):

```bash
uv run pytest tests/test_scraper.py -v
```

### A mecânica dos testes (mesma ideia do FakeLLM)

Os testes nunca tocam a rede. Eles trocam `fetch_static`/`fetch_dynamic` por
uma função que devolve um `Selector` montado a partir de um HTML salvo em
`tests/fixtures/`. O adapter roda a **mesma lógica de parsing**, sem navegador:

```python
monkeypatch.setattr("scraping.wow.fetch_dynamic", lambda *a, **k: Selector(html))
```

Isso só é possível porque os adapters **nunca chamam o Scrapling direto** —
sempre passam por `scraping/fetch.py`. Essa indireção é a "costura" (seam) que
torna o código testável.

> **Aprendizado real:** a fixture nunca é igual ao site. O HTML salvo da WOW
> tinha 40 nomes limpos; o site ao vivo trouxe 194, com ruído de UI
> (`"Ícone Fechar Menu"`) que o filtro inicial não pegava. Só o teste *ao vivo*
> revela isso — por isso mantemos as duas formas de rodar.

---

## 7. Limitações conhecidas do v1 (trabalho futuro)

- **Filtros de ruído são heurísticos e frágeis.** Cada adapter filtra ruído por
  palavra-chave (`logo`, `ícone`, nome de arquivo...). O jeito robusto seria
  escopar num container específico do grid — fica para uma evolução.
- **Nomes ainda crus.** O nome derivado de domínio (Latitud) vem minúsculo
  (`salvy`); o slug da WOW pode não casar com o nome do grid. Tudo bem: o
  **Extractor** normaliza depois.
- **`raw_startups` é sobrescrito, não acumulado.** Idempotente de propósito —
  re-executar (ex.: no loop de baixa confiança do Evidence Validator) recoleta
  do zero.
- **Sem persistência ainda.** O resultado vive no `RadarState` (memória). Salvar
  no PostgreSQL e mostrar no frontend são passos das próximas semanas.
- **Rate limiting / robots.txt** ainda dependem do comportamento padrão do
  Scrapling; um controle explícito por domínio entra quando o volume crescer.

---

## 8. Resumo de uma frase

> O Scraper descobre startups em fontes heterogêneas usando um padrão de
> adapters intercambiáveis sobre o Scrapling, escolhendo a técnica certa
> (HTML estático, render JS, link externo, ...) para cada fonte — e o que ele
> **não** consegue raspar é documentado, porque entender o limite também é
> aprendizado.
