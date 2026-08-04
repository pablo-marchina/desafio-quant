from __future__ import annotations

import unicodedata

from radar.graph.state import RadarState
from radar.schemas import NvidiaKnowledgeChunk, NvidiaRecommendation, TechnicalGap


TECHNOLOGY_GUIDANCE: dict[str, dict[str, str]] = {
    "NVIDIA Inception": {
        "gap": "Startup precisa de validacao do ecossistema e suporte estruturado da NVIDIA.",
        "technical": "Inception conecta a startup a recursos tecnicos NVIDIA e orientacao do ecossistema enquanto o stack de IA amadurece.",
        "business": "O programa oferece suporte a startups, acesso a comunidade e alinhamento de go-to-market.",
        "priority": "medium",
        "complexity": "low",
        "action": "Revisar evidencias publicas e avaliar adesao para outreach do NVIDIA Inception.",
    },
    "NVIDIA NIM": {
        "gap": "Workflow de LLM ou agente validado pode precisar de deploy otimizado alem do uso generico de API.",
        "technical": "NIM empacota microsservicos de inferencia otimizados para workloads de IA generativa.",
        "business": "Inferencia otimizada reduz atrito de deploy e suporta servicos AI-native escalaveis.",
        "priority": "high",
        "complexity": "medium",
        "action": "Avaliar caminho atual de deploy de modelo e comparar com NIM para o workflow de IA validado.",
    },
    "NeMo Guardrails": {
        "gap": "Agente de IA ou workflow de cliente validado pode precisar de controle de comportamento e governanca.",
        "technical": "NeMo Guardrails pode restringir comportamento de assistentes e adicionar controles de politica em interacoes de agentes.",
        "business": "Agentes governados reduzem risco operacional para automacao voltada ao cliente ou critica para workflow.",
        "priority": "high",
        "complexity": "medium",
        "action": "Identificar fluxos de risco de agentes e prototipar guardrails para a interacao de maior impacto.",
    },
    "NVIDIA Triton Inference Server": {
        "gap": "Workflow de IA em producao pode precisar de serving escalavel e controle de latencia.",
        "technical": "Triton padroniza serving de inferencia em producao e suporta padroes de deploy escalaveis.",
        "business": "Infraestrutura de serving melhorada pode aumentar confiabilidade, latencia e previsibilidade de custos.",
        "priority": "medium",
        "complexity": "medium",
        "action": "Mapear endpoints de inferencia em producao e avaliar Triton para padronizacao de serving.",
    },
    "TensorRT-LLM": {
        "gap": "Workload de LLM pode precisar de otimizacao de inferencia com menor latencia e maior throughput.",
        "technical": "TensorRT-LLM otimiza performance de inferencia de LLMs com tecnicas de batching e baixa latencia.",
        "business": "Inferencia de LLM otimizada reduz custo de serving e melhora capacidade de resposta de produtos de IA.",
        "priority": "high",
        "complexity": "high",
        "action": "Testar prompts LLM representativos contra caminhos de otimizacao do TensorRT-LLM.",
    },
    "NVIDIA RAPIDS": {
        "gap": "Workflow de IA com muitos dados pode precisar de analytics mais rapidos ou processamento de pipelines deFeatures.",
        "technical": "RAPIDS acelera pipelines de ciencia de dados e analytics em GPUs.",
        "business": "Pipelines de dados mais rapidos podem encurtar ciclos de experimentacao e reduzir gargalos de processamento.",
        "priority": "medium",
        "complexity": "medium",
        "action": "Perfil de workloads tabulares ou analytics e identificar um prova de conceito com RAPIDS.",
    },
    "cuDF": {
        "gap": "Workload com muitos dataframes pode precisar de pre-processamento mais rapido.",
        "technical": "cuDF acelera operacoes de dataframe em GPUs e pode reduzir gargalos na preparacao de dados tabulares.",
        "business": "Processamento de dataframe mais rapido melhora velocidade de iteracao para produtos de IA com muitos analytics.",
        "priority": "medium",
        "complexity": "medium",
        "action": "Identificar jobs com muitos dataframes e comparar processamento estilo pandas contra cuDF.",
    },
    "cuML": {
        "gap": "Workflow de machine learning preditivo pode precisar de treinamento ou experimentacao acelerada de modelo.",
        "technical": "cuML acelera algoritmos classicos de machine learning em GPUs.",
        "business": "Experimentacao acelerada de modelos pode encurtar ciclos de validacao para startups intensivas em dados.",
        "priority": "medium",
        "complexity": "medium",
        "action": "Revisar workloads de ML preditivo e selecionar um benchmark compativel com cuML.",
    },
    "NVIDIA Riva": {
        "gap": "Produto de voz ou transcricao pode precisar de capacidades de speech AI de nivel de producao.",
        "technical": "Riva suporta workloads de speech AI como ASR, TTS e aplicacoes de voz.",
        "business": "Aceleracao de speech AI pode melhorar experiencia do usuario em call center, voz ou workflows de transcricao.",
        "priority": "medium",
        "complexity": "medium",
        "action": "Validar requisitos de workload de voz e avaliar Riva para componentes ASR/TTS.",
    },
    "NVIDIA Clara": {
        "gap": "Workflow de IA em saude pode precisar de ferramentas NVIDIA especificas do dominio de saude.",
        "technical": "Clara suporta workflows de IA em saude e ciencias da vida.",
        "business": "Ferramentas de saude alinhadas ao dominio reduzem atrito de adocao em contextos regulados ou clinicos.",
        "priority": "medium",
        "complexity": "high",
        "action": "Revisar caso de uso de saude, necessidades de compliance e alinhamento potencial com Clara.",
    },
    "NVIDIA Omniverse": {
        "gap": "Workflow de simulacao ou digital twin pode precisar de uma camada mais forte de colaboracao 3D e simulacao.",
        "technical": "Omniverse suporta simulacao, workflows 3D e digital twins para ambientes industriais.",
        "business": "Melhor simulacao pode reduzir custo de testes fisicos e acelerar validacao robotica ou industrial.",
        "priority": "medium",
        "complexity": "high",
        "action": "Mapear ativos de simulacao e avaliar onde Omniverse pode suportar workflows de digital twin.",
    },
    "NVIDIA Isaac": {
        "gap": "Workflow de robotica ou autonomia pode precisar de ferramentas NVIDIA para simulacao e deploy.",
        "technical": "Isaac suporta simulacao robotica, autonomia e workflows de desenvolvimento de robos.",
        "business": "Ferramentas especificas de robotica podem melhorar velocidade de validacao e reduzir risco de deploy.",
        "priority": "medium",
        "complexity": "high",
        "action": "Revisar stack de autonomia robotica e identificar um prova de conceito de simulacao ou deploy com Isaac.",
    },
    "NVIDIA NeMo": {
        "gap": "Workflow de IA generativa pode precisar de um caminho estruturado para customizacao, avaliacao e prontidao de deploy.",
        "technical": "NeMo suporta construcao, customizacao, avaliacao e deploy de modelos de IA generativa.",
        "business": "Um ciclo de vida de IA generativa mais forte ajuda startups AI-native a reduzir risco de modelo e melhorar diferenciacao de produto.",
        "priority": "high",
        "complexity": "medium",
        "action": "Revisar workflow de IA generativa validado e identificar se fine-tuning, avaliacao ou governanca de modelo e o proximo gargalo.",
    },
    "CUDA": {
        "gap": "Workload de IA pesado em GPU pode precisar de aceleracao ou otimizacao de baixo nivel.",
        "technical": "CUDA e a fundacao para aceleracao NVIDIA GPU em IA, HPC, analytics e workloads de simulacao.",
        "business": "Aceleracao GPU pode melhorar performance e eficiencia de custos quando workloads superam execucao generica apenas em CPU.",
        "priority": "medium",
        "complexity": "high",
        "action": "Perfil do workload validado e identificar se bibliotecas CUDA ou kernels customizados sao recomendados.",
    },
    "NVIDIA Morpheus": {
        "gap": "Workflow de IA em ciberseguranca pode precisar de deteccao de ameacas em tempo real ou analise de anomalias.",
        "technical": "Morpheus suporta pipelines de ciberseguranca acelerados por GPU para telemetria, deteccao de anomalias e resposta a ameacas.",
        "business": "IA de ciberseguranca em tempo real melhora velocidade de deteccao e fortalece propostas de valor empresariais.",
        "priority": "medium",
        "complexity": "high",
        "action": "Mapear fluxo de dados de ciberseguranca e avaliar se Morpheus se adequa ao workload de deteccao validado.",
    },
    "NVIDIA AI Enterprise": {
        "gap": "Workflow de IA em producao pode precisar de suporte enterprise, seguranca e infraestrutura de deploy estavel.",
        "technical": "NVIDIA AI Enterprise empacota software de IA de producao incluindo NIM, Triton, RAPIDS e suporte enterprise.",
        "business": "Infraestrutura de IA de nivel enterprise reduz risco operacional para startups vendendo para ambientes regulados ou grandes empresas.",
        "priority": "medium",
        "complexity": "medium",
        "action": "Avaliar requisitos de producao, seguranca e suporte para clientes enterprise e avaliar adesao ao AI Enterprise.",
    },
}



