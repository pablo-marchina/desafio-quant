# Scripts map

Scripts históricos permanecem no `main` para reproduzir a sequência científica; não devem ser alterados retroativamente para refletir resultados posteriores.

## Health checks atuais

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2b_ias_frozen_bundle_integrity_v1.py
python scripts/w2b_ias_smaa_result_freeze_validate_v1.py
python scripts/w3_go_no_go_synthetic_v1.py
```

`repository_hygiene_validate.py` protege FST-v1.0/SF-v3.0, ART-030, EPS/GenAI e o frozen submission bundle.

## W2-A

- `w2a_portfolio_contract_synthetic_validation.py` — 20 cenários sintéticos do contrato financiado.
- execução real já concluída sobre o R1 congelado após Gate 0 provenance-preserving.
- resultado: `NO_PROMOTION_R1`.

A execução real não autoriza novo sizing, recapitalização, leverage ou promoção por métrica secundária.

## W2-B / IAS

- `w2b_ias_contract_synthetic_validation.py` — 18 cenários sintéticos do contrato IAS/feasibility.
- `w2b_ias_score_synthetic_v1.py` — valida schema/scorer sem evidência real.
- `w2b_ias_score_v1_0.py` — scorer real congelado; executado uma única vez sobre a matriz de 50 células.
- `w2b_ias_frozen_bundle_integrity_v1.py` — verifica byte-identidade do bundle de método.
- `w2b_ias_evidence_validate_v1.py` — valida matriz + source registry antes do scoring.
- `w2b_ias_smaa_result_freeze_validate_v1.py` — protege o resultado real congelado.

Resultado real: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`, sem leitura de F1–F9 durante SMAA.

## W2-C / PIT-v2.1

A lineage inclui discovery, semantic validation/adjudication e PIT-v2.1. Os scripts históricos de semantic v1/PIT-A v1 permanecem preservados, mas seus outputs invalidados não podem ser reutilizados como ciência.

O resultado F1–F9 autoritativo está em `../registry/w2c_pit_v2_1_family_gates.json`:

- earnings → FAIL F1/F2/F3;
- FDA/PDUFA → FAIL F1/F2/F3;
- macro statistical release → FAIL F1/F2/F3.

## W3 gate final

Estes são agora os executáveis de maior precedência operacional da extensão:

- `w3_go_no_go_synthetic_v1.py` — tenta quebrar a regra final sem combinar dados reais;
- `w3_go_no_go_v1.py` — engine real congelado que combina exclusivamente os blobs IAS/SMAA e PIT F1–F9 registrados no manifest.

Freeze: `../registry/w3_go_no_go_freeze_v1_0.json`, bundle `c4db745a4c38a80743ec29779f638f5ebf79ff8f7f0df0a30c9ab682ae34aac2`.

**Ainda não executar scripts experimentais W3.** O único próximo ato autorizado é executar exatamente `w3_go_no_go_v1.py` sobre os inputs congelados; seu output pode autorizar no máximo drafting de um protocolo W3 futuro.

## Pipelines científicos congelados

- `art028_*` — feasibility/materialização outcome-blind.
- `art029_*` — freeze H2 antes dos outcomes.
- `art030_*` — execução H2.
- `ic*`, `information_completeness_*`, `pass_a*`, `pass_b*` — contracts/gates pré-experimento.
- `finalize_*` — transições históricas de `STATUS.yaml`; não executar arbitrariamente.

## Regras

1. Preservar seeds, hashes e parâmetros dos artefatos históricos.
2. Nunca usar outcomes em scripts outcome/performance-blind.
3. Não modificar IAS scorer, evidence matrix, PIT gates ou W3 engine depois de seus freezes.
4. `FEASIBILITY_NOT_ESTABLISHED` nunca vira PASS por imputação.
5. Resultados negativos/NO-GO são first-class outputs e devem permanecer registrados.
6. H2 e `C0_NO_TRADE` não são reabertos pela extensão.
7. Um eventual `GO_DRAFT_W3_PROTOCOL` não autoriza execução W3; exige novo protocolo e freeze prospectivo.
