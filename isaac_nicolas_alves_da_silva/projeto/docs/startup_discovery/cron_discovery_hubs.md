# Cron de descoberta em hubs de startups

Atualizado em 29/06/2026.

Este documento define como rodar uma descoberta recorrente de startups em hubs
publicos, com foco em startups brasileiras, sem misturar esse fluxo com o
golden dataset de avaliacao.

## 1. Objetivo

Transformar hubs publicos em entrada continua para o radar:

```txt
hubs publicos -> candidatos -> dedupe -> ranking -> url_ingestion_jobs -> analise -> revisao
```

O cron deve descobrir candidatos. Ele nao deve criar verdade final sobre uma
startup sem passar pelo pipeline e pela revisao.

## 2. Principio central

```txt
Discovery gera candidatos.
Url ingestion gera evidencias.
Recommendations gera hipoteses.
Revisao humana valida o resultado.
```

Por isso, o cron nao substitui:

- scraping;
- validacao de evidencia;
- classificacao AI-native / AI-enabled / non-AI;
- recomendacoes NVIDIA;
- revisao humana;
- golden dataset.

## 3. Fluxo recomendado

```txt
Scheduler
  -> POST /startup-discovery/runs
  -> RunStartupDiscovery
  -> HubLinkExtractor por hub
  -> StartupCandidate(name, website_url, hub_profile_url, descricao curta)
  -> normalizacao e deduplicacao de candidatos por website_url
  -> limite por STARTUP_DISCOVERY_MAX_PER_RUN
  -> cria url_ingestion_jobs
  -> worker processa URL ponta a ponta
```

O endpoint atual e:

```txt
POST /startup-discovery/runs
GET  /startup-discovery/runs/{run_id}
```

O fluxo pesado continua no worker de `url_ingestion`. O hub nao classifica a
startup; ele so tenta descobrir nome, site oficial e origem para o cadastro
inicial.

Campos atuais do candidato:

| Campo | Uso |
|---|---|
| name | nome exibido no hub, quando disponivel |
| website_url | site oficial enviado para analise automatica |
| hub_profile_url | perfil/listagem de origem para auditoria |
| short_description | descricao curta do perfil, quando disponivel |
| declared_sector | setor declarado, reservado para hubs que expuserem esse dado |

Esses campos ficam persistidos em `startup_discovery_submissions`, ligados ao
`startup_discovery_run` e ao `url_ingestion_job` criado.

## 4. O que entra no cron

O catalogo versionado de fontes fica em:

```txt
docs/startup_discovery/source_catalog.md
```

Importante: o catalogo inclui fontes planejadas. O runtime atual usa somente
fontes registradas em `HUB_SOURCES`, que possuem extrator implementado.

Fontes prioritarias:

| Prioridade | Hub/fonte | Motivo |
|---|---|---|
| Alta | InovAtiva Brasil | foco Brasil, startups early-stage |
| Alta | Abstartups | ecossistema brasileiro |
| Alta | 100 Open Startups | sinais de tracao e corporate-startup |
| Media | Distrito | base brasileira de mercado/startups |
| Media | Latitud | startups e founders LATAM/Brasil |
| Media | Startups.com.br | noticias e perfis |
| Media | Endeavor Brasil | empresas com tracao |
| Baixa | BrazilLAB | bom sinal para govtechs e casos B2G/B2B |
| Baixa | Sebrae Startups | cobertura regional e programas de aceleracao |
| Baixa | Cubo/Itaú, hubs corporativos | bom sinal, mas pode ter paginas menos estruturadas |

Fora do escopo inicial:

- redes sociais pessoais;
- listas genericas sem website oficial;
- bases pagas sem contrato;
- crawling amplo na web sem hub de origem;
- importar resultados do Google/Tavily como verdade final.

## 5. Frequencia

Recomendacao inicial:

```txt
Discovery de hubs: 1 vez por semana
Enriquecimento de baixa confianca: 1 vez por dia
Reprocessamento de startups antigas: a cada 30 ou 60 dias
```

Detalhe:

| Job | Frequencia | Volume sugerido |
|---|---|---|
| Hub discovery | Semanal | top 20-50 URLs |
| Low-confidence enrichment | Diario | top 10 startups com lacunas |
| Reprocessamento | Mensal/bimestral | startups sem atualizacao recente |

## 6. Comando manual

Enquanto nao existir scheduler interno, o cron pode chamar a API diretamente.

PowerShell:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/startup-discovery/runs" `
  -ContentType "application/json" `
  -Body "{}"
```

Consulta:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/startup-discovery/runs/<RUN_ID>" |
  ConvertTo-Json -Depth 6
```

## 7. Exemplo de agendamento

### Scheduler interno da API

O backend possui um scheduler interno opcional, desligado por padrao. Para
ativar:

```txt
STARTUP_DISCOVERY_SCHEDULER_ENABLED=true
STARTUP_DISCOVERY_SCHEDULER_INTERVAL_SECONDS=604800
STARTUP_DISCOVERY_SCHEDULER_RUN_ON_STARTUP=false
```

Com essa configuracao, a propria API dispara uma rodada de discovery a cada
intervalo configurado.

Para testar imediatamente ao subir a API:

```txt
STARTUP_DISCOVERY_SCHEDULER_RUN_ON_STARTUP=true
```

Cuidados:

```txt
em producao multi-worker, somente um processo deve rodar o scheduler;
sem lock distribuido, cada worker habilitado dispararia sua propria rodada.
```

### Windows Task Scheduler

Acao:

```txt
Program/script:
powershell.exe

