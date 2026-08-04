# 05 — Motor de Recomendação NVIDIA

## Responsabilidade deste documento

Este documento descreve apenas o motor de recomendação: como gaps, evidências e contextos NVIDIA viram recomendações, ações e ranking. Ele não detalha coleta, RAG interno, LangGraph ou frontend.

## Objetivo do motor

O motor deve transformar diagnóstico técnico em uma decisão operacional para a NVIDIA:

- qual tecnologia NVIDIA recomendar;
- por que essa tecnologia resolve o gap;
- qual é a prioridade;
- qual é a confiança;
- qual é a incerteza;
- qual evidência sustenta;
- qual contexto NVIDIA sustenta;
- qual próxima ação o time NVIDIA deve tomar;
- quando abster/rejeitar por falta de evidência.

## Entrada do motor

```json
{
  "gap_results": [],
  "rag_contexts_by_gap": {},
  "evidence_items": [],
  "scores": {},
  "startup_profile": {}
}
```

## Saída do motor

```json
{
  "nvidia_recommendations": [
    {
      "recommendation_id": "...",
      "gap_id": "...",
      "gap_type": "...",
      "nvidia_technology": "NVIDIA NIM",
      "reason": "...",
      "mapping_score": 0.0,
      "mapping_confidence": 0.0,
      "recommendation_priority_score": 0.0,
      "confidence": 0.0,
      "uncertainty": 0.0,
      "business_impact": 0.0,
      "implementation_complexity": 0.0,
      "supporting_rag_context_ids": [],
      "supporting_evidence_ids": [],
      "production_allowed": true,
      "blockers": [],
      "recommendation_action": "approach_now|technical_validation|monitor|not_recommended",
      "next_best_action": "...",
      "evidence_support_score": 0.0,
      "rag_support_score": 0.0,
      "expected_utility": 0.0,
      "why_not": []
    }
  ],
  "ranking_status": "passed|needs_review|failed|blocked_uncalibrated_recommendation",
  "production_allowed": true,
  "blockers": []
}
```

## Arquivos principais

| Arquivo | Responsabilidade |
|---|---|
| `src/recommendation/nvidia_technology_mapping.py` | mapping quantitativo gap→tecnologia |
| `src/recommendation/recommendation_engine.py` | ranking final e ações |
| `src/diagnosis/nvidia_mapping.py` | matriz determinística base por `TechnicalGap` |
| `src/decisioning/expected_utility_ranker.py` | fórmula de expected utility |
| `src/decisioning/adaptive_recommendation_ranker.py` | ranking adaptativo/decisioning |
| `src/decisioning/feedback_learner.py` | ajuste por feedback |
| `src/decisioning/calibration_service.py` | calibração |
| `src/decisioning/decision_ledger_writer.py` | ledger |
| `src/quality/decision_calibration_registry.py` | registry de decisões calibradas |
| `src/quality/evaluators/recommendation_actionability.py` | qualidade/actionability |
| `src/services/product/activation_service.py` | playbooks de ativação |
| `src/config/playbooks/nvidia_activation_playbooks.yaml` | playbooks NVIDIA |

## Tecnologias e técnicas usadas

| Técnica/tecnologia | Uso |
|---|---|
| Weighted scoring | mapping score e priority score |
| Confidence scoring | confiança do mapping e recomendação |
| Uncertainty penalty | penaliza baixa evidência/alta incerteza |
| Evidence support gate | exige evidência da startup |
| RAG support gate | exige contexto NVIDIA |
| Calibration registry | valores de score/threshold precisam ser calibrados |
| Expected utility | ranking adicional considerando valor, confiança, incerteza, evidência, complexidade e risco |
| Abstention policy | bloqueia recomendação sem suporte |
| Next-best-action | traduz ranking em ação operacional |
| Why-not explanation | explica bloqueios/alternativas perdidas |
| Decision ledger | rastreia decisão final |
| Activation playbooks | conecta tecnologia a ação de Inception/GTW/technical workshop |
| Pydantic | schemas e validação |

