# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0**. Para preservar a trilha histórica, a fase autorizada pelo freeze continua registrada como `FINAL_REPORT_AUTHORING_AND_QA`; o trabalho operacional atual é uma extensão **pós-freeze** separada, em `POST_FREEZE_PROTOCOL_DRAFTING`.

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

O resultado congelado não é uma estratégia long/short promovida: a probabilidade agregada da Polymarket teve valor preditivo frente aos baselines públicos gratuitos testados, mas a camada congelada de movimentos não acrescentou informação incremental demonstrável além de M2. O stop rule encerra a cadeia testada em **no-trade**.

## Baseline de submissão preservado

O relatório de cinco páginas já possui QA independente registrado em `registry/final_report_pdf_qa.json` com status `PASS_FINAL_REPORT_PDF_QA_READY_FOR_SUBMISSION` e veredito `PASS_READY_FOR_SUBMISSION`.

- page set autoritativo: `report/pages_submission/`;
- PDF aprovado: `ARGOS_Desafio_Quant_AI_2026_FINAL.pdf`;
- SHA-256 do PDF aprovado: `5144f85f77d1f1d72ed06a9b867e92f47fd139f58729cf25c76e80bd9095a561`;
- exatamente 5 páginas, 16:9, anonimato e renderização validados.

Esse PDF é **checkpoint seguro**, não autorização para reescrever a ciência. Qualquer versão posterior deve preservar o baseline, regenerar hash e repetir o QA.

## Extensão pós-freeze atual

A pesquisa metodológica pré-freeze de W2-A e W2-B/IAS foi concluída **sem calcular novo P&L de portfólio, sem pontuar famílias reais no IAS e sem congelar protocolos**. O estado atual é `POST_FREEZE_PROTOCOL_DRAFTING`.

### W2-A — Portfolio Backtest Integrity Upgrade

A recomendação de pesquisa é reconstruir o **mesmo R1 primário congelado** como um portfólio financiado, não criar um novo otimizador. A reconciliação exata dos 34 trades (21 long / 13 short) com ART-025 será o gate zero; NAV, exposição, turnover, max drawdown e métricas de risco só serão reportáveis depois dessa reconciliação e de um protocolo próprio congelado.

### W2-B — Information-Asymmetry Score

A pesquisa concluiu que IAS não deve ser “EUAS com outros pesos”. O candidato é um índice **formativo de assimetria estrutural**, separado dos gates de viabilidade, com cinco dimensões ainda não congeladas: `PAC`, `LSO`, `SIB`, `TAW` e `PSI`. A força da evidência ficará em uma camada separada de confiança, e a robustez de ranking deverá testar incerteza de pesos/anchors em vez de depender de um único vetor especialista.

### W2-C / W3

O deep census só começará depois do freeze do protocolo IAS/discovery. Um novo experimento continuará bloqueado até uma família passar, ex ante, tanto os critérios de assimetria quanto os gates de viabilidade. Nenhum desses passos reabre H2.

Artefatos atuais:

- roadmap: `docs/35_post_freeze_extension_roadmap.md`;
- pesquisa W2-A: `docs/36_w2a_portfolio_backtest_methodology_research.md`;
- pesquisa W2-B/IAS: `docs/37_w2b_ias_methodology_research.md`;
- síntese machine-readable da pesquisa: `registry/post_freeze_methodology_research_v1.json`;
- estado da extensão: `registry/post_freeze_extension_plan.json`.

**Regra absoluta:** nenhum artefato dessa extensão pode alterar retrospectivamente `FAIL_UNDER_FROZEN_EXP07I`, promover um subgrupo de earnings ou transformar um resultado negativo antigo em alpha.

## Fonte de verdade

Para a submissão congelada, leia nesta ordem:

1. `STATUS.yaml` — estado científico/operacional do freeze.
2. `registry/final_scientific_truth.json` — verdade científica final.
3. `registry/final_submission_answers_sf_v3.json` — sete respostas finais congeladas.
4. `registry/final_submission_claims.csv` — fronteira de claims permitidos/proibidos.
5. `registry/final_submission_numbers.csv` — números autorizados para a entrega.
6. `registry/final_submission_manifest.json` — manifesto de hashes e identidades.
7. `registry/final_submission_freeze_validation.json` — prova do gate final executado.
8. `registry/final_report_pdf_qa.json` — QA do PDF baseline.
9. `docs/29_final_scientific_truth_submission_freeze.md` — leitura humana do freeze.

Para trabalho pós-freeze, use adicionalmente `registry/post_freeze_extension_plan.json`, `registry/post_freeze_methodology_research_v1.json` e `docs/35`–`37`. Eles têm autoridade apenas sobre a **extensão**, nunca sobre a verdade científica congelada.

Bundle final congelado: `c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885`.

## Estrutura do repositório

```text
.
├── README.md                  # entrada e navegação
├── STATUS.yaml                # estado científico congelado + execução histórica
├── data/                      # datasets derivados auditáveis necessários à reprodução
├── docs/                      # documentação ativa + histórico científico + extensão pós-freeze
├── registry/                  # contratos, manifests, gates, claims, hashes e summaries
├── report/                    # figures e page sets do relatório
├── scripts/                   # pipelines e validadores reproduzíveis
├── templates/                 # templates metodológicos
└── .github/workflows/         # execuções reproduzíveis e gates de CI
```

Consulte os índices locais em `docs/README.md`, `registry/README.md`, `scripts/README.md` e `.github/workflows/README.md`.

## Política de limpeza

**Não deletar nem reescrever evidência histórica para deixar o repositório “bonito”.** Resultados negativos, protocolos pré-resultados, outputs superados e falhas documentadas fazem parte da trilha de auditoria.

- separar claramente **autoritativo atual** de **histórico**;
- preservar o baseline de submissão e sua trilha de hashes;
- não usar extensão pós-freeze para reclassificar H1–H5 antigos;
- manter raw/derivados e hashes necessários à reprodução;
- evitar arquivos locais, caches, secrets e outputs temporários no Git;
- impedir que documentação antiga ou pesquisa futura substitua o freeze final.

## Validação atual

Para verificar a integridade **pós-finalização**, rode:

```bash
python scripts/repository_hygiene_validate.py
```

Esse validador confirma que os 8 blobs do `final_submission_manifest.json` continuam byte-idênticos, que o bundle SHA permanece congelado e que a navegação ativa continua alinhada a FST-v1.0/SF-v3.0. A extensão pós-freeze é deliberadamente adicional e não muda os hashes do bundle.

`final_submission_freeze_validate.py` é preservado como **validador histórico do momento de freeze** e continua esperando a fase `FINAL_REPORT_AUTHORING_AND_QA` autorizada pelo manifesto.

## Regra de precedência

Para o conteúdo submetido: **ART-027/TF-v1.0 → FST-v1.0 → CT-v4.0 → SF-v3.0 → manifesto/claims/números finais → QA do PDF → artefatos individuais → documentação histórica**.

Para a extensão pós-freeze: **freeze acima permanece imutável → post_freeze_extension_plan → pesquisa metodológica → futuros protocolos pré-resultado → futuros resultados**.

Nenhum novo threshold, subgrupo, feature, modelo, universo ou experimento pós-ART-030 pode alterar a verdade congelada da submissão sem erro factual/proveniência demonstrado.
