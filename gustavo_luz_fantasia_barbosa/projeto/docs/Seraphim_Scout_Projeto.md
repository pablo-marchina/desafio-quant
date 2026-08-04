# Seraphim Scout

## Documento vivo de arquitetura e status do projeto

**Projeto:** Seraphim Scout  
**Contexto:** Inteli Academy / Processo seletivo técnico  
**Tipo de solução:** Plataforma de inteligência com scraping, agentes, RAG, banco vetorial e motor de recomendação  
**Status:** MVP técnico funcional com arquitetura, requisitos, roadmap e status de implementação atualizados

---

## Como ler este documento

Este documento separa três camadas do projeto:

| Camada | O que significa | Onde aparece |
|---|---|---|
| **Arquitetura-alvo** | Desenho completo da solução e decisões técnicas esperadas | Seções 1 a 18 |
| **Implementação atual** | Funcionalidades já atendidas pelo MVP no repositório | Seções 19, 20, 22 e 25 |
| **Evolução planejada** | Melhorias técnicas e estratégicas após o MVP | Seções 26 e 28 |

Sempre que uma funcionalidade estiver marcada como implementada, ela deve ter pelo menos uma evidência verificável: arquivo relacionado, endpoint, script de validação, teste automatizado, dado persistido ou comportamento visível na interface.

---

# 1. Visão geral do projeto

O **Seraphim Scout** é uma plataforma de inteligência projetada para identificar, analisar e priorizar startups brasileiras com potencial de uso intensivo de inteligência artificial. A solução tem como objetivo apoiar o trabalho de prospecção, qualificação técnica e nutrição de startups para o ecossistema NVIDIA, especialmente no contexto do programa **NVIDIA Inception**.

A proposta central é construir um sistema capaz de coletar dados públicos sobre startups, estruturar essas informações, avaliar sinais de maturidade AI-native, identificar gaps técnicos e recomendar tecnologias NVIDIA adequadas ao perfil de cada empresa.

Diferentemente de um chatbot simples, este projeto deve funcionar como um **motor multiagente de análise técnica e estratégica**. O sistema não apenas responde perguntas, mas executa uma pipeline de busca, coleta, extração, classificação, validação de evidências, recuperação de conhecimento técnico e geração de recomendações personalizadas.

---

# 2. Contextualização do problema

O mercado de inteligência artificial está passando por uma mudança estrutural. Grandes laboratórios de IA deixaram de atuar apenas como fornecedores de modelos fundacionais e passaram a oferecer produtos finais, APIs multimodais, agentes, ferramentas corporativas, automações, busca, voz, código, integrações e soluções completas.

Esse movimento cria uma ameaça direta para startups que dependem apenas de APIs de terceiros e se posicionam como simples interfaces sobre modelos de linguagem. Startups que não possuem dados proprietários, workflow operacional profundo, distribuição clara ou otimização técnica podem ser rapidamente substituídas por funcionalidades nativas dos grandes labs.

Ao mesmo tempo, existe uma oportunidade relevante para startups que evoluem para o modelo de **AI-native services**. Nesse modelo, a empresa combina software, agentes, automação, dados proprietários, especialização setorial e serviço operacional para entregar resultados de negócio de ponta a ponta.

Nesse cenário, a NVIDIA tem uma posição estratégica. Muitas startups começam usando APIs externas por simplicidade, mas conforme crescem passam a enfrentar desafios de custo, latência, escalabilidade, governança, privacidade, avaliação, observabilidade, deployment e dependência de fornecedores. A stack NVIDIA pode ajudar essas startups a evoluir de protótipos baseados em APIs para sistemas de IA preparados para produção.

---

# 3. Pergunta norteadora

**Como a NVIDIA pode identificar, atrair e nutrir startups brasileiras AI-native em um contexto no qual os grandes laboratórios de IA ameaçam startups que dependem apenas de wrappers de LLM?**

---

# 4. Objetivo geral

Construir um sistema capaz de encontrar startups brasileiras com sinais de uso intensivo de IA, coletar dados públicos sobre elas, diagnosticar sua maturidade técnica, consultar uma base de conhecimento sobre tecnologias NVIDIA e gerar recomendações personalizadas para apoiar ações comerciais, técnicas e comunitárias ligadas ao NVIDIA Inception.

## 4.1 Valor de negócio para NVIDIA

O projeto deve apoiar decisões práticas de prospecção e nutrição técnica, não apenas gerar relatórios. Os principais usuários internos seriam:

| Usuário interno | Decisão apoiada | Saída útil do sistema |
|---|---|---|
| Time NVIDIA Inception | Quais startups priorizar para aproximação ou nutrição | Fit Score, timing de oportunidade, briefing executivo e trilha de adoção |
| DevRel / engenharia de soluções | Qual dor técnica explorar em uma primeira conversa | Gaps técnicos, tecnologias NVIDIA recomendadas e evidências públicas |
| Parcerias e ecossistema | Quais setores ou clusters têm maior aderência à stack NVIDIA | Radar por setor, padrões de gaps e startups similares |
| Comercial técnico | Como abordar a startup sem parecer uma recomendação genérica | Playbook de abordagem, hipótese de valor e pergunta de descoberta |

KPIs esperados para uma evolução do MVP:

- Reduzir o tempo de triagem inicial de startups.
- Aumentar a proporção de abordagens com justificativa técnica clara.
- Identificar mais cedo startups com risco de dependência excessiva de APIs externas.
- Melhorar a rastreabilidade das recomendações feitas para cada startup.
- Priorizar oportunidades com maior chance de adoção de tecnologias NVIDIA.

---

# 5. Objetivos específicos

- Encontrar startups brasileiras com sinais relevantes de uso de inteligência artificial.
- Coletar dados públicos sobre empresa, produto, setor, clientes, funding, founders e tecnologias utilizadas.
- Extrair informações estruturadas a partir de páginas públicas, notícias, blogs, diretórios e perfis institucionais.
- Classificar startups como **AI-native**, **AI-enabled**, **non-AI**, **wrapper risk** ou **insufficient evidence**.
- Identificar gaps técnicos relacionados a custo, latência, escalabilidade, governança, inferência, dados, observabilidade e dependência de fornecedores.
- Consultar uma base RAG com tecnologias NVIDIA.
- Recomendar tecnologias NVIDIA adequadas ao perfil e aos gaps da startup.
- Gerar um briefing executivo com evidências, justificativa técnica, justificativa de negócio e próxima ação sugerida.
- Manter a base de conhecimento NVIDIA atualizada por meio de uma automação de checagem de novidades nos sites oficiais.

---

# 6. Escopo da solução

A solução será composta por uma pipeline multiagente que recebe uma requisição do usuário, busca ou analisa uma startup, coleta fontes públicas, estrutura os dados encontrados, classifica a maturidade AI-native, valida evidências, consulta uma base RAG sobre tecnologias NVIDIA e gera recomendações personalizadas.

O foco principal do projeto está nos seguintes elementos:

1. **Pipeline de scraping e coleta de dados públicos**
2. **Sistema multiagente com LangGraph**
3. **RAG NVIDIA com banco vetorial e reranking**
4. **Motor de classificação AI-native**
5. **Motor de recomendação de tecnologias NVIDIA**
6. **Validação de evidências e rastreabilidade das fontes**
7. **Automação de atualização da base NVIDIA**
8. **Interface web ou dashboard para visualização dos resultados**

## 6.1 Evidence Quality Gate

O **Evidence Quality Gate** é uma regra central do sistema, não apenas um diferencial visual. Ele impede que o projeto gere recomendações convincentes, mas pouco sustentadas por fontes.

Uma recomendação técnica só deve ser considerada **aceita** quando cumprir todos os critérios mínimos:

