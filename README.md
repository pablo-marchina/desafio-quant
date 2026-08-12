# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0**. A fase histórica autorizada pelo freeze continua `FINAL_REPORT_AUTHORING_AND_QA`; a extensão pós-freeze é separada e não modifica a verdade científica.

> **Anonimato:** este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.

## Estado científico congelado

- H1: `SUPPORTED_IN_TESTED_SAMPLE`
- H2: `FAIL_UNDER_FROZEN_EXP07I`
- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`
- H4: `BLOCKED_BY_H2_FAIL`
- H5: `BLOCKED_BY_H4`
- champion probabilístico: `M2`
- champion econômico: `C0_NO_TRADE`
- official EPS independente: 116/117; 116/116 validados concordantes; residual `BLSH|2025-09-17`
- frozen bundle: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

Autoridade primária: `registry/final_scientific_truth.json`, seguida por `registry/final_submission_answers_sf_v3.json`, claims/numbers/manifest e `registry/final_submission_freeze_validation.json`.

O resultado congelado continua negativo para a incrementalidade H2. Nenhuma extensão pode transformar esse resultado em alpha pós-hoc.

## PDF baseline preservado

`registry/final_report_pdf_qa.json` registra `PASS_READY_FOR_SUBMISSION`. O PDF QA-approved possui SHA-256 `5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`, 5 páginas, 16:9 e anonimato validado. Qualquer PDF futuro exige novo hash e QA completo.

## W2 freeze

Os contratos W2-A e W2-B/IAS estão congelados byte a byte em `W2PF-v1.0`:

- W2-A blob: `639f900eb876d6e46ecbeb10c1b3b3e6c3621a28`
- W2-B blob: `cb9a9638f236c6c61c97f86805de9bf666209b21`
- freeze bundle: `e7b48d08f657aea7552f2a692f19c1b941ebd678aa03d8ff28b961c0b317777b`
- synthetic validation pré-freeze: 38/38 PASS.

Manifesto: `registry/w2_protocol_freeze_manifest.json`.

## Extensão pós-freeze — estado atual

`registry/post_freeze_extension_plan.json`: `PFEP-v1.5` / `W2A_GATE0_BLOCKED_W2C_DISCOVERY_MATERIALIZED`.

### W2-A — Gate 0

Gate 0 foi executado e terminou em:

`FAIL_GATE0_MISSING_AUTHORITATIVE_ART025_TRADE_LEVEL_LEDGER`.

O workbook ART-025 autoritativo contém apenas resultados agregados/protocolo/auditoria e não preserva o ledger row-level exigido pelo contrato W2-A. ART-023 existe, mas usa semântica EXP-06 anterior e não pode ser relabelado como ART-025. Não houve reconstrução com vendor novo.

Consequência: **NAV financiada, Sharpe, Sortino, portfolio MDD, turnover e exposure path não foram calculados**. W2-A só pode retomar se a materialização row-level original de ART-025 for recuperada com provenance.

- machine-readable: `registry/w2a_gate0_reconciliation.json`
- humano: `docs/42_w2a_gate0_reconciliation.md`

### W2-C — performance-blind discovery

O discovery foi materializado sob `W2C-DISC-v2.0` / `W2C-DF-v2.0` depois de duas tentativas pré-resultado que falharam por exigir exaustão do archive. O v2.0 foi congelado antes de abrir resultados de família e usa discovery bounded de **lower bounds**, com telemetria explícita de truncamento.

Execução autoritativa: GitHub Actions run `31610392101` — hash gate, discovery, firewall e persistência: PASS.

Snapshot promovido a `main` sem regeneração:

- 13.491 eventos únicos observados entre canais;
- 4.364 candidate rows;
- 154 rotas de paginação;
- 4 rotas truncadas.

Esses counts são **raw/unvalidated discovery candidates**, não population estimates, IAS, F1–F9 ou seleção de W3.

- materialização/provenance: `registry/w2c_discovery_materialization_v2_0.json`
- summary: `registry/w2c_discovery_summary.json`
- fila: `registry/w2c_discovery_validation_queue.csv.gz`
- telemetria: `registry/w2c_discovery_pagination_telemetry.json`
- humano: `docs/43_w2c_performance_blind_discovery.md`

### IAS / W3

Nenhum IAS real foi calculado e nenhum gate F1–F9 foi pontuado. W3 continua não autorizado.

A próxima ação válida é **congelar um protocolo outcome-blind de semantic validation** para a fila W2-C antes de transformar candidatos em evidência validada. Em paralelo, W2-A só admite busca por recuperação de provenance original — não reconstrução de mercado pós-hoc.

## Navegação

- `STATUS.yaml` — estado científico/histórico do freeze.
- `docs/README.md` — mapa de documentação.
- `registry/README.md` — precedência dos registries.
- `scripts/README.md` — executáveis e validators.
- `.github/workflows/README.md` — workflows/gates.
- `docs/29_final_scientific_truth_submission_freeze.md` — freeze humano.
- `docs/35_post_freeze_extension_roadmap.md` — roadmap pós-freeze.
- `docs/36`–`41` — pesquisa, contracts, revisão adversarial e byte-freeze W2.
- `docs/42` — W2-A Gate 0.
- `docs/43` — W2-C discovery.

## Política de governança

- nunca sobrescrever protocolo histórico para refletir resultado posterior;
- nunca usar P&L/Brier/log loss/H2 para escolher família IAS;
- nunca inferir IAS/F1–F9 de raw discovery counts;
- não inventar ART-025 trade rows, borrow fee, L2 histórico ou dados PIT indisponíveis;
- preservar resultados negativos, NO-GO e falhas;
- qualquer W3 precisa de hipótese/estimand, população, cutoffs, adequacy prospectiva, modelos, benchmark, custos, inferência, multiplicidade, stop/promotion rules congelados antes dos outcomes.

## Validação do `main`

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2_protocol_freeze_validate.py
```

`repository_hygiene_validate.py` continua verificando byte-identidade do frozen submission bundle. `w2_protocol_freeze_validate.py` protege os bytes de W2PF-v1.0.
