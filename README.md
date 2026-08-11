# ARGOS — Desafio Itaú Asset Quant AI 2026

Repositório central de trabalho do **ARGOS**, consolidando o estado científico, a proveniência, os experimentos, os claims, as pendências e o plano do relatório final.

> **Importante:** este repositório é operacional e identifica seus autores pelo próprio GitHub. **Não deve ser citado nem linkado no PDF final**, que precisa ser totalmente anônimo.

## Estado atual

- **Tese:** congelada em ART-027 / TF-v1.0.
- **Implementação empírica inicial:** Polymarket + contratos de earnings/EPS + ações individuais dos EUA.
- **Champion probabilístico:** `M2` — probabilidade point-in-time da Polymarket.
- **Champion econômico:** `C0_NO_TRADE` entre as regras já testadas.
- **H1:** suportada no conjunto testado.
- **H2:** pendente — principal gate atual.
- **H3:** bloqueada até H2.
- **H4:** bloqueada até H2.
- **H5:** bloqueada até H4.
- **Próximo caminho crítico:** `ART-028 → ART-029 → ART-030 / EXP-07I → H4 → H5`.
- **Entrega final:** 17/08/2026.

## Estrutura

```text
.
├── README.md
├── STATUS.yaml
├── docs/
│   ├── 00_current_truth.md
│   ├── 01_challenge_requirements.md
│   ├── 02_thesis_governance.md
│   ├── 03_data_provenance.md
│   ├── 04_experiments_results.md
│   ├── 05_claim_registry.md
│   ├── 06_final_report_plan.md
│   ├── 07_audit_gaps.md
│   ├── 08_source_index.md
│   ├── 09_project_history.md
│   └── 10_genai_ledger.md
├── registry/
│   └── artifacts.csv
└── templates/
    ├── thesis-map.md
    └── experiment-closeout.md
```

## Regra de precedência

Em caso de conflito:

1. comunicação oficial mais recente do desafio;
2. instrução específica da etapa;
3. ART-027 FREEZE v1.0;
4. Current Truth CT-v3.0;
5. Registro Mestre SR-v3.0;
6. Matriz HM-v3.0;
7. artefatos individuais;
8. documentação histórica.

Resultados numéricos só podem entrar no relatório após a cadeia **fonte bruta → transformação → código/versão → parâmetros → output → auditoria → claim** estar fechada.

## Leitura recomendada

Comece por `STATUS.yaml` e `docs/00_current_truth.md`. Antes de executar qualquer novo experimento, leia `docs/02_thesis_governance.md`, `docs/05_claim_registry.md` e use `templates/thesis-map.md`.