| Critério | Regra mínima |
|---|---|
| Evidência da startup | Pelo menos uma fonte pública rastreável ligada ao produto, setor, uso de IA ou dor técnica |
| Evidência NVIDIA | Pelo menos um trecho recuperado da base NVIDIA com URL de origem |
| Relação entre gap e tecnologia | Justificativa explícita conectando dor técnica da startup e tecnologia recomendada |
| Confiança mínima | Score de recuperação, groundedness ou validação acima do threshold definido para o MVP |
| Rastreabilidade | IDs de fonte, evidência, chunk ou briefing disponíveis para auditoria |

Quando os critérios não forem atendidos, a recomendação deve ser **rebaixada** ou **bloqueada**, e o briefing deve explicar a limitação em linguagem clara.

## 6.2 Governança de scraping, privacidade e fontes públicas

O scraping do projeto deve seguir uma abordagem conservadora:

- Coletar apenas informações públicas e necessárias para a análise.
- Respeitar `robots.txt`, termos de uso conhecidos e limites razoáveis de requisição.
- Evitar coleta de dados pessoais sensíveis que não sejam necessários para a qualificação técnica.
- Registrar URL, data de coleta, tipo de fonte, trecho usado e metadados de rastreabilidade.
- Diferenciar fato observado, inferência do sistema e hipótese comercial.
- Permitir marcação de baixa confiança quando as fontes forem incompletas, antigas ou ambíguas.
- Não usar scraping para burlar paywalls, autenticação, bases fechadas ou restrições explícitas de acesso.

Essas regras reduzem risco legal, aumentam a confiabilidade da análise e tornam o sistema mais defensável em uma avaliação técnica.

---

# 7. Ideia central do funcionamento

O usuário poderá iniciar uma análise de duas formas principais:

## 7.1 Análise de uma startup específica

Exemplo de entrada:

```txt
Analise a startup NeuralMed e recomende tecnologias NVIDIA adequadas.
```

Fluxo esperado:

1. O sistema verifica se a base de conhecimento NVIDIA está atualizada.
2. O sistema busca informações públicas sobre a startup.
3. As fontes são coletadas e limpas.
4. Um agente extrai dados estruturados.
5. Um agente classifica a startup.
6. Um agente valida evidências.
7. O RAG consulta documentos NVIDIA relevantes.
8. O motor de recomendação cruza gaps técnicos com tecnologias NVIDIA.
9. O briefing executivo é gerado.

## 7.2 Busca por startups de um setor

Exemplo de entrada:

```txt
Encontre startups brasileiras de IA no setor de saúde.
```

Fluxo esperado:

1. O Search Planner Agent transforma a consulta em termos de busca.
2. O Scraper Agent coleta fontes públicas.
3. O Extractor Agent estrutura os dados encontrados.
4. O Classifier Agent ranqueia as startups por maturidade AI-native.
5. O Recommendation Agent identifica quais startups têm maior fit com NVIDIA.
6. O sistema exibe uma lista priorizada.

---

# 8. Arquitetura de alto nível

```txt
Usuário
  ↓
Interface Web / Dashboard
  ↓
Backend API
  ↓
LangGraph Orchestrator
  ↓
NVIDIA Knowledge Freshness Agent
  ↓
Search Planner Agent
  ↓
Scraper Agent
  ↓
Extractor Agent
  ↓
Banco estruturado de startups
  ↓
Startup Classifier Agent
  ↓
Evidence Validator Agent
  ↓
NVIDIA RAG Agent
  ↓
Reranker
  ↓
Recommendation Agent
  ↓
Briefing Agent
  ↓
Briefing executivo com recomendações e evidências
```

---

# 9. Componentes principais

## 9.1 Frontend / Dashboard

A interface web deve permitir:

- Inserir o nome ou site de uma startup.
- Buscar startups por setor ou termo.
- Visualizar status da pipeline.
- Ver fontes coletadas.
- Ver evidências extraídas.
- Consultar classificação AI-native.
- Ver tecnologias NVIDIA recomendadas.
- Exportar briefing em Markdown ou PDF.
- Visualizar alertas de atualização da base NVIDIA.

O frontend pode ser construído com:

- React + Vite
- Next.js
- TailwindCSS

## 9.2 Backend API

O backend será responsável por expor endpoints para iniciar análises, consultar startups, recuperar briefings, buscar recomendações e acionar processos de ingestão.

Tecnologias sugeridas:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- LangGraph
- Qdrant Client
- PostgreSQL

## 9.3 Banco relacional

O banco relacional será usado para armazenar dados estruturados:

- Startups
- Fontes públicas
- Evidências
- Perfis extraídos
- Classificações
- Gaps técnicos
- Tecnologias NVIDIA
- Recomendações
- Briefings
- Logs de agentes
- Execuções da pipeline
- Registro de documentos NVIDIA
- Histórico de verificações de atualização

Banco sugerido:

- PostgreSQL

## 9.4 Banco vetorial

O banco vetorial será usado para armazenar embeddings e permitir busca semântica.

Banco escolhido para o projeto:

- Qdrant local via Docker

Collections principais:

```txt
nvidia_knowledge_base
startup_evidence
```

### Collection `nvidia_knowledge_base`

Armazena chunks vetorizados de documentos NVIDIA.

Exemplo de payload:

```json
{
  "document_id": "uuid-do-documento",
  "product_name": "NVIDIA NIM",
  "category": "model_deployment",
  "source_type": "official_docs",
  "source_url": "https://...",
  "chunk_index": 0,
  "chunk_text": "Texto do chunk...",
  "published_at": "2026-01-10",
  "last_checked_at": "2026-06-14"
}
```

### Collection `startup_evidence`

Armazena chunks vetorizados de textos coletados sobre startups.

Exemplo de payload:

```json
{
  "startup_id": "uuid-da-startup",
  "startup_name": "Startup X",
  "source_id": "uuid-da-fonte",
  "source_type": "official_website",
  "source_url": "https://startupx.com",
  "sector": "healthcare",
  "chunk_index": 0,
  "chunk_text": "Texto coletado sobre a startup..."
}
```

---

# 10. Agentes do sistema

## 10.0 Contrato geral dos agentes

Todos os agentes devem operar sobre um estado compartilhado da pipeline e seguir um contrato mínimo de entrada, saída e falha. Isso facilita testes, fallback sequencial, rastreabilidade e substituição futura de implementações.

Contrato comum:

```json
{
  "run_id": "uuid-da-execucao",
  "input": {},
  "output": {},
  "evidence_refs": [],
  "confidence": 0.0,
  "status": "success | partial | skipped | failed",
  "errors": [],
  "started_at": "2026-06-30T10:00:00Z",
  "finished_at": "2026-06-30T10:00:02Z"
}
```

Regras comuns:

- Cada agente deve registrar status e erro sem apagar o estado anterior.
- Saídas inferidas devem ser diferenciadas de fatos observados em fonte pública.
- Agentes que geram claims devem retornar referências de evidência ou indicar baixa confiança.
- Falhas parciais não devem interromper a pipeline quando houver fallback seguro.
- O `pipeline_trace` deve permitir reconstruir a ordem, duração e resultado de cada etapa.

Resumo dos contratos específicos:

| Agente | Entrada principal | Saída principal | Falha esperada |
|---|---|---|---|
| Knowledge Freshness | Registro de fontes NVIDIA e política de atualização | Status de atualização, decisão de ingestão e motivo | Fonte indisponível, data ausente, conteúdo ambíguo |
| Search Planner | Consulta do usuário, setor ou nome da startup | Queries, fontes prioritárias e campos-alvo | Consulta vaga ou sem setor claro |
| Scraper | Queries, site ou URLs candidatas | Fontes públicas, textos limpos e metadados | Timeout, bloqueio, página sem conteúdo útil |
| Extractor | Textos coletados e metadados | Perfil estruturado, sinais de IA, gaps e evidências | Texto insuficiente ou contraditório |
| Classifier | Perfil estruturado e evidências | Classe AI-native, scores e justificativa | Evidência insuficiente para classificação forte |
| Evidence Validator | Claims, recomendações e fontes | Claims aceitas, rebaixadas ou bloqueadas | Claim sem fonte ou fonte fraca |
| NVIDIA RAG | Perfil, gaps e consulta técnica | Chunks NVIDIA, scores e URLs | Baixa recuperação ou tecnologia fora de escopo |
| Recommendation | Perfil, gaps, scores e chunks NVIDIA | Recomendações priorizadas com próxima ação | Falta de conexão entre gap e tecnologia |
| Briefing | Estado consolidado da análise | Relatório executivo com evidências e limitações | Dados incompletos ou recomendações bloqueadas |

