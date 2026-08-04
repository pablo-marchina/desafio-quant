# NVIDIA Triton Inference Server

NVIDIA Triton Inference Server é um servidor de inferência open-source para servir modelos
de IA em produção em escala, em GPU ou CPU. Padroniza o deployment de modelos de qualquer
framework (TensorRT, PyTorch, ONNX, TensorFlow, Python, vLLM) atrás de uma interface comum.

## Capacidades
- **Batching dinâmico**: agrupa requisições em tempo real para maximizar throughput sem
  estourar a latência — ganho direto de tokens/s e de utilização da GPU.
- **Execução concorrente de modelos**: várias instâncias/modelos na mesma GPU, melhorando
  custo por inferência.
- **Model ensembles e pipelines**: encadeia pré/pós-processamento e múltiplos modelos no
  servidor, simplificando a aplicação.
- **Métricas e observabilidade**: expõe latência (p50/p95), filas e uso de GPU (Prometheus).

## Quando recomendar
Indicado quando a startup serve modelos próprios e sofre com **latência de inferência**,
baixa utilização de GPU ou custo de serving. Combinado a TensorRT-LLM e batching, ataca o gap
de **Technical Optimization**. É o motor por baixo dos NIMs e o serving dos modelos no
GPU Graduation Engine do TAPI.
