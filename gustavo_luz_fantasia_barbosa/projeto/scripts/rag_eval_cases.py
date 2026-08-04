from __future__ import annotations


RAG_EVAL_CASES: list[dict[str, object]] = [
    {
        "id": "inception_startup_support",
        "query": "startup brasileira quer suporte tecnico, comunidade e go-to-market NVIDIA",
        "expected_products": {"NVIDIA Inception"},
    },
    {
        "id": "nim_llm_deployment",
        "query": "deploy de LLM em producao com menor latencia e custo de inferencia",
        "expected_products": {"NVIDIA NIM", "NVIDIA Triton Inference Server", "TensorRT-LLM"},
    },
    {
        "id": "nemo_customization",
        "query": "customizacao avaliacao e operacao de modelos generativos empresariais",
        "expected_products": {"NVIDIA NeMo", "NeMo Guardrails"},
    },
    {
        "id": "guardrails_governance",
        "query": "governanca guardrails seguranca e controle de respostas para agentes LLM",
        "expected_products": {"NeMo Guardrails", "NVIDIA NeMo", "NVIDIA AI Enterprise"},
    },
    {
        "id": "triton_model_serving",
        "query": "serving de modelos em producao com multi model inference e observabilidade",
        "expected_products": {"NVIDIA Triton Inference Server", "NVIDIA NIM"},
    },
    {
        "id": "tensorrt_llm_optimization",
        "query": "otimizacao de inferencia para grandes modelos de linguagem LLM em GPU",
        "expected_products": {"TensorRT-LLM", "NVIDIA Triton Inference Server", "NVIDIA NIM"},
    },
    {
        "id": "rapids_data_pipeline",
        "query": "acelerar pipelines de dados tabulares ETL pandas analytics em GPU",
        "expected_products": {"NVIDIA RAPIDS", "cuDF", "cuML"},
    },
    {
        "id": "cudf_dataframes",
        "query": "processamento de dataframes em GPU compatibilidade pandas dados tabulares",
        "expected_products": {"cuDF", "NVIDIA RAPIDS"},
    },
    {
        "id": "cuml_ml",
        "query": "machine learning acelerado em GPU para treinamento e experimentos tabulares",
        "expected_products": {"cuML", "NVIDIA RAPIDS"},
    },
    {
        "id": "riva_speech",
        "query": "ASR TTS voz transcricao call center atendimento com baixa latencia",
        "expected_products": {"NVIDIA Riva", "NVIDIA NIM"},
    },
    {
        "id": "ai_enterprise_production",
        "query": "plataforma empresarial para IA em producao governanca seguranca suporte",
        "expected_products": {"NVIDIA AI Enterprise", "NeMo Guardrails"},
    },
    {
        "id": "omniverse_digital_twins",
        "query": "digital twins simulacao 3D colaboracao industrial e ambientes virtuais",
        "expected_products": {"NVIDIA Omniverse"},
    },
    {
        "id": "isaac_robotics",
        "query": "robotica autonomia simulacao de robos percepcao e sistemas autonomos",
        "expected_products": {"NVIDIA Isaac", "NVIDIA Omniverse"},
    },
    {
        "id": "clara_healthcare",
        "query": "healthcare medical imaging dados clinicos life sciences IA em saude",
        "expected_products": {"NVIDIA Clara", "NVIDIA AI Enterprise", "NVIDIA NIM"},
    },
    {
        "id": "morpheus_cybersecurity",
        "query": "cybersecurity deteccao de anomalias telemetria threat detection com IA",
        "expected_products": {"NVIDIA Morpheus"},
    },
]


def required_technology_coverage() -> set[str]:
    return {
        "NVIDIA Inception",
        "NVIDIA NIM",
        "NVIDIA NeMo",
        "NeMo Guardrails",
        "NVIDIA Triton Inference Server",
        "TensorRT-LLM",
        "NVIDIA RAPIDS",
        "NVIDIA Riva",
        "NVIDIA AI Enterprise",
    }

