# NVIDIA API Catalog (build.nvidia.com)

O NVIDIA API Catalog, em build.nvidia.com, é o ponto de entrada para experimentar e
prototipar com modelos NVIDIA e da comunidade via API hospedada, sem precisar provisionar
GPU. Cada modelo é servido como um NIM gerenciado, com endpoints compatíveis com OpenAI.

## Capacidades
- **Prototipagem imediata**: chave de API e créditos gratuitos para testar LLMs (Nemotron),
  embeddings e reranking (NeMo Retriever), visão e fala, antes de qualquer infraestrutura.
- **Mesma interface do self-hosted**: o que roda como API hospedada aqui usa a mesma
  assinatura de um NIM rodando na GPU local — a migração para self-hosted vira troca de
  base_url, não reescrita de código.
- **Caminho de graduação**: começar via API gerenciada e graduar para NIM otimizado on-prem
  conforme escala e custo exigem — a jornada que o TAPI diagnostica e prescreve.

## Quando recomendar
É o primeiro passo para qualquer startup começar com a stack NVIDIA sem capital inicial em
hardware. Serve de ponte: valida o caso na API hospedada e depois migra para NIM/TensorRT-LLM
self-hosted quando o volume justificar o ROI. O próprio TAPI consome este catálogo no build.
