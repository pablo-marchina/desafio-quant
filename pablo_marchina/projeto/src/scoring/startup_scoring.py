from __future__ import annotations

from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, Field

from src.quality.decision_calibration_registry import CalibrationStatus, DecisionCalibrationRecord, get_project_decision_inventory

AI_NATIVE_WEIGHTS_DECISION_ID = "ai_native_score.weights"
AI_NATIVE_THRESHOLD_DECISION_ID = "ai_native_score.production_threshold"
AI_NATIVE_UNCERTAINTY_DECISION_ID = "ai_native_score.uncertainty_penalty"
NVIDIA_FIT_WEIGHTS_DECISION_ID = "nvidia_fit_score.weights"
NVIDIA_FIT_THRESHOLD_DECISION_ID = "nvidia_fit_score.production_threshold"
NVIDIA_FIT_UNCERTAINTY_DECISION_ID = "nvidia_fit_score.uncertainty_penalty"
REQUIRED_CALIBRATION_DECISIONS = [AI_NATIVE_WEIGHTS_DECISION_ID, AI_NATIVE_THRESHOLD_DECISION_ID, AI_NATIVE_UNCERTAINTY_DECISION_ID, NVIDIA_FIT_WEIGHTS_DECISION_ID, NVIDIA_FIT_THRESHOLD_DECISION_ID, NVIDIA_FIT_UNCERTAINTY_DECISION_ID]

_AI_SIGNAL_KEYWORDS = {"ai", "ia", "artificial intelligence", "inteligencia artificial", "machine learning", "ml", "deep learning", "neural", "computer vision", "nlp", "generative", "generativa", "llm", "gpt", "predictive"}
_TECHNICAL_AI_TERMS = {"pytorch", "tensorflow", "transformer", "fine-tuning", "kubernetes", "model", "models", "inference", "training", "neural", "cuda", "gpu"}
_PRODUCT_AI_CLAIM_KEYWORDS = {"platform", "plataforma", "api", "chatbot", "analytics", "recomendacao", "recommendation", "fraud", "fraude"}
_MODEL_ML_INFRA_KEYWORDS = {"pytorch", "tensorflow", "kubernetes", "cuda", "gpu", "transformers", "fine-tuning", "inference", "training", "cluster"}
_NVIDIA_GPU_KEYWORDS = {"gpu", "a100", "h100", "nvidia"}
_NVIDIA_CUDA_KEYWORDS = {"cuda", "acceleration", "aceleracao", "tensorrt", "rapids"}
_NVIDIA_INFERENCE_KEYWORDS = {"inference", "inferencia", "serving", "triton", "nim", "training", "treinamento"}
_NVIDIA_DATA_KEYWORDS = {"data pipeline", "pipeline", "etl", "spark", "rapids", "cudf", "cuml"}
_NVIDIA_INDUSTRY_KEYWORDS = {"health", "healthcare", "medical", "saude", "robotics", "simulation", "cybersecurity", "finance", "fintech", "manufacturing"}

class ScoreStatus(str, Enum):
    CALIBRATED = "calibrated"
    BLOCKED_UNCALIBRATED_SCORING = "blocked_uncalibrated_scoring"

class StartupScoringFeatures(BaseModel):
    ai_signal_count: int = 0
    ai_signal_source_coverage: float = 0.0
    technical_ai_term_count: int = 0
    product_ai_claim_count: int = 0
    accepted_ai_evidence_count: int = 0
    ai_claim_support_ratio: float = 0.0
    evidence_confidence_mean_for_ai_claims: float = 0.0
    source_quality_mean_for_ai_sources: float = 0.0
    technical_depth_signal_count: int = 0
    model_or_ml_infrastructure_signal_count: int = 0
    uncertainty_penalty: float = 1.0

