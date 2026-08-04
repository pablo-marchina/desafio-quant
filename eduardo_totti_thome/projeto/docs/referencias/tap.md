Projeto: NVIDIA Startup AI Radar

- Contextualização do problema

O mercado de inteligência artificial está passando por uma mudança estrutural. Grandes
laboratórios como OpenAI, Anthropic, Google DeepMind, Meta e outros deixaram de atuar
apenas como fornecedores de modelos fundacionais e passaram a subir na cadeia de valor.
Hoje, esses laboratórios oferecem APIs multimodais, agentes, ferramentas de
produtividade, busca, voz, código, automação de workflows, memória, integrações
corporativas e produtos finais para empresas.

Esse movimento cria uma ameaça direta para startups de IA, principalmente para aquelas
que se posicionam apenas como wrappers de LLMs. Uma startup que apenas conecta uma
API da OpenAI, Anthropic ou outro provedor a uma interface gráfica, sem dados
proprietários, sem workflow profundo, sem distribuição clara e sem otimização técnica, pode
ser rapidamente substituída por funcionalidades nativas dos grandes labs.

Ao mesmo tempo, surge uma oportunidade importante: startups podem se diferenciar ao se
tornarem AI-native services. Nesse modelo, a empresa combina software, agentes de IA,
dados proprietários, automação e serviço especializado para entregar resultados de negócio
de ponta a ponta. Em vez de vender apenas uma ferramenta SaaS, a empresa passa a
vender um resultado operacional aumentado por IA.

Nesse contexto, a NVIDIA tem uma posição estratégica. Muitas startups usam IA, mas
poucas otimizam toda a stack técnica. Em geral, founders começam usando APIs externas
pela simplicidade, mas conforme crescem passam a enfrentar problemas de custo, latência,
escalabilidade, governança, privacidade, avaliação, observabilidade e dependência de
fornecedores. A stack da NVIDIA pode ajudar essas empresas a evoluir de protótipos
baseados em APIs para sistemas de IA escaláveis, eficientes e preparados para produção.

Este projeto propõe a construção de uma plataforma multi-agente capaz de mapear startups
brasileiras com potencial AI-native, coletar informações públicas sobre elas, diagnosticar
sua maturidade técnica e recomendar tecnologias da NVIDIA adequadas ao perfil de cada
empresa. A solução deve funcionar como uma ferramenta de inteligência para apoiar o

gerente de Startups & VCs da NVIDIA no Brasil a atrair, qualificar e nutrir startups para o
programa NVIDIA Inception.

- Objetivo do projeto

Construir um sistema capaz de:

- Encontrar startups brasileiras com sinais de uso intensivo de IA.
- Coletar dados públicos sobre empresa, produto, setor, clientes, funding, founders e
tecnologias utilizadas.
- Avaliar possíveis gaps na stack de IA da empresa.
- Consultar uma base de conhecimento sobre tecnologias NVIDIA.
- Recomendar as tecnologias NVIDIA mais adequadas para a startup encontrada.
- Gerar um briefing executivo para apoiar abordagem comercial, técnica e comunitária pelo
NVIDIA Inception.

- Pergunta norteadora

Como a NVIDIA pode identificar, atrair e nutrir startups brasileiras AI-native em um contexto
no qual os grandes labs de IA estão ameaçando startups que dependem apenas de
wrappers de LLM?

- Escopo da solução

O sistema deve possuir uma pipeline multi-agente que deve buscar empresas relevantes,
coletar informações públicas, estruturar os dados encontrados, classificar a maturidade
AI-native da empresa e consultar uma base RAG com tecnologias NVIDIA para gerar
recomendações personalizadas.

O frontend fica livre para os alunos escolherem. O foco principal do projeto está na
arquitetura de IA, nos agentes, na pipeline de dados, no RAG com reranking e na qualidade
das recomendações.

- Tecnologias principais

5.1 LangGraph


LangGraph será utilizado para criar o sistema multi-agente. Diferentemente de uma cadeia
simples de prompts, o LangGraph permite modelar um fluxo de trabalho com estado, nós,
transições condicionais, checkpoints, retry, intervenção humana e controle mais robusto
sobre o comportamento dos agentes.

Agentes sugeridos:

- Search Planner Agent: transforma a consulta do usuário em termos de busca e fontes
prioritárias.
- Scraper Agent: coleta informações públicas de sites, notícias, diretórios e páginas
institucionais.
- Extractor Agent: transforma conteúdo não estruturado em dados estruturados.
- Startup Classifier Agent: classifica a empresa como AI-native, AI-enabled ou non-AI.
- Evidence Validator Agent: valida se as afirmações possuem fontes suficientes.
- NVIDIA RAG Agent: consulta a base de conhecimento de tecnologias NVIDIA.
- Recommendation Agent: cruza o perfil da startup com as tecnologias NVIDIA.
- Briefing Agent: gera o relatório final para o gerente de Startups & VCs.

