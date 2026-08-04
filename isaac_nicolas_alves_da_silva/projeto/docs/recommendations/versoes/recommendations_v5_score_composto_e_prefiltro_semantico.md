# Recommendations V5 — Score composto + prefiltro semântico

## Objetivo

Substituir o score de cobertura de keywords por um fit composto de 5 dimensões,
com nova confiança, e pré-filtrar candidatos por retrieval semântico.

## O que entregou (27/06/2026, passos 3+4 do Briefing V4)

### Score composto (substitui `score = keywords/total`)

```txt
fit = 0.35 * workload_alignment      (StartupAIContext.ai_workload_type x supported_workloads)
    + 0.25 * evidence_signal         (qualidade + profundidade das evidências)
    + 0.15 * startup_maturity        (deployment_stage)
    + 0.15 * keyword_prior           (ratio de keywords — mantido como sinal)
    + 0.10 * implementation_viability (gpu_need x complexity; bônus ai_native aqui)
```

- `NvidiaTechnology.supported_workloads` (mapa workload→relevância, 16 techs).
- `StartupAIContext` (dataclass frozen em `domain/policies.py`) — subconjunto de
  IA da startup no vocabulário do módulo, sem importar enums de `startups`.
- `MatchResult.score_breakdown` (as 5 dimensões para observabilidade).
- `MIN_MATCH_SCORE` ajustado 0.25 → 0.20.

### Nova confiança (5 fatores)

```txt
confidence = 0.25 * source_quality + 0.25 * signal_clarity
           + 0.20 * workload_proximity + 0.20 * evidence_depth
           + 0.10 * operational_signal
```

### Prefiltro semântico (passo 4)

- `NvidiaSemanticCandidateSelector` (ABC) + `RagSemanticNvidiaCandidateSelector`
  (chama `rag.public.Retriever.search()` filtrado por `nvidia_knowledge`).
- `GenerateRecommendations._apply_semantic_prefilter()` filtra candidatos antes
  do keyword matching; set vazio = fallback graceful (nenhuma recomendação
  perdida).

Testes: 47 → 87 unit. Total backend: 606 → 617 coletados.

Versão atual do módulo: **Recommendations V5** (ver `../visao_geral.md`).
