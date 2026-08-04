# NVIDIA Startup AI Radar — CLAUDE.md

## Contexto do Projeto

Plataforma multi-agente de inteligência para o gerente de Startups & VCs da NVIDIA Brasil.
O sistema encontra startups brasileiras com uso intensivo de IA, coleta e cruza dados públicos
sobre elas, avalia a maturidade técnica (AI-native / AI-enabled / non-AI), consulta uma base
de conhecimento sobre tecnologias NVIDIA via RAG e gera um briefing executivo com recomendações
personalizadas para apoiar atração e nutrição de startups no programa NVIDIA Inception.

Desenvolvedor: solo
Duração: junho de 2025 (commits contínuos, sem sprints formais)
Parceiro: NVIDIA Brasil — programa NVIDIA Inception

---

## Filosofia de Desenvolvimento

### Mínimo funcional antes de qualquer refinamento
A regra mais importante do projeto: **sempre construir a versão mais simples possível que funcione de ponta a ponta antes de adicionar qualquer complexidade.**

Isso significa:
- Em cada bloco, identificar o subconjunto mínimo que já entrega valor e implementar só isso primeiro.
- Só adicionar fontes, agentes, enriquecimentos ou features extras depois que o núcleo mínimo estiver funcionando e validado.
- Nunca construir a versão "completa" de uma vez. Iterar sobre algo funcionando é sempre melhor do que construir algo grande que falha de formas desconhecidas.
- Se um bloco tem 6 itens no checklist, os primeiros são o mínimo funcional. O restante é enriquecimento — só vem depois.

Exemplos práticos do que isso significa em cada bloco:
- Bloco 1: scraper do site oficial funcionando e salvando no banco → depois adicionar GitHub, vagas, podcasts.
- Bloco 2: RAG com 2–3 tecnologias NVIDIA ingerindo e recuperando corretamente → depois ingerir todas as 16.
- Bloco 3: pipeline com 3 agentes simples rodando → depois refinar classificação e adicionar validação.
- Bloco 4: recomendação básica para 1 startup funcionando de ponta a ponta → depois refinar o briefing.

### Explicar antes de implementar — sempre
Antes de escrever qualquer código, o Claude Code deve explicar em linguagem técnica simplificada:
- **O que** esse componente é
- **Por que** ele entra agora nessa ordem
- **Como** ele se conecta com o que já existe

Essa explicação não é um plano de implementação detalhado. É uma descrição curta e clara suficiente para Eduardo saber explicar o que está sendo construído para qualquer pessoa. Só depois da confirmação de Eduardo o código é escrito.

Isso vale para cada sub-passo dentro de um bloco, não só para blocos inteiros. Cada arquivo novo, cada função relevante, cada integração — explicar primeiro, implementar depois.

### Outras regras
- Avance passo a passo. Nunca pule etapas para "agilizar".
- Prefira código funcional e legível a código "inteligente" ou excessivamente abstrato.
- Cada bloco deve estar funcionando de ponta a ponta antes de avançar para o próximo.
- Se houver duas formas de fazer algo, apresente as opções com prós e contras antes de escolher.
- Não assuma nada que não esteja documentado aqui ou em @docs/. Pergunte primeiro.
- Se Eduardo afirmar algo tecnicamente impreciso, contradiga diretamente com justificativa.
- Nunca gerar código que Eduardo não entende. Se algo é complexo, explicar antes de escrever.

---

## Visão Estratégica

O sistema deve operar em dois níveis simultâneos:

- **Micro** — análise individual de cada startup: produto, stack, maturidade técnica, equipe, funding.
- **Macro** — leitura do movimento de mercado de IA no Brasil como um todo: tendências, setores emergentes, padrões de adoção.

A perspectiva do parceiro é de **apoio e atração**, não de triagem eliminatória. O sistema deve
refletir isso no tom das recomendações — a NVIDIA quer nutrir essas empresas, não avaliá-las friamente.

Startups emergentes no Brasil tendem a priorizar crescimento e usam APIs externas por padrão,
nem sempre a melhor opção técnica a longo prazo. O sistema deve identificar esse padrão como gap
e recomendar evolução de forma construtiva.

Presença de Venture Capital é um sinal relevante: indica capacidade de investimento em infraestrutura
e potencial de escala. Deve ser capturado e considerado na análise e nas recomendações.

---

## Arquitetura Geral

