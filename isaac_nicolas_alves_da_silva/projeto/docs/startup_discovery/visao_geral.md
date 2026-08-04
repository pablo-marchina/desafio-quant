# Modulo Startup Discovery - Visao Geral

Atualizado em 01/07/2026.

## 1. Papel no produto

O modulo `startup_discovery` alimenta o topo do funil. Em vez de depender apenas
de URLs digitadas manualmente, ele consulta hubs publicos, cria candidatos e
submete URLs confiaveis para o pipeline de `url_ingestion_jobs`.

O discovery nao classifica startups, nao gera recomendacoes e nao cria verdade
final. Ele so descobre candidatos rastreaveis.

## 2. Fontes que rodam hoje

As fontes executadas ficam em `HUB_SOURCES`:

| Fonte | Modo | Extrator |
|---|---|---|
| InovAtiva Brasil | url | `inovativa` |
| Abstartups | url | `abstartups` |
| 100 Open Startups | name | `open_startups` |

O catalogo mais amplo fica em `DISCOVERY_SOURCE_CATALOG` e em
`docs/startup_discovery/source_catalog.md`. Fontes `planned` aparecem na
documentacao, mas nao rodam ate terem extrator e teste.

## 3. Fluxo

```txt
POST /startup-discovery/runs
  -> cria DiscoveryRun
  -> percorre HUB_SOURCES
  -> modo url: extrai URLs/perfis diretamente
  -> modo name: extrai nomes/ranking/categoria
  -> salva candidatos quando necessario
  -> enriquece candidatos por Tavily quando configurado
  -> auto-submete candidatos confiaveis como url_ingestion_jobs
  -> registra metricas do run
```

Consulta:

```txt
GET /startup-discovery/runs/{run_id}
GET /startup-discovery/runs/{run_id}/candidates
```

## 4. Guardrails

- limite por rodada via `STARTUP_DISCOVERY_MAX_PER_RUN`;
- falha de um hub nao derruba os demais;
- consultorias/prestadores sao rejeitados quando ha sinal forte de servico sem
  sinal de produto;
- fontes planejadas nao entram no runtime;
- URLs descobertas sempre passam pelo pipeline normal antes de virarem resultado
  executivo.

## 5. Estrutura

```txt
startup_discovery/
  presentation/     rotas REST
  application/      RunStartupDiscovery, GetDiscoveryRun, ports
  domain/           DiscoveryRun, StartupDiscoveryCandidate, hub_registry
  infrastructure/   hub_extractors/, enrichment/, orchestration_adapters/
  factories/        composicao de extratores e adapters
  tests/            unitarios do run, name discovery, scheduler, registry
```

## 6. Testes recentes

```txt
apps/api/src/modules/startup_discovery/tests/unit: 25 passed
```

## 7. Proximos passos

1. Promover novas fontes do catalogo uma por vez.
2. Persistir URLs descartadas e motivo.
3. Melhorar ranking de candidatos antes da submissao.
4. Expor historico de discovery no frontend com filtros.
5. Rodar scheduler/cron apenas com guardrails de volume.
