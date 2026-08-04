# NVIDIA Knowledge V1 - Catalogo Inicial

Esta entrega cria o primeiro catalogo estruturado de tecnologias NVIDIA para
alimentar Recommendations V1.

## 1. Objetivo

```txt
tecnologias NVIDIA -> categoria/casos de uso/fonte -> consulta por recommendations
```

## 2. Decisao Arquitetural

V1 usa catalogo estatico versionado em codigo:

```txt
apps/api/src/modules/nvidia_knowledge/infrastructure/static_catalog/catalog_data.py
```

Nao ha tabela nem ingestion automatica nesta versao. Isso e intencional:
Recommendations V1 precisa de um catalogo confiavel agora, enquanto ingestao de
documentacao oficial, chunking e embeddings entram em NVIDIA Knowledge V2.

## 3. Componentes

```txt
apps/api/src/modules/nvidia_knowledge
  domain/entities.py
  domain/enums.py
  domain/repositories.py
  application/public/technology_catalog.py
  application/use_cases/list_nvidia_technologies.py
  infrastructure/static_catalog/catalog_data.py
  infrastructure/static_catalog/static_repository.py
  presentation/routes.py
  presentation/schemas.py
```

Contrato publico:

```txt
NvidiaTechnologyCatalog.list_technologies(...)
NvidiaTechnologyCatalog.get_technology(slug)
```

## 4. API

```txt
GET /nvidia-knowledge/technologies
GET /nvidia-knowledge/technologies?category=model_serving
GET /nvidia-knowledge/technologies?query=llm
GET /nvidia-knowledge/technologies/{slug}
```

## 5. Catalogo Atual

```txt
NVIDIA Inception
NVIDIA NIM
NVIDIA NeMo
NeMo Guardrails
NVIDIA Triton Inference Server
TensorRT-LLM
NVIDIA TensorRT
RAPIDS
cuDF
cuML
NVIDIA Riva
NVIDIA CUDA
NVIDIA AI Enterprise
MONAI
NVIDIA Clara
NVIDIA Omniverse
NVIDIA Isaac
NVIDIA Morpheus
```

O catalogo cobre os itens do brief original e inclui entradas extras
relacionadas quando elas ajudam o motor de recomendacao.

## 6. Limites da V1

```txt
sem banco relacional
sem ingestion de documentacao oficial
sem embeddings especificos de conhecimento NVIDIA
sem ranking de fit por startup
sem recomendacao automatica
```

## 7. Validacao

```txt
test_nvidia_knowledge_catalog.py
5 testes unitarios do modulo passando
```

## 8. Proximo Passo

```txt
NVIDIA Knowledge V2 - ingestao de documentacao oficial NVIDIA
```
