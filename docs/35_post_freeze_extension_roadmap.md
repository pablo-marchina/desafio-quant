# ARGOS — Roadmap de extensão pós-freeze

**Estado:** `POST_FREEZE_PROTOCOLS_SYNTHETICALLY_VALIDATED_READY_FOR_FREEZE`  
**Science reopened:** `false`  
**Autoridade da submissão preservada:** `FST-v1.0 / SF-v3.0 / ART-029 / ART-030`

## Baseline imutável

H1 continua `SUPPORTED_IN_TESTED_SAMPLE`; H2 continua `FAIL_UNDER_FROZEN_EXP07I`; H3/H4/H5 permanecem bloqueadas; `M2` continua champion probabilístico e `C0_NO_TRADE` champion econômico histórico. O PDF QA-approved permanece checkpoint seguro.

## W2-A — funded portfolio accounting

A pesquisa e o protocol design foram concluídos sem abrir novo P&L de portfólio. O draft `W2A-PA-DRAFT-v1.0` transforma somente o R1 primário congelado em contabilidade financiada diária.

Principais invariants:

- 34 trades / 21L / 13S, T−1, 10 sessões e custos 20/35 bps permanecem imutáveis;
- normalização de capital depende apenas de schedule/sign-cost class, nunca realized prices/PnL;
- short proceeds são restricted e não financiam novas posições;
- cash negativo falha `NO_LEVERAGE_CASH_GATE`; não existe recapitalização ex post;
- matched-SPY replica sign/dates/notional/overlaps;
- starting capital `C0=1` é high-water mark inicial do drawdown;
- bootstrap primário opera em additive active daily PnL;
- Sharpe/Sortino são secundários;
- Gate 0 de reconciliação legada vem antes de qualquer métrica real.

Synthetic validator: **20/20 PASS**.

## W2-B — IAS + feasibility

O draft `W2B-IAS-DRAFT-v1.0` mantém IAS separado de viabilidade.

Dimensões estruturais: `PAC / LSO / SIB / TAW / PSI`, cada uma com anchors 0–5 explícitos.

ECG governa incerteza da evidência: A `±0.5`, B `±1`, C `±2` por triangular clipped; D = evidência insuficiente, anchor null e `Uniform(0,5)`. ECG-D é `UNRESOLVED`, não score baixo.

Score central, apenas com evidência completa: média igual das cinco dimensões. Robustez global: SMAA com `Dirichlet(1,1,1,1,1)`, seed `20260812`, 200k draws na futura avaliação real.

Robust-high requer `IAS_central>=3`, `P(IAS>=3)>=0.75` e evidence gate. Claim de “maior assimetria” exige ainda rank-1 `>=0.50` e margem `>=0.05` sobre runner-up.

Feasibility permanece em F1–F9: contractability, PIT PM, sample floor, resolução, linked asset, PIT asset, safe cutoff, mandatory inputs e reproducibility. Passar tudo autoriza apenas `ELIGIBLE_TO_DRAFT_W3_PROTOCOL`, não executar W3.

Synthetic validator: **18/18 PASS**.

## Adversarial review

Combined suite: **38/38 PASS** sem ler real ARGOS performance nem real IAS family scores.

Correções encontradas antes do freeze:

1. drawdown W2-A deve iniciar do capital 1.0;
2. capital normalization não pode depender de MTM realizado;
3. catastrophic short deve falhar cash gate em vez de aumentar capital;
4. bootstrap ativo deve reconciliar exatamente terminal active wealth;
5. ECG-D deve ficar unresolved e fora de claims comparativos confiantes;
6. practical IAS tie usa feasibility ex ante, nunca ARGOS performance;
7. W2 GO autoriza somente drafting de W3; execução exige freeze W3 separado com adequacy prospectiva.

Detalhes: `docs/38_w2a_portfolio_accounting_contract_draft.md`, `docs/39_w2b_ias_feasibility_contract_draft.md`, `docs/40_w2_protocol_adversarial_review.md`.

## Próxima transição permitida

**Não executar dados reais ainda.** O próximo passo é byte-freeze dos dois drafts revisados. Se qualquer conteúdo substantivo mudar, criar nova versão de draft e rerodar os 38 synthetic cases antes do freeze.

Depois do freeze:

1. executar W2-A e fechar Gate 0 antes de abrir métricas;
2. executar W2-C discovery performance-blind;
3. preencher IAS + feasibility;
4. emitir `GO_DRAFT_W3_PROTOCOL` ou `NO_GO_NO_W3_PROTOCOL_CANDIDATE`;
5. se GO, fazer W3 design/power/precision/simulation adequacy e freeze próprio antes de outcomes.

Nenhuma etapa pode alterar retrospectivamente H2 ou substituir a ciência congelada por um resultado mais conveniente.
