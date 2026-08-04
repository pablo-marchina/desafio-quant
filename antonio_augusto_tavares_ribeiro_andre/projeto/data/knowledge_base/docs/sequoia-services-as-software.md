# Sequoia — "Services: The New Software" (§10.1, grounding)

Snapshot curado do ensaio de Julien Bek (Sequoia Capital), citável pela URL canônica. É um
dos materiais conceituais que **definem AI-native vs wrapper** e fundamentam os pilares do
AIMI (F0.11) — não é documentação de produto NVIDIA.

## Tese central
- **Copiloto × Autopiloto.** Um *copiloto* vende a **ferramenta** ao profissional (a IA assiste,
  o humano decide). Um *autopiloto* vende o **trabalho/resultado** ao cliente final. O orçamento
  de "trabalho" é muito maior que o de "ferramenta".
- **Corrida contra o modelo.** Quem vende a ferramenta corre contra o próprio modelo: a cada
  versão melhor, o wrapper vira *feature*. Quem vende o trabalho **se fortalece** com modelos
  melhores — "cada melhoria do modelo deixa o serviço mais rápido, mais barato e mais difícil de
  copiar". Esta é a fronteira AI-native × wrapper.
- **TAM dos serviços.** "Para cada dólar gasto em software, seis são gastos em serviços" — o alvo
  do autopiloto é o gasto com **mão de obra** de uma categoria (insourced + outsourced), não só o
  de software.
- **O que torna o serviço durável (não um wrapper):** (1) começar pelo trabalho **terceirizado**
  (já há linha de orçamento e mercado provado — a cunha de distribuição); (2) alta razão
  **inteligência/julgamento** (tarefas em que a IA já executa com autonomia); (3) **composição de
  dados** — julgamento proprietário de domínio que aprofunda a defensabilidade com o uso.

## Grounding da rubrica AIMI
Mapeia direto nos 4 pilares (ver `docs/ARQUITETURA.md §3.6`):
- **P2 Workflow Depth** ≙ vender o **trabalho** (autopiloto end-to-end), não a caixa de texto.
- **P1 Data Moat** ≙ **composição de dados** / julgamento proprietário que melhora com o uso.
- **P3 Technical Optimization** ≙ não ficar "em corrida contra o modelo" sobre API crua — o gatilho
  da graduação para stack própria (NIM/TensorRT-LLM/Triton).
- **P4 Distribution & Moat** ≙ a cunha do trabalho terceirizado → contrato/lock-in insourced.
