# NVIDIA CUDA Toolkit

O CUDA Toolkit é a base da computação acelerada por GPU da NVIDIA: o modelo de programação,
o compilador (nvcc), as bibliotecas e as ferramentas que permitem que aplicações usem a GPU
para computação de propósito geral. Toda a stack de IA/dados da NVIDIA (cuDNN, TensorRT,
Triton, RAPIDS, NeMo) é construída sobre CUDA.

## Componentes
- **Bibliotecas otimizadas**: cuBLAS, cuFFT, cuSPARSE, cuDNN — primitivas de álgebra linear,
  FFT e deep learning altamente otimizadas.
- **Ferramentas de desenvolvimento**: compilador nvcc, profilers (Nsight Systems/Compute) e
  o CUDA runtime.
- **Modelo de programação**: kernels paralelos, gerência de memória de GPU e streams.

## Quando recomendar
CUDA raramente é uma recomendação isolada — é a fundação implícita de qualquer execução em
GPU. Aparece quando a startup tem código numérico/custom que poderia ser acelerado em GPU, ou
como contexto técnico das demais recomendações (NIM, TensorRT-LLM, Triton, RAPIDS todos
dependem dele). É a base de toda execução em GPU no próprio TAPI.
