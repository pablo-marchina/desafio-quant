# Catalogo de fontes de discovery

Atualizado em 30/06/2026.

Este catalogo lista fontes conhecidas para alimentar o topo do funil do AI
Venture Radar. Ele e intencionalmente maior que o conjunto executado hoje:
fontes planejadas so devem entrar no runtime depois de terem extrator, teste e
criterios de descarte.

## Status atual

```txt
implemented -> fonte ja esta em HUB_SOURCES e pode ser usada pelo discovery
planned     -> fonte mapeada para roadmap, mas ainda nao roda automaticamente
```

| Fonte | Status | Modo esperado | Prioridade | Por que importa |
|---|---|---|---|---|
| InovAtiva Brasil | implemented | url | high | Hub publico brasileiro com foco em startups early-stage. |
| Abstartups | implemented | url | high | Base do ecossistema brasileiro e boa origem de auditoria. |
| 100 Open Startups | implemented | name | high | Ranking com sinais de tracao e relacionamento corporate-startup. |
| Distrito | planned | mixed | medium | Inteligencia de mercado e listas setoriais de startups brasileiras. |
| Latitud | planned | mixed | medium | Rede de founders e conteudo LATAM com forte presenca brasileira. |
| Startups.com.br | planned | news | medium | Noticias e perfis que ajudam a descobrir empresas em tracao. |
| Endeavor Brasil | planned | mixed | medium | Fonte de scale-ups e empresas com maturidade comercial. |
| Cubo Itau | planned | mixed | low | Hub corporativo com bom sinal de ecossistema e parcerias. |
| BrazilLAB | planned | mixed | low | Govtechs e startups com casos de uso B2G/B2B relevantes. |
| Sebrae Startups | planned | mixed | low | Fonte ampla para descoberta regional e programas de aceleracao. |

## Criterio para promover uma fonte

Para mover uma fonte de `planned` para `implemented`:

1. Criar extrator em `apps/api/src/modules/startup_discovery/infrastructure/hub_extractors/`.
2. Registrar a fonte em `HUB_SOURCES`.
3. Adicionar teste unitario para parsing e limite por rodada.
4. Garantir que o extrator retorne site oficial, quando possivel, e perfil de origem para auditoria.
5. Documentar sinais de descarte: rede social pessoal, diretorio generico, noticia sem empresa identificavel ou pagina sem site oficial.

## Observacao operacional

O discovery nao transforma uma fonte em verdade final. Ele cria candidatos e
jobs de ingestion. Classificacao, evidencias, recomendacoes e briefing seguem
passando pelo pipeline normal e pela revisao humana.