```
Consulta do usuário
  → Search Planner Agent
  → Scraper Agent          ← múltiplas fontes (ver seção de coleta)
  → Extractor Agent
  → Banco estruturado de startups (PostgreSQL)
  → Startup Classifier Agent
  → Evidence Validator Agent
  → Diagnóstico de maturidade AI-native
  → NVIDIA RAG Agent
  → Reranker (Cohere)
  → Recommendation Agent
  → Briefing Agent
  → Interface web (frontend livre)
```

Orquestração: LangGraph (grafo com estado, checkpoints, transições condicionais)
Cada nó do grafo = um agente especializado

---

## Agentes — Responsabilidades

| Agente | Responsabilidade |
|---|---|
| Search Planner Agent | Transforma a consulta do usuário em termos de busca e fontes prioritárias |
| Scraper Agent | Coleta informações públicas de todas as fontes mapeadas |
| Extractor Agent | Transforma conteúdo não estruturado em dados estruturados |
| Startup Classifier Agent | Classifica a empresa como AI-native, AI-enabled ou non-AI com base na rubrica definida em docs/decisions.md |
| Evidence Validator Agent | Valida se as afirmações possuem fontes suficientes |
| NVIDIA RAG Agent | Consulta a base de conhecimento de tecnologias NVIDIA |
| Recommendation Agent | Cruza perfil da startup com tecnologias NVIDIA |
| Briefing Agent | Gera o relatório executivo final |

---

## Stack Técnica

### Orquestração de Agentes
- **LangGraph** — grafo com estado, checkpoints, retry, transições condicionais, suporte a intervenção humana

### Ambiente e gerenciamento de dependências
- **Python 3.12** — versão fixa do projeto
- **uv** — gerenciador de pacotes e ambientes virtuais (substitui pip + venv). Mais rápido, lock file nativo, reproduzível.
- Comandos base: `uv init`, `uv add <pacote>`, `uv run <script>`, `uv sync`
- O arquivo `pyproject.toml` é a fonte de verdade das dependências. Nunca instalar pacotes manualmente com pip.

### LLM Provider
- **OpenRouter** (provider principal — acesso unificado a múltiplos modelos)
- **Groq** (alternativa para chamadas que exigem baixa latência)
- **Google Gemini** (alternativa, especialmente para contextos longos)
- Usar variáveis de ambiente para trocar de provider sem alterar código. Nunca hardcoded.

### Scraping e Coleta de Dados
- **Scrapling** — lib principal de scraping: substitui Playwright + BeautifulSoup. Cobre fetch, parsing, bypass de anti-bot (Cloudflare, etc.) e rastreamento adaptativo de elementos (seletores não quebram quando o site muda layout). API similar ao BeautifulSoup, sem curva de aprendizado grande.
- **Firecrawl** — converte páginas inteiras em markdown limpo para RAG. Não substituível pelo Scrapling — propósito diferente.
- **trafilatura** — extrai texto principal de artigos e blogs, removendo nav/footer/ads automaticamente. Não substituível pelo Scrapling — propósito diferente.
- **Scrapy** — entra apenas se o volume escalar para crawling massivo. Fora do escopo inicial.

### RAG
- **Qdrant** — banco vetorial principal
- **PostgreSQL** — dados estruturados de startups
- **BM25** — busca lexical (busca híbrida)
- **Cohere Rerank** — reranking dos trechos recuperados
- Pipeline completa:
  1. Ingestão de documentos (blogs, docs, whitepapers, transcrições de vídeos e podcasts)
  2. Limpeza e normalização
  3. Chunking semântico
  4. Geração de embeddings
  5. Armazenamento no Qdrant
  6. Busca híbrida (vetorial + BM25)
  7. Reranking com Cohere
  8. Geração com citações
  9. Avaliação de qualidade

### Frontend
- Livre. Decidir após os entregáveis de backend estarem funcionando.

---

## Coleta e Enriquecimento de Dados

A coleta deve ser criativa e exaustiva. Quanto mais contexto sobre a startup, melhor o diagnóstico.
Todas as fontes devem ser cruzadas antes de classificar. O objetivo é montar o contexto mais completo
possível de cada empresa a partir de dados 100% públicos e automatizáveis.