5.2 Scraping e coleta de informações

A etapa de scraping será responsável por buscar informações públicas sobre empresas. O
objetivo não é copiar bases fechadas ou violar termos de uso, mas coletar informações
disponíveis publicamente com rastreabilidade das fontes.

Tecnologias recomendadas:

- Playwright: scraping de sites dinâmicos que dependem de JavaScript.
- BeautifulSoup: parsing de páginas HTML simples.
- Scrapy: crawling estruturado em maior escala.
- Firecrawl: extração de páginas web em formato limpo para RAG.
- trafilatura: extração de texto principal de páginas, blogs e notícias.
5.3 RAG com reranking

O RAG será usado para armazenar e consultar conhecimentos sobre tecnologias NVIDIA,
conceitos de AI-native services, stack de IA, NVIDIA Inception e materiais de apoio.

Pipeline recomendada:

- Ingestão de documentos: blogs, documentações, vídeos transcritos, whitepapers e
páginas oficiais.
- Limpeza e normalização do texto.
- Chunking semântico dos documentos.
- Geração de embeddings.
- Armazenamento em vector database.

- Busca híbrida: busca vetorial + busca lexical.
- Reranking dos trechos recuperados.
- Geração da resposta com citações.
- Avaliação de qualidade da resposta.

Tecnologias recomendadas:

- Qdrant, mas é permitido o uso de outros bancos como ChromaDB, Pinecone ou pgvector
como banco vetorial.
- PostgreSQL para dados estruturados de empresas.
- BM25 para busca lexical.
- Cohere Rerank para a estratégia de reranking

5.4 Base de conhecimento NVIDIA

A base de conhecimento deve conter informações sobre tecnologias NVIDIA e seus casos
de uso. O objetivo é permitir que o sistema recomende a tecnologia certa com base no
problema identificado na startup.

Tecnologias NVIDIA a incluir:

- NVIDIA Inception: programa para startups, benefícios, comunidade, credits, suporte
técnico e go-to-market.
- NVIDIA NIM: microservices para deploy de modelos de IA otimizados.
- NVIDIA NeMo: treinamento, customização, avaliação e guardrails para modelos
generativos.
- NeMo Guardrails: controle de comportamento de assistentes e agentes.
- NVIDIA Triton Inference Server: serving de modelos em produção.
- TensorRT-LLM: otimização de inferência de LLMs.
- NVIDIA RAPIDS: aceleração de pipelines de dados com GPU.
- cuDF: processamento de dataframes em GPU.
- cuML: machine learning acelerado em GPU.
- CUDA: programação paralela em GPU.
- NVIDIA Riva: ASR, TTS e modelos de voz.
- NVIDIA Omniverse: simulação, 3D e digital twins.
- NVIDIA Isaac: robotics, simulação e autonomia.
- NVIDIA Clara: healthcare e life sciences.
- NVIDIA Morpheus: cybersecurity com IA acelerada.
- NVIDIA AI Enterprise: plataforma empresarial para IA em produção.

5.5 Motor de recomendação

O motor de recomendação deve cruzar o perfil da empresa com os possíveis gaps técnicos
identificados.


Exemplos de recomendação:

- Se a startup usa LLMs em atendimento ao cliente, mas depende apenas de APIs externas:
recomendar NIM, NeMo Guardrails, Triton e benchmark de custo/latência.
- Se a startup processa grandes volumes de dados tabulares: recomendar RAPIDS, cuDF e
cuML.
- Se a startup faz voz, call center ou transcrição: recomendar NVIDIA Riva e NIM.
- Se a startup atua em saúde: considerar Clara, MONAI, NIM, NeMo Guardrails e AI
## Enterprise.
- Se a startup faz robotics ou simulação: recomendar Isaac, Omniverse e GPUs NVIDIA.
- Se a startup sofre com latência de inferência: recomendar Triton, TensorRT-LLM e
batching.
- Se a startup precisa de governança em agentes: recomendar NeMo Guardrails e avaliação
com NeMo.

O output da recomendação deve conter:

- Tecnologias NVIDIA recomendadas.
- Justificativa técnica.
- Justificativa de negócio.
- Nível de prioridade.
- Complexidade de implementação.
- Próxima ação sugerida para o time NVIDIA.
- Evidências usadas.

