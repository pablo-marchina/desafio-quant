# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. O projeto já encerrou sua fase científica confirmatória para a submissão de 2026 e está em **FINAL_REPORT_AUTHORING_AND_QA**.

> **Anonimato:** este repositório identifica seus autores pelo GitHub e **não deve ser citado nem linkado no PDF final**.

## Estado científico congelado

- **Tese:** `TF-v1.0` / `ART-027_FREEZE_v1.0`.
- **Final Scientific Truth:** `FST-v1.0`.
- **Submission Freeze:** `SF-v3.0`.
- **Implementação empírica:** Polymarket + earnings/EPS + ações individuais dos EUA.
- **H1:** `SUPPORTED_IN_TESTED_SAMPLE`.
- **H2:** `FAIL_UNDER_FROZEN_EXP07I`.
- **H3:** `BLOCKED_BY_H2_FAIL_NO_RESCUE`.
- **H4:** `BLOCKED_BY_H2_FAIL`.
- **H5:** `BLOCKED_BY_H4`.
- **Champion probabilístico:** `M2`.
- **Champion econômico:** `C0_NO_TRADE`.
- **Blockers científicos para a submissão:** nenhum.
- **Limitação de outcome restante:** `BLSH|2025-09-17`, mantida fail-closed; 116/117 eventos possuem validação oficial independente e 116/116 validados concordam com a resolução contratual.

O resultado final não é uma estratégia long/short promovida: a probabilidade agregada da Polymarket teve valor preditivo frente aos baselines públicos gratuitos testados, mas a camada congelada de movimentos não acrescentou informação incremental demonstrável além de M2. O stop rule encerra a cadeia testada em **no-trade**.

## Fonte de verdade

Leia nesta ordem:

1. `STATUS.yaml` — estado operacional machine-readable.
2. `registry/final_scientific_truth.json` — verdade científica final.
3. `registry/final_submission_answers_sf_v3.json` — sete respostas finais congeladas.
4. `registry/final_submission_claims.csv` — fronteira de claims permitidos/proibidos.
5. `registry/final_submission_numbers.csv` — números autorizados para a entrega.
6. `registry/final_submission_manifest.json` — manifesto de hashes e identidades.
7. `registry/final_submission_freeze_validation.json` — prova do gate final executado.
8. `docs/29_final_scientific_truth_submission_freeze.md` — leitura humana do freeze.

Bundle final congelado: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`.

## Estrutura do repositório

```text
.
├── README.md                  # entrada e navegação
├── STATUS.yaml                # estado operacional atual
├── data/                      # datasets derivados auditáveis necessários à reprodução
├── docs/                      # documentação ativa + histórico científico
├── registry/                  # contratos, manifests, gates, claims, hashes e summaries
├── scripts/                   # pipelines e validadores reproduzíveis
├── templates/                 # templates metodológicos
└── .github/workflows/         # execuções reproduzíveis e gates de CI
```

Consulte os índices locais em `docs/README.md`, `registry/README.md`, `scripts/README.md` e `.github/workflows/README.md`.

## Política de limpeza

**Não deletar nem reescrever evidência histórica para deixar o repositório “bonito”.** Resultados negativos, protocolos pré-resultados, outputs superados e falhas documentadas fazem parte da trilha de auditoria. A limpeza deste repo significa:

- separar claramente **autoritativo atual** de **histórico**;
- remover linguagem stale dos documentos ativos;
- manter raw/derivados e hashes necessários à reprodução;
- evitar arquivos locais, caches, secrets e outputs temporários no Git;
- impedir que documentação antiga substitua o freeze final.

## Validação atual

Para verificar o estado **pós-finalização**, rode:

```bash
python scripts/repository_hygiene_validate.py
```

Esse validador confirma que os 8 blobs do `final_submission_manifest.json` continuam byte-idênticos, que o bundle SHA permanece congelado e que README/docs/STATUS refletem a fase final.

`final_submission_freeze_validate.py` é preservado como **validador histórico do momento de freeze**: ele foi executado antes do finalizer e deliberadamente exige a fase pré-finalização. Não é o comando de higiene do `main` atual.

## Regra de precedência

Para o conteúdo submetido: **ART-027/TF-v1.0 → FST-v1.0 → CT-v4.0 → SF-v3.0 → manifesto/claims/números finais → artefatos individuais → documentação histórica**.

Nenhum novo threshold, subgrupo, feature, modelo ou experimento pós-ART-030 pode alterar a verdade congelada da submissão sem erro factual/proveniência demonstrado.
