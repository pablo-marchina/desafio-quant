# Documentation map

A pasta `docs/` mistura documentação ativa, relatórios de gates e histórico científico. **Numeração não significa precedência.** Use esta página para navegar.

## Camada ativa para a submissão

| Arquivo | Uso |
|---|---|
| `00_current_truth.md` | resumo operacional da verdade final |
| `01_challenge_requirements.md` | contrato oficial da entrega |
| `02_thesis_governance.md` | tese, gates e stop rules |
| `03_data_provenance.md` | dados, PIT, semântica e limitações |
| `04_experiments_results.md` | sequência de experimentos até ART-030 |
| `05_claim_registry.md` | versão humana da fronteira de claims |
| `06_final_report_plan.md` | plano ativo: maximização de score → autoria → QA |
| `07_audit_gaps.md` | limitações científicas atuais; blockers fechados |
| `08_source_index.md` | IDs e fontes principais |
| `10_genai_ledger.md` | uso final de GenAI e controles |
| `29_final_scientific_truth_submission_freeze.md` | contrato humano do freeze final |
| `30_report_scoring_maximization_contract.md` | contrato de score e Wave 1 |
| `31_model_complexity_technique_sufficiency_audit.md` | W1-A: adequação de complexidade/técnicas |
| `32_economic_backtest_quality_audit.md` | W1-B: qualidade do backtest econômico |
| `33_event_universe_information_asymmetry_audit.md` | W1-C: adequação do universo à assimetria informacional |

## Subfase editorial atual

`WAVE_1_SCORING_CONTRACT_AND_CRITICAL_AUDITS`

Objetivo: antes do design das cinco páginas, fechar três questões de pontuação que podem mudar o framing do relatório sem reabrir a ciência:

1. complexidade/modelagem adequada ao n efetivo;
2. qualidade e completude do backtest econômico já executado;
3. justificativa ex ante do universo earnings/EPS frente à tese de assimetria informacional.

Estado machine-readable:

- `../registry/report_scoring_maximization_matrix.csv`
- `../registry/wave1_maximization_status.json`

## Autoridade machine-readable

A documentação acima é explicativa. Para claims/números/estado científico, prevalecem:

- `../STATUS.yaml`
- `../registry/final_scientific_truth.json`
- `../registry/final_submission_answers_sf_v3.json`
- `../registry/final_submission_claims.csv`
- `../registry/final_submission_numbers.csv`
- `../registry/final_submission_manifest.json`
- `../registry/final_submission_freeze_validation.json`

Os arquivos de Wave 1 **não substituem o freeze científico**. Eles governam somente score optimization, framing, evidence selection e planejamento editorial.

## Histórico e pesquisa

`09_project_history.md` e os documentos `11_...` a `28_...` preservam pesquisa, protocolos, audits e decisões que levaram ao freeze final. Eles **não devem ser deletados nem reinterpretados como estado atual**.

Em especial:

- protocolos pré-resultado permanecem como prova contra data snooping;
- resultados negativos permanecem como evidência;
- versões anteriores podem conter linguagem como “próximo gate” que era correta naquele snapshot;
- somente os documentos listados na camada ativa devem ser usados para redação atual sem verificar o freeze final.

## Regra simples

Para responder **“o que é verdade agora?”**, comece em `00_current_truth.md` e no registry final.  
Para responder **“como chegamos aqui?”**, use os relatórios numerados/históricos.  
Para responder **“como maximizar a nota sem mudar a ciência?”**, use `30`–`33` + scoring matrix.  
Para responder **“o que pode entrar no PDF?”**, use `final_submission_claims.csv` + `final_submission_numbers.csv` e, após Wave 2, o authoring evidence pack.
