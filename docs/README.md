# Documentation map

A pasta `docs/` mistura documentação ativa, relatórios de gates e histórico científico. **Numeração não significa precedência.** Use esta página para navegar.

## Camada ativa da submissão congelada

| Arquivo | Uso |
|---|---|
| `00_current_truth.md` | resumo operacional da verdade final |
| `01_challenge_requirements.md` | contrato oficial da entrega |
| `02_thesis_governance.md` | tese, gates e stop rules |
| `03_data_provenance.md` | dados, PIT, semântica e limitações |
| `04_experiments_results.md` | sequência de experimentos até ART-030 |
| `05_claim_registry.md` | versão humana da fronteira de claims |
| `06_final_report_plan.md` | plano editorial da entrega |
| `07_audit_gaps.md` | limitações científicas do freeze |
| `08_source_index.md` | IDs e fontes principais |
| `10_genai_ledger.md` | uso final de GenAI e controles |
| `29_final_scientific_truth_submission_freeze.md` | contrato humano do freeze final |
| `30_report_scoring_maximization_contract.md` | contrato de maximização de score |
| `31_model_complexity_technique_sufficiency_audit.md` | W1-A: adequação de complexidade/técnicas |
| `32_economic_backtest_quality_audit.md` | W1-B: qualidade do backtest econômico |
| `33_event_universe_information_asymmetry_audit.md` | W1-C: universo e EUAS |
| `34_investment_thesis_report_framing_freeze.md` | framing congelado do relatório |

## Trabalho operacional atual — extensão pós-freeze

`POST_FREEZE_PROTOCOL_DRAFTING`

A Wave 1 e o PDF baseline estão concluídos. A pesquisa metodológica de W2-A/W2-B também foi concluída, mas **nenhum protocolo novo foi congelado** e nenhum resultado novo de portfólio/IAS foi calculado.

Documentação ativa da extensão:

| Arquivo | Uso |
|---|---|
| `35_post_freeze_extension_roadmap.md` | sequência, fronteiras, gates e estado atual da extensão |
| `36_w2a_portfolio_backtest_methodology_research.md` | pesquisa pré-freeze para contabilidade financiada do backtest |
| `37_w2b_ias_methodology_research.md` | pesquisa pré-freeze para IAS, evidência, robustez e discovery |
| `../registry/post_freeze_methodology_research_v1.json` | síntese machine-readable das decisões de pesquisa |
| `../registry/post_freeze_extension_plan.json` | estado machine-readable e próximo gate |

### Estado de cada workstream

1. **W2-A Portfolio Backtest Integrity Upgrade:** `RESEARCH_COMPLETE_PROTOCOL_DRAFT_PENDING`. Recomendação: reconstruir o mesmo R1 primário como livro financiado; reconciliação exata dos 34 trades é gate zero.
2. **W2-B Information-Asymmetry Score:** `RESEARCH_COMPLETE_PROTOCOL_DRAFT_PENDING`. Recomendação: IAS formativo de assimetria estrutural, evidência/confiança separada e feasibility fora do score.
3. **W2-C Deep Event-Universe Census:** `PLANNED_DISCOVERY_NOT_STARTED`. Só começa depois do freeze do IAS/discovery protocol.
4. **W3 New Preregistered Experiment:** `BLOCKED_PENDING_W2_GO_GATE`. Nenhum rescue de H2.

### Fronteira atual

Os próximos artefatos devem ser **protocol drafts**, revisados adversarialmente e testados em casos sintéticos antes de congelamento. Não usar famílias reais para calibrar anchors, pesos, thresholds GO/NO-GO, sizing ou capital base.

## Baseline de relatório

O page set de submissão está em `../report/pages_submission/`. O QA do PDF está em `../registry/final_report_pdf_qa.json`, com `PASS_READY_FOR_SUBMISSION` e SHA-256 `5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`.

O baseline permanece recuperável durante toda a extensão. Uma versão futura do PDF só substitui esse checkpoint após novo QA completo.

## Autoridade machine-readable

Para claims/números/estado científico da submissão, prevalecem:

- `../STATUS.yaml`
- `../registry/final_scientific_truth.json`
- `../registry/final_submission_answers_sf_v3.json`
- `../registry/final_submission_claims.csv`
- `../registry/final_submission_numbers.csv`
- `../registry/final_submission_manifest.json`
- `../registry/final_submission_freeze_validation.json`
- `../registry/final_report_pdf_qa.json`

Os arquivos de Wave 1, framing e extensão pós-freeze **não substituem o freeze científico**. W1 governa avaliação/framing; W2 pesquisa e protocolos governam apenas trabalho novo.

## Histórico e pesquisa

`09_project_history.md` e os documentos `11_...` a `28_...` preservam pesquisa, protocolos, audits e decisões que levaram ao freeze final. Eles **não devem ser deletados nem reinterpretados como estado atual**.

Em especial:

- protocolos pré-resultado permanecem como prova contra data snooping;
- resultados negativos permanecem como evidência;
- versões anteriores podem conter linguagem de “próximo gate” correta naquele snapshot;
- nenhuma extensão futura pode sobrescrever ART-029/ART-030.

## Regra simples

Para responder **“o que ficou provado na submissão?”**, comece em `00_current_truth.md` e no registry final.  
Para responder **“como chegamos aqui?”**, use os relatórios históricos.  
Para responder **“por que earnings foi um laboratório defensável?”**, use `33` + EUAS.  
Para responder **“qual lacuna estamos fechando agora?”**, use `35`–`37` + registries pós-freeze.  
Para responder **“o que pode entrar no PDF baseline?”**, use claims/números finais + authoring evidence pack + QA do PDF.