### Fontes primárias — diretórios e ecossistema brasileiro
- StartSe: https://www.startse.com/
- Distrito: https://distrito.me/
- Latitud: https://www.latitud.com/
- Cubo Itaú: https://cubo.network/
- ACE Startups: https://acestartups.com.br/
- Endeavor Brasil: https://endeavor.org.br/
- Abstartups: https://abstartups.com.br/
- Bossa Invest: https://bossainvest.com/
- Anjos do Brasil: https://www.anjosdobrasil.net/
- Darwin Startups: https://www.darwinstartups.com/
- Liga Ventures: https://liga.ventures/
- WOW Aceleradora: https://www.wow.ac/
- InovAtiva Brasil: https://www.inovativabrasil.com.br/
- 100 Open Startups: https://www.openstartups.net/

### Fontes primárias — notícias e sinais públicos
- Brazil Journal: https://braziljournal.com/
- NeoFeed: https://neofeed.com.br/
- Exame Startups: https://exame.com/bussola/startups/
- Startups.com.br: https://startups.com.br/
- Pequenas Empresas & Grandes Negócios: https://revistapegn.globo.com/
- Valor Econômico: https://valor.globo.com/
- Meio & Mensagem: https://www.meioemensagem.com.br/
- Mobile Time: https://www.mobiletime.com.br/

### Fontes de enriquecimento — por startup
Coletar quando disponível publicamente:
- Site oficial e blog da empresa
- Página de carreiras
- Perfis públicos dos founders
- Setor, produto, clientes declarados, funding, tecnologias mencionadas

### Fontes de enriquecimento — dados cruzados automatizáveis

| Fonte | O que capturar | Sinal diagnóstico |
|---|---|---|
| **LinkedIn público** | Cargos, headcount, crescimento da equipe, tecnologias declaradas no perfil | Quantos ML Engineers, MLOps, AI Researchers vs papéis genéricos |
| **Crunchbase / Dealroom API** | Funding rounds, investidores, VCs, valuation, data de fundação | Presença de VC, capacidade de investimento em infra |
| **GitHub público da empresa** | Repositórios abertos, linguagens, presença de modelos próprios, frequência de commits | Distingue "produz" (modelos próprios) de "consome" (só integrações) |
| **Vagas de emprego** (LinkedIn Jobs, Gupy, Indeed) | Perfil técnico das contratações em andamento — via Scrapling | Startup buscando MLOps Engineer ou Fine-tuning Specialist está em nível diferente de quem busca "analista de IA" |
| **Transcrições de podcasts** | Episódios em que founders participaram (buscar por nome + empresa) | Contexto estratégico, visão de produto, decisões técnicas declaradas pelos próprios fundadores |

---

## Classificação de Maturidade AI-native

O Startup Classifier Agent classifica cada empresa em um de quatro níveis.
A rubrica foi definida antes do desenvolvimento e está documentada aqui e em `docs/decisions.md`.
O critério foi validado pelo parceiro como livre para o projeto definir — deve ser bem justificado no briefing.

### Níveis

| Nível | Nome | Definição central |
|---|---|---|
| 3 | **AI-native** | Produz: modelo próprio, fine-tuning, pipeline de treinamento, dados proprietários. IA é o núcleo do produto. |
| 2 | **AI-enabled** | Consome com profundidade: integra APIs de IA com workflow próprio, automação real, diferenciação clara no uso. |
| 1 | **AI-wrapper** | Consome superficialmente: interface sobre uma API de terceiro sem dados proprietários ou diferenciação técnica real. |
| 0 | **Non-AI** | IA ausente ou puramente cosmética no produto. |

### Eixo central: produz vs. consome

- **Produz** → modelo próprio, fine-tuning, pipeline de treinamento, dados proprietários exclusivos. Sinal forte de AI-native (nível 3).
- **Consome com profundidade** → usa APIs externas mas com workflow próprio, automação real, resultado diferenciado. Nível 2.
- **Consome superficialmente** → thin wrapper, troca o provider e o produto continua igual. Nível 1.
- **Não usa** → IA inexistente ou só em marketing. Nível 0.

### Método de classificação: checklist + raciocínio do agente

O Classifier Agent NÃO usa pesos numéricos. Ele responde um checklist obrigatório com as evidências
coletadas, depois classifica por raciocínio. Isso garante rastreabilidade sem depender de pesos arbitrários.
Toda classificação deve ser explicável mostrando o checklist preenchido.

#### Checklist obrigatório (responder antes de classificar)