- Arquitetura proposta

Fluxo de alto nível:

Consulta do usuário
## -> Search Planner Agent
## -> Scraper Agent
## -> Extractor Agent
-> Banco estruturado de startups
## -> Startup Classifier Agent
## -> Evidence Validator Agent
-> Diagnóstico de maturidade AI-native
-> NVIDIA RAG Agent
## -> Reranker
## -> Recommendation Agent
## -> Briefing Agent
-> Interface web


- Fontes para scraping de empresas

7.1 Fontes principais no Brasil

- Sites oficiais das startups.
- Blogs oficiais das startups.
- Páginas de carreiras das startups.
- Perfis públicos de founders.
- StartSe: https://www.startse.com/
- Distrito: https://distrito.me/
- Latitud: https://www.latitud.com/
- Cubo Itau: https://cubo.network/
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

7.2 Fontes de notícias e sinais públicos

- Brazil Journal: https://braziljournal.com/
- NeoFeed: https://neofeed.com.br/
- Exame Startups: https://exame.com/bussola/startups/
- Startups.com.br: https://startups.com.br/
- Pequenas Empresas & Grandes Negócios: https://revistapegn.globo.com/
- Valor Econômico: https://valor.globo.com/
- Meio & Mensagem: https://www.meioemensagem.com.br/
- Mobile Time: https://www.mobiletime.com.br/


- Fontes para base de conhecimento NVIDIA

8.1 Materiais de apoio do case

Sequoia - AI services: https://sequoiacap.com/article/services-the-new-software/


Emergence Capital - AI-native services playbook:
https://www.emcap.com/thoughts/the-ai-native-services-playbook

NVIDIA AI 5-layer cake: https://blogs.nvidia.com/blog/ai-5-layer-cake/

Playlist de tecnologias NVIDIA:
https://youtube.com/playlist?list=PLBaUJRFQ-j_WJZdZfFNsgUWDWF1Ldjp_X

Comunidade startups NVIDIA: https://youtu.be/NmZDQSdUVUQ

Benefícios Inception: https://www.youtube.com/live/fWfkE6cibwQ

8.2 Documentações oficiais NVIDIA

- NVIDIA Inception: https://www.nvidia.com/en-us/startups/
- NVIDIA NIM: https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/
- NVIDIA API Catalog: https://build.nvidia.com/
- NVIDIA NeMo: https://www.nvidia.com/en-us/ai-data-science/products/nemo/
- NeMo Guardrails: https://github.com/NVIDIA/NeMo-Guardrails
- NVIDIA Triton Inference Server: https://developer.nvidia.com/triton-inference-server
- Triton docs: https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/
- TensorRT-LLM: https://github.com/NVIDIA/TensorRT-LLM
- NVIDIA RAPIDS: https://rapids.ai/
- cuDF: https://docs.rapids.ai/api/cudf/stable/
- cuML: https://docs.rapids.ai/api/cuml/stable/
- CUDA Toolkit: https://developer.nvidia.com/cuda-toolkit
- NVIDIA Riva: https://developer.nvidia.com/riva
- NVIDIA Omniverse: https://www.nvidia.com/en-us/omniverse/
- NVIDIA Isaac: https://developer.nvidia.com/isaac
- NVIDIA Clara: https://www.nvidia.com/en-us/clara/
- NVIDIA Morpheus: https://developer.nvidia.com/morpheus-cybersecurity
- NVIDIA AI Enterprise: https://www.nvidia.com/en-us/data-center/products/ai-enterprise/


- Entregáveis esperados
Não é estipulado um prazo prévio para a realização das entregas durante o processo,
porém, é esperado que dentro do repositório que o projeto for desenvolvido, exista
contribuições constantes que demonstram uma evolução do trabalho durante o mês.
Entregável 1 - Pipeline de scraping


Sistema capaz de buscar e coletar informações públicas sobre startups a partir de uma
consulta.

Entregável 2 - Sistema multiagente com LangGraph

Sistema com agentes especializados para busca, extração, classificação, validação, RAG e
recomendação.

Entregável 3 - RAG NVIDIA com reranking

Base de conhecimento contendo materiais NVIDIA e mecanismo de recuperação com
reranking e citações.

Entregável 4 - Motor de recomendação

Sistema que recomenda tecnologias NVIDIA a partir do perfil da startup.

Entregável 5 - Interface web

Dashboard ou aplicação web para consulta, visualização de empresas, recomendações e
exportação de briefing.

Entregável 6 - Diferencial do projeto.

Desenvolver algo único no seu projeto, para fins de diferenciação e destaque competitivo.


