# Roadmap do Modulo Scraping

O modulo `scraping` coleta conteudo publico da web, valida tecnica e
textualmente, decide entre aceitar/revisar/descartar, e escalona para LLM ou
agente quando a validacao deterministica nao e suficiente.

Ele nao limpa/normaliza texto (isso e `ingestion`) e nao decide se a
evidencia e relevante para uma startup especifica alem do que a validacao
evidencial basica ja cobre.

---

## Objetivo do Modulo

```txt
URL -> estrategia de coleta -> validacao deterministica -> quality_score ->
ACCEPT | LLM_REVIEW | AGENT_REVIEW | FALLBACK | REJECT
```

---

## Estado atual

```txt
V8 - modulo completo (ver CLAUDE.md, secao "Scraping module")
```

Nao ha V9 planejada como feature nova — o modulo cobre hoje toda a
pipeline V1-V8 descrita no `CLAUDE.md` (BS4 -> Playwright -> Trafilatura,
validacao deterministica + semantica + agente, source_type para fontes
curadas). Este documento existe para registrar **tecnologias candidatas**
sobre fraquezas reais encontradas lendo o codigo, nao para inventar uma
nova versao sem necessidade comprovada (regra 8 do `CLAUDE.md`).

Documentos historicos de versao: `docs/scraping/scraper_v1.md` ate
`docs/scraping/scraper_v8_agente_investigacao.md`; visao consolidada em
`docs/scraping/modulo_scraping_atualizado.md`.

---

## Dividas tecnicas

Ver inventario consolidado: `docs/geral/dividas_tecnicas.md`.

Itens deste modulo: DT-01 (Firecrawl), DT-02 (circuit breaker), DT-03 (logar quality_score), DT-04 (timeout por source_type), DT-05 (heuristica captcha).
Itens fechados deste modulo: DT-F01 (cache por URL, 23/06/2026), DT-F07 (word boundary no match, 23/06/2026).

**Cache por URL — concluido em 23/06/2026:**
`ScrapingResultRepository.get_recent_by_url(url, since=...)` (novo, Postgres
+ in-memory); `CreateScrapingJob.execute()` consulta esse cache primeiro
(janela de `SCRAPING_RESULT_CACHE_TTL = timedelta(days=3)`,
`domain/policies.py`) e, se achar um resultado aprovado recente, completa o
job direto (`job.start()` + `job.complete(cached.id)`) sem despachar para a
fila. TTL unico de 3 dias para todo `source_type`, sem diferenciacao —
decisao do usuario. Efeito colateral corrigido de graca: reenviar a mesma
URL hoje em dia podia falhar com `DuplicateScrapingContentError` (unique
constraint em `content_hash`) se o conteudo viesse byte-identico; o cache
evita chegar nesse caminho.

---

## Descoberta de startups ("Radar" de verdade) - V1 ENTREGUE
```txt
docs/decisoes_pendentes.md, secao 4 — "vou colocar isso o teto acho valido
pensarmos para demo algo gratuito, somente provar que o projeto consegue
fazer"
```

Hoje toda `Startup` nasce de uma URL submetida manualmente. Decidido
construir um mecanismo de descoberta automatica, com teto de custo
**zero/gratuito** (sem API paga) e proposito explicito de **provar o
conceito pra demo**, nao virar um crawler de produção.

As fontes fornecidas se dividem em 2 tipos com desenho tecnico diferente:

**Descoberta de startups novas** (hubs/diretorios — cada um lista MUITAS
startups, exige um passo extra de extrair links individuais antes de
alimentar o pipeline existente — diferente do
`NvidiaKnowledgeSourceRegistry`, que ja aponta direto pra URL final):

```txt
StartSe          https://www.startse.com/
Distrito          https://distrito.me/
Latitud           https://www.latitud.com/
Cubo Itau         https://cubo.network/
ACE Startups      https://acestartups.com.br/
Endeavor Brasil   https://endeavor.org.br/
Abstartups        https://abstartups.com.br/
Bossa Invest      https://bossainvest.com/
Anjos do Brasil   https://www.anjosdobrasil.net/
Darwin Startups   https://www.darwinstartups.com/
Liga Ventures     https://liga.ventures/
WOW Aceleradora   https://www.wow.ac/
InovAtiva Brasil  https://www.inovativabrasil.com.br/
100 Open Startups https://www.openstartups.net/
```

**Enriquecimento de startup ja conhecida** (nao descobrem startup nova; ja
encaixam na "chain de enriquecimento" do Search Planner Agent, ver
`docs/agents/roadmap_agentes.md` e `docs/orchestration/roadmap_orchestration.md`):

```txt
site oficial da startup
blog oficial da startup
pagina de carreiras da startup
perfis publicos de founders
```

Entregaveis (descoberta, escopo de demo — gratuito, prova de conceito):

- extrator de links por hub: cada um dos 14 hubs provavelmente tem
  estrutura de HTML diferente — viavel comecar com 2-3 hubs (ex:
  Abstartups, InovAtiva Brasil, que tendem a ter listagem mais simples) em
  vez dos 14 de uma vez;
- cada link extraido entra no pipeline existente
  (`CreateScrapingJob`/`url_ingestion_jobs`) exatamente como uma URL
  submetida manualmente — nenhuma mudanca no pipeline de scraping/
  ingestion/embeddings/analise, so a origem da URL muda;
- teto de custo diario (ex: "no maximo N startups novas descobertas por
  dia") — decisao consciente antes de ligar, nao depois (ver
  `docs/decisoes_pendentes.md`, secao 4);
- sem API de busca paga (Tavily etc.) nesta entrega — fica reservada pra
  chain de enriquecimento (que e' sobre startup ja conhecida, escopo
  diferente).

V1 entregue no modulo `startup_discovery` com InovAtiva Brasil, Abstartups e 100 Open Startups. Ver `docs/startup_discovery/roadmap_startup_discovery.md`. Continua futuro expandir para os demais hubs e integrar a chain de enriquecimento por busca.