## 10.1 NVIDIA Knowledge Freshness Agent

Este agente será executado no início de uma requisição de análise de startup. Sua função é verificar se a base de conhecimento NVIDIA está atualizada antes que o RAG gere recomendações.

Responsabilidades:

- Consultar a lista de fontes oficiais NVIDIA registradas.
- Verificar a data da versão mais recente armazenada localmente.
- Acessar o site oficial correspondente.
- Identificar se há conteúdo mais recente.
- Comparar a data local com a data remota.
- Fazer uma análise simples de utilidade para startups.
- Decidir se o conteúdo novo deve ser ingerido no RAG.
- Registrar o resultado da checagem.

Exemplo de saída:

```json
{
  "source_url": "https://developer.nvidia.com/triton-inference-server",
  "local_latest_date": "2026-04-01",
  "remote_latest_date": "2026-06-10",
  "status": "outdated",
  "is_useful_for_startups": true,
  "usefulness_score": 0.82,
  "reason": "A atualização menciona melhorias de deployment e inferência em produção, o que pode ser relevante para startups com problemas de latência e escala.",
  "action": "ingest_new_content"
}
```

## 10.2 Search Planner Agent

Transforma a consulta do usuário em uma estratégia de busca.

Entrada exemplo:

```txt
Encontre startups brasileiras de IA em saúde.
```

Saída esperada:

```json
{
  "search_queries": [
    "startup brasileira inteligência artificial saúde",
    "healthtech IA generativa Brasil",
    "startup diagnóstico médico inteligência artificial Brasil"
  ],
  "priority_sources": [
    "sites oficiais",
    "Startups.com.br",
    "Distrito",
    "Brazil Journal",
    "Exame Startups"
  ],
  "target_fields": [
    "nome",
    "setor",
    "produto",
    "uso de IA",
    "clientes",
    "funding",
    "founders",
    "tecnologias"
  ]
}
```

## 10.3 Scraper Agent

Coleta informações públicas em sites, notícias, blogs, diretórios, perfis de aceleradoras e páginas institucionais.

Tecnologias sugeridas:

- Playwright
- BeautifulSoup
- Scrapy
- Firecrawl
- trafilatura

O objetivo não é violar termos de uso, acessar bases fechadas ou copiar conteúdo indevido. O foco é coletar informações públicas com rastreabilidade.

## 10.4 Extractor Agent

Transforma texto não estruturado em dados estruturados.

Campos extraídos:

- Nome da startup
- Site
- Setor
- Descrição
- Produto
- Clientes
- Fundadores
- Funding
- Sinais de IA
- Técnicas de IA utilizadas
- Possíveis tecnologias
- Gaps técnicos
- Evidências

## 10.5 Startup Classifier Agent

Classifica a startup com base nos sinais coletados.

Categorias:

```txt
ai_native
ai_enabled
non_ai
wrapper_risk
insufficient_evidence
```

Critérios:

- IA está no core do produto?
- A startup possui dados proprietários?
- Existe workflow profundo ou apenas interface superficial?
- Há dependência de APIs externas?
- Existem sinais de escala, latência ou inferência em produção?
- O setor tem aderência à stack NVIDIA?
- Há evidências públicas suficientes?

## 10.6 Evidence Validator Agent

Valida se as afirmações do sistema possuem suporte em fontes públicas.

Responsabilidades:

- Verificar se cada claim tem fonte.
- Diferenciar evidência direta de inferência.
- Atribuir score de confiança.
- Identificar incertezas.
- Evitar recomendações baseadas em alucinação.

## 10.7 NVIDIA RAG Agent

Consulta a base de conhecimento NVIDIA e recupera trechos relevantes para o perfil da startup.

Pipeline:

1. Recebe o perfil e os gaps da startup.
2. Gera consulta semântica.
3. Busca no Qdrant.
4. Combina com busca lexical BM25 quando necessário.
5. Aplica reranking.
6. Retorna trechos relevantes com fontes.

## 10.8 Recommendation Agent

Cruza o perfil da startup, os gaps técnicos e os documentos NVIDIA recuperados para gerar recomendações.

Cada recomendação deve conter:

- Tecnologia NVIDIA recomendada.
- Justificativa técnica.
- Justificativa de negócio.
- Nível de prioridade.
- Complexidade de implementação.
- Próxima ação sugerida.
- Evidências usadas.

## 10.9 Briefing Agent

Gera o relatório final para uso executivo.

O briefing deve conter:

- Resumo da startup.
- Sinais de IA.
- Classificação AI-native.
- Scores.
- Gaps técnicos.
- Tecnologias NVIDIA recomendadas.
- Justificativa técnica.
- Justificativa de negócio.
- Próxima ação.
- Evidências e fontes.
- Limitações e incertezas.

---

# 11. Automação de atualização da base NVIDIA

## 11.1 Motivação

Como a base RAG depende de documentos técnicos da NVIDIA, existe o risco de o sistema recomendar tecnologias com base em informações antigas. Para reduzir esse problema, será implementada uma automação de checagem de atualização.

Sempre que uma nova análise de startup for iniciada, o sistema deverá verificar se os documentos NVIDIA usados pelo RAG estão atualizados.

## 11.2 Funcionamento esperado

Fluxo:

```txt
Usuário inicia análise de startup
  ↓
Sistema consulta registro local de fontes NVIDIA
  ↓
Sistema acessa páginas oficiais cadastradas
  ↓
Sistema identifica data mais recente no site
  ↓
Sistema compara com data mais recente armazenada localmente
  ↓
Se estiver atualizado: segue a análise normalmente
  ↓
Se houver atualização: avalia utilidade para startups
  ↓
Se for útil: coleta, limpa, chunka, embeda e salva no Qdrant
  ↓
Sistema registra atualização e continua a análise da startup
```

## 11.3 Critérios de utilidade para startups

Uma atualização será considerada útil quando estiver relacionada a pelo menos um dos seguintes tópicos:

- Deployment de modelos em produção.
- Redução de latência.
- Redução de custo de inferência.
- Escalabilidade.
- Segurança e guardrails.
- Governança de IA.
- Observabilidade.
- Avaliação de modelos.
- Otimização com GPU.
- Casos de uso setoriais.
- Programas, benefícios ou recursos para startups.
- Integrações úteis para produtos AI-native.
- Novos microservices ou ferramentas NVIDIA aplicáveis a startups.

## 11.4 Resultado da análise simples de utilidade

Exemplo:

```json
{
  "title": "New NVIDIA NIM updates for inference deployment",
  "source_url": "https://...",
  "remote_date": "2026-06-10",
  "local_latest_date": "2026-05-15",
  "is_newer": true,
  "is_useful_for_startups": true,
  "usefulness_score": 0.78,
  "useful_topics": [
    "inference_latency",
    "model_deployment",
    "production_ai"
  ],
  "decision": "ingest",
  "reason": "O conteúdo é útil porque aborda deployment otimizado de modelos, tema relevante para startups que dependem de LLMs em produção."
}
```

## 11.5 Estratégia MVP

Na versão inicial, a checagem pode ser simples:

1. Manter uma lista fixa de URLs NVIDIA.
2. Buscar a página.
3. Tentar identificar data por:
   - metadados HTML;
   - tags `datePublished` ou `dateModified`;
   - cabeçalho HTTP `Last-Modified`;
   - padrões textuais na página.
