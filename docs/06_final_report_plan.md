# Plano de ação — maximização de score, relatório final e QA

**Entrega:** 17/08/2026.  
**Fase científica:** congelada em `FST-v1.0 / SF-v3.0`; não abrir nova busca de resultado.  
**Subfase editorial atual:** `WAVE_1_SCORING_CONTRACT_AND_CRITICAL_AUDITS`.  
**Princípio:** primeiro maximizar a qualidade defensável da tese/evidência; só depois desenhar as cinco páginas.

## Objetivo

Transformar a evidência já congelada em um PDF anônimo, autossuficiente, visual e rigoroso de **até 5 páginas, horizontal 16:9**, maximizando os critérios da banca sem alterar a verdade científica.

A autoria do PDF **não começa pela estética**. Antes, Wave 1 deve resolver três dúvidas que afetam diretamente a nota:

1. a complexidade técnica usada foi adequada e suficientemente sofisticada para o mecanismo/amostra?
2. o backtest econômico já executado é completo e defensável para o critério de Backtest?
3. earnings/EPS foi um universo ex-ante adequado à tese de assimetria informacional, e como isso deve ser explicado?

## Scoring contract

O contrato de maximização está em:

- `docs/30_report_scoring_maximization_contract.md`;
- `registry/report_scoring_maximization_matrix.csv`;
- `registry/wave1_maximization_status.json`.

Pesos usados para otimização:

| Critério | Peso |
|---|---:|
| Conceito da estratégia | 20% |
| Modelagem | 20% |
| Backtest | 15% |
| Análise dos resultados | 15% |
| Uso de IA Generativa | 15% |
| Conclusão e próximos passos | 10% |
| Apresentação do robô | 5% |

## Wave 1 — Scoring Contract + três audits críticos

### W1-0 — Report Scoring Maximization Contract

**Objetivo:** mapear 100% da rubrica a evidência, visual, página, claim e risco.

**Artefato:** `docs/30_report_scoring_maximization_contract.md`.

**Regra:** nenhum elemento entra no PDF apenas por ser interessante; precisa ganhar pontos ou ser necessário para interpretar corretamente a evidência.

### W1-A — Model Complexity & Technique Sufficiency Audit

**Objetivo:** demonstrar que a sofisticação do projeto está na combinação de busca ampla + redução outcome-blind + parcimônia compatível com o n efetivo, e não em quantidade de parâmetros.

**Artefato:** `docs/31_model_complexity_technique_sufficiency_audit.md`.

Questões principais:
- cobertura das principais famílias de mecanismo;
- redundância antes dos outcomes;
- complexidade relativa a 75 previsões OOS / 54 clusters;
- justificativa para modelo interpretável regularizado + um challenger;
- técnicas deferidas por dados/sample complexity;
- wording e visual report-safe.

### W1-B — Economic Backtest Quality Audit

**Objetivo:** provar exatamente o que foi historicamente simulado em termos de capital e recuperar o melhor conjunto de métricas já permitido pelos trials congelados.

**Artefato:** `docs/32_economic_backtest_quality_audit.md`.

Prioridade: **máxima**, porque este é o maior risco restante para os 15% de Backtest.

Auditar:
- regra de sinal/entry/exit/holding;
- long/short/no-trade mapping;
- benchmark SPY e C0;
- custos/slippage assumidos;
- opportunities/trades/exposure;
- retornos gross/net;
- equity curve, drawdown, volatility, turnover e distribuição de trades **somente se deterministicamente deriváveis de regras/trades já congelados**;
- multiplicidade e anti-overfit;
- distinção entre backtest informacional e econômico.

Proibido: criar uma nova regra vencedora, threshold, subgroup, horizon ou timing.

### W1-C — Event Universe Information-Asymmetry Audit

**Objetivo:** avaliar ex ante se earnings/EPS foi um bom laboratório para o mecanismo de assimetria/difusão informacional e definir como universos futuros devem ser escolhidos.

**Artefato:** `docs/33_event_universe_information_asymmetry_audit.md`.

Dimensões:
- information asymmetry potential;
- ex-ante contractability;
- prediction-market observability;
- liquidity/statistical density;
- linked-asset sensitivity;
- resolution objectivity;
- sampleability;
- cross-market timing opportunity;
- public-information saturation;
- contract-creation/selection bias;
- data/execution friction.

Comparar, sem outcome cherry-picking: earnings/EPS, M&A completion/approval, FDA/advisory, antitrust/regulatory, litigation/legal, macro/Fed e outras famílias corporativas elegíveis.

## Wave 1 exit gate

A Wave 1 fecha quando:

- [ ] 100% do peso da rubrica está mapeado a evidência e visual;
- [ ] W1-A tem verdict explícito de complexidade/suficiência;
- [ ] W1-B inventaria todas as regras econômicas relevantes e métricas display-safe;
- [ ] W1-B decide se faltam apenas cálculos descritivos determinísticos de trades congelados;
- [ ] W1-C congela dimensões/weights antes de pontuar famílias históricas;
- [ ] W1-C classifica earnings com base em propriedades ex ante e evidência primária;
- [ ] framing final da tese pode ser congelado sem contradizer FST-v1.0;
- [ ] nenhuma análise reabre H2 ou promove R3.

