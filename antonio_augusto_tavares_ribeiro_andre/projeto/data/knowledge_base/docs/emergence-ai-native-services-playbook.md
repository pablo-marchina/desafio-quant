# Emergence — "The AI-Native Services Playbook" (§10.1, grounding)

Snapshot curado do playbook da Emergence Capital, citável pela URL canônica. Material conceitual
que **define AI-native services (AINS) vs AI-enabled vs wrapper** e fundamenta os pilares do AIMI
(F0.11) — não é documentação de produto NVIDIA.

## Definição e distinção
- **AI-Native Service (AINS):** entrega de **resultados** majoritariamente **executados por IA** —
  distinto de serviço tradicional (intensivo em humano) e de serviço **AI-enabled** (IA é só uma
  ferramenta). No AINS "**você É a implementação**": a empresa é o mecanismo de entrega integrado,
  não um software que o cliente opera por conta própria.
- **Data flywheel (fundamental):** "cada engajamento deve deixar sua IA melhor, sua entrega mais
  rápida e seus resultados mais previsíveis". Exige direito contratual de usar os dados de
  engajamento — vira **infraestrutura**, não só prestação de serviço.
- **Precificação por resultado:** o serviço **é** o resultado (sem problema de atribuição);
  começa-se por preço por trabalho e migra-se para outcome-based à medida que a IA amadurece.
- **Fossos:** (1) data flywheel; (2) credibilidade de marca; (3) **profundidade de integração** —
  virar o *system of record* cria custo de troca.

## O teste do wrapper ("Mirage PMF")
Sinais de alavancagem de IA **falsa** (= wrapper): margem bruta estagnada/caindo com a receita
crescendo; receita por funcionário travada; headcount escalando linearmente com clientes; trabalho
sob medida em vez de produto. AINS real mostra **escala não-linear vs custo** (ganho mensurável de
qualidade/velocidade/custo). Sem IA fazendo trabalho material a alta margem, é "só uma empresa de
serviços que usa ferramentas de IA".

## Grounding da rubrica AIMI
Mapeia nos 4 pilares (ver `docs/ARQUITETURA.md §3.6`):
- **P1 Data Moat** ≙ data flywheel / dados de engajamento que compõem vantagem.
- **P2 Workflow Depth** ≙ "você É a implementação" — IA executa o resultado, não assiste.
- **P3 Technical Optimization** ≙ o teste Mirage PMF (margem/escala não-linear) — IA precisa fazer
  trabalho material a alta margem, o que puxa otimização de stack (gatilho NVIDIA).
- **P4 Distribution & Moat** ≙ profundidade de integração / *system of record* e lock-in.
