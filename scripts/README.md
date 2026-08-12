# Scripts map

Scripts históricos permanecem no `main` para reproduzir a sequência científica; não os altere para refletir resultados posteriores.

## Health checks atuais

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2a_portfolio_contract_synthetic_validation.py
python scripts/w2b_ias_contract_synthetic_validation.py
```

`repository_hygiene_validate.py` protege FST-v1.0/SF-v3.0, ART-030, EPS/GenAI e os 8 blobs do frozen submission bundle.

## W2 synthetic-only validators

- `w2a_portfolio_contract_synthetic_validation.py` — implementa o núcleo do funded-accounting contract e tenta falsificá-lo com 20 cenários sintéticos. Não lê real ARGOS P&L.
- `w2b_ias_contract_synthetic_validation.py` — implementa anchors/ECG/SMAA/feasibility/GO semantics e tenta falsificá-los com 18 cenários sintéticos. Não lê scores de famílias reais nem ARGOS performance.

Status combinado: **38/38 PASS READY FOR FREEZE**. Esses scripts validam drafts; não são autorização para execução real.

## Pipelines científicos congelados

- `art028_*` — feasibility/materialização outcome-blind.
- `art029_*` — freeze H2 antes dos outcomes.
- `art030_*` — execução H2.
- `ic*`, `information_completeness_*`, `pass_a*`, `pass_b*` — contracts/gates pré-experimento.
- `finalize_*` — transições históricas de `STATUS.yaml`; não executar arbitrariamente.

## Regras

1. Preservar seeds/hashes/parâmetros dos artefatos históricos.
2. Nunca usar outcomes em scripts marcados outcome/performance-blind.
3. Qualquer mudança substantiva nos W2 protocol drafts exige nova versão e rerun de todos os 38 synthetic cases.
4. Real W2-A somente depois do byte-freeze W2-A e Gate 0 de reconciliação.
5. Real IAS/W2-C somente depois do byte-freeze IAS/discovery.
6. W3 só depois de freeze independente com prospective adequacy.
