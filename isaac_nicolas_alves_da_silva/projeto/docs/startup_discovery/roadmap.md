# Roadmap do Modulo Startup Discovery

Atualizado em 01/07/2026.

## Objetivo

```txt
hubs publicos -> candidatos -> url_ingestion_jobs -> pipeline completo
```

O modulo deve aumentar cobertura sem virar crawler amplo, caro ou pouco
auditavel.

## Entregue

### V1 - hubs publicos por URL

- `POST /startup-discovery/runs`
- `GET /startup-discovery/runs/{run_id}`
- tabela `startup_discovery_runs`
- extratores `httpx` + BeautifulSoup;
- best-effort por hub;
- submissao para `url_ingestion_jobs`.

### V2 - discovery por nome + enriquecimento

- `HubSource.extraction_mode = "url" | "name"`;
- 100 Open Startups como fonte por nome;
- `startup_discovery_candidates`;
- enriquecimento por Tavily quando `TAVILY_API_KEY` existe;
- auto-submit quando a confianca do site oficial passa do limiar;
- `GET /startup-discovery/runs/{run_id}/candidates`.

### V2.1 - catalogo de fontes

- `DISCOVERY_SOURCE_CATALOG`;
- `docs/startup_discovery/source_catalog.md`;
- testes garantindo que fontes `planned` nao entram no runtime.

## Fontes

Implementadas:

```txt
InovAtiva Brasil
Abstartups
100 Open Startups
```

Planejadas:

```txt
Distrito
Latitud
Startups.com.br
Endeavor Brasil
Cubo Itau
BrazilLAB
Sebrae Startups
```

## Proximas evolucoes

1. Persistir descartes:
   - URL duplicada;
   - rede social pessoal;
   - diretorio generico;
   - consultoria sem produto;
   - baixa confianca de site oficial.
2. Criar score antes de submeter candidatos.
3. Promover uma fonte planejada por vez, sempre com extrator e teste.
4. Melhorar tela `/discovery` com historico, falhas por hub e candidatos.
5. Rodar scheduler semanal somente apos metricas basicas ficarem visiveis.

## Fora de escopo

- crawling amplo sem hub de origem;
- importar resultados de busca como verdade final;
- bases pagas sem contrato;
- discovery substituindo scraping, evidence validation ou revisao humana.

Documento operacional: `docs/startup_discovery/cron_discovery_hubs.md`.
