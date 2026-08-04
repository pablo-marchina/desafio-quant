# NVIDIA NeMo

NVIDIA NeMo é a plataforma end-to-end para construir, customizar e operar modelos de IA
generativa em produção. Cobre o ciclo completo: curadoria de dados, treinamento e
fine-tuning, recuperação (RAG), guardrails e avaliação.

## Componentes relevantes
- **NeMo Retriever**: microsserviços de **embedding** (ex.: nv-embedqa, multilíngue) e
  **reranking** (nv-rerankqa) — a espinha do RAG de qualidade com busca semântica e
  reordenação. É o que o TAPI usa para embeddings e reranking da base NVIDIA.
- **NeMo Customizer**: fine-tuning e técnicas como LoRA/PEFT para adaptar modelos ao domínio
  proprietário da startup (dado próprio vira moat de produto).
- **NeMo Guardrails**: trilhos de segurança/escopo para apps de LLM (item próprio na KB).
- **NeMo Evaluator**: avaliação sistemática de qualidade de modelos e pipelines de RAG —
  governança de IA (seção própria abaixo).
- **NeMo Curator**: curadoria e deduplicação de grandes corpora de treino.

## NeMo Evaluator (avaliação e governança)
O **NeMo Evaluator** é o componente do NeMo para **avaliação sistemática** de modelos, agentes
e pipelines de RAG: mede qualidade com benchmarks acadêmicos e *custom*, métricas de RAG
(faithfulness, precisão/recall de contexto, relevância da resposta) e *LLM-as-a-judge*. É a peça
de **governança de IA** que permite à startup **medir** seus agentes, não só rodá-los — pegar
regressão a cada release, comparar modelos/prompts e sustentar decisões com número.

**Quando recomendar (§5.5 — governança):** quando a recomendação de produção pede *governança*,
ela sai com **Guardrails + NeMo Evaluator** — o Guardrails impõe os trilhos em tempo de execução
e o Evaluator dá a medição contínua de qualidade. Endereça o pilar **Technical Optimization** do
AIMI (uma startup que não mede a qualidade dos próprios agentes tem governança imatura). É a
mesma família de avaliação que o próprio TAPI dogfooda ao medir seu RAG via RAGAS (F3.9).

## Quando recomendar
Indicado para startups que precisam ir além de prompt em API crua: customizar modelos com
dado próprio, montar RAG robusto, ou estabelecer governança/avaliação de agentes. Endereça
gaps de **Workflow Depth** (orquestração, RAG) e **Data Moat** (fine-tuning sobre dado
proprietário) no AIMI.