## Mapeamento gap → tecnologia

Matriz base de tecnologias:

| Gap | Tecnologias candidatas |
|---|---|
| external API dependency | NVIDIA NIM, NVIDIA AI Enterprise |
| high inference cost | TensorRT-LLM, Triton Inference Server, NVIDIA NIM |
| high latency | TensorRT-LLM, Triton Inference Server, NVIDIA NIM |
| agent governance gap | NeMo Guardrails, NVIDIA NeMo |
| observability gap | NVIDIA AI Enterprise |
| model evaluation gap | NVIDIA NeMo |
| privacy/controlled deployment | NVIDIA AI Enterprise, NVIDIA NIM |
| slow data pipeline | NVIDIA RAPIDS, cuDF, cuML |
| heavy tabular processing | NVIDIA RAPIDS, cuML |
| voice need | NVIDIA Riva, NVIDIA NIM |
| simulation need | NVIDIA Omniverse |
| computer vision need | NVIDIA AI Enterprise, TensorRT, NVIDIA NIM |
| robotics need | NVIDIA Isaac, NVIDIA Omniverse |
| healthcare compliance need | NVIDIA Clara, MONAI, NVIDIA AI Enterprise |
| AI cybersecurity need | NVIDIA Morpheus |

## Mapping quantitativo

O mapping produz, para cada par gap→tecnologia:

- `mapping_score`;
- `mapping_confidence`;
- `uncertainty`;
- `supporting_rag_context_ids`;
- `supporting_evidence_ids`;
- `production_allowed`;
- `blockers`;
- `explanation`.

O mapping é bloqueado quando:

- decisões de calibração não existem;
- golden set/registry bloqueia produção;
- RAG context count abaixo do mínimo;
- evidence support abaixo do mínimo;
- score abaixo do threshold;
- confidence baixa;
- não há suporte nenhum.

## Calibrações de mapping

Decisões esperadas:

- `nvidia_mapping.mapping_score_weights`;
- `nvidia_mapping.mapping_confidence_weights`;
- `nvidia_mapping.production_threshold`;
- `nvidia_mapping.minimum_rag_contexts`;
- `nvidia_mapping.minimum_evidence_support`;
- `nvidia_mapping.uncertainty_penalty`.

## Ranking de recomendação

`rank_recommendations_from_mappings` aplica:

1. parsing do mapping;
2. leitura de calibrações;
3. cálculo de features;
4. cálculo de priority score;
5. gates de evidência/RAG;
6. confidence final;
7. action classification;
8. next-best-action;
9. expected utility simplificado;
10. ordenação.

## Features de priority score

```json
{
  "mapping_score": 0.0,
  "mapping_confidence": 0.0,
  "gap_severity_score": 0.0,
  "gap_confidence_score": 0.0,
  "evidence_support": 0.0,
  "rag_support": 0.0,
  "business_impact": 0.0,
  "implementation_complexity_inverse": 0.0
}
```

## Gates fortes de recomendação

Uma recomendação final produtiva exige:

```text
mapping.production_allowed = true
mapping_score >= recommendation.production_threshold
mapping_confidence >= recommendation.minimum_mapping_confidence
combined_support_score >= recommendation.minimum_evidence_support
supporting_evidence_ids > 0
supporting_rag_context_ids > 0
```

Se qualquer um falha, `production_allowed=false` e o motivo entra em `blockers`/`why_not`.

## Evidence/RAG support

Cálculo atual:

```text
evidence_support_score = min(1.0, len(supporting_evidence_ids) / 5.0)
rag_support_score = min(1.0, len(supporting_rag_context_ids) / 5.0)
combined_support_score = min(1.0, evidence_support_score + rag_support_score)
```

Interpretação:

- evidência da startup prova que o gap existe;
- contexto NVIDIA prova que a tecnologia recomendada é relevante;
- ambos são obrigatórios para produto.