class NvidiaFitFeatures(BaseModel):
    gpu_compute_signal_count: int = 0
    cuda_or_acceleration_signal_count: int = 0
    inference_or_training_signal_count: int = 0
    computer_vision_signal_count: int = 0
    genai_llm_signal_count: int = 0
    data_pipeline_signal_count: int = 0
    nvidia_keyword_signal_count: int = 0
    nvidia_relevant_industry_signal_count: int = 0
    accepted_nvidia_fit_evidence_count: int = 0
    rag_context_alignment_count: int = 0
    evidence_confidence_mean_for_nvidia_claims: float = 0.0
    implementation_complexity_proxy: float = 0.0
    uncertainty_penalty: float = 1.0

class ScoreComponent(BaseModel):
    score_name: str
    score_value: float
    score_status: ScoreStatus
    production_allowed: bool
    features: dict[str, Any] | None = None
    weights: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    calibration_decision_ids: list[str] = Field(default_factory=list)
    uncertainty: float = 0.0
    explanation: str = ""
    blockers: list[str] = Field(default_factory=list)

class StartupScoreResult(BaseModel):
    ai_native: ScoreComponent
    nvidia_fit: ScoreComponent
    scoring_status: str = "passed"
    production_allowed: bool = True
    blockers: list[str] = Field(default_factory=list)
    score_metrics: dict[str, float | int] = Field(default_factory=dict)


def _text(x: Any) -> str:
    if isinstance(x, dict):
        return " ".join(str(x.get(k, "")) for k in ("claim_text", "text", "snippet", "claim"))
    return " ".join(str(getattr(x, k, "")) for k in ("claim_text", "text", "quote_or_evidence", "claim"))

