"""Fontes oficiais planejadas para NVIDIA Knowledge V2."""

from apps.api.src.modules.nvidia_knowledge.domain.entities import (
    NvidiaKnowledgeSource,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaKnowledgeSourceType,
)


INITIAL_NVIDIA_KNOWLEDGE_SOURCES: tuple[NvidiaKnowledgeSource, ...] = (
    NvidiaKnowledgeSource(
        slug="nvidia-inception-startups",
        title="NVIDIA Inception Program for Startups",
        url="https://www.nvidia.com/en-us/startups/",
        source_type=NvidiaKnowledgeSourceType.PRODUCT_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="nvidia-inception",
        description=(
            "Programa NVIDIA para startups, beneficios, elegibilidade, portal, "
            "credits, treinamento tecnico e relacao com VCs."
        ),
        tags=("startup", "inception", "benefits", "credits", "vc", "training"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-nim-docs",
        title="NVIDIA NIM Documentation",
        url="https://docs.nvidia.com/nim/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="nvidia-nim",
        description=(
            "Documentacao de NIM microservices para deploy de foundation models, "
            "LLMs, embeddings, reranking, speech, vision e blueprints."
        ),
        tags=("nim", "microservices", "inference", "deployment", "llm"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-nemo-framework-docs",
        title="NVIDIA NeMo Framework User Guide",
        url="https://docs.nvidia.com/nemo-framework/user-guide/latest/overview.html",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="nvidia-nemo",
        description=(
            "Framework generativo para criar, customizar e implantar modelos "
            "LLM, multimodais e speech."
        ),
        tags=("nemo", "training", "customization", "llm", "speech"),
    ),
    NvidiaKnowledgeSource(
        slug="nemo-guardrails-github",
        title="NVIDIA NeMo Guardrails Repository",
        url="https://github.com/NVIDIA/NeMo-Guardrails",
        source_type=NvidiaKnowledgeSourceType.GITHUB_REPOSITORY,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="nemo-guardrails",
        description=(
            "Repositorio oficial do toolkit para adicionar guardrails "
            "programaveis a assistentes e agentes baseados em LLM."
        ),
        tags=("guardrails", "safety", "agents", "llm", "governance"),
    ),
    NvidiaKnowledgeSource(
        slug="triton-inference-server-docs",
        title="NVIDIA Triton Inference Server Documentation",
        url="https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="triton-inference-server",
        description=(
            "Documentacao de serving multi-framework com batching, ensembles, "
            "metricas, Kubernetes, HTTP/gRPC e model repository."
        ),
        tags=("triton", "model serving", "batching", "kubernetes", "inference"),
    ),
    NvidiaKnowledgeSource(
        slug="tensorrt-llm-docs",
        title="TensorRT-LLM Documentation",
        url="https://nvidia.github.io/TensorRT-LLM/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="tensorrt-llm",
        description=(
            "Documentacao para otimizar e executar inferencia de LLMs com foco "
            "em throughput, latencia e eficiencia em GPUs NVIDIA."
        ),
        tags=("tensorrt-llm", "llm", "optimization", "latency", "throughput"),
    ),
    NvidiaKnowledgeSource(
        slug="tensorrt-docs",
        title="NVIDIA TensorRT Documentation",
        url="https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="tensorrt",
        description=(
            "Documentacao do SDK TensorRT para otimizar inferencia de deep "
            "learning em modelos PyTorch, TensorFlow e ONNX."
        ),
        tags=("tensorrt", "optimization", "inference", "onnx", "latency"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-ai-enterprise-product",
        title="NVIDIA AI Enterprise",
        url="https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
        source_type=NvidiaKnowledgeSourceType.PRODUCT_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P0,
        technology_slug="nvidia-ai-enterprise",
        description=(
            "Suite empresarial de software para desenvolver, implantar e operar "
            "IA em producao com suporte, governanca e NIM."
        ),
        tags=("ai enterprise", "production", "governance", "support", "nim"),
    ),
    NvidiaKnowledgeSource(
        slug="rapids-docs",
        title="RAPIDS Documentation",
        url="https://docs.rapids.ai/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="rapids",
        description=(
            "Documentacao central do ecossistema RAPIDS para data science, "
            "analytics, APIs, instalacao e deployment."
        ),
        tags=("rapids", "data science", "analytics", "gpu", "dataframe"),
    ),
    NvidiaKnowledgeSource(
        slug="cudf-docs",
        title="cuDF Documentation",
        url="https://docs.rapids.ai/api/cudf/stable/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="cudf",
        description=(
            "API de dataframes acelerados por GPU, compativel com workloads "
            "pandas e ETL em grandes volumes."
        ),
        tags=("cudf", "dataframe", "pandas", "etl", "gpu"),
    ),
    NvidiaKnowledgeSource(
        slug="cuml-docs",
        title="cuML Documentation",
        url="https://docs.rapids.ai/api/cuml/stable/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="cuml",
        description=(
            "API de machine learning acelerado por GPU com interface proxima "
            "do scikit-learn."
        ),
        tags=("cuml", "machine learning", "scikit-learn", "gpu", "rapids"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-riva-developer",
        title="NVIDIA Riva for Developers",
        url="https://developer.nvidia.com/riva",
        source_type=NvidiaKnowledgeSourceType.DEVELOPER_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="riva",
        description=(
            "Speech AI para ASR, TTS e traducao neural em pipelines de voz "
            "multilingues e tempo real."
        ),
        tags=("riva", "speech", "asr", "tts", "translation", "voice"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-isaac-developer",
        title="NVIDIA Isaac Developer Platform",
        url="https://developer.nvidia.com/isaac",
        source_type=NvidiaKnowledgeSourceType.DEVELOPER_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="nvidia-isaac",
        description=(
            "Plataforma de robotica com simulacao, robot learning, CUDA "
            "libraries, Isaac ROS, Isaac Sim e Isaac Lab."
        ),
        tags=("isaac", "robotics", "simulation", "ros", "perception", "jetson"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-omniverse-product",
        title="NVIDIA Omniverse",
        url="https://www.nvidia.com/en-us/omniverse/",
        source_type=NvidiaKnowledgeSourceType.PRODUCT_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="nvidia-omniverse",
        description=(
            "Plataforma para desenvolver aplicacoes de physical AI, simulacao, "
            "OpenUSD e digital twins."
        ),
        tags=("omniverse", "simulation", "digital twin", "openusd", "physical ai"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-clara-product",
        title="NVIDIA Clara",
        url="https://www.nvidia.com/en-us/clara/",
        source_type=NvidiaKnowledgeSourceType.PRODUCT_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="nvidia-clara",
        description=(
            "Plataforma NVIDIA para healthcare e life sciences, incluindo "
            "imagem medica, genomica e descoberta de farmacos."
        ),
        tags=("clara", "healthcare", "life sciences", "medical imaging", "genomics"),
    ),
    NvidiaKnowledgeSource(
        slug="monai-docs",
        title="MONAI Documentation",
        url="https://docs.monai.io/",
        source_type=NvidiaKnowledgeSourceType.OFFICIAL_DOCS,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="monai",
        description=(
            "Documentacao MONAI para workflows de IA medica, treinamento, "
            "inferencia e deploy em healthcare."
        ),
        tags=("monai", "healthcare", "medical imaging", "segmentation"),
    ),
    NvidiaKnowledgeSource(
        slug="nvidia-morpheus-developer",
        title="NVIDIA Morpheus Cybersecurity",
        url="https://developer.nvidia.com/morpheus-cybersecurity",
        source_type=NvidiaKnowledgeSourceType.DEVELOPER_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P1,
        technology_slug="nvidia-morpheus",
        description=(
            "Framework de IA acelerada para deteccao de ameacas, anomalias, "
            "logs e resposta a incidentes."
        ),
        tags=("morpheus", "cybersecurity", "anomaly detection", "logs", "security"),
    ),
    NvidiaKnowledgeSource(
        slug="cuda-toolkit-developer",
        title="NVIDIA CUDA Toolkit",
        url="https://developer.nvidia.com/cuda-toolkit",
        source_type=NvidiaKnowledgeSourceType.DEVELOPER_PAGE,
        priority=NvidiaKnowledgeSourcePriority.P2,
        technology_slug="cuda",
        description=(
            "Toolkit para desenvolver, otimizar e implantar aplicacoes "
            "GPU-accelerated com bibliotecas, compilador, runtime e ferramentas."
        ),
        tags=("cuda", "accelerated computing", "gpu", "compiler", "libraries"),
    ),
    NvidiaKnowledgeSource(
        slug="sequoia-ai-services",
        title="Sequoia - AI Services: The New Software",
        url="https://sequoiacap.com/article/services-the-new-software/",
        source_type=NvidiaKnowledgeSourceType.STRATEGIC_CONTEXT,
        priority=NvidiaKnowledgeSourcePriority.P2,
        technology_slug=None,
        description=(
            "Contexto estrategico sobre AI-native services usado pelo case para "
            "avaliar posicionamento e maturidade de startups."
        ),
        tags=("ai-native services", "strategy", "startup", "services"),
    ),
    NvidiaKnowledgeSource(
        slug="emergence-ai-native-services-playbook",
        title="Emergence Capital - AI-Native Services Playbook",
        url="https://www.emcap.com/thoughts/the-ai-native-services-playbook",
        source_type=NvidiaKnowledgeSourceType.STRATEGIC_CONTEXT,
        priority=NvidiaKnowledgeSourcePriority.P2,
        technology_slug=None,
        description=(
            "Material de contexto do case para diferenciar AI-native services "
            "de wrappers simples de LLM."
        ),
        tags=("ai-native services", "playbook", "strategy", "startup"),
    ),
)
