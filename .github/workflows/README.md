# GitHub Actions map

Os workflows desta pasta são parte da trilha de execução do ARGOS. A maioria representa gates científicos **já concluídos** e é mantida para auditoria/reprodutibilidade.

## Workflow operacional atual

- `repository_hygiene.yml` — verifica o estado pós-finalização: blob SHAs do bundle congelado, FST/SF, ART-030, EPS/GenAI, STATUS e documentação ativa.

## Workflow de freeze concluído

- `final_submission_freeze.yml` — executou o freeze FST-v1.0/SF-v3.0 e depois promoveu `STATUS.yaml` para `FINAL_REPORT_AUTHORING_AND_QA`.

O script `final_submission_freeze_validate.py` dentro desse workflow checava deliberadamente a fase **pré-finalizer**. Portanto, rerodar esse validador isoladamente no `main` final não é um health check válido; sua execução histórica bem-sucedida está preservada nos runs/commits do freeze.

## Workflows históricos preservados

Incluem:

- IC-02/03/04/06 e Information Completeness Gate;
- Pass A/Pass B do audit cross-strategy;
- ART-028;
- ART-029;
- ART-030;
- closeout/reconciliação pós-H2;
- finalizers de `STATUS.yaml` de fases anteriores.

Eles **não indicam a fase atual** apenas porque permanecem em `.github/workflows/`.

## Regra de manutenção

- Não apagar workflows que sustentem artefatos congelados.
- Não rerodar workflow histórico com inputs atuais esperando reproduzir snapshot antigo; use o commit/run correspondente.
- Não modificar protocolo histórico para refletir resultado posterior.
- Novos workflows após o freeze final devem ser de **autoria, QA, validação, build ou submissão**, não de busca de novo alpha para alterar SF-v3.0.

## Estado atual

A ciência está congelada. O pipeline permitido agora é:

`frozen evidence → report authoring → report QA → PDF validation → submission`.
