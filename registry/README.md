# Registry map

`registry/` é a camada machine-readable de governança, auditoria e freeze. Não usar um CSV/JSON isolado sem entender em qual fase ele foi produzido.

## 1. Autoridade final da submissão

Estes arquivos governam qualquer claim ou número científico do PDF baseline:

- `final_scientific_truth.json` — H1–H5, champions, limitações e reopen rule.
- `final_submission_answers_sf_v3.json` — sete respostas finais.
- `final_submission_claims.csv` — claims permitidos/proibidos.
- `final_submission_numbers.csv` — números autorizados.
- `final_submission_manifest.json` — blobs/hashes/identidades do freeze.
- `final_submission_freeze_validation.json` — resultado do gate final.
- `genai_usage_summary.json` + `genai_usage_ledger.csv` — uso final de GenAI.
- `final_report_pdf_qa.json` — QA do PDF de cinco páginas e hash do checkpoint aprovado.

Bundle final SHA-256:

`c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

PDF baseline SHA-256:

`5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`

## 2. Maximização editorial pós-freeze concluída

Estes arquivos **não alteram a verdade científica** e registram a Wave 1 / autoria:

- `report_scoring_maximization_matrix.csv` — mapeamento da rubrica.
- `wave1_maximization_status.json` — fechamento dos três audits críticos.
- `model_complexity_sufficiency_summary.json` — W1-A.
- `economic_backtest_quality_summary.json` — W1-B.
- `event_universe_euas_*` — W1-C e ranking EUAS.
- `report_framing_freeze.json` — framing pré-autoria.
- `report_authoring_evidence_pack.json` — pack determinístico para as cinco páginas.
- `report_authoring_claim_overlay.csv` / `report_figure_inputs.csv` — fronteira editorial.
- `argos_visual_identity_freeze.json` — identidade visual.
- `adversarial_report_scoring_review_v1.json` — revisão adversarial do relatório.

Nenhum número de performance foi autorizado por ser favorável; o resultado negativo e o no-trade permanecem.

## 3. Extensão pós-freeze — estado atual

### `post_freeze_extension_plan.json`

Estado operacional da extensão. Versão atual `PFEP-v1.1`, fase `POST_FREEZE_PROTOCOL_DRAFTING`.

Ele é **subordinado** ao freeze de submissão e não pode modificar FST-v1.0, SF-v3.0, ART-029 ou ART-030.

### `post_freeze_methodology_research_v1.json`

Síntese machine-readable da pesquisa pré-freeze concluída para W2-A e W2-B/IAS.

Flags críticas:

- `performance_results_computed: false`;
- `ias_family_scores_computed: false`;
- `protocols_frozen: false`.

Estado: `RESEARCH_COMPLETE_PROTOCOL_DRAFT_PENDING`.

### Workstreams

- `W2A_PORTFOLIO_BACKTEST_INTEGRITY` — pesquisa concluída; próximo passo é protocol draft + revisão adversarial. O gate zero recomendado é reconciliação exata do R1 primário antes de qualquer métrica de NAV/Sharpe/MDD.
- `W2B_INFORMATION_ASYMMETRY_SCORE` — pesquisa concluída; próximo passo é congelar constructo, anchors, ECG, feasibility e robustez usando validação sintética antes de scores reais.
- `W2C_DEEP_EVENT_UNIVERSE_CENSUS` — ainda não iniciado; discovery só após freeze do protocolo IAS/discovery.
- `W3_NEW_PREREGISTERED_EXPERIMENT` — bloqueado até GO ex ante; nenhuma seleção por performance do ARGOS.

Os documentos humanos correspondentes são `docs/35_post_freeze_extension_roadmap.md`, `docs/36_w2a_portfolio_backtest_methodology_research.md` e `docs/37_w2b_ias_methodology_research.md`.

## 4. Information completeness

Arquivos `ic02_*` a `ic07_*` e `information_completeness_*` registram disponibilidade, semântica, PIT, limitações e gates dos dados antes da seleção de arquitetura.

Pontos essenciais:

- trade/dense probability pre-cutoff: 115/117;
- canonical on-chain tape: 12.752 rows;
- full historical L2: NO-GO retroativo;
- daily event timing: 117/117;
- context retrievable ≠ materialized;
- Information Completeness Gate: 16/16 PASS.

## 5. Cross-strategy implementation audit

- `cross_strategy_transfer_map.csv` — superset congelado de 69 técnicas.
- `implementation_audit.csv` — status final Pass A/Pass B.
- `pass_a_*` — viabilidade estrutural outcome-blind.
- `pass_b_*` — redundância/arquitetura outcome-blind.
- `history/implementation_audit_pre_information_completeness_gate.csv` — snapshot explicitamente histórico.

## 6. ART-028 / ART-029 / ART-030

- `art028_*` — materialização label-free/outcome-blind, cobertura e handoff de features.
- `art029_*` — freeze confirmatório pré-outcome. Não editar retroativamente.
- `art030_*` — execução confirmatória que decidiu `FAIL_H2`, incluindo predictions, metrics, inference, ablations e hashes.

## 7. Política de manutenção

- **Nunca sobrescrever protocolo pré-resultado com interpretação pós-resultado.**
- Nunca usar a extensão pós-freeze para “resgatar” H2, escolher subgrupos de earnings ou promover um challenger após outcomes.
- Quando uma metodologia nova for congelada, criar novo artefato/versionamento em vez de reescrever o antigo.
- Não promover `RETRIEVABLE` a `DATA_READY` sem materialização/auditoria.
- Não apagar falha, NO-GO ou resultado negativo.
- Novos summaries devem apontar para inputs, código e hashes.
- A pasta `history/` contém estados superados preservados deliberadamente.

## 8. Regra de precedência

**Submissão:** final scientific truth → submission freeze → manifest/claims/numbers → PDF QA → artefatos individuais.  
**Extensão:** toda a cadeia acima permanece imutável → `post_freeze_extension_plan.json` → pesquisa metodológica → futuros protocolos pré-resultado → futuros resultados.

Nenhum registry novo pode alterar retroativamente a interpretação autorizada de H1–H5 sem um erro factual/proveniência demonstrado.
