# ARGOS — Roadmap de extensão pós-freeze

**Estado atual:** `W4_B_MULTI_VENUE_CENSUS_FORECASTEX_ACTIVE`  
**Plano machine-readable:** `PFEP-v4.2`  
**Science reopened:** `false`

## Progresso consolidado

| Frente | Estado | Resultado |
|---|---|---|
| W4-R | ATIVO | primeira wave de fontes/venues/famílias materializada |
| W4-A Kalshi | PASS | 488/488 rotas live+historical; 30/30 probes; 0 HTTP 400 |
| W4-B semantic freeze | PASS | protocolo congelado antes dos resultados |
| W4-B Kalshi cleaning | PASS | 488 séries; 1.690 candidatos; 668 aceitações estritas |
| W4-B canonicalization | PASS | 391 eventos canônicos; 277 aliases colapsados; 0 ambiguidades |
| W4-B Kalshi T−10d→T0 | PASS | 391 eventos; 5.196 tickers; 0 `API_UNRESOLVED` |
| W4-B ForecastEx | EM EXECUÇÃO | run `31694324574` |
| W4-B Polymarket | BLOQUEADO | aguarda PASS ForecastEx |
| W4-B cross-venue dedup | BLOQUEADO | aguarda PASS Polymarket |
| W4-B official truth | BLOQUEADO | aguarda PASS dedup |
| W4-B final attrition | BLOQUEADO | aguarda PASS official truth |
| W4-C saturation | PENDENTE | começa após closeout W4-B |

## Cadeia autoritativa

`ForecastEx PASS -> hardened promotion -> Polymarket -> hardened promotion -> cross-venue dedup -> hardened promotion -> official truth -> hardened promotion -> W4-B final attrition -> W4-C saturation gate`

## Distinção W4-B vs W4-C

W4-B produz evidência auditável de census, deduplicação, verdade oficial e attrition pré-outcome. W4-C usa esse closeout para medir contribuição marginal e decidir saturação antes da construção do data lake.

## Ordem restante

1. fechar ForecastEx;
2. Polymarket recensus;
3. cross-venue dedup;
4. official event truth;
5. W4-B final attrition;
6. W4-C saturation/marginal-capacity;
7. W4-D canonical data lake;
8. W4-E maximal pre-outcome features;
9. W4-F outcome-blind adequacy/simulation;
10. W4-G full protocol freeze;
11. W4-H controlled outcome reveal;
12. W4-I backtest battery;
13. W4-J validation battery;
14. W4-K scientific truth freeze.

A ciência original permanece preservada e a unidade inferencial padrão continua sendo `canonical_event_id`.