## Expected utility

Fórmula de `expected_utility_ranker.py`:

```text
utility = clamp(
  expected_value * confidence * (1 - uncertainty) * (0.5 + 0.5 * evidence_support)
  - mean(complexity, risk)
)
```

Componentes:

- `expected_value`: valor esperado da recomendação;
- `confidence`: confiança do mapping/recomendação;
- `uncertainty`: incerteza residual;
- `evidence_support`: suporte por evidência;
- `complexity`: custo de implementação;
- `risk`: risco de adoção.

## Recommendation action

A recomendação deve expor uma ação operacional:

| Action | Quando usar |
|---|---|
| `approach_now` | evidência e RAG fortes; recomendação pronta |
| `technical_validation` | potencial existe, mas precisa validação técnica |
| `monitor` | oportunidade fraca ou baixa confiança |
| `not_recommended` | falta evidência/RAG ou blockers críticos |

## Next-best-action

O campo `next_best_action` precisa ser específico. Exemplos desejados:

- rodar benchmark NIM vs API externa medindo custo, p50/p95 e erro;
- marcar workshop sobre Triton/TensorRT-LLM;
- validar stack de inferência com CTO;
- solicitar evidência sobre volume de dados/tabular;
- monitorar funding e contratações técnicas;
- não abordar até haver fonte oficial e contexto NVIDIA suficiente.

## Why-not

`why_not` lista razões pelas quais a recomendação não está pronta ou foi bloqueada:

- missing startup evidence;
- missing NVIDIA RAG context;
- mapping score baixo;
- confidence baixa;
- support score baixo;
- calibração ausente;
- RAG context count insuficiente;
- evidência insuficiente.

## Playbooks de ativação

O motor se conecta a playbooks para transformar recomendação em movimento NVIDIA:

- Inception outreach;
- technical workshop;
- benchmark/Poc;
- partner/community activation;
- GTM support;
- monitoramento.

Os playbooks entram depois do ranking e ajudam a gerar dossier/briefing.

## Métricas do motor

- `mapping_count`;
- `recommendation_count`;
- `blocked_recommendation_count`;
- `missing_recommendation_calibration_count`;
- média de mapping score;
- média de confidence;
- média de priority;
- recomendações production allowed;
- recomendações needs review.

## Calibrações de recomendação

Decisões esperadas:

- `recommendation.priority_score_weights`;
- `recommendation.production_threshold`;
- `recommendation.confidence_threshold`;
- `recommendation.uncertainty_penalty`;
- `recommendation.minimum_mapping_confidence`;
- `recommendation.minimum_evidence_support`.

## Output ideal para o case

Para cada recomendação, o frontend/export deve mostrar:

- tecnologia NVIDIA;
- gap resolvido;
- score;
- expected utility;
- confidence;
- uncertainty;
- technical justification;
- business justification;
- implementation complexity;
- startup evidence;
- NVIDIA RAG context;
- next-best-action;
- blockers;
- why-not;
- production allowed;
- action.

## Testes específicos

```bash
pytest -q tests/unit/test_recommendation_engine.py
pytest -q tests/evals/test_recommendation_baseline.py
pytest -q tests/unit/test_decisioning_adaptive.py
pytest -q tests/unit/test_workflow_rag_recommendations.py
```

## Critérios de aceite

| Critério | Aceite |
|---|---|
| Mapping | todo gap relevante gera tecnologias candidatas |
| Evidência | recomendação sem evidence IDs é bloqueada |
| RAG | recomendação sem RAG context IDs é bloqueada |
| Score | priority score calculado com weights calibrados |
| Confidence | confidence e uncertainty expostos |
| Action | `recommendation_action` preenchido |
| Next step | `next_best_action` específico |
| Why-not | blockers explicados |
| Ranking | recomendações ordenadas por prioridade/utilidade |
| Produto | ao menos uma recomendação `production_allowed=true` para output final pronto |
