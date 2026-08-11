# Experimentos e resultados consolidados

## H1 — M0 vs M2

O resultado mais sólido atual é probabilístico.

| Horizonte | M0 Brier | M2 Brier | Melhora M0−M2 | M2 AUC |
|---|---:|---:|---:|---:|
| T−3 | 0.19106193 | 0.15660954 | 0.03445239 | 0.7253 |
| T−1 | 0.19784897 | 0.15741267 | 0.04043630 | 0.7603 |

IC cluster-date da melhora:
- T−3: `[0.0069005, 0.0637691]`
- T−1: `[0.0106034, 0.0699468]`

Conclusão permitida: M2 supera os baselines públicos gratuitos testados em desempenho probabilístico, principalmente T−3/T−1.

## ART-018 — M1-ZB

- 224/224 previsões M0 reproduzidas;
- cobertura de 100% nos horizontes T−3/T−1 usados;
- zero leakage detectado;
- M1-ZB agrupado piorou M0 em T−3 e T−1;
- M2 permaneceu melhor que ambos.

Decisão: `COMPLETED_NO_M1_PROMOTION`.

## ART-019 — M3

- protocolo confirmatório congelado;
- pool adaptativo M0/M2 escolheu peso `1.00` em M2 nas `224/224` previsões;
- M3 adaptativo ficou idêntico a M2;
- pools fixos com 75% e 50% M2 pioraram Brier/log loss.

Decisão: `COMPLETED_NO_M3_PROMOTION`; M2 permanece champion.

## ART-022 — EXP-05 horizonte

**ATENÇÃO: bloqueado para uso final até reconciliação.** Há duas versões conflitantes.

### Planilha atual ART-022
Complete-case `n=57`:
- T−10 Brier `0.19937149`
- T−5 `0.17114300`
- T−3 `0.16884718`
- T−1 `0.16770252`
- ADAPT `0.17041945`
- protocolo SHA-256 `675f0a230b83cdda79d70f3a8d38908258e8132b30ada68b0549fb5b0d3c0006`

### SR-v3.0
Registra:
- T−10 `0.198839`
- T−5 `0.181715`
- T−3 `0.164346`
- T−1 `0.161021`
- ADAPT `0.165314`
- protocolo SHA-256 `c20ed9a4e16725829855ce7b2cc600fa95b818468bd09e30e55a46bd63901437`

Não usar valores de EXP-05 no PDF antes de fechar qual execução é autoritativa.

## ART-023 — EXP-06 tradução econômica

- regras pré-evento C1–C5 falharam gates;
- custos usados: long 20 bps round-trip; short 35 bps;
- C1 foi negativo;
- contrarian C5 teve ponto positivo, mas IC cruzou zero e correção de Holm falhou;
- bug material de GAMB foi detectado e corrigido exigindo `entry_date <= company_event_date`.

Decisão: `COMPLETED_NO_ECONOMIC_PROMOTION`; `C0_NO_TRADE` permanece champion.

## ART-024/025 — EXP-06R

R1 congelou drift confirmado por M2 + reação pós-evento. Resultado primário T−1/10:

- 108 oportunidades;
- 34 trades;
- retorno líquido ajustado ao SPY por oportunidade: `−0.205034%`;
- IC: `[−0.971914%, +0.559016%]`;
- Holm p = `1.0`.

R1 rejeitada.

R3 diagnóstico:

- 108 oportunidades;
- 57 trades;
- `+1.350315%` por oportunidade;
- IC `[+0.236616%, +2.470575%]`;
- p unilateral `0.009199`;
- Holm p `0.036796`;
- mediana por trade `+1.8970%`;
- hit rate `64.91%`.

**R3 não pode ser promovido:** usa somente reação da ação pós-evento e quebra a cadeia prediction-market → movimento → evento → ativo.

## ART-026 — EXP-06S

Protocolo de confirmação independente de R3 foi congelado, mas após ART-027 passou a `SUSPENDED_DIAGNOSTIC_NOT_CORE`. Não consumir caminho crítico.

## ART-027 e próximo experimento

ART-027 reancorou a tese em movimentos anormais e definiu:

- ART-028: auditoria de viabilidade dos dados de movimentos (`SUPPORT`);
- ART-029: protocolo pré-resultados do EXP-07I;
- ART-030: execução H2 `M2 vs M_MOVE`.

Esse é o experimento decisivo que falta.
