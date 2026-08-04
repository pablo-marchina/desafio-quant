# Playlist de tecnologias NVIDIA (vídeos, §10.1)

Snapshot curado do conteúdo da playlist oficial de tecnologias NVIDIA. É um resumo fiel dos
pontos cobertos pelos vídeos, citável pela URL canônica; a transcrição literal via Riva ASR é
hook de rede (F3.1b). Serve de visão geral da stack que o TAPI recomenda.

## Stack apresentada
- **Inferência em produção**: NVIDIA NIM empacota modelos como microsserviços com API
  compatível, servidos por Triton Inference Server e otimizados com TensorRT-LLM para baixa
  latência e custo controlado em GPU.
- **IA generativa de ponta a ponta**: a plataforma NeMo cobre o ciclo de LLMs — incluindo
  NeMo Retriever (embeddings + reranking para RAG), NeMo Guardrails (trilhos de segurança) e
  NeMo Evaluator (avaliação) — para construir aplicações de IA confiáveis.
- **Data science acelerada**: RAPIDS (cuDF, cuML) move ETL e machine learning clássico para a
  GPU, mantendo APIs familiares (pandas/scikit-learn) com ganho de desempenho.
- **Domínios especializados**: Riva (IA de fala — ASR/TTS), além de plataformas de saúde,
  robótica e simulação, mostrando a amplitude do catálogo NVIDIA.
- **Base comum**: CUDA e NVIDIA AI Enterprise sustentam a execução acelerada e o suporte de
  produção em nuvem, data center e edge.

## Por que está na KB
Dá ao RAG uma fonte de visão geral que conecta as tecnologias entre si (como NIM, NeMo e
RAPIDS se encaixam), útil quando a recomendação precisa contextualizar a stack para a startup.
