# NVIDIA NIM (NVIDIA Inference Microservices)

NVIDIA NIM é um conjunto de microsserviços de inferência empacotados como contêineres
prontos para produção. Cada NIM expõe um modelo (LLM, embedding, reranking, visão, fala)
atrás de uma API padrão compatível com OpenAI, com o motor de inferência já otimizado
(TensorRT-LLM / Triton por baixo) para a GPU de destino.

## Capacidades
- **Deploy em qualquer lugar**: o mesmo contêiner roda em nuvem, data center ou estação
  local com GPU NVIDIA — base concreta da "graduação" de API gerenciada para self-hosted.
- **Performance otimizada**: throughput (tokens/s) e latência (p50/p95) melhores que servir
  o modelo cru, por usar TensorRT-LLM, batching dinâmico e kernels otimizados.
- **API estável**: endpoints compatíveis com OpenAI reduzem o custo de migração; o código
  da aplicação quase não muda ao trocar de API hospedada para NIM self-hosted.
- **Catálogo amplo**: modelos NVIDIA (Nemotron, NeMo Retriever) e da comunidade.

## Quando recomendar
Indicado quando a startup depende só de APIs externas de inferência e sofre com custo por
token, latência ou falta de controle/privacidade. Migrar a inferência para NIM self-hosted
reduz custo por 1M tokens e dá previsibilidade — gap típico de **Technical Optimization**
baixo no AIMI. Disponível tanto hospedado (build.nvidia.com) quanto self-hosted na GPU.
