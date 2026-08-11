# Registry map

`registry/` é a camada machine-readable de governança, auditoria e freeze. Não usar um CSV/JSON isolado sem entender em qual fase ele foi produzido.

## 1. Autoridade final da submissão

Estes arquivos governam qualquer claim ou número do PDF final:

- `final_scientific_truth.json` — H1–H5, champions, limitações e reopen rule.
- `final_submission_answers_sf_v3.json` — sete respostas finais.
- `final_submission_claims.csv` — claims permitidos/proibidos.
- `final_submission_numbers.csv` — números autorizados.
- `final_submission_manifest.json` — blobs/hashes/identidades do freeze.
- `final_submission_freeze_validation.json` — resultado do gate final.
- `genai_usage_summary.json` + `genai_usage_ledger.csv` — uso final de GenAI.

Bundle final SHA-256:

`c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

## 2. Information completeness

Arquivos `ic02_*` a `ic07_*` e `information_completeness_*` registram disponibilidade, semântica, PIT, limitações e gates dos dados antes da seleção de arquitetura.

Pontos essenciais:

- trade/dense probability pre-cutoff: 115/117;
- canonical on-chain tape: 12.752 rows;
- full historical L2: NO-GO retroativo;
- daily event timing: 117/117;
- context retrievable ≠ materialized;
- Information Completeness Gate: 16/16 PASS.

## 3. Cross-strategy implementation audit

- `cross_strategy_transfer_map.csv` — superset congelado de 69 técnicas.
- `implementation_audit.csv` — status final Pass A/Pass B.
- `pass_a_*` — viabilidade estrutural outcome-blind.
- `pass_b_*` — redundância/arquitetura outcome-blind.
- `history/implementation_audit_pre_information_completeness_gate.csv` — snapshot explicitamente histórico.

## 4. ART-028

Arquivos `art028_*` registram materialização label-free/outcome-blind, cobertura, correlação, estabilidade e handoff de features.

## 5. ART-029

Arquivos `art029_*` são o freeze confirmatório pré-outcome. Não editar retroativamente para refletir ART-030.

## 6. ART-030

Arquivos `art030_*` registram a execução confirmatória que decidiu `FAIL_H2`, incluindo predictions, metrics, inference, ablations e hashes.

## 7. Política de manutenção

- **Nunca sobrescrever protocolo pré-resultado com interpretação pós-resultado.**
- Quando uma metodologia mudar, arquivar a versão anterior com rótulo explícito.
- Não promover `RETRIEVABLE` a `DATA_READY` sem materialização/auditoria.
- Não apagar falha, NO-GO ou resultado negativo.
- Novos summaries devem apontar para inputs, código e hashes.
- A pasta `history/` contém estados superados preservados deliberadamente.

## 8. O que usar no relatório

Somente o conjunto final de claims/números/manifests deve alimentar diretamente a redação. Demais registries servem para rastreabilidade, não para “garimpar” um número mais conveniente.
