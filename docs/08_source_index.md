# Índice de fontes, governança e artefatos

Este repositório contém a camada operacional/reprodutível. Arquivos oficiais originais e documentos de governança Google Workspace permanecem no Drive. Não duplicar material privado ou licenciado em repositório público.

## Documentos oficiais do desafio

| Código | Documento | Drive ID |
|---|---|---|
| OFF-001 | Edital Desafio Quant AI.pdf | `1XwZz5Val7ZnPghCg3wd5B7GE58M0utDD` |
| OFF-002 | Guia de Primeiros Passos – Desafio Quant AI 2026.pdf | `12rFTASNMP88ODUgYyyT43l5UHz47Nbmm` |
| OFF-003 | Criterios_Avaliacao_Desafio.pdf | `1nYjiRXYFyWCrIysqQiLsyHQD_L3Qnks4` |
| OFF-004 | Diretrizes Relatório Final.pdf | `1VO4QQj0I52d29GjvMJAjgHVE4JHUUU3K` |
| OFF-005 | Regulamento Desafio Quant AI 2026.pdf | `1TE8tf-MV4HNktufINHqUglDyPQoszlmA` |

Pasta principal do desafio: `152vF7375STYHVKKSChxiHOJKaJgHiAan`.

## Governança ARGOS — estado final

| Documento | Versão / papel | Drive ID |
|---|---|---|
| Current Truth final | `CT-v4.0` — fatos pós-ART-030 e submissão | `1MRWhaYaVkEwBVJTWTWtwziK7qQtFOtxJsvabzUV5Msw` |
| Registro Mestre | `SR-v3.0` + overlay final — proveniência | `12dGCC306uEVNC62qU8nUKL_jT__WKSD1jhzBT-VHXHk` |
| Constituição da tese | `ART-027 FREEZE v1.0 / TF-v1.0` | `1WyH-cJ_BB42r0jJ1LlU6JC4PQZHj3ysJAOnKdKsjH9o` |
| Matriz de Hipóteses | `HM-v4.0`; abas 12/13 finais | `1h1JAzYdqFurIP17_69c1ZWqcKI1NzrAbChi-DGLC8io` |
| Current Truth anterior | `CT-v3.0` — histórico pré-resultado | `16eXAZ2zi8VmPBnMCXg1j7QpB-PV6zWlsUg47CiVjhPA` |
| Arquivo integral pré-reancoragem | histórico | `1t3ezXqbe38bd93d17NUjsVL8i85aY0gmfyqjZqRAZ74` |

## Artefatos finais no repositório

| Arquivo | Papel |
|---|---|
| `registry/final_scientific_truth.json` | estado final H1–H5, champions, limitações e reopen rule |
| `registry/final_submission_answers_sf_v3.json` | sete respostas finais congeladas |
| `registry/final_submission_claims.csv` | claim boundary da submissão |
| `registry/final_submission_numbers.csv` | números autorizados |
| `registry/final_submission_manifest.json` | hashes/identidades do freeze |
| `registry/final_submission_freeze_validation.json` | resultado do validador final |
| `docs/29_final_scientific_truth_submission_freeze.md` | versão humana do freeze |
| `STATUS.yaml` | snapshot operacional |

Bundle SHA-256 final:

`c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

## Artefatos Google Workspace confirmados

| Artefato | Drive ID |
|---|---|
| ART-016 — Auditoria features M1-ZB | `1hH0G91tUsN_tAr6LEcIdnxd_diJOSKuaM3yPYYuHnpI` |
| ART-018 — Resultados M1-ZB | `19WVFoYzDX0FTAht4xti30DPvdZskseNquyUKNuJn2CY` |
| ART-019 — EXP-04 M3 | `12_1w7fvJGUBSw26HeQp47zOnh049S1lrcZiG0jA21FU` |
| ART-020 — Controle DAT-007 Equity | `1mcqyokeXaWBvPW2ZIA92FxSoxVnJ2pmcxjP2ZAssoFg` |
| ART-021 — Auditoria DAT-007 | `1Hst0x_IszR2BjxsmnV-XO0W8ey4sC6QNencJz9kYnhA` |
| ART-022 — EXP-05 horizonte | `1RhSm_K4UszP3phL6we7oF8YF2QisV5z4fWx-WK2ws7Y` |
| ART-023 — EXP-06 tradução econômica | `1fNcVAW7OgqGrpAg_p9gbIoM6Y1fHgnuAIEvF80jvr6I` |
| ART-024 — decisão EXP-06R | `1ztvcEdAO4GVL2Oq_BWS0JprzJgn-tHJKsBU8yQmfuLg` |
| ART-025 — resultados EXP-06R | `16-SejsFJeyk6GJXHCimXAWRGCUqeiEB68qsp3ZpfbsA` |
| ART-026 — protocolo EXP-06S | `19DjMY73v6HXZgREFd8-eLB5cwsz6Zlt3Vwv66akmFYc` |
| ART-027 — tese/freeze | `1WyH-cJ_BB42r0jJ1LlU6JC4PQZHj3ysJAOnKdKsjH9o` |

ART-022 está reconciliado e ART-025 usa o ID vivo acima.

## Fontes operacionais principais

- Polymarket Gamma API — universo/metadados.
- Polymarket Data/CLOB — trades e price history.
- Polymarket V1/V2 exchange contracts — semântica on-chain.
- SEC EDGAR + Investor Relations — timing e EPS oficial.
- NYSE/exchange-calendars — sessões/cutoffs.
- Yahoo Finance chart v8 + SPY — painel equity reproduzível aprovado.

As limitações e a classificação de fontes contextuais estão em `registry/information_inventory.csv` e `registry/ic07_contextual_data_matrix.csv`.

## Materiais educacionais

EDU-001 a EDU-007 e VID-001 permanecem registrados no SR-v3.0. Materiais não auditados integralmente não sustentam claims finais por default.

## Regra de precedência

Para fatos da submissão: `ART-027/TF-v1.0 → FST-v1.0 → CT-v4.0 → SF-v3.0 → final manifest/claims/numbers → artefatos individuais → histórico`.