TECHNOLOGY_SECTORS: dict[str, set[str] | None] = {
    "NVIDIA Clara": {"Healthcare", "Saude", "Life Sciences", "Ciencias da Vida"},
    "NVIDIA Isaac": {"Robotics", "Robotica", "Industrial", "Manufacturing"},
    "NVIDIA Omniverse": {"Industrial", "Manufacturing", "Robotics", "Simulation", "Gaming"},
    "NVIDIA Riva": {"Voice AI", "Customer Service", "Call Center"},
    "NVIDIA Morpheus": {"Cybersecurity", "Seguranca"},
    "NVIDIA RAPIDS": None,
    "cuDF": None,
    "cuML": None,
    "CUDA": None,
    "NVIDIA NIM": None,
    "NVIDIA NeMo": None,
    "NeMo Guardrails": None,
    "NVIDIA Triton Inference Server": None,
    "TensorRT-LLM": None,
    "NVIDIA AI Enterprise": None,
    "NVIDIA Inception": None,
}

TECHNOLOGY_EVIDENCE_PATTERNS: dict[str, tuple[str, ...]] = {
    "NVIDIA Inception": ("ai", "ia", "startup", "empresa", "platform", "plataforma"),
    "NVIDIA NIM": ("llm", "generative", "generativa", "agent", "agente", "chatbot", "inference", "inferencia"),
    "NVIDIA NeMo": ("llm", "generative", "generativa", "fine tuning", "fine-tuning", "agent", "agente", "evaluation"),
    "NeMo Guardrails": ("agent", "agente", "assistant", "assistente", "governance", "governanca", "guardrail", "workflow"),
    "NVIDIA Triton Inference Server": ("inference", "inferencia", "serving", "latency", "latencia", "production", "producao"),
    "TensorRT-LLM": ("llm", "latency", "latencia", "throughput", "inference", "inferencia"),
    "NVIDIA RAPIDS": ("data", "dados", "analytics", "tabular", "etl", "dataframe"),
    "cuDF": ("dataframe", "tabular", "pandas", "etl", "dados"),
    "cuML": ("machine learning", "predictive", "preditivo", "tabular", "modelo"),
    "CUDA": ("gpu", "cuda", "performance", "aceleracao", "acceleration"),
    "NVIDIA Riva": ("voice", "voz", "speech", "audio", "transcricao", "transcription", "asr", "tts", "call center"),
    "NVIDIA Clara": ("healthcare", "saude", "medical", "clinica", "clinical", "life sciences"),
    "NVIDIA Omniverse": ("simulation", "simulacao", "digital twin", "3d", "industrial"),
    "NVIDIA Isaac": ("robot", "robotica", "robotics"),
    "NVIDIA Morpheus": ("cyber", "cybersecurity", "threat", "ameaca", "anomaly", "anomalia"),
    "NVIDIA AI Enterprise": ("production", "producao", "enterprise", "seguranca", "security", "governance", "governanca", "compliance"),
}

