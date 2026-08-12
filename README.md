# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório operacional e reprodutível do **ARGOS**. A ciência confirmatória da submissão permanece congelada em **FST-v1.0 / SF-v3.0**. Para preservar a trilha histórica, a fase autorizada pelo freeze continua registrada como `FINAL_REPORT_AUTHORING_AND_QA`; o trabalho operacional atual é uma extensão **pós-freeze** separada, em `POST_FREEZE_EXTENSION_PLANNING`.

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

A continuação do projeto busca fechar duas lacunas metodológicas sem rescatar H2:

1. **Portfolio Backtest Integrity Upgrade** — recontabilizar as regras econômicas já congeladas como portfólio financiado, com overlaps, capital, NAV, exposição, turnover e métricas de portfólio, sem alterar sinais/thresholds/modelos/entry/exit com base no resultado.
2. **Information-Asymmetry Universe Research** — separar “melhor laboratório operacional” de “maior assimetria informacional”, criar um protocolo específico de assimetria e aprofundar o censo performance-blind de M&A completion/regulatory clearance, FDA e demais famílias relevantes.
3. **Novo experimento somente se gateado ex ante** — qualquer futura família alternativa só poderá entrar em um novo teste após protocolo, população, cutoffs, métricas, custos e stop rules serem congelados antes de abrir performance.

Roadmap humano: `docs/35_post_freeze_extension_roadmap.md`  
Estado machine-readable: `registry/post_freeze_extension_plan.json`

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

Para trabalho pós-freeze, use adicionalmente `registry/post_freeze_extension_plan.json` e `docs/35_post_freeze_extension_roadmap.md`. Eles têm autoridade apenas sobre a **extensão**, nunca sobre a verdade científica congelada.

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

Para a extensão pós-freeze: **freeze acima permanece imutável → post_freeze_extension_plan → futuros protocolos pré-resultado → futuros resultados**.

Nenhum novo threshold, subgrupo, feature, modelo, universo ou experimento pós-ART-030 pode alterar a verdade congelada da submissão sem erro factual/proveniência demonstrado.