## Wave 2 — Thesis & Authoring Evidence Freeze

Após Wave 1:

1. `ARGOS INVESTMENT THESIS — REPORT FRAMING FREEZE`;
2. `FINAL REPORT AUTHORING EVIDENCE PACK`;
3. consolidar números H1/H2/econômicos/GenAI que podem aparecer no PDF;
4. especificar visuals por critério e página.

## Wave 3 — Robot / Visual System / Figure Factory

- identidade ARGOS coerente com `observe → validate → allocate`;
- slogan preferencial: **“Informação só vira posição quando sobrevive ao teste.”**;
- evitar estética genérica de crypto/robô neon;
- gerar somente figuras que explicam mecanismo, desenho anti-bias, resultado ou decisão.

## Wave 4 — 5-page report build

A arquitetura final só será congelada depois da Wave 1. A hipótese de trabalho é:

### Página 1 — ARGOS: tese e política de capital

- nome/identidade;
- ineficiência/mecanismo cross-market;
- `SENSOR → DETECTOR → VALIDATOR → TRANSMISSION → CAPITAL`;
- saída `LONG / SHORT / ABSTAIN`.

### Página 2 — pesquisa, modelagem e anti-overfit

- research funnel `69 → mecanismo independente → 6 features → 1 modelo + 1 challenger`;
- dados PIT;
- walk-forward / same-date batching / freeze.

### Página 3 — teste informacional decisivo

- H1 M2;
- H2 `M2_RAW / M2_CAL / M_MOVE_CORE`;
- ΔBrier/ΔLogLoss, ICs e estabilidade temporal;
- `FAIL_H2` corretamente interpretado.

### Página 4 — capital e backtest econômico

- resultados econômicos já congelados;
- custos/benchmark/risk metrics aprovados pela W1-B;
- stop rule e `C0_NO_TRADE`;
- R3 apenas se útil como exemplo de resultado atraente recusado por desalinhamento causal.

### Página 5 — GenAI, conclusão e próximo experimento

- três casos GenAI de maior impacto;
- human-in-the-loop e outcome firewall;
- limites do laboratório earnings;
- próxima geração de universo definida pela W1-C;
- conclusão proporcional.

## Contrato editorial permanente

O relatório deve mostrar simultaneamente:

- identidade ARGOS e problema econômico;
- mecanismo e tese de investimento;
- modelagem adequada ao n efetivo;
- dados e disciplina point-in-time;
- evidência positiva de H1;
- resultado confirmatório negativo de H2;
- backtest econômico realmente executado;
- consequência `C0_NO_TRADE` sem vender ausência de edge como alpha;
- uso concreto de GenAI e controles humanos;
- limitações materiais;
- conclusão crítica e próximo experimento ex ante.

Qualquer número usado precisa existir no authoring evidence pack/frozen registries. Qualquer frase material precisa respeitar `registry/final_submission_claims.csv` e `registry/final_scientific_truth.json`.

## Adversarial scoring QA

Antes da versão final, simular pelo menos:

- **Quant reviewer:** leakage, timing, overfit, n efetivo, inferência;
- **Portfolio manager:** edge, capital, costs, benchmark, no-trade;
- **Skeptical academic:** claims proporcionais e pós-hoc;
- **Fast reviewer:** entendimento em ~30 segundos por página;
- **GenAI reviewer:** contribuição real + validação;
- **Compliance reviewer:** anonimato, URLs, metadados e limites de claims.

Fazer pelo menos duas waves de scoring: `QA-1 → correção → QA-2`.

## Checklist técnico do PDF

- [ ] `≤ 5` páginas;
- [ ] horizontal `16:9`;
- [ ] pt-BR;
- [ ] legível em tela cheia sem zoom;
- [ ] sem identidade pessoal/institucional;
- [ ] sem speaker notes/comments/metadados identificáveis;
- [ ] sem links necessários para entendimento;
- [ ] sem URL pública do repositório;
- [ ] texto e figuras não cortados;
- [ ] PDF reaberto e inspecionado após exportação;
- [ ] hash SHA-256 final registrado;
- [ ] nome final `[chave].pdf`;
- [ ] comprovante de submissão preservado.

## QA científico antes da exportação

Rode:

```bash
python scripts/repository_hygiene_validate.py
```

Depois compare manualmente o PDF contra:

- `registry/final_scientific_truth.json`;
- `registry/final_submission_freeze_validation.json`;
- `registry/final_submission_claims.csv`;
- `registry/final_submission_numbers.csv`;
- `registry/final_submission_answers_sf_v3.json`;
- authoring evidence pack criado na Wave 2.

## Regra de mudança

Após FST-v1.0/SF-v3.0, **design, framing e seleção de evidência podem melhorar; ciência não pode ser reescrita**. Só corrigir o freeze se surgir erro factual/proveniência demonstrado ou conflito com fonte oficial mais autoritativa.