```
1. A empresa tem evidência de modelo próprio ou fine-tuning?
   → sim / não / inconclusivo | evidência: [fonte]

2. Há perfis técnicos de IA no time (ML Engineer, MLOps, AI Researcher)?
   → sim / não / inconclusivo | evidência: [fonte]

3. A stack técnica é identificável além de "usamos IA"?
   → sim / não / inconclusivo | evidência: [fonte]

4. Há menção a dados proprietários ou datasets exclusivos?
   → sim / não / inconclusivo | evidência: [fonte]

5. O produto seria substituível por um GPT wrapper genérico?
   → sim / não / inconclusivo | evidência: [fonte]

6. Há presença de VC ou funding relevante?
   → sim / não / inconclusivo | evidência: [fonte]
```

"Inconclusivo" é uma resposta válida quando o dado não está disponível publicamente.
O agente classifica com o que tem e registra explicitamente o que estava faltando.

### Viabilidade de coleta por sinal diagnóstico

| Sinal | Automatizável? | Observação |
|---|---|---|
| GitHub público | ✅ Sim | API pública, sem autenticação para dados básicos |
| Vagas (Gupy, Indeed) | ✅ Sim | HTML estático na maioria, Playwright para dinâmicos |
| Site oficial e blog | ✅ Sim | trafilatura + Firecrawl |
| Portais de notícias | ✅ Sim | trafilatura + Firecrawl |
| Transcrições de podcasts | ⚠️ Parcial | Busca por nome+empresa funciona; transcrição de áudio via Whisper é viável mas adiciona complexidade |
| Crunchbase / Dealroom | ⚠️ Parcial | APIs pagas; funding aparece indiretamente em notícias e diretórios brasileiros |
| LinkedIn | ❌ Não confiável | Bloqueia scraping ativamente, viola ToS, quebra constantemente — não depender disso |
| Cargos do time | ⚠️ Parcial | Página "Sobre" ou "Time" do site quando disponível; fallback para vagas abertas |

---

## Base de Conhecimento NVIDIA (Seção 8 do TAPI)

Toda a seção 8 do TAPI deve ser trabalhada em duas frentes:
1. **Estudo** — entender o que cada tecnologia faz antes de implementar o motor de recomendação.
2. **Ingestão** — ingerir todas as fontes listadas completamente na base RAG.

Ordem de ingestão recomendada: começar pelos **materiais contextuais** (para entender o framework
conceitual de AI-native e o posicionamento da NVIDIA), depois as **documentações oficiais** por tecnologia.

### Tecnologias a incluir na base RAG

| Tecnologia | Descrição |
|---|---|
| NVIDIA Inception | Programa para startups: benefícios, créditos, suporte técnico, go-to-market |
| NVIDIA NIM | Microservices para deploy de modelos de IA otimizados |
| NVIDIA NeMo | Treinamento, customização, avaliação e guardrails para modelos generativos |
| NeMo Guardrails | Controle de comportamento de assistentes e agentes |
| NVIDIA Triton Inference Server | Serving de modelos em produção |
| TensorRT-LLM | Otimização de inferência de LLMs |
| NVIDIA RAPIDS | Aceleração de pipelines de dados com GPU |
| cuDF | Processamento de dataframes em GPU |
| cuML | Machine learning acelerado em GPU |
| CUDA | Programação paralela em GPU |
| NVIDIA Riva | ASR, TTS e modelos de voz |
| NVIDIA Omniverse | Simulação, 3D e digital twins |
| NVIDIA Isaac | Robotics, simulação e autonomia |
| NVIDIA Clara | Healthcare e life sciences |
| NVIDIA Morpheus | Cybersecurity com IA acelerada |
| NVIDIA AI Enterprise | Plataforma empresarial para IA em produção |

### Fontes — materiais contextuais (ingerir primeiro)
- Sequoia - AI services: https://sequoiacap.com/article/services-the-new-software/
- Emergence Capital - AI-native services playbook: https://www.emcap.com/thoughts/the-ai-native-services-playbook
- NVIDIA AI 5-layer cake: https://blogs.nvidia.com/blog/ai-5-layer-cake/
- Playlist de tecnologias NVIDIA: https://youtube.com/playlist?list=PLBaUJRFQ-j_WJZdZfFNsgUWDWF1Ldjp_X
- Comunidade startups NVIDIA: https://youtu.be/NmZDQSdUVUQ
- Benefícios Inception: https://www.youtube.com/live/fWfkE6cibwQ