4. Comparar com a data local registrada.
5. Se a data remota for mais recente, extrair o texto.
6. Pedir ao LLM uma classificação simples de utilidade.
7. Se útil, atualizar a base RAG.

## 11.6 Estratégia futura

Em versões mais maduras, a automação pode ser melhorada com:

- Scheduler assíncrono.
- Cache de páginas.
- Controle de versão de documentos.
- Hash de conteúdo para detectar mudança mesmo sem data.
- Fila de ingestão.
- Revisão humana antes de atualizar documentos críticos.
- Dashboard de novidades NVIDIA.

---

# 12. Tecnologias NVIDIA na base de conhecimento

A base de conhecimento deve conter informações sobre:

## 12.1 NVIDIA Inception

Programa para startups, benefícios, comunidade, créditos, suporte técnico e go-to-market.

## 12.2 NVIDIA NIM

Microservices para deploy de modelos de IA otimizados e prontos para produção.

## 12.3 NVIDIA NeMo

Framework para treinamento, customização, avaliação e operação de modelos generativos.

## 12.4 NeMo Guardrails

Ferramenta para controle de comportamento de assistentes e agentes.

## 12.5 NVIDIA Triton Inference Server

Servidor de inferência para deploy e escala de modelos em produção.

## 12.6 TensorRT-LLM

Biblioteca para otimização de inferência de grandes modelos de linguagem.

## 12.7 NVIDIA RAPIDS

Suite para aceleração de pipelines de dados e analytics com GPU.

## 12.8 cuDF

Processamento de dataframes em GPU.

## 12.9 cuML

Machine learning acelerado em GPU.

## 12.10 CUDA

Plataforma de computação paralela em GPU.

## 12.11 NVIDIA Riva

ASR, TTS e aplicações de voz.

## 12.12 NVIDIA Omniverse

Simulação, colaboração 3D e digital twins.

## 12.13 NVIDIA Isaac

Robótica, simulação e autonomia.

## 12.14 NVIDIA Clara

Aplicações de IA em saúde e life sciences.

## 12.15 NVIDIA Morpheus

Cybersecurity com IA acelerada.

## 12.16 NVIDIA AI Enterprise

Plataforma empresarial para IA em produção.

---

# 13. Motor de recomendação

O motor de recomendação deve mapear gaps técnicos para tecnologias NVIDIA.

## 13.1 Exemplos de regras

### Caso 1: Startup usa LLM em atendimento e depende de API externa

Recomendações possíveis:

- NVIDIA NIM
- NeMo Guardrails
- Triton Inference Server
- TensorRT-LLM

Justificativa:

- Redução de dependência de APIs externas.
- Maior controle sobre deployment.
- Possibilidade de otimização de latência e custo.
- Melhor governança para agentes e assistentes.

### Caso 2: Startup processa grandes volumes de dados tabulares

Recomendações possíveis:

- NVIDIA RAPIDS
- cuDF
- cuML

Justificativa:

- Aceleração de ETL.
- Aceleração de dataframes.
- Redução de tempo em pipelines de machine learning.

### Caso 3: Startup atua com voz, call center ou transcrição

Recomendações possíveis:

- NVIDIA Riva
- NVIDIA NIM
- Triton Inference Server

Justificativa:

- Reconhecimento de fala.
- Síntese de voz.
- Deploy de serviços de voz em produção.

### Caso 4: Startup atua em saúde

Recomendações possíveis:

- NVIDIA Clara
- MONAI
- NVIDIA NIM
- NeMo Guardrails
- NVIDIA AI Enterprise

Justificativa:

- Aderência ao setor de healthcare.
- Possíveis demandas de governança, privacidade e avaliação.
- Uso de IA em imagens médicas, dados clínicos e assistentes especializados.

### Caso 5: Startup atua em robótica ou simulação

Recomendações possíveis:

- NVIDIA Isaac
- NVIDIA Omniverse
- CUDA

Justificativa:

- Simulação robótica.
- Digital twins.
- Desenvolvimento de sistemas autônomos.

---

# 14. Scores do projeto

Os scores devem ser explicáveis, reproduzíveis e acompanhados das evidências usadas no cálculo. No MVP, a pontuação pode combinar regras heurísticas e sinais extraídos por LLM, desde que cada componente seja registrado no briefing e no `pipeline_trace`.

Interpretação geral:

| Faixa | Leitura |
|---:|---|
| 0 a 39 | Baixo sinal ou evidência insuficiente |
| 40 a 69 | Sinal intermediário, requer validação humana ou mais fontes |
| 70 a 100 | Sinal forte o suficiente para priorização no MVP |

Nenhum score deve ser usado isoladamente. A decisão final deve considerar também a qualidade das evidências, a maturidade da startup e a aderência estratégica para NVIDIA.

## 14.1 AI-Native Score

Pontuação de 0 a 100 que mede o quanto a startup parece ser nativa de IA.

Critérios:

| Critério | Peso sugerido |
|---|---:|
| IA no core do produto | 20 |
| Dados proprietários | 15 |
| Profundidade do workflow | 15 |
| Uso técnico avançado de IA | 15 |
| Potencial de escala | 10 |
| Gaps resolvíveis pela NVIDIA | 15 |
| Evidências públicas confiáveis | 10 |

Fórmula sugerida:

```txt
AI-Native Score =
  core_ai_score * 0.20 +
  proprietary_data_score * 0.15 +
  workflow_depth_score * 0.15 +
  advanced_ai_score * 0.15 +
  scale_potential_score * 0.10 +
  nvidia_solvable_gap_score * 0.15 +
  evidence_quality_score * 0.10
```

Cada componente deve ser normalizado de 0 a 100. Quando não houver evidência suficiente para um componente, o sistema deve atribuir baixa confiança e explicar a lacuna, em vez de preencher o valor com suposição otimista.

## 14.2 Wrapper Risk Score

Pontuação de 0 a 100 que mede o risco de a startup ser apenas uma interface sobre APIs de LLM.

Sinais de alto risco:

- Produto descrito apenas como chatbot.
- Ausência de dados proprietários.
- Ausência de workflow específico.
- Ausência de diferenciação técnica.
- Forte dependência de APIs externas.
- Baixa barreira de entrada.

Interpretação:

| Faixa | Leitura |
|---:|---|
| 0 a 39 | Baixo risco de wrapper |
| 40 a 69 | Risco moderado; investigar diferenciação técnica e dados proprietários |
| 70 a 100 | Alto risco; abordagem NVIDIA deve focar independência, custo, governança e produção |

Fórmula sugerida:

```txt
Wrapper Risk Score =
  shallow_interface_score * 0.25 +
  external_api_dependency_score * 0.20 +
  lack_of_proprietary_data_score * 0.20 +
  low_workflow_depth_score * 0.15 +
  low_technical_differentiation_score * 0.10 +
  low_entry_barrier_score * 0.10
```

## 14.3 NVIDIA Fit Score

Pontuação de 0 a 100 que mede o quanto faz sentido a NVIDIA abordar essa startup.

Critérios:

- Uso intensivo de IA.
- Dor técnica alinhada à stack NVIDIA.
- Setor estratégico.
- Potencial de escala.
- Maturidade suficiente para adotar tecnologias NVIDIA.
- Possível aderência ao NVIDIA Inception.
- Existência de evidências públicas confiáveis.

Fórmula sugerida:

```txt
NVIDIA Fit Score =
  ai_intensity_score * 0.20 +
  nvidia_gap_alignment_score * 0.25 +
  strategic_sector_score * 0.15 +
  scale_potential_score * 0.15 +
  adoption_readiness_score * 0.10 +
  inception_fit_score * 0.10 +
  evidence_quality_score * 0.05
```

Leitura operacional:

| Faixa | Ação sugerida |
|---:|---|
| 0 a 39 | Manter como exploratória ou aguardar mais evidências |
| 40 a 69 | Nutrir com conteúdo, benchmark técnico ou pergunta de descoberta |
| 70 a 100 | Priorizar abordagem técnica ou encaminhamento para NVIDIA Inception |

