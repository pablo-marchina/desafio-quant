# `data/eval/` — Eval set rotulado (F1.12)

Ground-truth de **classificação** (§5.1) + **AIMI esperado** (4 pilares × 0–25) por
startup. Criado **cedo** (F1.12) porque é consumido por:

- **F6.4** — correlação do AIMI do modelo com os rótulos (Spearman ≥ 0,70, meta F7);
- **F7.1/F7.2** — métricas de classificação (macro-F1 ≥ 0,75) e consolidação;
- **F7.2b** — eval da recomendação: `expected_nvidia_techs` por empresa.

F7 **consolida/expande** este conjunto — não cria do zero.

## Como os rótulos são feitos
Por **revisão humana** sobre a definição de pilares/escala de
[`docs/ARQUITETURA.md §3.6`](../../docs/ARQUITETURA.md) (F0.11). O ground-truth depende **só
da definição** (escala 0–25 imutável), nunca da heurística de pontuação (v0 F2.6 / v1
F6.1) — trocar a heurística não invalida os rótulos. Cada entrada carrega a **região do
plano `classe × AIMI`** (RUBRICA §6): `fora_escopo` · `periferico` · `wrapper` ·
`alvo_graduacao` ★ · `maduro`.

## `synthetic: true` vs entradas reais
As 24 entradas de `labeled_startups.yaml` são **fixtures-semente sintéticas**
(`synthetic: true`): empresas fictícias ancoradas na rubrica, que cobrem todas as
regiões do mapa de decisão e **destravam F6.4/F7 desde já**. Não são empresas reais e
**não** trazem `evidence_urls`.

Entradas **reais** (`synthetic: false`) — **exigem** `evidence_urls` rastreáveis; o loader
recusa entrada real sem fonte.

## `cohort_real.yaml` — expansão real automática (F7.1)
A metade real da F7.1 é **automática**: o cohort builder (F1.14) parte das candidatas curadas
(`data/seeds/cohort_candidates.yaml` — empresas BR de IA reais), o pipeline **resolve e raspa
ao vivo** (Tavily+Firecrawl) e diagnostica (Nemotron-Super), e `packages/eval/cohort_to_eval.py`
materializa as entradas em `data/eval/cohort_real.yaml` (`synthetic: false`, `evidence_urls`
reais). Reproduzível por:

```
python -m packages.agents.cohort --seed --db sqlite:///data/cohort.db   # + flags de rede/LLM
python -m packages.eval.cohort_to_eval --db sqlite:///data/cohort.db
```

**Honestidade — `label_source`.** Recém-geradas, essas entradas saem com `label_source: model`
(o rótulo é a **saída do próprio modelo** → medir o modelo contra ele é **baseline circular**), e
`load_eval_set()` as mantém **fora do headline** por padrão (`include_model=True` para incluí-las).
Promover a ground-truth exige **revisão humana** (virar `label_source: human`).

**Curadoria feita em 2026-06-15.** As 9 entradas foram revisadas contra a **evidência pública** (cada
`evidence_urls` + busca) e **8 promovidas a `label_source: human`** (entram no headline). Correções
relevantes: **Unico** `non-AI/fora_escopo` → `AI-native/maduro` (biometria facial é visão computacional
no núcleo — erro de extração só-de-descrição); **Hand Talk / Gupy / Idwall** `wrapper` → `alvo_graduacao`
(data moat estabelecido: corpus Libras, dados de recrutamento, base de documentos BR + lab de fraude);
**Kunumi** re-pontuada (era `6/6/6/6` subavaliado) e confirmada AI-native. **BotCity / Aquarela / Take
Blip** tiveram o rótulo do pipeline **confirmado** sem alteração (inclusive Take Blip como wrapper real —
orquestra NLP de terceiros). A **Semantix** segue `label_source: model` (fora do headline): a evidência de
LLM próprio ("Lloro") mostra que `wrapper` está subavaliado, mas a região (provável `maduro`) ficou
pendente de decisão.

⚠️ **Arquivo curado à mão.** Re-rodar `python -m packages.eval.cohort_to_eval` com o `--out` padrão
**sobrescreve** a curadoria — use outro `--out` ou faça backup antes. (Por que curada e não por crawl: o
crawl-discovery Scrapy rende **0 ao vivo** — robots/JS/bloqueio; a coleta por-empresa via Tavily/Firecrawl
é robusta. Ver `data/seeds/cohort_candidates.yaml`.)

## Esquema (validado em `packages/eval/dataset.py`)
`id` · `nome` · `setor` · `descricao` · `classificacao` (`AI-native|AI-enabled|non-AI`) ·
`region` · `aimi {data_moat, workflow_depth, technical_optimization, distribution_moat}`
(0–25 cada) · `expected_nvidia_techs[]` (F7.2b) · `rationale` · `evidence_urls[]` ·
`synthetic` · `label_source` (`human|model`) · `notes`.

O loader valida **coerência direcional** da anotação (ex.: `non-AI` não tem Workflow
Depth alto por IA; `alvo_graduacao` tem P3 ≤ 8 com P1 ou P2 ≥ 13) — sanidade da
rotulagem, **não** o corte de decisão calibrado (esse é F6.4).