def generate_recommendations(state: RadarState) -> tuple[list[TechnicalGap], list[NvidiaRecommendation]]:
    validation = state.get("validation")
    if not validation or not validation.has_minimum_evidence:
        return [], []

    nvidia_context = state.get("nvidia_context", [])
    if not nvidia_context:
        return [], []

    evidence_text = _evidence_text(state, validation.supporting_evidence_ids)
    gaps: list[TechnicalGap] = []
    recommendations: list[NvidiaRecommendation] = []

    startup_sector = _detect_startup_sector(state)

    for chunk in nvidia_context:
        guidance = TECHNOLOGY_GUIDANCE.get(chunk.technology)
        if not guidance:
            continue
        if not _technology_supported(chunk.technology, evidence_text):
            continue
        if not _sector_compatible(chunk.technology, startup_sector):
            continue

        gap = _build_gap(chunk, guidance["gap"], validation.supporting_evidence_ids)
        gaps.append(gap)
        recommendations.append(
            NvidiaRecommendation(
                technology=chunk.technology,
                target_gap=gap.description,
                technical_justification=guidance["technical"],
                business_justification=guidance["business"],
                priority=guidance["priority"],
                implementation_complexity=guidance["complexity"],
                suggested_next_action=guidance["action"],
                startup_evidence_ids=validation.supporting_evidence_ids,
                nvidia_knowledge_ids=[chunk.id],
            )
        )

    return gaps, recommendations