---

# 15. Dados e modelagem

## 15.1 Tabelas principais do PostgreSQL

Tabelas planejadas:

```txt
startups
pipeline_runs
startup_sources
startup_extracted_profiles
evidences
ai_classifications
technical_gaps
nvidia_technologies
recommendations
briefings
agent_logs
rag_documents
nvidia_source_registry
nvidia_document_versions
nvidia_update_checks
```

## 15.2 Tabela `nvidia_source_registry`

Armazena as fontes oficiais monitoradas.

Campos sugeridos:

```txt
id
product_name
source_url
source_type
category
is_active
check_frequency
created_at
updated_at
```

## 15.3 Tabela `nvidia_document_versions`

Armazena versões locais dos documentos NVIDIA.

Campos sugeridos:

```txt
id
source_id
title
source_url
published_at
modified_at
content_hash
raw_text
cleaned_text
chunk_count
ingested_at
is_current
```

## 15.4 Tabela `nvidia_update_checks`

Registra cada checagem de atualização.

Campos sugeridos:

```txt
id
source_id
checked_at
local_latest_date
remote_latest_date
remote_content_hash
status
is_useful_for_startups
usefulness_score
usefulness_reason
action_taken
error_message
```

Status possíveis:

```txt
up_to_date
outdated
updated
new_content_not_useful
failed_to_check
manual_review_required
```

---

# 16. Estrutura de pastas sugerida

