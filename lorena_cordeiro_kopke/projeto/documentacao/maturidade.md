# Pipeline de Aprofundamento — Maturidade AI-Native

Documenta a lógida do cálculo de maturidade implementado.

---
## Lógica de cálculo de maturidade

### Filosofia central

O modelo usa **ancoragem com teto por nível**: `ia_e_core_product` define o teto máximo atingível, e os outros três pilares refinam a posição dentro desse teto. Isso impede que uma empresa acumule sinais positivos nos pilares secundários e chegue a `ai-native` sendo que IA não é o core do negócio.

### Visão geral do cálculo

```
score_maturidade_ia =
    pilar_centralidade (ia_e_core_product)     → 0.0 ou 4.0
  + pilar_sofisticacao (ia_tipo)               → 0.0 a 2.0
  + pilar_execucao     (produto_ia_lancado)    → 0.0 ou 2.0
  + pilar_genesis      (ano_fundacao)          → 0.0 a 2.0

score máximo possível = 10.0
```

```
nivel_maturidade_ia =
    se ia_e_core_product = NULL  →  NULL (não classificada)
    se ia_e_core_product = false →  max "ai-enabled" (hard cap)
    se ia_e_core_product = true  →  mapeado pelo score (ver tabela abaixo)
```

### Pilar 1 — Centralidade de IA (`ia_e_core_product`)

**O ancorador. Define o teto máximo do nível.**

| Valor | Pontos | Efeito no nível |
|---|---|---|
| `true` | 4.0 | Abre acesso a `ai-first` e `ai-native` |
| `false` | 0.0 | Hard cap em `ai-enabled` |
| `NULL` | — | Empresa não classificada; `nivel_maturidade_ia` permanece `NULL` |

`ia_e_core_product` tem peso 4.0 (40% do score máximo) para garantir que nenhuma combinação dos outros três pilares (max 6.0) consiga cruzar o threshold de `ai-first` (5.0) sem que IA seja o core.

### Pilar 2 — Sofisticação Técnica (`ia_tipo`)

Hierarquia de **profundidade de comprometimento técnico** — quão especializado e custoso é o stack de IA que a empresa precisa dominar.

| `ia_tipo` | Pontos | Raciocínio |
|---|---|---|
| `IA Generativa` | +2.0 | Frontier AI; exige domínio de LLMs, prompting, RAG, fine-tuning |
| `NLP / LLM` | +2.0 | Frontier AI; deepstack de linguagem, embeddings, modelos de linguagem |
| `Visão Computacional` | +2.0 | Deep learning denso; dados rotulados, GPU, pipelines de inferência |
| `Automação Inteligente` | +1.0 | IA aplicada e processual; integra modelos mas raramente os constrói |
| `Análise Preditiva` | +1.0 | ML clássico; mais acessível, baseado em features estruturadas |
| `Dados e Analytics` | +0.5 | Data-driven; pode não envolver aprendizado de máquina real |
| `NULL` | +0.0 | Dado ausente não pontua; não penaliza |

### Pilar 3 — Execução de Mercado (`produto_ia_lancado`)

| Valor | Pontos | Raciocínio |
|---|---|---|
| `true` | +2.0 | Produto de IA em produção com clientes reais |
| `false` | +0.0 | Produto em construção |
| `NULL` | +0.0 | Não coletado; não pontua, não penaliza |

Com `produto_ia_lancado = NULL`, uma empresa ainda pode atingir `ai-native` se os outros três pilares forem máximos (score 8.0). Isso impede que a ausência de dado bloqueie a classificação de uma startup early-stage genuinamente AI-native.

### Pilar 4 — Gênese / DNA Temporal (`ano_fundacao`)

O ano é mapeado às ondas tecnológicas de IA:

| `ano_fundacao` | Pontos | Onda de referência |
|---|---|---|
| >= 2022 | +2.0 | Era ChatGPT / LLM generativo |
| >= 2020 | +1.5 | Era GPT-3 / IA moderna acessível |
| >= 2017 | +1.0 | Era Transformers / deep learning mainstream |
| >= 2012 | +0.5 | Era Big Data / early deep learning |
| < 2012 | +0.0 | Era pré-IA — provavelmente pivotou para IA depois |

### Mapeamento score → nível

| Score | `nivel_maturidade_ia` | Perfil |
|---|---|---|
| >= 8.0 (requer `ia_e_core = true`) | `ai-native` | IA é o DNA fundacional e atual |
| >= 5.0 (requer `ia_e_core = true`) | `ai-first` | IA é o produto central mas com gaps |
| >= 2.0 | `ai-enabled` | IA integrada com relevância real, mas não é o core |
| < 2.0 | `ai-adjacent` | Menciona IA mas sem produto ou uso demonstrável |

### Exemplos de score por combinação

```
Score 10 (ai-native máximo):
  ia_e_core = true       → 4.0
  ia_tipo frontier       → 2.0
  produto_lancado = true → 2.0
  ano >= 2022            → 2.0

Score 8 (ai-native sem produto lançado):
  ia_e_core = true + frontier + ano >= 2022 + produto NULL  → 8

Score 7 (ai-first — empresa legada que pivotou):
  ia_e_core = true + tipo médio + produto true + ano < 2012 → 7

Score 6 (ai-enabled forte — hard cap por ia_e_core = false):
  ia_e_core = false + frontier + produto true + ano >= 2022 → 6 → cap nivel ai-enabled
  (score não é truncado pelo hard cap; somente o nível é limitado a ai-enabled)
```

### Validação com dados reais

| Empresa | Core | Tipo IA | Lançado | Ano | Score | Nível |
|---|---|---|---|---|---|---|
| Sinatra AI | true (+4.0) | IA Gen (+2.0) | true (+2.0) | 2023 (+2.0) | **10** | ai-native |
| Blip | true (+4.0) | Auto Int (+1.0) | true (+2.0) | 2001 (+0.0) | **7** | ai-first |
| Fintalk | true (+4.0) | Auto Int (+1.0) | NULL (+0.0) | 2019 (+1.0) | **6** | ai-first |
| Segura.ai | false → cap | Auto Int (+1.0) | true (+2.0) | 2024 (+2.0) | **5** → cap nivel | ai-enabled |
| Vivo | false → cap | NULL (+0.0) | true (+2.0) | 1998 (+0.0) | **2** → cap nivel | ai-enabled |

> **Nota:** `score_maturidade_ia` é gravado no banco como inteiro (`int(score)`) — truncamento, não arredondamento.

### Campos que NÃO entram no cálculo

| Campo | Motivo |
|---|---|
| `programa_aceleracao` | NULL ≠ não participa. Scraping falha silenciosamente (badges como imagem sem alt text). Disponível para consulta manual. |
| `mercado_alvo` | Dimensão de estratégia de negócio, não de maturidade de IA. |
| `modelo_negocio` | B2B vs B2C não determina profundidade de IA. |
| `uso_ia_descricao` | Campo textual não estruturado. O valor já está capturado em `ia_e_core_product`. |

---

## Campo: `situacao_coleta`

Coluna em `empresas_uso_ia` que rastreia em que ponto da coleta cada empresa está e decide se ela segue para a próxima fase.