def _build_gap(
    chunk: NvidiaKnowledgeChunk,
    description: str,
    evidence_ids: list[str],
) -> TechnicalGap:
    severity = "high" if chunk.technology in {"NVIDIA NIM", "NeMo Guardrails", "TensorRT-LLM"} else "medium"
    return TechnicalGap(
        description=description,
        evidence_ids=evidence_ids,
        severity=severity,
    )


def _evidence_text(state: RadarState, evidence_ids: list[str]) -> str:
    supported = [
        claim.text
        for claim in state.get("claims", [])
        if claim.id in evidence_ids
    ]
    profiles = state.get("extracted_startups", [])
    if profiles:
        profile = profiles[0]
        supported.extend(
            part for part in (
                profile.sector,
                profile.product,
                profile.ai_usage_summary,
                " ".join(profile.cited_technologies),
            ) if part
        )
    return _normalize("\n".join(supported))


def _technology_supported(technology: str, evidence_text: str) -> bool:
    patterns = TECHNOLOGY_EVIDENCE_PATTERNS.get(technology, ())
    if technology in {"NVIDIA Inception", "NVIDIA AI Enterprise"}:
        return bool(evidence_text) and any(pattern in evidence_text for pattern in patterns)
    return any(pattern in evidence_text for pattern in patterns)


def _normalize(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _detect_startup_sector(state: RadarState) -> str | None:
    profiles = state.get("extracted_startups", [])
    if profiles and profiles[0].sector:
        return profiles[0].sector
    classification = state.get("classification")
    if classification:
        return getattr(classification, "sector", None)
    return None


def _sector_compatible(technology: str, startup_sector: str | None) -> bool:
    allowed_sectors = TECHNOLOGY_SECTORS.get(technology)
    if allowed_sectors is None:
        return True
    if startup_sector is None:
        return False
    normalized_sector = _normalize(startup_sector)
    for allowed in allowed_sectors:
        if _normalize(allowed) in normalized_sector:
            return True
    return False