```txt
NvidiaCase/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── agents/
│   │   │   │   ├── search_planner.py
│   │   │   │   ├── scraper_agent.py
│   │   │   │   ├── extractor_agent.py
│   │   │   │   ├── classifier_agent.py
│   │   │   │   ├── evidence_validator.py
│   │   │   │   ├── nvidia_freshness_agent.py
│   │   │   │   ├── nvidia_rag_agent.py
│   │   │   │   ├── recommendation_agent.py
│   │   │   │   └── briefing_agent.py
│   │   │   ├── graph/
│   │   │   │   ├── state.py
│   │   │   │   └── workflow.py
│   │   │   ├── rag/
│   │   │   │   ├── ingest.py
│   │   │   │   ├── chunking.py
│   │   │   │   ├── embeddings.py
│   │   │   │   ├── vector_store.py
│   │   │   │   ├── reranker.py
│   │   │   │   └── freshness_check.py
│   │   │   ├── scraping/
│   │   │   │   ├── browser.py
│   │   │   │   ├── extract_text.py
│   │   │   │   └── search.py
│   │   │   ├── schemas/
│   │   │   ├── models/
│   │   │   └── routes/
│   │   └── tests/
│   └── web/
│       └── src/
├── database/
│   ├── migrations/
│   └── seeds/
├── docs/
│   ├── PROJECT.md
│   ├── ARCHITECTURE.md
│   ├── RAG_PIPELINE.md
│   ├── AGENTS.md
│   └── RECOMMENDATION_ENGINE.md
├── scripts/
│   ├── check_qdrant.py
│   ├── create_collections.py
│   ├── test_qdrant_insert.py
│   └── test_qdrant_search.py
├── qdrant_storage/
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

# 17. Pipeline RAG NVIDIA

## 17.1 Ingestão

1. Cadastrar URLs oficiais NVIDIA.
2. Coletar conteúdo.
3. Extrair texto principal.
4. Limpar texto.
5. Dividir em chunks.
6. Gerar embeddings.
7. Salvar chunks no Qdrant.
8. Salvar metadados no PostgreSQL.

## 17.2 Chunking

Cada chunk deve manter metadados:

```json
{
  "product_name": "NVIDIA Triton Inference Server",
  "category": "inference",
  "source_url": "https://...",
  "section_title": "Model Serving",
  "chunk_index": 3,
  "published_at": "2026-01-20"
}
```

## 17.3 Recuperação

1. Receber gaps da startup.
2. Criar consulta semântica.
3. Buscar no Qdrant.
4. Aplicar filtros por categoria quando útil.
5. Aplicar reranking.
6. Retornar trechos com fontes.

## 17.4 Reranking

O reranking será usado para melhorar a qualidade dos documentos recuperados antes da geração da resposta.

Possibilidades:

- Cohere Rerank
- Jina Reranker
- bge-reranker local
- LLM-based reranking no MVP

---

# 18. Tecnologias sugeridas

Esta seção lista tecnologias compatíveis com a arquitetura-alvo. A implementação atual do MVP usa um subconjunto delas; a aderência real está resumida na matriz de requisitos da seção 19.2.

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- LangGraph
- Requests
- Playwright
- BeautifulSoup
- trafilatura

Observação de implementação atual: o MVP usa principalmente Python, FastAPI, Pydantic, Qdrant, PostgreSQL, `requests`, `html.parser`, embeddings configuráveis e reranking híbrido. Playwright, Scrapy, BeautifulSoup/trafilatura e SQLAlchemy permanecem como alternativas de evolução, não como dependências centrais do MVP.

## Banco de dados

- PostgreSQL
- Qdrant

## IA e RAG

- LLM para extração, classificação, validação e briefing
- Modelo de embeddings
- Reranker
- BM25 para busca lexical

## Frontend

- React + Vite ou Next.js
- TailwindCSS

## Infraestrutura local

- Docker Desktop
- Docker Compose
- Qdrant via Docker
- PostgreSQL via Docker

---

# 19. Entregáveis esperados

Status usado nesta seção:

| Status | Significado |
|---|---|
| **Atendido** | Funcionalidade implementada e verificável no repositório |
| **Atendido em MVP** | Funcionalidade cobre o fluxo principal, com limitações conhecidas |
| **Parcial** | Existe implementação inicial, mas ainda faltam critérios importantes |
| **Planejado** | Ainda não implementado ou depende de evolução futura |

Critério de aceite geral: um entregável só deve ser considerado atendido quando houver evidência em código, teste, script, endpoint, interface ou dado persistido.

## 19.1 Matriz de aceite e rastreabilidade

| Entregável | Status atual | Evidências no repositório | Como validar |
|---|---|---|---|
| Pipeline de scraping | Atendido em MVP | `apps/api/app/scraping.py`, `apps/api/app/startup_sources.py`, `apps/api/app/startup_discovery.py`, `apps/api/app/startups/source_metadata.py` | Rodar análise de startup e verificar fontes com URL, tipo, trecho e metadados |
| Sistema multiagente | Atendido em MVP | `apps/api/app/analysis_graph.py`, `apps/api/app/pipeline.py`, `apps/api/app/profile_extraction.py` | Verificar `pipeline_trace`, retries, fallback sequencial e disponibilidade de LangGraph no `/health` |
| RAG NVIDIA com reranking | Atendido | `apps/api/app/rag/`, `scripts/ingest_nvidia_seed.py`, `scripts/evaluate_rag.py`, `scripts/rag_eval_cases.py` | Executar ingestão da base e avaliação RAG com perguntas fixas |
| Motor de recomendação | Atendido em MVP | `apps/api/app/briefing.py`, `apps/api/app/rag/reranker.py`, schemas de análise e radar | Conferir recomendações com prioridade, complexidade, fonte NVIDIA e próxima ação |
| Interface web | Atendido em MVP | `apps/api/app/static/index.html`, `apps/api/app/static/app.js`, `apps/api/app/static/styles.css` | Abrir dashboard servido pela API e validar radar, detalhe, evidências, histórico e exportação |
| Diferenciais competitivos | Atendido em MVP | `docs/DIFERENCIAIS_ESTRATEGICOS.md`, briefing, metadados da API e interface | Validar Evidence Quality Gate, Opportunity Timing Score, Demo Mode e explicação de oportunidade |

## Entregável 1 — Pipeline de scraping

Sistema capaz de buscar e coletar informações públicas sobre startups a partir de uma consulta.

Status no repositório: atendido em MVP. O sistema coleta site oficial, links internos, fontes públicas complementares do catálogo/notícia e GitHub quando disponível, registrando URL, título, tipo, data de coleta, trecho e metadados.

Critérios de aceite:

- Coletar pelo menos uma fonte pública rastreável quando a startup tiver site ou referência pública disponível.
- Registrar URL, título, tipo de fonte, data de coleta, trecho usado e metadados.
- Não interromper toda a pipeline quando uma fonte falhar.
- Marcar evidência insuficiente quando as fontes não sustentarem a análise.

## Entregável 2 — Sistema multiagente com LangGraph

Sistema com agentes especializados para busca, extração, classificação, validação, RAG, atualização da base NVIDIA, recomendação e briefing.

Status no repositório: atendido em MVP. A dependência `langgraph` está declarada e o `/health` informa disponibilidade nominal; quando ela está instalada, `LangGraphStateGraph` usa `StateGraph`; quando ela não está instalada, `SequentialStateGraph` opera como fallback compatível com estado compartilhado, condições, retries e `pipeline_trace`.

Critérios de aceite:

- Manter estado compartilhado entre etapas.
- Registrar `pipeline_trace` com duração, status e erros.
- Suportar fluxo nominal com LangGraph quando a dependência estiver instalada.
- Suportar fallback sequencial para demo local sem quebrar o fluxo principal.

## Entregável 3 — RAG NVIDIA com reranking

Base de conhecimento contendo materiais NVIDIA e mecanismo de recuperação com reranking e citações.

Status no repositório: atendido. Há seed com 24 tecnologias, ingestão oficial opcional, Qdrant, BM25 formal no reranking híbrido, CrossEncoder opcional, freshness com reingestão seletiva e avaliação RAG com 15 perguntas fixas em `scripts/evaluate_rag.py`.

Critérios de aceite:

- Recuperar tecnologias NVIDIA relevantes com URL ou metadado de origem.
- Aplicar busca semântica e etapa de reranking.
- Retornar trechos citáveis para fundamentar recomendações.
- Rodar avaliação fixa de RAG para detectar regressões.

## Entregável 4 — Motor de recomendação

Sistema que recomenda tecnologias NVIDIA a partir do perfil da startup e dos gaps técnicos identificados.

Status no repositório: atendido em MVP. As recomendações incluem prioridade, complexidade, próxima ação, fonte NVIDIA, score de recuperação e detalhes de reranking.

Critérios de aceite:

- Associar cada recomendação a pelo menos um gap técnico.
- Incluir justificativa técnica, justificativa de negócio, prioridade, complexidade e próxima ação.
- Rebaixar ou bloquear recomendações sem lastro suficiente no Evidence Quality Gate.
- Expor fontes NVIDIA e evidências da startup usadas na decisão.

## Entregável 5 — Interface web

Dashboard ou aplicação web para consulta, visualização de empresas, recomendações e exportação de briefing.

Status no repositório: atendido em MVP. A interface servida pela API cobre radar, detalhe, evidências, RAG, histórico, análise manual e exportação Markdown/PDF de briefings salvos.

Atualização de interface: a versão atual usa header superior com navegação por abas, modo escuro e explicação clicável da porcentagem de oportunidade. Ao clicar no percentual de um card do Radar, a interface mostra um resumo em linguagem simples com a fórmula, os termos do score e os valores usados para aquela startup.

Critérios de aceite:

- Permitir análise manual de startup.
- Exibir radar, detalhe, evidências, recomendações e histórico.
- Explicar scores e oportunidade em linguagem simples.
- Exportar briefing em Markdown ou PDF.

## Entregável 6 — Diferencial competitivo

Diferenciais implementados ou demonstráveis no MVP:

- AI-Native Score
- Wrapper Risk Score
- NVIDIA Fit Score
- Evidence Validator Agent
- NVIDIA Knowledge Freshness Agent
- Atualização automática da base NVIDIA antes da análise de startups
- Métricas de qualidade por análise
- Rastreabilidade por IDs de chunks do Qdrant

Status no repositório: atendido em MVP. Os diferenciais aparecem na resposta da API, no briefing e nos metadados persistidos.

Critérios de aceite:

- Mostrar risco de wrapper com sinais e narrativa de abordagem.
- Classificar timing da oportunidade como `quente`, `morno` ou `exploratorio`.
- Diferenciar recomendação aceita, rebaixada ou bloqueada.
- Demonstrar cenários contrastantes no Demo Mode.

## 19.2 Matriz requisito do case, implementação e validação

Esta matriz resume a aderência do MVP ao case. A versão expandida está em `docs/CHECKLIST_EXIGENCIAS_TAPI.md`.

| Requisito do case | Status | Implementação principal | Como testar ou demonstrar |
|---|---|---|---|
| Identificar e priorizar startups brasileiras AI-native | Atendido em MVP | `data/startups_br.csv`, `apps/api/app/startup_catalog.py`, `apps/api/app/startup_discovery.py` | Usar o Radar por setor/foco e conferir ranking por oportunidade |
| Analisar uma startup específica | Atendido | `POST /analysis/startup`, `apps/api/app/pipeline.py`, `apps/api/app/analysis_graph.py` | Rodar análise manual pela interface ou endpoint e verificar briefing final |
| Coletar dados públicos rastreáveis | Atendido em MVP | `apps/api/app/scraping.py`, `apps/api/app/startup_sources.py`, `apps/api/app/startups/source_metadata.py` | Conferir fontes com URL, tipo, trecho e data de coleta |
| Extrair perfil estruturado | Atendido em MVP | `apps/api/app/profile_extraction.py` | Verificar descrição, setor, sinais de IA, tecnologias, founders, clientes e gaps |
| Classificar maturidade AI-native e risco wrapper | Atendido em MVP | `score_startup_profile`, `StartupClassifierAgent`, schemas de análise | Validar classe, scores e justificativas no resultado da análise |
| Validar evidências e reduzir alucinação | Atendido em MVP | `EvidenceValidatorAgent`, Evidence Quality Gate, metadados de evidência | Confirmar recomendações aceitas, rebaixadas ou bloqueadas |
| Consultar base NVIDIA com RAG | Atendido | `apps/api/app/rag/`, `/rag/search`, Qdrant | Rodar busca RAG e conferir chunks com tecnologia e fonte |
| Usar reranking | Atendido | `apps/api/app/rag/reranker.py` | Conferir detalhes de reranking e score de recuperação |
| Recomendar tecnologias NVIDIA | Atendido em MVP | `RecommendationAgent`, `apps/api/app/briefing.py` | Conferir tecnologia, gap, prioridade, complexidade, próxima ação e fonte |
| Gerar briefing executivo | Atendido em MVP | `generate_briefing_markdown`, exportação Markdown/PDF | Exportar briefing salvo pela interface |
| Atualizar ou checar freshness da base NVIDIA | Atendido em MVP | `apps/api/app/rag/freshness.py`, `/rag/freshness/check` | Executar checagem de freshness e conferir status registrado |
| Exibir dashboard web | Atendido em MVP | `apps/api/app/static/index.html`, `app.js`, `styles.css` | Abrir a interface servida pela API e navegar por Radar, detalhe, RAG e histórico |
| Persistir dados estruturados | Atendido em MVP | `apps/api/app/storage.py`, `database/migrations/` | Aplicar migrations e consultar histórico de análises |
| Demonstrar qualidade do RAG | Atendido em MVP | `scripts/rag_eval_cases.py`, `scripts/evaluate_rag.py` | Rodar avaliação fixa quando API e base RAG estiverem no ar |

## 19.3 Exemplos de saída esperada

Exemplo resumido de recomendação aceita:

```json
{
  "technology": "NVIDIA NIM",
  "priority": "alta",
  "implementation_complexity": "media",
  "technical_gap": "dependência de API externa para inferência de LLM",
  "technical_reason": "NIM pode reduzir dependência de fornecedores externos e apoiar deploy otimizado de modelos em produção.",
  "business_reason": "A startup ganha mais controle de custo, latência e governança conforme escala o produto.",
  "next_action": "Validar volume de inferência, latência atual e restrições de privacidade antes de propor piloto.",
  "evidence_status": "accepted"
}
```

Exemplo resumido de recomendação bloqueada:

```json
{
  "technology": "NVIDIA Clara",
  "technical_gap": "possivel uso de IA em saude",
  "evidence_status": "blocked",
  "block_reason": "As fontes publicas nao indicam uso de imagens medicas, dados clinicos ou demanda clara de healthcare AI.",
  "next_action": "Buscar fonte adicional ou validar o caso de uso em conversa de descoberta."
}
```

Exemplo de trecho de briefing executivo:

```md
### Proxima acao sugerida

