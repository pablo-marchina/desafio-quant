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

`POST_FREEZE_EXTENSION_PLANNING`

A Wave 1 foi concluída e o PDF baseline já passou QA. O trabalho novo é separado da submissão científica congelada e está documentado em:

- `35_post_freeze_extension_roadmap.md` — sequência, fronteiras e gates da extensão;
- `../registry/post_freeze_extension_plan.json` — estado machine-readable.

A extensão tem quatro etapas planejadas:

1. **W2-A Portfolio Backtest Integrity Upgrade** — transformar a contabilização event-level já congelada em um portfólio financiado sem mudar as regras de trading após ver resultados.
2. **W2-B Information-Asymmetry Score (IAS)** — criar um protocolo separado para assimetria informacional pura; EUAS continua respondendo à pergunta diferente de “melhor laboratório conjunto”.
3. **W2-C Deep Event-Universe Census** — aprofundar M&A completion/regulatory clearance, FDA e famílias relacionadas de forma performance-blind.
4. **W3 New Preregistered Experiment** — somente se uma família passar gates ex ante; nenhum rescue de H2.

**Importante:** o protocolo de W2-A e o IAS ainda **não estão congelados** neste snapshot. O roadmap apenas fixa a ordem, as fronteiras e o anti-contamination policy. Pesos, thresholds e regras quantitativas finais devem ser definidos e versionados antes da execução correspondente.

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

Os arquivos de Wave 1, framing e extensão pós-freeze **não substituem o freeze científico**. W1 governa avaliação/framing; o roadmap pós-freeze governa apenas trabalho novo.

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
Para responder **“qual lacuna estamos fechando agora?”**, use `35` + `post_freeze_extension_plan.json`.  
Para responder **“o que pode entrar no PDF baseline?”**, use claims/números finais + authoring evidence pack + QA do PDF.