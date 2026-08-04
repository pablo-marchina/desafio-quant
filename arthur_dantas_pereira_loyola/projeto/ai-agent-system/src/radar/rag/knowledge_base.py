"""Seed knowledge base of 16 NVIDIA technologies relevant to startup assessment."""

NVIDIA_KNOWLEDGE_CHUNKS: list[dict] = [
    {
        "id": 1,
        "technology": "NVIDIA Inception",
        "title": "NVIDIA Inception — Programa para Startups",
        "url": "https://www.nvidia.com/en-us/startups/",
        "content": (
            "NVIDIA Inception is a free program for startups that provides go-to-market support, "
            "technical resources, and access to NVIDIA hardware credits. Members get access to "
            "NVIDIA AI Enterprise software, NIM microservices, and the Inception community of "
            "thousands of AI startups worldwide. The program helps startups accelerate their "
            "development with GPUs, deep learning frameworks, and connections to venture capital."
        ),
        "keywords": ["startup", "ecosystem", "go-to-market", "credits", "community", "support", "aceleracao"],
    },
    {
        "id": 2,
        "technology": "NVIDIA NIM",
        "title": "NVIDIA NIM — Optimized Inference Microservices",
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
        "content": (
            "NVIDIA NIM provides optimized inference microservices for deploying generative AI "
            "models in production. It supports major model architectures like Llama, Mistral, "
            "and Stable Diffusion with GPU-accelerated performance. NIM containers integrate "
            "with Kubernetes, Docker, and popular MLOps pipelines for scalable deployment."
        ),
        "keywords": ["llm", "inference", "microservices", "deploy", "generative", "containers"],
    },
    {
        "id": 3,
        "technology": "NVIDIA NeMo",
        "title": "NVIDIA NeMo — Framework for Generative AI",
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
        "content": (
            "NVIDIA NeMo is an end-to-end framework for building, customizing, and deploying "
            "generative AI models. It supports large language models (LLMs), multimodal models, "
            "and speech AI. NeMo provides tools for data curation, model training, fine-tuning, "
            "evaluation, and guardrails integration."
        ),
        "keywords": ["training", "fine-tuning", "customization", "evaluation", "generative", "llm", "multimodal"],
    },
    {
        "id": 4,
        "technology": "NeMo Guardrails",
        "title": "NeMo Guardrails — Safe AI Agent Control",
        "url": "https://github.com/NVIDIA/NeMo-Guardrails",
        "content": (
            "NeMo Guardrails is an open-source toolkit for adding safety and control to "
            "conversational AI agents. It lets developers define rules that constrain model "
            "behavior, prevent harmful outputs, enforce topic boundaries, and implement "
            "conversational workflows. It integrates with LangChain, LlamaIndex, and custom LLM backends."
        ),
        "keywords": ["agents", "guardrails", "safety", "control", "workflow", "conversational", "langchain"],
    },
    {
        "id": 5,
        "technology": "NVIDIA Triton Inference Server",
        "title": "Triton Inference Server — Production Model Serving",
        "url": "https://developer.nvidia.com/triton-inference-server",
        "content": (
            "Triton Inference Server standardizes and accelerates production model serving "
            "across GPUs, CPUs, and ARM. It supports multiple frameworks (PyTorch, TensorFlow, "
            "ONNX, TensorRT) with dynamic batching, model ensembles, and model versioning. "
            "It is the industry standard for high-throughput, low-latency inference at scale."
        ),
        "keywords": ["serving", "production", "latency", "inference", "batching", "orchestration"],
    },
    {
        "id": 6,
        "technology": "TensorRT-LLM",
        "title": "TensorRT-LLM — LLM Inference Optimization",
        "url": "https://github.com/NVIDIA/TensorRT-LLM",
        "content": (
            "TensorRT-LLM is an open-source library for optimizing large language model "
            "inference on NVIDIA GPUs. It provides techniques like in-flight batching, "
            "paged attention, quantization (FP8, INT4, INT8), and tensor parallelism "
            "for low-latency serving of LLMs at scale."
        ),
        "keywords": ["llm", "inference", "optimization", "latency", "batching", "quantization", "performance"],
    },
    {
        "id": 7,
        "technology": "NVIDIA RAPIDS",
        "title": "NVIDIA RAPIDS — GPU-Accelerated Data Science",
        "url": "https://rapids.ai/",
        "content": (
            "NVIDIA RAPIDS is a suite of open-source libraries for executing data science "
            "and analytics pipelines entirely on GPUs. It includes cuDF for dataframes, "
            "cuML for machine learning, and cuGraph for graph analytics. RAPIDS integrates "
            "with the Apache Arrow ecosystem and standard Python data science tools."
        ),
        "keywords": ["data", "analytics", "pipeline", "gpu", "dataframe", "tabular", "data science"],
    },
    {
        "id": 8,
        "technology": "cuDF",
        "title": "cuDF — GPU DataFrames",
        "url": "https://docs.rapids.ai/api/cudf/stable/",
        "content": (
            "cuDF is a GPU-accelerated DataFrame library with a pandas-like API. It enables "
            "data preprocessing, feature engineering, and ETL pipelines to run entirely on GPU, "
            "achieving 10-50x speedups over CPU-based pandas for large datasets."
        ),
        "keywords": ["dataframe", "tabular", "gpu", "pandas", "etl", "preprocessing"],
    },
    {
        "id": 9,
        "technology": "cuML",
        "title": "cuML — GPU Machine Learning",
        "url": "https://docs.rapids.ai/api/cuml/stable/",
        "content": (
            "cuML provides GPU-accelerated implementations of popular machine learning algorithms "
            "including random forests, XGBoost, PCA, UMAP, k-means, and linear models. It follows "
            "the scikit-learn API for easy integration into existing ML pipelines."
        ),
        "keywords": ["machine learning", "predictive", "classification", "clustering", "gpu"],
    },
    {
        "id": 10,
        "technology": "CUDA",
        "title": "CUDA — Parallel Computing Platform",
        "url": "https://developer.nvidia.com/cuda-zone",
        "content": (
            "CUDA is NVIDIA's parallel computing platform and programming model for GPU "
            "acceleration. It enables developers to harness GPU power for general-purpose "
            "computing across industries including AI, HPC, data analytics, and scientific "
            "simulation. CUDA is the foundation for all NVIDIA AI and HPC software."
        ),
        "keywords": ["gpu", "parallel", "computing", "acceleration", "hpc", "programming"],
    },
    {
        "id": 11,
        "technology": "NVIDIA Riva",
        "title": "NVIDIA Riva — Speech AI SDK",
        "url": "https://developer.nvidia.com/riva",
        "content": (
            "NVIDIA Riva is a GPU-accelerated SDK for building speech AI applications. "
            "It provides pre-trained models for automatic speech recognition (ASR), "
            "text-to-speech (TTS), neural machine translation, and natural language "
            "understanding (NLU). Riva supports real-time and batch processing."
        ),
        "keywords": ["voice", "speech", "asr", "tts", "transcription", "call center", "audio"],
    },
    {
        "id": 12,
        "technology": "NVIDIA Omniverse",
        "title": "NVIDIA Omniverse — 3D Simulation Platform",
        "url": "https://www.nvidia.com/en-us/omniverse/",
        "content": (
            "NVIDIA Omniverse is a platform for building and operating 3D applications "
            "and digital twins. It enables collaborative simulation, physics-accurate "
            "rendering, and AI-powered workflows for industries like manufacturing, "
            "automotive, robotics, and media. Omniverse supports USD (Universal Scene Description)."
        ),
        "keywords": ["simulation", "3d", "digital twins", "rendering", "collaboration", "industrial"],
    },
    {
        "id": 13,
        "technology": "NVIDIA Isaac",
        "title": "NVIDIA Isaac — Robotics Platform",
        "url": "https://developer.nvidia.com/isaac",
        "content": (
            "NVIDIA Isaac provides tools for developing, simulating, and deploying AI-powered "
            "robots. It includes Isaac Sim for physics-accurate simulation, Isaac ROS for "
            "GPU-accelerated ROS 2 nodes, and Isaac Perceptor for autonomous mobile robot "
            "perception. It supports the entire robotics development lifecycle."
        ),
        "keywords": ["robotics", "simulation", "autonomy", "ros", "perception", "robot"],
    },
    {
        "id": 14,
        "technology": "NVIDIA Clara",
        "title": "NVIDIA Clara — Healthcare AI Platform",
        "url": "https://www.nvidia.com/en-us/clara/",
        "content": (
            "NVIDIA Clara is a healthcare AI platform for medical imaging, genomics, "
            "and drug discovery. It provides tools for developing and deploying AI models "
            "in clinical workflows, including Clara Imaging for radiology AI, Clara Genomics "
            "for genome analysis, and Clara Discovery for drug development."
        ),
        "keywords": ["healthcare", "medical", "imaging", "genomics", "drug discovery", "clinical"],
    },
    {
        "id": 15,
        "technology": "NVIDIA Morpheus",
        "title": "NVIDIA Morpheus — Cybersecurity AI",
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/morpheus/",
        "content": (
            "NVIDIA Morpheus is a cybersecurity AI framework that enables real-time "
            "threat detection, data exfiltration monitoring, and network anomaly analysis "
            "using GPU-accelerated machine learning. It processes hundreds of gigabytes "
            "of telemetry data per second for rapid threat response."
        ),
        "keywords": ["security", "cybersecurity", "threat detection", "anomaly", "network", "gpu"],
    },
    {
        "id": 16,
        "technology": "NVIDIA AI Enterprise",
        "title": "NVIDIA AI Enterprise — Production AI Platform",
        "url": "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
        "content": (
            "NVIDIA AI Enterprise is a comprehensive software platform for production AI. "
            "It includes NVIDIA NIM, Triton Inference Server, RAPIDS, and over 50 other "
            "accelerated software tools. It provides enterprise-grade support, security "
            "patches, and API stability for deploying AI in production environments."
        ),
        "keywords": ["enterprise", "production", "platform", "support", "deploy", "infrastructure"],
    },
]


def get_seed_chunks() -> list[dict]:
    return list(NVIDIA_KNOWLEDGE_CHUNKS)