### Fontes — documentações oficiais (ingerir por tecnologia)
- NVIDIA Inception: https://www.nvidia.com/en-us/startups/
- NVIDIA NIM: https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/
- NVIDIA API Catalog: https://build.nvidia.com/
- NVIDIA NeMo: https://www.nvidia.com/en-us/ai-data-science/products/nemo/
- NeMo Guardrails: https://github.com/NVIDIA/NeMo-Guardrails
- Triton Inference Server: https://developer.nvidia.com/triton-inference-server
- Triton docs: https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/
- TensorRT-LLM: https://github.com/NVIDIA/TensorRT-LLM
- RAPIDS: https://rapids.ai/
- cuDF: https://docs.rapids.ai/api/cudf/stable/
- cuML: https://docs.rapids.ai/api/cuml/stable/
- CUDA Toolkit: https://developer.nvidia.com/cuda-toolkit
- NVIDIA Riva: https://developer.nvidia.com/riva
- NVIDIA Omniverse: https://www.nvidia.com/en-us/omniverse/
- NVIDIA Isaac: https://developer.nvidia.com/isaac
- NVIDIA Clara: https://www.nvidia.com/en-us/clara/
- NVIDIA Morpheus: https://developer.nvidia.com/morpheus-cybersecurity
- NVIDIA AI Enterprise: https://www.nvidia.com/en-us/data-center/products/ai-enterprise/

---

## Motor de Recomendação — Lógica

| Perfil da Startup | Tecnologias NVIDIA a Recomendar |
|---|---|
| Usa LLMs em atendimento, depende só de APIs externas | NIM, NeMo Guardrails, Triton, benchmark custo/latência |
| Processa grandes volumes de dados tabulares | RAPIDS, cuDF, cuML |
| Atua com voz, call center ou transcrição | NVIDIA Riva, NIM |
| Atua em saúde | Clara, MONAI, NIM, NeMo Guardrails, AI Enterprise |
| Faz robotics ou simulação | Isaac, Omniverse, GPUs NVIDIA |
| Sofre com latência de inferência | Triton, TensorRT-LLM, batching |
| Precisa de governança em agentes | NeMo Guardrails, avaliação com NeMo |

### Output estruturado de cada recomendação
- Tecnologias NVIDIA recomendadas
- Justificativa técnica
- Justificativa de negócio
- Nível de prioridade
- Complexidade de implementação
- Próxima ação sugerida para o time NVIDIA
- Evidências usadas

---

## Roadmap de desenvolvimento

Implementar nesta ordem de blocos. Não avançar para o próximo enquanto o anterior não estiver funcional de ponta a ponta. Cada bloco tem liberdade de implementação dentro dos critérios definidos aqui.

### Bloco 0 — Fundação
Objetivo: ambiente funcionando, sem nenhuma lógica de negócio ainda.

**Mínimo funcional:**
- [x] Repositório criado com estrutura de pastas conforme seção "Estrutura de Diretórios"
- [x] `uv init` rodado, `pyproject.toml` criado com Python 3.12 fixado
- [x] `.env.example` documentado com todas as variáveis necessárias
- [x] Docker Compose com PostgreSQL e Qdrant rodando localmente
- [x] Dependências do Bloco 0 adicionadas via `uv add` (`openai` + `python-dotenv`, suficientes para o teste do OpenRouter). As demais libs (LangGraph, Scrapling, Firecrawl, trafilatura, Cohere) entram no bloco que as usa — mínimo funcional.
- [x] Conexão com LLM provider (OpenRouter) validada com um teste simples via `uv run` (`scripts/check_openrouter.py`; modelo de teste: `nvidia/nemotron-nano-9b-v2:free`)

### Bloco 1 — Pipeline de scraping (Entregável 1)
Objetivo: dado o nome de uma startup, coletar contexto público e salvar estruturado no banco.

**Mínimo funcional — implementar e validar antes de qualquer enriquecimento:**
- [x] Scraper do site oficial funcionando (Scrapling para fetch + parsing, trafilatura para limpeza do texto). O scraper é agnóstico à URL — a mesma função serve para o blog, basta apontar a URL.
- [x] Dados salvos no PostgreSQL com campo de fonte rastreável (`source_url` + `source_type`)
- [x] Teste: dado "Startup X", o sistema retorna texto limpo e estruturado do site (validado com Hand Talk via `scripts/collect_startup.py`)

