# Startup Discovery V1 — Descoberta em hubs públicos

## Objetivo

Descobrir URLs de startups em hubs públicos e injetá-las no pipeline de análise.

## O que entregou (25/06/2026)

- `DiscoveryRun` (entidade: `PENDING → RUNNING → COMPLETED | FAILED`; campos
  `hubs_processed`, `urls_found`, `jobs_submitted`, `error_message`, timestamps).
- `HubSource` + `HUB_SOURCES` (3 hubs: InovAtiva Brasil, Abstartups,
  100 Open Startups).
- Porta `HubLinkExtractor` (mantém httpx/BS4 fora da camada de aplicação).
- `RunStartupDiscovery` — cria o run, itera hubs, extrai URLs, submete cada uma
  como `url_ingestion_job` (`source_type=startup_evidence`); best-effort por hub
  (falha de um não cancela os outros; falha total só se TODOS falharem); limite
  `STARTUP_DISCOVERY_MAX_PER_RUN` (default 20).
- `BaseHubLinkExtractor` + 3 extratores concretos (estratégia: links externos
  diretos → fallback para perfis internos com extração de website).
- `PostgresDiscoveryRunRepository` + migration `c9d3e7f0a4b8`
  (`startup_discovery_runs`).
- Rotas: `POST /startup-discovery/runs`, `GET /startup-discovery/runs/{run_id}`.

Run síncrono (fetches de hub são I/O barato; timeout 30s por hub). 8 testes unit.

## Limite

Seletores CSS estimados (constantes no topo de cada extrator); se o markup dos
hubs mudar, basta ajustar a constante. O extrator de 100 Open Startups tem filtro
extra (só aceita URLs com ponto no último segmento) para evitar links internos.

Versão atual do módulo: **Startup Discovery V1** (ver `../visao_geral.md`).