Arguments:
-ExecutionPolicy Bypass -Command "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/startup-discovery/runs' -ContentType 'application/json' -Body '{}'"
```

Frequencia sugerida:

```txt
Semanal, segunda-feira, 08:00
```

### Linux cron

```cron
0 8 * * 1 curl -s -X POST http://127.0.0.1:8000/startup-discovery/runs -H "content-type: application/json" -d '{}'
```

## 8. Guardrails obrigatorios

Antes de aumentar volume, o cron precisa respeitar:

1. Limite por rodada: `STARTUP_DISCOVERY_MAX_PER_RUN`.
2. Dedupe por URL normalizada.
3. Dedupe por dominio.
4. Nao submeter LinkedIn pessoal.
5. Nao submeter redes sociais como fonte principal.
6. Registrar hub de origem.
7. Registrar URLs descartadas e motivo.
8. Falha em um hub nao cancela os outros.
9. Nao reprocessar a mesma URL em janela curta.
10. Nao misturar discovery continuo com golden dataset.

## 9. Ranking de candidatos

Cada URL descoberta deve receber um score antes de virar job.

Sinais positivos:

| Sinal | Peso sugerido |
|---|---:|
| Dominio oficial da startup | +40 |
| Fonte de hub confiavel | +30 |
| Termos de IA no titulo/snippet | +25 |
| Termos Brasil/Brazil/fundadores | +15 |
| Funding, clientes, case ou aceleradora | +15 |
| Site em `.br` ou evidencia Brasil | +10 |

Sinais negativos:

| Sinal | Penalidade |
|---|---:|
| Rede social pessoal | descartar |
| URL duplicada | descartar |
| Conteudo sem startup identificavel | -40 |
| Diretorio generico/SEO farm | -30 |
| Pagina muito antiga | -10 |

Regra:

```txt
Somente top N por rodada vira url_ingestion_job.
```

## 10. Separacao dos datasets

Existem dois conjuntos diferentes:

| Conjunto | Uso |
|---|---|
| Golden dataset | calibrar e medir qualidade |
| Discovery continuo | descobrir novas startups |

O golden dataset atual fica em:

```txt
docs/recommendations/datasets/golden_startups_br20.json
```

Ele nao deve ser atualizado automaticamente pelo cron. Se uma startup nova for
muito boa para calibragem, ela deve ser promovida manualmente para o golden
dataset, com label esperado e justificativa.

## 11. Metricas do cron

Cada run deve permitir responder:

```txt
quantos hubs foram consultados?
quantos hubs falharam?
quantas URLs foram encontradas?
quantas URLs foram descartadas?
quantos jobs foram submetidos?
quantas startups validas nasceram?
quantas viraram AI-native / AI-enabled / non-AI?
quantas tiveram briefing gerado?
quantas recomendacoes fortes foram geradas?
quantos falsos positivos apareceram?
```

Metricas minimas por run:

| Metrica | Objetivo |
|---|---|
| hubs_processed | cobertura |
| hub_failures | estabilidade |
| urls_found | volume bruto |
| urls_discarded | qualidade/dedupe |
| jobs_submitted | carga no pipeline |
| completed_jobs | sucesso operacional |
| failed_jobs | falha de scraping/validacao |
| valid_startups | qualidade da descoberta |
| ai_distribution | mix AI-native/AI-enabled/non-AI |

## 12. Criterios de qualidade

O cron esta saudavel quando:

1. Pelo menos um hub entrega URLs por rodada.
2. Menos de 30% dos jobs falham por fonte ruim.
3. O sistema nao cria duplicatas obvias.
4. O volume nao congestiona o worker.
5. Startups non-AI nao recebem recomendacoes fortes indevidas.
6. O time consegue auditar de qual hub cada startup veio.

## 13. Falhas esperadas

Falhas normais:

- hub muda HTML;
- site bloqueia scraping;
- pagina exige JavaScript;
- URL aponta para noticia, nao website oficial;
- conteudo nao menciona IA;
- hub retorna startup antiga/inativa.

Como tratar:

```txt
registrar erro -> nao derrubar run -> ajustar extrator ou ranking -> tentar novamente em proxima rodada
```

## 14. Backlog recomendado

### Curto prazo

1. Persistir URLs descartadas com motivo.
2. Criar comando/script para disparar discovery local.
3. Expor historico de discovery no frontend.
4. Criar score antes de submeter candidatos ao `url_ingestion`.
5. Adicionar novos hubs brasileiros com extratores testados.

### Medio prazo

1. Adicionar scheduler interno ou job externo versionado.
2. Aumentar hubs com extratores testados.
3. Criar score de prioridade por URL.
4. Criar relatorio pos-run com metricas.
5. Reprocessar periodicamente startups antigas.

### Longo prazo

1. Discovery incremental por hub.
2. Deteccao de mudanca de site.
3. Feedback humano alimentando ranking de hubs.
4. Promocao manual de boas descobertas para golden dataset.

## 15. Decisao de produto

O cron vale a pena porque o produto foca startups brasileiras e precisa alimentar
o topo do funil continuamente.

Mas a regra de produto deve ser:

```txt
automatizar descoberta;
preservar rastreabilidade;
nao automatizar conclusao sem evidencia.
```
