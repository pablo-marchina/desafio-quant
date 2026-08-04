# Referencial — Materiais Contextuais (textos)

> Notas de estudo do **Bloco 2 (RAG NVIDIA)**, item "estudar os materiais contextuais antes de qualquer código".
> Resumo dos 3 textos-base do case, com a conexão de cada um ao nosso projeto.
> Este documento é um **digest** — não substitui a leitura dos originais, mas dá o framework.
> Consultado em junho/2026.

---

## 1. Sequoia — "Services: The New Software"
🔗 https://sequoiacap.com/article/services-the-new-software/

### Tese central
A IA está deixando de ser vendida como **ferramenta** (copilot) para ser vendida como **resultado** (autopilot). Quem entrega o resultado final captura o "orçamento de trabalho" (salários, terceirização), que é **~6x maior** que o orçamento de software. Por isso "serviços" é o novo grande mercado de software.

### Conceitos-chave
- **Inteligência vs. Julgamento:** *inteligência* = tarefas baseadas em regras (a IA já faz bem); *julgamento* = experiência acumulada e decisão estratégica (ainda humano). A IA cruzou o limiar de fazer a maior parte do trabalho de "inteligência" sozinha.
- **Copilot vs. Autopilot:** copilot vende a ferramenta ao profissional (ex.: Harvey p/ advogados); autopilot vende o resultado pronto ao cliente (ex.: Crosby entrega NDAs prontas).
- **Playbook p/ founders:** (1) começar por tarefas já terceirizadas (orçamento já existe), (2) que sejam predominantemente "inteligência" (IA já resolve), (3) expandir para trabalho com mais julgamento conforme a IA amadurece.

### Conexão com o nosso projeto
Esta é a base do **eixo "produz vs. consome"** da nossa rubrica. Frase-âncora:
> *"Se você vende a ferramenta, está em uma corrida contra o modelo."*

Startups que são só **wrapper** (interface sobre uma API) estão nessa "corrida contra o modelo" — exatamente o **nível 1** da nossa classificação. Já quem tem **dados proprietários + feedback contínuo** cria um *moat* — sinal de **AI-native (nível 3)**.

---

## 2. Emergence Capital — "The AI-Native Services Playbook"
🔗 https://www.emcap.com/thoughts/the-ai-native-services-playbook

### O que é uma empresa AI-native de serviços (AINS)
Vende **resultados entregues primariamente por IA**, e é responsável pelo outcome completo. O ativo principal é a credibilidade do time + o *flywheel* de dados — não um produto que o cliente usa sozinho.

### Sinais práticos de maturidade técnica (muito úteis pra nós)
- **Dados proprietários:** contratos garantem o direito de usar os dados dos clientes pra melhorar a IA → *flywheel* que compõe vantagem.
- **Workflow real:** times de domínio + engenheiros trabalhando em par, ajustando a IA em ciclos curtos (não "evals em lote" esporádicos).
- **Automação medível:** métrica como **HURT** (Human Review Time → tende a zero) e **ARR/FTE crescendo** (receita por funcionário sobe = IA faz mais do trabalho, margem expande).

### Armadilha: "Mirage PMF"
Crescimento de receita **não prova** product-market fit numa AINS. O teste real é se a IA escala **não-linearmente** vs. custos. Sinais de alerta: margem bruta plana/caindo, ARR/FTE estagnado, entrega ainda muito dependente de humano.

### Conexão com o nosso projeto
Dá substância às perguntas do **checklist de classificação** (Bloco 3):
- "modelo próprio / fine-tuning?" e "dados proprietários?" ↔ *data flywheel*.
- "perfis técnicos de IA no time?" ↔ domain expertise + engenheiros no delivery.
- "substituível por GPT wrapper genérico?" ↔ o teste do *moat* e da alavancagem não-linear.

---

## 3. NVIDIA — "AI 5-Layer Cake"
🔗 https://blogs.nvidia.com/blog/ai-5-layer-cake/

### As 5 camadas (da base ao topo)
| Camada | Função |
|---|---|
| **Energia** | "Inteligência em tempo real exige energia em tempo real" |
| **Chips** | Transformam energia em computação em escala (GPUs) |
| **Infraestrutura** | "Fábricas de IA": data centers, redes, resfriamento, orquestração |
| **Modelos** | IA treinada em linguagem, biologia, física, robótica, etc. |
| **Aplicações** | Onde o valor econômico nasce: produtos finais (descoberta de fármacos, veículos autônomos, robôs) |

Ideia central: **cada aplicação bem-sucedida "puxa" todas as camadas abaixo dela** — a stack funciona integrada, da energia ao usuário.

> ⚠️ O artigo dá a visão **macro** (estratégica) e **não cita** os produtos específicos (NIM, NeMo, Triton, etc.). O mapeamento produto-a-produto vem da nossa própria tabela de recomendação (no CLAUDE.md).

### Conexão com o nosso projeto
O "bolo de 5 camadas" é o **mapa mental** do motor de recomendação: dado o problema da startup, em qual camada ele está?
- Problema de **custo/latência de inferência** → camadas Modelos/Infra → **NIM, Triton, TensorRT-LLM**.
- Problema de **volume de dados tabulares** → **RAPIDS, cuDF, cuML**.
- Problema de **governança de agentes** → **NeMo Guardrails**.

Na prática, o nosso motor atua sobretudo nas camadas **Modelos / Infraestrutura / Aplicações**, que é onde mora o **software** da NVIDIA (NIM, NeMo, Triton, RAPIDS…).

---

## Síntese — o que levar pro código

1. **A rubrica de classificação** (níveis 0–3) é fundamentada: "produz vs. consome", *data flywheel*, alavancagem não-linear. Isso justifica as classificações no briefing (que o parceiro NVIDIA vai cobrar).
2. **O motor de recomendação** cruza o problema da startup (por camada do "bolo") com a tecnologia NVIDIA certa.
3. **O RAG** (o que vamos construir no Bloco 2) é o que vai guardar e recuperar o conhecimento sobre essas tecnologias NVIDIA, com **citação de fonte** — para que a recomendação seja justificável, não um "chute" do LLM.
