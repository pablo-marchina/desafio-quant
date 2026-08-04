"""Dados iniciais do catalogo NVIDIA Knowledge V1."""

from apps.api.src.modules.nvidia_knowledge.domain.entities import NvidiaTechnology
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaTechnologyCategory,
)


INITIAL_NVIDIA_TECHNOLOGIES: tuple[NvidiaTechnology, ...] = (
    NvidiaTechnology(
        slug="nvidia-nim",
        name="NVIDIA NIM",
        category=NvidiaTechnologyCategory.MODEL_SERVING,
        description=(
            "Microservicos para acelerar o deploy de foundation models e "
            "modelos generativos em cloud, data center ou workstation."
        ),
        use_cases=(
            "servir LLMs e modelos generativos em producao",
            "expor APIs de inferencia padronizadas",
            "reduzir tempo de deploy de modelos",
        ),
        keywords=(
            "llm",
            "generative ai",
            "inference",
            "api",
            "deployment",
            "microservice",
        ),
        official_url="https://docs.nvidia.com/nim/",
        complexity="low",
        supported_workloads={
            "nlp": 0.80,
            "speech": 0.50,
            "recommendation": 0.40,
            "analytics": 0.40,
            "vision": 0.30,
            "mlops": 0.50,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-nemo",
        name="NVIDIA NeMo",
        category=NvidiaTechnologyCategory.MODEL_TRAINING,
        description=(
            "Framework e suite modular para criar, customizar e otimizar "
            "modelos de IA generativa, speech e agentes."
        ),
        use_cases=(
            "fine-tuning de modelos generativos",
            "treinamento e customizacao de modelos de linguagem",
            "ciclo de vida de agentes e modelos corporativos",
        ),
        keywords=(
            "training",
            "fine tuning",
            "llm",
            "agent",
            "generative ai",
            "speech",
        ),
        official_url=(
            "https://docs.nvidia.com/nemo-framework/user-guide/latest/overview.html"
        ),
        complexity="high",
        supported_workloads={
            "nlp": 0.90,
            "speech": 0.70,
            "mlops": 0.50,
            "vision": 0.20,
        },
    ),
    NvidiaTechnology(
        slug="triton-inference-server",
        name="NVIDIA Triton Inference Server",
        category=NvidiaTechnologyCategory.MODEL_SERVING,
        description=(
            "Servidor de inferencia para publicar modelos de diferentes "
            "frameworks com batching, multiplos backends e observabilidade."
        ),
        use_cases=(
            "serving multi-modelo em producao",
            "inferencias com baixa latencia e alto throughput",
            "padronizar deploy de modelos em Kubernetes ou data center",
        ),
        keywords=(
            "model serving",
            "kubernetes",
            "inference",
            "batching",
            "pytorch",
            "onnx",
        ),
        official_url=(
            "https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/"
        ),
        complexity="medium",
        supported_workloads={
            "mlops": 0.70,
            "vision": 0.60,
            "nlp": 0.55,
            "analytics": 0.50,
            "speech": 0.50,
            "recommendation": 0.45,
        },
    ),
    NvidiaTechnology(
        slug="tensorrt-llm",
        name="TensorRT-LLM",
        category=NvidiaTechnologyCategory.MODEL_OPTIMIZATION,
        description=(
            "Toolkit para otimizar e executar inferencia de LLMs em GPUs "
            "NVIDIA com foco em throughput e eficiencia."
        ),
        use_cases=(
            "otimizar inferencia de LLMs",
            "reduzir custo por token em producao",
            "servir modelos generativos com alta eficiencia",
        ),
        keywords=(
            "llm",
            "optimization",
            "inference",
            "throughput",
            "token",
            "quantization",
        ),
        official_url="https://nvidia.github.io/TensorRT-LLM/",
        complexity="high",
        supported_workloads={
            "nlp": 0.95,
            "speech": 0.30,
            "vision": 0.20,
        },
    ),
    NvidiaTechnology(
        slug="tensorrt",
        name="NVIDIA TensorRT",
        category=NvidiaTechnologyCategory.MODEL_OPTIMIZATION,
        description=(
            "SDK para otimizar e acelerar inferencia de deep learning em GPUs "
            "NVIDIA, com suporte a precisao mista e formas dinamicas."
        ),
        use_cases=(
            "otimizar modelos PyTorch, TensorFlow ou ONNX",
            "reduzir latencia de inferencia",
            "acelerar workloads de visao computacional e transformers",
        ),
        keywords=(
            "onnx",
            "pytorch",
            "tensorflow",
            "optimization",
            "latency",
            "inference",
        ),
        official_url=(
            "https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html"
        ),
        complexity="high",
        supported_workloads={
            "vision": 0.70,
            "mlops": 0.60,
            "nlp": 0.50,
            "analytics": 0.40,
            "speech": 0.30,
        },
    ),
    NvidiaTechnology(
        slug="rapids",
        name="RAPIDS",
        category=NvidiaTechnologyCategory.DATA_SCIENCE,
        description=(
            "Ecossistema de bibliotecas para acelerar ciencia de dados e "
            "analytics em GPUs, incluindo dataframes e machine learning."
        ),
        use_cases=(
            "acelerar pipelines de data science",
            "processar grandes volumes de dados tabulares",
            "migrar workloads pandas/scikit-learn para GPU",
        ),
        keywords=(
            "data science",
            "analytics",
            "dataframe",
            "gpu",
            "pandas",
            "spark",
        ),
        official_url="https://docs.rapids.ai/",
        complexity="medium",
        supported_workloads={
            "analytics": 0.95,
            "recommendation": 0.75,
            "mlops": 0.60,
            "vision": 0.20,
        },
    ),
    NvidiaTechnology(
        slug="riva",
        name="NVIDIA Riva",
        category=NvidiaTechnologyCategory.SPEECH_AI,
        description=(
            "SDK para IA conversacional e speech, incluindo reconhecimento de "
            "fala, sintese de voz e traducao neural."
        ),
        use_cases=(
            "automatic speech recognition",
            "text-to-speech",
            "traducao e assistentes de voz",
        ),
        keywords=(
            "speech",
            "asr",
            "tts",
            "voice",
            "translation",
            "conversational ai",
        ),
        official_url="https://docs.nvidia.com/deeplearning/riva/user-guide/docs/index.html",
        complexity="medium",
        supported_workloads={
            "speech": 0.99,
            "nlp": 0.40,
        },
    ),
    NvidiaTechnology(
        slug="cuda",
        name="NVIDIA CUDA",
        category=NvidiaTechnologyCategory.ACCELERATED_COMPUTING,
        description=(
            "Plataforma e toolkit de computacao acelerada para desenvolver "
            "aplicacoes C/C++ e bibliotecas que usam GPUs NVIDIA."
        ),
        use_cases=(
            "acelerar computacao numerica",
            "criar kernels GPU customizados",
            "otimizar workloads cientificos e de engenharia",
        ),
        keywords=(
            "gpu",
            "accelerated computing",
            "c++",
            "kernel",
            "hpc",
            "parallel computing",
        ),
        official_url="https://docs.nvidia.com/cuda/",
        complexity="high",
        supported_workloads={
            "analytics": 0.55,
            "simulation": 0.60,
            "mlops": 0.50,
            "vision": 0.45,
            "nlp": 0.30,
            "recommendation": 0.30,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-ai-enterprise",
        name="NVIDIA AI Enterprise",
        category=NvidiaTechnologyCategory.AI_PLATFORM,
        description=(
            "Plataforma empresarial para desenvolver, implantar e operar "
            "aplicacoes de IA com suporte, frameworks, NIM e SDKs."
        ),
        use_cases=(
            "padronizar stack corporativa de IA",
            "operar IA em ambiente enterprise",
            "combinar frameworks, NIM e infraestrutura GPU",
        ),
        keywords=(
            "mlops",
            "model governance",
            "on-prem",
            "enterprise ai",
            "model management",
            "compliance",
            "production deployment",
        ),
        official_url="https://docs.nvidia.com/ai-enterprise/",
        complexity="medium",
        supported_workloads={
            "mlops": 0.80,
            "nlp": 0.55,
            "analytics": 0.55,
            "vision": 0.45,
            "speech": 0.35,
        },
    ),
    NvidiaTechnology(
        slug="monai",
        name="MONAI",
        category=NvidiaTechnologyCategory.HEALTHCARE_AI,
        description=(
            "Toolkit para workflows de IA medica, com foco em imagens, "
            "treinamento, inferencia e deploy em healthcare."
        ),
        use_cases=(
            "analise de imagens medicas",
            "segmentacao e classificacao em healthcare",
            "pipelines de IA clinica e pesquisa medica",
        ),
        keywords=(
            "healthcare",
            "medical imaging",
            "monai",
            "segmentation",
            "radiology",
            "clinical ai",
        ),
        official_url="https://docs.nvidia.com/clara/monai/",
        complexity="high",
        supported_workloads={
            "vision": 0.95,
            "analytics": 0.30,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-inception",
        name="NVIDIA Inception",
        category=NvidiaTechnologyCategory.STARTUP_PROGRAM,
        description=(
            "Programa gratuito da NVIDIA para startups, com beneficios em "
            "credits de cloud/GPU, suporte tecnico, acesso a comunidade de "
            "investidores e co-marketing para acelerar empresas que "
            "constroem produtos de IA."
        ),
        use_cases=(
            "acessar credits de cloud e GPU para startups",
            "conectar com investidores e parceiros de go-to-market",
            "obter suporte tecnico e mentoria da NVIDIA",
            "participar de comunidade de startups de IA",
        ),
        keywords=(
            "startup",
            "inception",
            "credits",
            "mentoria",
            "comunidade",
            "investidores",
            "go-to-market",
        ),
        official_url="https://www.nvidia.com/en-us/startups/",
        complexity="low",
        supported_workloads={
            "nlp": 0.40,
            "vision": 0.40,
            "analytics": 0.40,
            "speech": 0.40,
            "mlops": 0.40,
            "recommendation": 0.40,
            "simulation": 0.40,
        },
    ),
    NvidiaTechnology(
        slug="nemo-guardrails",
        name="NeMo Guardrails",
        category=NvidiaTechnologyCategory.MODEL_TRAINING,
        description=(
            "Toolkit open-source para adicionar guardrails programaveis a "
            "assistentes e agentes conversacionais baseados em LLM, "
            "controlando topicos, seguranca e comportamento."
        ),
        use_cases=(
            "controlar topicos permitidos em assistentes de IA",
            "prevenir respostas inseguras ou fora de escopo",
            "adicionar guardrails de seguranca a agentes LLM",
        ),
        keywords=(
            "guardrails",
            "safety",
            "llm",
            "agent",
            "conversational ai",
            "governance",
        ),
        official_url="https://github.com/NVIDIA/NeMo-Guardrails",
        complexity="medium",
        supported_workloads={
            "nlp": 0.90,
            "recommendation": 0.25,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-clara",
        name="NVIDIA Clara",
        category=NvidiaTechnologyCategory.HEALTHCARE_AI,
        description=(
            "Plataforma de IA para healthcare e life sciences, com "
            "ferramentas para imagem medica, genomica e descoberta de "
            "farmacos aceleradas por GPU."
        ),
        use_cases=(
            "acelerar pesquisa em genomica e descoberta de farmacos",
            "construir aplicacoes de imagem medica",
            "padronizar infraestrutura de IA para healthcare",
        ),
        keywords=(
            "healthcare",
            "life sciences",
            "genomics",
            "medical imaging",
            "clara",
            "drug discovery",
        ),
        official_url="https://www.nvidia.com/en-us/clara/",
        complexity="high",
        supported_workloads={
            "vision": 0.80,
            "analytics": 0.55,
        },
    ),
    NvidiaTechnology(
        slug="cudf",
        name="cuDF",
        category=NvidiaTechnologyCategory.DATA_SCIENCE,
        description=(
            "Biblioteca GPU-accelerated para manipulacao de dataframes com "
            "API compativel com pandas, parte do ecossistema RAPIDS."
        ),
        use_cases=(
            "acelerar processamento de dataframes em GPU",
            "migrar pipelines pandas para GPU sem reescrever logica",
            "reduzir tempo de ETL em grandes volumes tabulares",
        ),
        keywords=(
            "dataframe",
            "pandas",
            "gpu",
            "rapids",
            "etl",
            "data science",
        ),
        official_url="https://docs.rapids.ai/api/cudf/stable/",
        complexity="low",
        supported_workloads={
            "analytics": 0.95,
            "recommendation": 0.55,
            "mlops": 0.50,
        },
    ),
    NvidiaTechnology(
        slug="cuml",
        name="cuML",
        category=NvidiaTechnologyCategory.DATA_SCIENCE,
        description=(
            "Biblioteca de machine learning acelerada por GPU com API "
            "compativel com scikit-learn, parte do ecossistema RAPIDS."
        ),
        use_cases=(
            "treinar modelos de machine learning classico em GPU",
            "migrar pipelines scikit-learn para GPU",
            "acelerar clustering, regressao e classificacao em grandes datasets",
        ),
        keywords=(
            "machine learning",
            "scikit-learn",
            "gpu",
            "rapids",
            "clustering",
            "classification",
        ),
        official_url="https://docs.rapids.ai/api/cuml/stable/",
        complexity="low",
        supported_workloads={
            "analytics": 0.85,
            "recommendation": 0.70,
            "mlops": 0.70,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-omniverse",
        name="NVIDIA Omniverse",
        category=NvidiaTechnologyCategory.ROBOTICS_SIMULATION,
        description=(
            "Plataforma de simulacao e colaboracao em 3D baseada em "
            "OpenUSD, usada para construir digital twins e mundos virtuais "
            "fisicamente precisos."
        ),
        use_cases=(
            "criar digital twins de fabricas e ambientes industriais",
            "simular cenarios fisicos para treinar robos e veiculos autonomos",
            "colaborar em pipelines 3D entre ferramentas diferentes",
        ),
        keywords=(
            "simulation",
            "3d",
            "digital twin",
            "omniverse",
            "openusd",
            "virtual world",
        ),
        official_url="https://www.nvidia.com/en-us/omniverse/",
        complexity="high",
        supported_workloads={
            "simulation": 0.99,
            "vision": 0.45,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-isaac",
        name="NVIDIA Isaac",
        category=NvidiaTechnologyCategory.ROBOTICS_SIMULATION,
        description=(
            "Plataforma para desenvolvimento de robotica com simulacao, "
            "percepcao e navegacao aceleradas por GPU."
        ),
        use_cases=(
            "simular e treinar robos antes de implantar no mundo real",
            "acelerar percepcao e navegacao de robos autonomos",
            "construir pipelines de robotica com IA",
        ),
        keywords=(
            "robotics",
            "isaac",
            "simulation",
            "autonomy",
            "navigation",
            "perception",
        ),
        official_url="https://developer.nvidia.com/isaac",
        complexity="high",
        supported_workloads={
            "simulation": 0.95,
            "vision": 0.35,
        },
    ),
    NvidiaTechnology(
        slug="nvidia-morpheus",
        name="NVIDIA Morpheus",
        category=NvidiaTechnologyCategory.CYBERSECURITY,
        description=(
            "Framework de IA acelerada por GPU para deteccao de ameacas, "
            "analise de seguranca e resposta a incidentes em tempo real."
        ),
        use_cases=(
            "detectar anomalias e ameacas de seguranca em tempo real",
            "acelerar analise de logs e trafico de rede com IA",
            "automatizar resposta a incidentes de ciberseguranca",
        ),
        keywords=(
            "cybersecurity",
            "morpheus",
            "threat detection",
            "anomaly detection",
            "security",
            "incident response",
        ),
        official_url="https://developer.nvidia.com/morpheus-cybersecurity",
        complexity="high",
        # "cybersecurity"/"anomaly_detection" nao existem em AiWorkloadType
        # (startups/domain/enums.py): vocabulario real e
        # nlp/vision/recommendation/simulation/analytics/mlops/speech/unknown.
        # Vazio mantem o workload neutro (0.40, abaixo do limiar de admissao
        # 0.60) — Morpheus so entra por keyword real, nunca por falso-positivo
        # de "analytics".
        supported_workloads={},
    ),
)
