# TensorRT-LLM

TensorRT-LLM é uma biblioteca open-source da NVIDIA para otimizar e executar inferência de
grandes modelos de linguagem em GPUs NVIDIA com máxima eficiência. Compila o modelo em
engines TensorRT otimizadas para a arquitetura de GPU de destino.

## Capacidades
- **Kernels otimizados**: atenção fundida (FlashAttention), paged KV cache e kernels
  dedicados que aumentam tokens/s e reduzem latência.
- **Quantização**: FP8, INT8, INT4/AWQ para encolher o modelo e acelerar a inferência com
  perda mínima de qualidade — menos memória e menor custo por token.
- **In-flight (continuous) batching**: mantém a GPU saturada com requisições chegando em
  fluxo, elevando o throughput agregado.
- **Paralelismo**: tensor/pipeline parallelism para servir modelos grandes em múltiplas GPUs.

## Quando recomendar
Indicado para startups com volume de inferência relevante e gargalo de **latência/custo**:
ao otimizar o lado self-hosted com TensorRT-LLM (servido por Triton/NIM), o ROI vs. API
externa fica concreto (throughput maior, p95 menor, custo por 1M tokens menor). Ataca o gap
de **Technical Optimization** e alimenta o GPU Graduation Engine do TAPI.
