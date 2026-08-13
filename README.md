# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0 / ART-029 / ART-030**. A extensão pós-freeze atual é a **W4 — Maximal Backtest Research**, separada da verdade científica original e mantida performance-blind até um futuro outcome reveal controlado.

> **Anonimato:** este repositório identifica seus autores pelo GitHub e não deve ser citado/linkado no PDF final.

## Estado científico congelado

- H1: `SUPPORTED_IN_TESTED_SAMPLE`
- H2: `FAIL_UNDER_FROZEN_EXP07I`
- H3: `BLOCKED_BY_H2_FAIL_NO_RESCUE`
- H4: `BLOCKED_BY_H2_FAIL`
- H5: `BLOCKED_BY_H4`
- champion probabilístico: `M2`
- champion econômico histórico: `C0_NO_TRADE`
- frozen bundle: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`

Autoridade científica primária: `registry/final_scientific_truth.json`.

O resultado H2 continua negativo. Nenhuma extensão pode ser usada como resgate pós-hoc.

## Extensão pós-freeze — estado atual

Plano operacional: `registry/post_freeze_extension_plan.json` — **`PFEP-v4.0`** / `W4_MAXIMAL_BACKTEST_RESEARCH_ACTIVE_PRE_OUTCOME_FREEZE`.

Plano W4 detalhado: `registry/w4_maximal_backtest_research_plan_v1.json` + `docs/45_w4_maximal_backtest_research_plan.md`.

### Objetivo W4

Construir o maior backtest histórico **defensável, PIT e reproduzível** possível, maximizando simultaneamente:

1. **N independente** de `canonical_event_id`;
2. **profundidade temporal** pré-evento;
3. **breadth informacional** de venues, contratos, ativos, horizontes e camadas de dados;
4. **profundidade de validação** com falsificação e inferência dependence-aware.

`N>=300`, `N>=500` e `N>=1000` são marcos, não stop rules. A coleta para apenas por **saturação marginal**, falha de PIT/provenance/reprodutibilidade, falta de justificativa econômica ou inviabilidade de custo/tempo.

### Regra de independência

A unidade inferencial padrão é `canonical_event_id`.

Markets, strikes, venues, ativos, horizontes, quotes, trades e ticks podem aumentar informação por evento, mas nunca aumentam automaticamente o N independente.

### Estado do census

A pesquisa W4-BER-v1.0 já está preregistrada e performance-blind. O último workflow executado foi `W4 Kalshi Series-First Census` no commit `7fdb8cd`; ele falhou no step de census com HTTP 400 antes de materializar o resultado.

O blocker é operacional/API. A correção autorizada não pode alterar o frozen family dictionary nem consultar linked-asset outcomes.

### Ordem W4

1. **W4-R** — maximal backtest research;
2. **W4-A** — reparar e validar Kalshi series-first census;
3. **W4-B** — exhaustive multi-venue census;
4. **W4-C** — attrition + saturation audit;
5. **W4-D** — canonical event-centric data lake;
6. **W4-E** — maximal pre-outcome feature materialization;
7. **W4-F** — outcome-blind adequacy/simulation;
8. **W4-G** — full W4 protocol freeze;
9. **W4-H** — single controlled outcome reveal;
10. **W4-I** — backtest battery + funded accounting;
11. **W4-J** — maximal robustness/falsification/inference battery;
12. **W4-K** — W4 scientific truth freeze.

Backtests planejados, todos congelados antes de outcomes:

- BT-A — Expanded Discrete Replication;
- BT-B — Continuous All-Event Portfolio;
- BT-C — Distributional Multi-Venue;
- event-response surface;
- microstructure event study quando houver histórico PIT suficiente.

## Histórico W2/W3 preservado

### W2-A — funded portfolio accounting

Concluído sobre o R1 congelado:

- terminal NAV: `1.0019679107011892`;
- total return: `+0.196791%`;
- matched-SPY total return: `+2.649834%`;
- max drawdown: `-6.384130%`;
- HAC Sharpe lag 10: `0.0751533`;
- decisão: `NO_PROMOTION_R1`.

`C0_NO_TRADE` continua champion econômico histórico.

### W2-C — discovery / semantic / PIT-v2.1

312/335 candidatos aceitos; 260 eventos entraram no PIT-v2.1. As três famílias exatas testadas terminaram `NO_GO_CURRENT_PROTOCOL`:

- `EARNINGS_EPS`;
- `FDA_FINAL_PDUFA_DECISION`;
- `MACRO_STATISTICAL_RELEASE`.

As famílias não testadas permanecem `FEASIBILITY_NOT_ESTABLISHED`.

### W2-B — IAS / ECG / SMAA

- 50 células `família × dimensão`;
- 200.000 SMAA draws;
- seed `20260812`;
- resultado: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`;
- líder numérico: `MA_PRE_ANNOUNCEMENT_OR_RUMOR`, rank-1 `45.704%`;
- runner-up: `FDA_FINAL_PDUFA_DECISION`, rank-1 `40.4465%`.

### W3

O gate final IAS × PIT permanece registrado como **frozen pré-combinação real**. A W4 é uma trilha separada de pesquisa de capacidade/dados e não implica autorização W3 nem reabertura de outcomes.

## PDF baseline preservado

`registry/final_report_pdf_qa.json` registra `PASS_READY_FOR_SUBMISSION`. O PDF QA-approved possui SHA-256 `5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`, 5 páginas, 16:9 e anonimato validado.

## Navegação

- `STATUS.yaml` — estado científico/histórico congelado;
- `registry/post_freeze_extension_plan.json` — estado operacional atual (`PFEP-v4.0`);
- `registry/w4_maximal_backtest_research_plan_v1.json` — plano W4 machine-readable;
- `docs/45_w4_maximal_backtest_research_plan.md` — roadmap W4 detalhado;
- `docs/44_w4_quantitative_backtest_expansion_research.md` — pesquisa W4 anterior preservada;
- `docs/35_post_freeze_extension_roadmap.md` — histórico consolidado W2/W3 + transição W4;
- `docs/README.md` — mapa de documentação;
- `registry/README.md` — precedência dos registries;
- `scripts/README.md` — executáveis e validators;
- `.github/workflows/README.md` — workflows/gates.

## Política de governança

- protocolo pré-resultado nunca é reescrito para refletir resultado posterior;
- resultado negativo, FAIL, INDETERMINATE e NO-GO são preservados;
- H2 e `C0_NO_TRADE` permanecem imutáveis como truth histórica;
- W4 permanece performance-blind até o controlled reveal;
- linked-asset realized returns não podem selecionar fontes, famílias ou features antes do freeze;
- não alterar o frozen W4 family dictionary para inflar N;
- `canonical_event_id` é a unidade inferencial padrão;
- pseudo-replicação por contracts/assets/horizons/ticks é proibida;
- W3 pending state é preservado separadamente.

## Próxima ação

Corrigir o request/routing histórico da Kalshi sem alterar a semântica científica, reexecutar e materializar o series-first census e então iniciar o registry exaustivo de venues/fontes + multi-venue attrition census.

## Health checks

```bash
python scripts/repository_hygiene_validate.py
python scripts/w2b_ias_frozen_bundle_integrity_v1.py
python scripts/w2b_ias_smaa_result_freeze_validate_v1.py
python scripts/w3_go_no_go_synthetic_v1.py
```