**Enriquecimento — só depois do mínimo validado:**
- [ ] Scraper de página de carreiras (Scrapling)
- [ ] Scraper de portais de notícias (NeoFeed, Brazil Journal — trafilatura + Scrapling)
- [ ] Integração com GitHub API (repositórios, linguagens, frequência de commits)
- [ ] Scraper de vagas de emprego (Gupy, Indeed — Scrapling)
- [ ] Busca e extração de transcrições de podcasts por nome do founder

### Bloco 2 — Base de conhecimento NVIDIA (Entregável 3)
Objetivo: RAG funcional sobre tecnologias NVIDIA com qualidade de recuperação validada.

**Mínimo funcional — implementar e validar antes de ingerir tudo:**
- [x] Estudo dos materiais contextuais (Sequoia, Emergence, NVIDIA blog) antes de qualquer código — resumido em `docs/referencias/estudo-materiais-textuais.md` e `estudo-videos.md`
- [x] Pipeline RAG básica funcionando: ingestão → chunking → embeddings → Qdrant → recuperação
- [x] Ingestão de 2–3 tecnologias NVIDIA (NIM, NeMo, Inception) — embeddings locais via fastembed
- [x] Teste: pergunta sobre NIM retorna resposta relevante com citação de fonte (via `scripts/ask_nvidia.py`)

**Enriquecimento — só depois do mínimo validado:**
- [ ] Ingestão dos materiais contextuais completos
- [ ] Ingestão das documentações oficiais das 16 tecnologias NVIDIA restantes
- [ ] Busca híbrida (vetorial + BM25)
- [ ] Reranking com Cohere integrado
- [ ] Teste de qualidade amplo: todas as tecnologias respondem bem

### Bloco 3 — Sistema multiagente + classificação (Entregável 2)
Objetivo: LangGraph orquestrando agentes com classificação de maturidade funcionando.

**Mínimo funcional — pipeline simples de ponta a ponta antes de qualquer refinamento:**
- [x] Grafo LangGraph com 3 agentes básicos: Scraper → Extractor → Classifier
- [x] Classifier Agent respondendo o checklist de 6 perguntas com o que já foi coletado
- [x] Output com nível de classificação + checklist preenchido (inconclusivo é válido)
- [x] Teste com 1 startup real: classificação faz sentido? (Hand Talk → AI-enabled/nível 2, via `scripts/classify_startup.py`)

**Enriquecimento — só depois do mínimo validado:**
- [ ] Search Planner Agent integrado
- [ ] Evidence Validator Agent validando fontes
- [ ] Todos os agentes do grafo completo conectados
- [ ] Teste com 3–5 startups reais para validar qualidade da classificação

### Bloco 4 — Motor de recomendação + briefing (Entregável 4)
Objetivo: pipeline completa gerando briefing executivo utilizável para o gerente da NVIDIA.

**Mínimo funcional — 1 startup gerando briefing de ponta a ponta antes de refinar:**
- [x] NVIDIA RAG Agent consultando a base com contexto da startup
- [x] Recommendation Agent gerando recomendações básicas
- [x] Briefing Agent gerando relatório simples mas completo
- [x] Teste: dado "Startup X", o briefing gerado faz sentido e seria útil ao gerente? (validado com Hand Talk via `scripts/run_radar.py`)

**Enriquecimento — só depois do mínimo validado:**
- [ ] Output estruturado completo: justificativa técnica, justificativa de negócio, prioridade, complexidade, próxima ação, evidências
- [ ] Refinamento do tom e formato do briefing
- [ ] Teste com múltiplas startups de setores diferentes

### Bloco 5 — Interface web (Entregável 5)
Objetivo: dashboard utilizável pelo gerente da NVIDIA para consultar, visualizar e exportar.

**Mínimo funcional:**
- [ ] Stack a definir após blocos 1–4 funcionando
- [ ] Input de consulta + exibição do briefing gerado em tela

**Enriquecimento:**
- [ ] Visualização do perfil da startup com dados coletados
- [ ] Visualização da classificação com checklist e evidências
- [ ] Visualização das recomendações NVIDIA organizadas
- [ ] Exportação do briefing (PDF ou similar)

### Bloco 6 — Diferencial (Entregável 6)
- [ ] Definir escopo após blocos 1–4 prontos e com mais contexto do parceiro
- [ ] Explorar dores reais do time de Startups & VCs não cobertas pelo escopo principal

---

## Convenções de Código

