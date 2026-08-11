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
| `06_final_report_plan.md` | plano atual de autoria/QA das cinco páginas |
| `07_audit_gaps.md` | limitações atuais; blockers fechados |
| `08_source_index.md` | IDs e fontes principais |
| `10_genai_ledger.md` | uso final de GenAI e controles |
| `29_final_scientific_truth_submission_freeze.md` | contrato humano do freeze final |

## Autoridade machine-readable

A documentação acima é explicativa. Para claims/números/estado, prevalecem:

- `../STATUS.yaml`
- `../registry/final_scientific_truth.json`
- `../registry/final_submission_answers_sf_v3.json`
- `../registry/final_submission_claims.csv`
- `../registry/final_submission_numbers.csv`
- `../registry/final_submission_manifest.json`
- `../registry/final_submission_freeze_validation.json`

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
Para responder **“o que pode entrar no PDF?”**, use `final_submission_claims.csv` + `final_submission_numbers.csv`.