Abordar a startup com uma conversa exploratória sobre custo, latência e dependência de APIs externas. A hipótese NVIDIA mais forte é iniciar por NVIDIA NIM e NeMo Guardrails, mas a recomendação deve permanecer condicionada a evidências adicionais sobre volume de inferência e requisitos de governança.
```

---

# 20. MVPs e evolução do desenvolvimento

Esta seção registra a progressão do MVP. Itens descritos como objetivo representam a intenção original de cada etapa; o status indica o que já está implementado no repositório.

## MVP 1 — Qdrant local e collections

Objetivo:

- Rodar Qdrant local via Docker.
- Criar collections `nvidia_knowledge_base` e `startup_evidence`.
- Inserir e buscar vetores fake.

Status atual implementado:

```txt
Qdrant local funcionando
Collections reais criadas
Scripts Python de teste criados
```

## MVP 2 — Ingestão simples da base NVIDIA

Objetivo:

- Inserir manualmente pequenos textos sobre tecnologias NVIDIA.
- Gerar embeddings reais.
- Salvar no Qdrant.
- Fazer busca semântica.

Status atual implementado:

```txt
Seed NVIDIA com 24 tecnologias
Ingestão oficial opcional
Embeddings e metadados persistidos no Qdrant
Busca semântica disponível via pipeline RAG
```

## MVP 3 — Análise de startup única

Entrada:

```txt
Nome e site da startup
```

Saída:

```txt
Resumo da startup
Sinais de IA
Classificação AI-native
Gaps técnicos
Recomendações NVIDIA
Briefing final
```

Status atual implementado:

```txt
Análise de startup única disponível pelo backend
Extração de perfil, classificação, evidências, recomendações e briefing
Persistência de resultado e histórico
```

## MVP 4 — Scraping automatizado

Objetivo:

- Coletar textos reais de sites públicos.
- Limpar textos.
- Salvar fontes e evidências.

Status atual implementado:

```txt
Coleta de site oficial e fontes públicas complementares
Registro de metadados, trechos e tipos de fonte
Fallbacks para falhas de coleta
```

## MVP 5 — LangGraph

Objetivo:

- Orquestrar os agentes.
- Criar fluxo com estado.
- Implementar retries e condicionais.

Status atual implementado:

```txt
Orquestração com LangGraph quando disponível
Fallback sequencial compatível para execução local
Estado compartilhado, retries e pipeline_trace
```

## MVP 6 — Dashboard

Objetivo:

- Visualizar startups analisadas.
- Ver scores.
- Ver recomendações.
- Exportar briefing.

Status atual implementado:

```txt
Dashboard servido pela API
Radar, detalhe, evidências, RAG, histórico e análise manual
Exportação Markdown/PDF de briefings salvos
```

---

# 21. Endpoints sugeridos

```txt
POST /analysis/startup
GET /analysis/{run_id}
GET /startups
GET /startups/{startup_id}
GET /startups/{startup_id}/recommendations
GET /startups/{startup_id}/briefing
POST /rag/ingest/nvidia
POST /rag/check-updates
GET /rag/update-checks
GET /nvidia/technologies
```

## Endpoint principal

```txt
POST /analysis/startup
```

Entrada:

```json
{
  "startup_name": "Startup X",
  "website_url": "https://startupx.com",
  "force_nvidia_update_check": true
}
```

Fluxo interno:

1. Criar `pipeline_run`.
2. Rodar `NVIDIA Knowledge Freshness Agent`.
3. Rodar scraping da startup.
4. Extrair dados.
5. Classificar startup.
6. Validar evidências.
7. Consultar RAG.
8. Gerar recomendações.
9. Gerar briefing.
10. Retornar resultado.

---

# 22. Critérios de qualidade

O projeto deve ser avaliado por:

- Qualidade da arquitetura.
- Clareza da separação entre agentes.
- Qualidade do scraping.
- Rastreabilidade das evidências.
- Qualidade da classificação AI-native.
- Precisão do RAG.
- Uso adequado do banco vetorial.
- Capacidade de explicar as decisões técnicas.
- Qualidade das recomendações.
- Utilidade do briefing final.
- Diferencial competitivo.
- Evolução constante no repositório.

Métricas implementadas por análise:

- Cobertura de evidências: quantidade de páginas públicas rastreáveis e percentual frente à meta de 3 fontes.
- Groundedness das recomendações: percentual de recomendações com fonte NVIDIA e evidências da startup.
- Taxa de recomendações acionáveis: percentual de recomendações com próxima ação estruturada.
- Latência estimada da pipeline: soma das durações registradas no `pipeline_trace`.
- Checks bloqueados: quantidade de claims ou recomendações marcadas como insuficientes.

Avaliação RAG implementada:

- `scripts/rag_eval_cases.py`: 15 perguntas fixas cobrindo Inception, NIM, NeMo, Guardrails, Triton, TensorRT-LLM, RAPIDS, Riva, AI Enterprise e outras tecnologias.
- `scripts/evaluate_rag.py`: executa as perguntas contra `/rag/search`, valida presença de tecnologia esperada no top-N e verifica links de fonte.
- `python scripts/validate_mvp.py --with-rag-eval`: opção para rodar a avaliação junto da validação quando a API e a base NVIDIA estiverem no ar.

Métricas recomendadas para evolução da avaliação RAG:

| Métrica | O que mede | Critério esperado no MVP |
|---|---|---|
| Recall@K | Se a tecnologia esperada aparece entre os K primeiros resultados | Tecnologia esperada presente no top 5 |
| MRR | Quão cedo o resultado correto aparece no ranking | Resultado correto preferencialmente no top 3 |
| Citation Coverage | Percentual de respostas com URL ou metadado de fonte | Todas as recomendações aceitas devem ter fonte NVIDIA |
| Source Relevance | Se o trecho recuperado realmente sustenta a recomendação | Trecho deve mencionar tecnologia, caso de uso ou capacidade técnica relacionada |
| Groundedness | Se a resposta final usa apenas informações sustentadas por evidências | Claims sem fonte devem ser rebaixados ou bloqueados |
| Regression Rate | Quantidade de perguntas fixas que pioraram desde a última execução | Regressões devem ser revisadas antes de demo ou entrega |

Casos de falha que devem ser registrados:

- Recuperação de tecnologia correta, mas com trecho genérico demais.
- Recuperação de tecnologia relacionada, mas não ideal para o gap da startup.
- Citação presente, mas sem conexão clara com a recomendação.
- Resultado bom semanticamente, mas sem URL rastreável.
- Pergunta sem resposta confiável, exigindo `insufficient_evidence` em vez de geração especulativa.

---

# 23. Riscos e mitigação

## Risco 1 — Fontes públicas incompletas

Mitigação:

- Usar múltiplas fontes.
- Marcar incertezas.
- Criar categoria `insufficient_evidence`.

## Risco 2 — Alucinação do LLM

Mitigação:

- Evidence Validator Agent.
- Claims sempre ligados a fontes.
- Saída com nível de confiança.

## Risco 3 — RAG retornar contexto irrelevante

Mitigação:

- Busca híbrida.
- Reranking.
- Filtros por categoria.
- Avaliação manual de exemplos.

## Risco 4 — Scraping quebrar

Mitigação:

- Separar scraping por fonte.
- Usar fallback com BeautifulSoup/trafilatura.
- Registrar erro sem parar toda a pipeline.

## Risco 5 — Base NVIDIA desatualizada

Mitigação:

- NVIDIA Knowledge Freshness Agent.
- Registro de versões.
- Checagem por data e hash de conteúdo.
- Atualização automática ou revisão manual.

---

# 24. Como defender tecnicamente o projeto

Frase principal:

> O projeto é uma plataforma multiagente de inteligência para prospecção técnica de startups AI-native. Ela coleta dados públicos, estrutura evidências, classifica a maturidade de IA da empresa, consulta uma base RAG sobre tecnologias NVIDIA, verifica se a base técnica está atualizada e gera recomendações personalizadas com justificativa técnica, justificativa de negócio e fontes.

## Por que LangGraph?

Porque o fluxo não é linear. Existem etapas condicionais, retries, validação de evidências, checagem de atualização da base NVIDIA e decisões que dependem do estado da análise.

## Por que Qdrant?

Porque o projeto precisa armazenar e recuperar conhecimento não estruturado de forma semântica. Os textos sobre startups e documentos NVIDIA não são apenas registros tabulares; eles precisam ser buscados por significado.

## Por que PostgreSQL?

Porque o sistema também precisa de dados estruturados, relacionamentos, histórico de execução, fontes, evidências, recomendações e logs.

## Por que RAG com reranking?

Porque a recomendação precisa ser fundamentada em documentos técnicos. O reranking melhora a precisão dos trechos recuperados antes de gerar a resposta final.

## Por que checar atualização da base NVIDIA?

Porque uma recomendação técnica baseada em documentação antiga pode ser incorreta ou perder oportunidades recentes. A checagem de atualização aumenta a confiabilidade do RAG.

---

# 25. Estado inicial do desenvolvimento local

## Qdrant via Docker

Arquivo `docker-compose.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: nvidia_radar_qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```

## Collections reais

```txt
nvidia_knowledge_base
startup_evidence
```

## Scripts iniciais

```txt
scripts/check_qdrant.py
scripts/create_collections.py
scripts/test_qdrant_insert.py
scripts/test_qdrant_search.py
```

---

# 26. Próximas tarefas técnicas

1. Calibrar extração estruturada com amostras reais de startups brasileiras.
2. Rodar avaliações recorrentes das fontes públicas e ajustar thresholds.
3. Ampliar fontes com bases comerciais ou internas quando disponíveis.
4. Criar scheduler para freshness e descoberta de startups fora da requisição.
5. Evoluir estratégia de deploy com observabilidade completa, auth de usuário na interface e gestão de segredos.
6. Garantir que o ambiente de demo tenha `langgraph` instalado quando a avaliação exigir execução nominal pela biblioteca.
7. Refatorar os módulos maiores (`main.py`, `storage.py`, `analysis_graph.py`, `app.js` e `styles.css`) em rotas, serviços e componentes menores.

## 26.1 Plano de refatoração recomendado

A refatoração não é necessária para provar o MVP, mas melhora manutenção, testes e leitura em uma avaliação técnica.

| Módulo atual | Problema provável | Separação recomendada |
|---|---|---|
| `apps/api/app/main.py` | Concentra bootstrap, rotas e configuração da API | Separar routers por domínio: análise, startups, RAG, briefings e health |
| `apps/api/app/storage.py` | Tende a acumular persistência de múltiplas entidades | Separar repositórios ou serviços para startups, evidências, recomendações e execuções |
| `apps/api/app/analysis_graph.py` | Mistura orquestração, nós e regras de transição | Separar estado, nós, montagem do grafo e fallback sequencial |
| `apps/api/app/static/app.js` | Cresce com múltiplas telas e estados de UI | Separar componentes ou módulos por aba: radar, detalhe, RAG, histórico e demo |
| `apps/api/app/static/styles.css` | Pode virar arquivo único difícil de manter | Organizar por tokens, layout, componentes e estados |

Critérios de aceite da refatoração:

- Nenhuma mudança funcional visível sem teste ou validação manual equivalente.
- Rotas e payloads públicos preservados.
- Testes existentes passando após cada etapa pequena.
- Redução de responsabilidade por arquivo, sem criar abstrações artificiais.

---

# 27. Conclusão

O Seraphim Scout é defendido como uma plataforma técnica de inteligência, não apenas como um chatbot. O valor do projeto está na combinação entre coleta de dados públicos, estruturação de evidências, classificação AI-native, RAG técnico sobre NVIDIA, recomendação personalizada e atualização automática da base de conhecimento.

O diferencial principal é a capacidade de gerar recomendações explicáveis e rastreáveis para apoiar a NVIDIA na identificação e nutrição de startups brasileiras com maior potencial de adoção de sua stack de IA.

---

# 28. Diferenciais estratégicos recomendados

Como muitos projetos tendem a entregar os mesmos blocos principais do case, como scraping, agentes, RAG, dashboard e briefing, o Seraphim Scout deve ser defendido por uma camada acima: qualidade de decisão e utilidade real para prospecção técnica.

Esses diferenciais devem responder a três perguntas:

- **Por que abordar essa startup?**
- **Por que agora?**
- **Qual conversa técnica a NVIDIA deveria iniciar?**

## 28.1 Diferenciais implementados no MVP

1. **Playbook de abordagem NVIDIA**

   Cada briefing deve indicar timing de abordagem, hipótese de valor, risco competitivo e pergunta de descoberta. Isso transforma a análise em uma ação clara para Inception, DevRel, parcerias ou time comercial.

   Status no repositório: implementado no briefing e exibido na interface de análise manual/detalhe.

2. **Wrapper Displacement Map**

   O sistema deve explicar se a startup corre risco de ser substituída por features nativas dos grandes labs de IA. Quando o risco for alto, a narrativa NVIDIA deve focar independência de APIs externas, custo, latência, controle, governança e operação em produção.

   Status no repositório: implementado na interface como bloco visual com sinais de risco e caminho NVIDIA.

3. **Evidence Quality Gate**

   Recomendações técnicas devem ser bloqueadas ou rebaixadas quando não houver lastro suficiente em fonte pública da startup, fonte NVIDIA recuperada, score mínimo de recuperação e trecho técnico robusto. Esse gate diferencia o projeto de demos que apenas geram texto convincente.

   Status no repositório: implementado no Evidence Validator e exibido na interface como recomendação aceita, rebaixada ou bloqueada.

4. **Opportunity Timing Score**

   Além do NVIDIA Fit Score, o sistema deve indicar se a oportunidade está `quente`, `morna` ou `exploratória`. Essa leitura ajuda a priorizar quais startups abordar agora e quais precisam de mais evidências.

   Status no repositório: implementado no Radar como `quente`, `morno` ou `exploratorio`.

5. **Demo Mode**

   A interface deve permitir demonstrar rapidamente comportamentos distintos do sistema: uma startup forte, uma startup com risco wrapper e uma empresa com evidências fracas.

   Status no repositório: implementado como aba da interface, com execução dos três cenários em sequência e resumo comparativo.

## 28.2 Diferenciais planejados após o MVP

6. **NVIDIA Adoption Path**

   As recomendações devem evoluir de produtos isolados para trilhas de adoção: diagnóstico, piloto pequeno, métrica de sucesso, escala e encaminhamento para NVIDIA Inception.

7. **Similar Startup Memory**

   A cada nova análise, o sistema pode comparar a startup com outras já vistas, mostrando startups parecidas, scores relativos, tecnologias recorrentes e padrões de gap por setor.

## 28.3 Como defender esses diferenciais

O argumento principal é que o sistema não apenas encontra startups: ele qualifica a oportunidade, mede risco de commoditização por wrappers, bloqueia recomendações sem evidência e transforma a análise em uma próxima ação técnica para NVIDIA.

Documento complementar: `docs/DIFERENCIAIS_ESTRATEGICOS.md`.