- Linguagem principal: **Python 3.12**
- Gerenciador de pacotes: **uv** — nunca usar pip diretamente
- Nomenclatura de arquivos: `snake_case`
- Nomenclatura de classes: `PascalCase`
- Nomenclatura de funções e variáveis: `snake_case`
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`)
- Branches: `feature/nome-descritivo`, `fix/nome-descritivo`
- Nunca commitar credenciais. Tudo em `.env`, com `.env.example` documentado.
- Variáveis de ambiente para LLM provider — nunca hardcoded.

---

## Estrutura de Diretórios (referência inicial)

```
/
├── CLAUDE.md
├── .env.example
├── README.md
├── pyproject.toml        # dependências e metadados do projeto (gerenciado pelo uv)
├── uv.lock               # lock file gerado automaticamente — commitar sempre
├── .python-version       # versão do Python fixada (3.12)
├── docs/                     # CLAUDE.md (este guia) + materiais de referência
│   └── referencias/          # contexto e estudo (mantém a raiz de docs/ limpa)
│       ├── tap.md                        # briefing original do projeto
│       ├── estudo-materiais-textuais.md  # resumo dos textos (Sequoia, Emergence, NVIDIA)
│       ├── tranc_youtube.md              # transcrições dos vídeos (NVIDIA Inception)
│       └── estudo-videos.md              # resumo dos vídeos (NVIDIA Inception)
├── src/                          # código-fonte (src layout — pacotes instalados em modo editável via uv)
│   ├── agents/
│   │   ├── llm.py                # helper de chamada ao LLM (OpenRouter), compartilhado
│   │   ├── scraper.py            # [Bloco 3] coleta o texto da startup
│   │   ├── extractor.py          # [Bloco 3] texto bruto → dados estruturados (LLM)
│   │   ├── classifier.py         # [Bloco 3] checklist + nível de maturidade (LLM)
│   │   ├── search_planner.py     # (futuro)
│   │   ├── evidence_validator.py # (futuro)
│   │   ├── nvidia_rag.py         # (futuro)
│   │   ├── recommender.py        # (futuro)
│   │   └── briefing.py           # (futuro)
│   ├── graph/
│   │   ├── state.py              # estado compartilhado do grafo (TypedDict)
│   │   └── pipeline.py           # grafo LangGraph (Scraper → Extractor → Classifier)
│   ├── rag/
│   │   ├── embeddings.py         # fastembed (modelo local, 384 dims)
│   │   ├── chunking.py           # quebra texto em chunks
│   │   ├── vector_store.py       # cliente Qdrant + coleção
│   │   ├── ingestion.py          # página → chunks → vetores → Qdrant
│   │   ├── retrieval.py          # busca por similaridade no Qdrant
│   │   ├── generation.py         # LLM responde com base nos trechos + cita fonte
│   │   └── reranker.py           # Cohere rerank (enriquecimento, futuro)
│   ├── scraping/
│   │   ├── scrapling_fetcher.py  # fetch + parsing + anti-bot (substitui playwright + bs4)
│   │   ├── firecrawl_client.py   # extração de conteúdo limpo para RAG
│   │   ├── trafilatura_parser.py # extração de texto principal de artigos
│   │   ├── github_scraper.py
│   │   ├── jobs_scraper.py
│   │   └── podcast_transcript.py
│   ├── enrichment/
│   │   ├── crunchbase_client.py
│   │   └── dealroom_client.py
│   └── db/
│       ├── models.py             # Modelos (tabelas) SQLAlchemy
│       ├── session.py            # Conexão com o PostgreSQL (engine + sessões)
│       ├── repository.py         # Funções de leitura/gravação no banco
│       └── migrations/
├── scripts/                      # scripts utilitários e de diagnóstico (ex.: check_openrouter.py)
├── frontend/                     # A definir
└── tests/
```

> **Nota sobre o `src/` layout:** os pacotes ficam em `src/` e são instalados em modo editável pelo `uv sync`.
> O `pyproject.toml` declara `build-system = hatchling` e lista os pacotes em `[tool.hatch.build.targets.wheel]`,
> o que torna `import agents`, `import graph`, etc. válidos em qualquer script (`uv run`) e nos testes — sem mexer em `PYTHONPATH`.

---

## Documentos de Referência

Materiais de contexto e estudo ficam em `docs/referencias/`:
- `referencias/tap.md` — briefing original do projeto (TAPI).
- `referencias/estudo-materiais-textuais.md` — framework AI-native (Sequoia, Emergence) + "5-layer cake" (NVIDIA).
- `referencias/estudo-videos.md` — NVIDIA Inception: elegibilidade, benefícios, critérios de avaliação, ferramentas.
- `referencias/tranc_youtube.md` — transcrições brutas dos vídeos.

Mantenha este arquivo (CLAUDE.md) focado no essencial para toda sessão; o detalhe vai nas referências.

---

## Prompt inicial para Claude Code

Copie e cole isso como primeira mensagem ao abrir o Claude Code no repositório:

```
Leia o CLAUDE.md completo antes de qualquer coisa.