def _contains(text: str, keys: Iterable[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keys)

def _count_keywords(texts: Iterable[str], keys: set[str]) -> int:
    hay = "\n".join(texts).lower()
    return sum(1 for k in keys if k in hay)

def _confidence_float(v: Any) -> float:
    s=str(v).lower()
    if "high" in s: return 1.0
    if "medium" in s: return 0.6
    if "low" in s: return 0.3
    try: return max(0.0,min(1.0,float(v)))
    except Exception: return 0.5

def _mean(vals: list[float], default: float=0.0) -> float:
    return sum(vals)/len(vals) if vals else default

def extract_ai_native_features(claims: list[Any], accepted_evidence_items: list[Any], evidence_items: list[Any]) -> StartupScoringFeatures:
    if not claims and not accepted_evidence_items and not evidence_items:
        return StartupScoringFeatures()
    texts = [_text(x) for x in claims + accepted_evidence_items + evidence_items]
    ai_texts=[t for t in texts if _contains(t,_AI_SIGNAL_KEYWORDS)]
    accepted_ai=[e for e in accepted_evidence_items if _contains(_text(e),_AI_SIGNAL_KEYWORDS)]
    source_ids={str(e.get("source_id", i)) if isinstance(e,dict) else str(i) for i,e in enumerate(accepted_ai)}
    supported=sum(1 for c in claims if str(c.get("support_status", "supported")).lower()=="supported") if claims and isinstance(claims[0],dict) else len(claims)
    confs=[float(e.get("evidence_confidence_score", _confidence_float(e.get("confidence",0.5)))) for e in accepted_ai if isinstance(e,dict)]
    quals=[float(e.get("source_quality_score",0.5)) for e in accepted_ai if isinstance(e,dict)]
    return StartupScoringFeatures(
        ai_signal_count=len(ai_texts),
        ai_signal_source_coverage=min(1.0,len(source_ids)/max(1,len(evidence_items))),
        technical_ai_term_count=_count_keywords(texts,_TECHNICAL_AI_TERMS),
        product_ai_claim_count=sum(1 for t in texts if _contains(t,_PRODUCT_AI_CLAIM_KEYWORDS)),
        accepted_ai_evidence_count=len(accepted_ai),
        ai_claim_support_ratio=supported/max(1,len(claims)),
        evidence_confidence_mean_for_ai_claims=_mean(confs,0.0),
        source_quality_mean_for_ai_sources=_mean(quals,0.0),
        technical_depth_signal_count=_count_keywords(texts,_TECHNICAL_AI_TERMS),
        model_or_ml_infrastructure_signal_count=_count_keywords(texts,_MODEL_ML_INFRA_KEYWORDS),
        uncertainty_penalty=max(0.0,1.0-min(1.0,len(accepted_ai)/5.0)),
    )

def extract_nvidia_fit_features(claims: list[Any], accepted_evidence_items: list[Any], evidence_items: list[Any], rag_contexts: list[Any] | None=None) -> NvidiaFitFeatures:
    texts=[_text(x) for x in claims+accepted_evidence_items+evidence_items]+[str(x) for x in (rag_contexts or [])]
    nvidia_texts=[t for t in texts if _contains(t,_NVIDIA_GPU_KEYWORDS|_NVIDIA_CUDA_KEYWORDS|_NVIDIA_INFERENCE_KEYWORDS)]
    confs=[float(e.get("evidence_confidence_score", _confidence_float(e.get("confidence",0.5)))) for e in accepted_evidence_items if isinstance(e,dict) and _contains(_text(e),_NVIDIA_GPU_KEYWORDS|_NVIDIA_CUDA_KEYWORDS|_NVIDIA_INFERENCE_KEYWORDS)]
    return NvidiaFitFeatures(
        gpu_compute_signal_count=_count_keywords(texts,_NVIDIA_GPU_KEYWORDS),
        cuda_or_acceleration_signal_count=_count_keywords(texts,_NVIDIA_CUDA_KEYWORDS),
        inference_or_training_signal_count=_count_keywords(texts,_NVIDIA_INFERENCE_KEYWORDS),
        computer_vision_signal_count=sum(1 for t in texts if "computer vision" in t.lower() or "imagem" in t.lower()),
        genai_llm_signal_count=sum(1 for t in texts if any(k in t.lower() for k in ["llm","gpt","generative","generativa","transformer"])),
        data_pipeline_signal_count=_count_keywords(texts,_NVIDIA_DATA_KEYWORDS),
        nvidia_keyword_signal_count=sum(1 for t in texts if "nvidia" in t.lower()),
        nvidia_relevant_industry_signal_count=_count_keywords(texts,_NVIDIA_INDUSTRY_KEYWORDS),
        accepted_nvidia_fit_evidence_count=len(nvidia_texts),
        rag_context_alignment_count=sum(1 for t in (rag_contexts or []) if _contains(str(t), _NVIDIA_GPU_KEYWORDS|_NVIDIA_CUDA_KEYWORDS|_NVIDIA_INFERENCE_KEYWORDS)),
        evidence_confidence_mean_for_nvidia_claims=_mean(confs,0.0),
        implementation_complexity_proxy=0.3 if nvidia_texts else 0.6,
        uncertainty_penalty=max(0.0,1.0-min(1.0,len(nvidia_texts)/5.0)),
    )

def _record_map(inv): return {r.decision_id:r for r in inv}
def _allowed(rec): return rec and rec.production_allowed and rec.calibration_status in {CalibrationStatus.CALIBRATED,CalibrationStatus.BASELINE_MEASURED}
def _norm_feature(name: str, val: Any) -> float:
    if name.endswith("count") or name.endswith("coverage") or name.endswith("ratio"):
        return max(0.0,min(1.0,float(val)/5.0 if isinstance(val,int) else float(val)))
    if name == "implementation_complexity_proxy": return max(0.0,min(1.0,1.0-float(val)))
    if name == "uncertainty_penalty": return max(0.0,min(1.0,1.0-float(val)))
    return max(0.0,min(1.0,float(val)))

def _component(name, features: BaseModel, inv, weights_id, threshold_id, uncertainty_id) -> ScoreComponent:
    recs=_record_map(inv)
    required=[weights_id,threshold_id,uncertainty_id]
    missing=[rid for rid in required if not _allowed(recs.get(rid))]
    if missing:
        return ScoreComponent(score_name=name, score_value=0.0, score_status=ScoreStatus.BLOCKED_UNCALIBRATED_SCORING, production_allowed=False, features=features.model_dump(), calibration_decision_ids=required, blockers=[f"Missing calibrated decision: {m}" for m in missing], explanation="Blocked because quantitative calibration is incomplete.")
    weights=recs[weights_id].current_value if isinstance(recs[weights_id].current_value,dict) else {}
    fd=features.model_dump(); total=sum(float(v) for v in weights.values()) or 1.0
    score=sum(_norm_feature(k,fd.get(k,0))*float(w) for k,w in weights.items())/total
    return ScoreComponent(score_name=name, score_value=max(0.0,min(1.0,score)), score_status=ScoreStatus.CALIBRATED, production_allowed=True, features=fd, weights={k:float(v) for k,v in weights.items()}, thresholds={"production_threshold":float(recs[threshold_id].current_value or 0)}, calibration_decision_ids=required, uncertainty=float(fd.get("uncertainty_penalty",0.0)), explanation="Score computed from calibrated quantitative feature weights.")

def compute_startup_scoring(claims: list[Any], accepted_evidence_items: list[Any], evidence_items: list[Any], *, inventory: list[DecisionCalibrationRecord] | None=None, rag_contexts: list[Any] | None=None) -> StartupScoreResult:
    inv=get_project_decision_inventory() if inventory is None else inventory
    ai=extract_ai_native_features(claims,accepted_evidence_items,evidence_items)
    nv=extract_nvidia_fit_features(claims,accepted_evidence_items,evidence_items,rag_contexts=rag_contexts)
    ai_c=_component("ai_native_score",ai,inv,AI_NATIVE_WEIGHTS_DECISION_ID,AI_NATIVE_THRESHOLD_DECISION_ID,AI_NATIVE_UNCERTAINTY_DECISION_ID)
    nv_c=_component("nvidia_fit_score",nv,inv,NVIDIA_FIT_WEIGHTS_DECISION_ID,NVIDIA_FIT_THRESHOLD_DECISION_ID,NVIDIA_FIT_UNCERTAINTY_DECISION_ID)
    allowed=ai_c.production_allowed and nv_c.production_allowed
    return StartupScoreResult(ai_native=ai_c,nvidia_fit=nv_c,production_allowed=allowed,scoring_status="passed" if allowed else "blocked",blockers=ai_c.blockers+nv_c.blockers)

def build_scoring_summary(result: StartupScoreResult, *, accepted_evidence_count:int=0, rejected_evidence_count:int=0, accepted_claim_count:int=0, average_evidence_confidence:float=0.0, average_source_quality:float=0.0, unsupported_critical_claims_count:int=0) -> StartupScoreResult:
    metrics={
        "ai_native_feature_coverage": sum(1 for v in (result.ai_native.features or {}).values() if v)/max(1,len(result.ai_native.features or {})),
        "nvidia_fit_feature_coverage": sum(1 for v in (result.nvidia_fit.features or {}).values() if v)/max(1,len(result.nvidia_fit.features or {})),
        "accepted_evidence_count":accepted_evidence_count,
        "rejected_evidence_count":rejected_evidence_count,
        "accepted_claim_count":accepted_claim_count,
        "average_evidence_confidence":average_evidence_confidence,
        "average_source_quality":average_source_quality,
        "scoring_uncertainty":(result.ai_native.uncertainty+result.nvidia_fit.uncertainty)/2,
        "calibrated_decision_count": int(result.ai_native.production_allowed)*3+int(result.nvidia_fit.production_allowed)*3,
        "missing_calibration_count": len(result.ai_native.blockers)+len(result.nvidia_fit.blockers),
        "unsupported_critical_claims_count":unsupported_critical_claims_count,
    }
    result.score_metrics=metrics
    if unsupported_critical_claims_count>0:
        result.scoring_status="failed"; result.production_allowed=False; result.blockers.append("unsupported critical claims present")
    return result
