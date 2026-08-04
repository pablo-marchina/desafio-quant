from dataclasses import dataclass


@dataclass(frozen=True)
class NvidiaTechnologyCatalogItem:
    name: str
    category: str
    description: str
    source_url: str
    keywords: tuple[str, ...]


NVIDIA_TECHNOLOGY_CATALOG: tuple[NvidiaTechnologyCatalogItem, ...] = (
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Inception",
        category="startup_program",
        description=(
            "Program for startups with community, technical resources, go-to-market support, "
            "and access to NVIDIA ecosystem benefits."
        ),
        source_url="https://www.nvidia.com/en-us/startups/",
        keywords=("startup", "program", "community", "go-to-market", "credits", "inception"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA NIM",
        category="model_serving",
        description=(
            "Optimized inference microservices for deploying generative AI models in "
            "production environments."
        ),
        source_url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
        keywords=("llm", "inference", "microservice", "deployment", "api", "production"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA NeMo",
        category="generative_ai",
        description=(
            "Framework and services for building, customizing, evaluating, and deploying "
            "generative AI models."
        ),
        source_url="https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
        keywords=("training", "customization", "evaluation", "generative ai", "llm"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NeMo Guardrails",
        category="ai_governance",
        description=(
            "Toolkit for adding safety, policy, and behavior controls to assistants and "
            "AI agents."
        ),
        source_url="https://github.com/NVIDIA/NeMo-Guardrails",
        keywords=("guardrails", "safety", "governance", "agents", "policy", "compliance"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Triton Inference Server",
        category="model_serving",
        description=(
            "Inference serving platform for deploying, scaling, and optimizing AI models "
            "across frameworks."
        ),
        source_url="https://developer.nvidia.com/triton-inference-server",
        keywords=("serving", "latency", "throughput", "batching", "model server", "production"),
    ),
    NvidiaTechnologyCatalogItem(
        name="TensorRT-LLM",
        category="inference_optimization",
        description="Library for optimizing LLM inference performance on NVIDIA GPUs.",
        source_url="https://github.com/NVIDIA/TensorRT-LLM",
        keywords=("llm", "latency", "cost", "optimization", "gpu", "inference"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA RAPIDS",
        category="data_acceleration",
        description=(
            "GPU-accelerated data science and analytics suite for large-scale data pipelines."
        ),
        source_url="https://rapids.ai/",
        keywords=("dataframe", "analytics", "gpu", "etl", "data pipeline", "machine learning"),
    ),
    NvidiaTechnologyCatalogItem(
        name="cuDF",
        category="data_acceleration",
        description="GPU DataFrame library for accelerating pandas-like data processing workloads.",
        source_url="https://docs.rapids.ai/api/cudf/stable/",
        keywords=("dataframe", "pandas", "tabular", "etl", "gpu"),
    ),
    NvidiaTechnologyCatalogItem(
        name="cuML",
        category="machine_learning",
        description="GPU-accelerated machine learning algorithms for data science workloads.",
        source_url="https://docs.rapids.ai/api/cuml/stable/",
        keywords=("machine learning", "gpu", "classification", "clustering", "regression"),
    ),
    NvidiaTechnologyCatalogItem(
        name="CUDA",
        category="gpu_programming",
        description="Parallel computing platform and programming model for NVIDIA GPUs.",
        source_url="https://developer.nvidia.com/cuda-toolkit",
        keywords=("gpu", "parallel", "acceleration", "programming", "cuda"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Riva",
        category="speech_ai",
        description="GPU-accelerated speech AI SDK for ASR, TTS, and real-time voice applications.",
        source_url="https://developer.nvidia.com/riva",
        keywords=("voice", "speech", "asr", "tts", "call center", "transcription"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Omniverse",
        category="simulation",
        description=(
            "Platform for industrial digitalization, 3D workflows, simulation, and digital twins."
        ),
        source_url="https://www.nvidia.com/en-us/omniverse/",
        keywords=("simulation", "3d", "digital twin", "industrial", "visualization"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Isaac",
        category="robotics",
        description="Robotics platform for simulation, autonomy, and robot AI development.",
        source_url="https://developer.nvidia.com/isaac",
        keywords=("robotics", "simulation", "autonomy", "robots", "isaac"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Clara",
        category="healthcare",
        description=(
            "Healthcare and life sciences platform for medical imaging, genomics, and "
            "healthcare AI."
        ),
        source_url="https://www.nvidia.com/en-us/clara/",
        keywords=("healthcare", "medical", "life sciences", "imaging", "clara"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA Morpheus",
        category="cybersecurity",
        description=(
            "AI cybersecurity framework for GPU-accelerated threat detection and "
            "security analytics."
        ),
        source_url="https://developer.nvidia.com/morpheus-cybersecurity",
        keywords=("cybersecurity", "threat", "security", "anomaly", "morpheus"),
    ),
    NvidiaTechnologyCatalogItem(
        name="NVIDIA AI Enterprise",
        category="enterprise_ai",
        description=(
            "Enterprise software platform for developing and deploying production AI applications."
        ),
        source_url="https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
        keywords=("enterprise", "production", "support", "governance", "deployment"),
    ),
)