Este é o projeto NVIDIA Startup AI Radar (TAPI) — uma plataforma multi-agente para mapear, classificar e recomendar tecnologias NVIDIA para startups brasileiras de IA.

Estamos no início absoluto. O repositório está vazio.

Duas regras inegociáveis deste projeto:

1. Mínimo funcional antes de qualquer enriquecimento.
   Cada bloco do roadmap tem uma seção "Mínimo funcional" — implemente só isso primeiro.
   A seção "Enriquecimento" só entra depois que o mínimo estiver validado e funcionando.

2. Explicar antes de implementar — sempre.
   Antes de qualquer código, explique em linguagem técnica simplificada:
   o que é aquele componente, por que ele entra agora e como se conecta com o que já existe.
   Essa explicação deve ser curta — só o suficiente para eu saber explicar o que está sendo feito.
   Aguarde minha confirmação antes de escrever qualquer código.
   Isso vale para cada sub-passo, não só para blocos inteiros.

Quero começar pelo Bloco 0 (Fundação), conforme descrito no CLAUDE.md.

Antes de qualquer coisa:
1. Confirme que leu e entendeu o CLAUDE.md
2. Me explique o que é o Bloco 0 e o que cada peça dele faz
3. Aguarde minha confirmação para começar

Se algo não estiver documentado no CLAUDE.md, pergunte antes de assumir.
Se eu afirmar algo tecnicamente impreciso, me contradiga diretamente.
```

---

## Decisões Resolvidas

Registradas aqui para rastreabilidade. Detalhes em `docs/decisions.md`.

- [x] **Rubrica de classificação AI-native** — 4 níveis (AI-native / AI-enabled / AI-wrapper / Non-AI), método checklist + raciocínio do agente. Ver seção acima.
- [x] **Volume por consulta** — inicialmente pequeno (handful de startups). Playwright suficiente por ora. Scrapy entra quando escalar.
- [x] **Modo de operação** — one-shot. Usuário consulta, sistema processa, entrega briefing. Sem monitoramento contínuo na versão inicial.
- [x] **Infra inicial** — local (Docker Compose). Deploy estruturado quando o sistema estiver estável e antes de apresentar ao parceiro NVIDIA.

---

## Decisões Pendentes

Registrar em `docs/decisions.md` quando resolvidas.

- [x] **Formato do briefing executivo** — DECIDIDO por nós (sem validação externa): markdown com seções Resumo / Classificação + justificativa / Recomendações NVIDIA / Próxima ação. Refinável depois.
- [ ] **Escopo do Entregável 6** — diferencial a definir por nós, após os entregáveis 1–4 estarem funcionando.
- [ ] **Ordem final de ingestão da base RAG NVIDIA** — recomendação atual: contextuais primeiro, depois docs oficiais por tecnologia.
- [ ] **Modelo LLM de produção** — Bloco 0 validado com `nvidia/nemotron-nano-9b-v2:free` (grátis, porém instável: vimos rate-limit `429` e retorno vazio durante os testes). Antes do Bloco 3 (pipeline multi-agente, muitas chamadas), definir um modelo pago barato e confiável + crédito no OpenRouter.
- [x] **Provider de embeddings** — RESOLVIDO: local via fastembed (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dims, multilíngue). Sem chave nem custo.
- [ ] **Versão do Qdrant** (pós-MVP) — cliente `qdrant-client` 1.18 vs imagem do servidor 1.12.4. Alinhar subindo a tag da imagem no `docker-compose.yml` (re-pull + re-ingestão).
- [ ] **Estratégia de enriquecimento** — terminar o MVP (mínimo de todos os blocos, ponta a ponta) ANTES de qualquer enriquecimento. Só então: ingerir as 16 tecnologias NVIDIA, busca híbrida (BM25), rerank com Cohere, teste amplo.