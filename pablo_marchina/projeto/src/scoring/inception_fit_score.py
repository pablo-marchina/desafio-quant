from __future__ import annotations
from pydantic import BaseModel, Field
from src.extraction.schemas import AINativeLevel, ConfidenceLevel, StartupProfile, TechnicalGap
from src.classification.ai_native_classifier import ClassificationResult

class InceptionFitDimension(BaseModel):
    dimension_name: str
    raw_score: float
    adjusted_score: float
    weight: float
    confidence: ConfidenceLevel
    reasoning: str = ""
class InceptionFitScoreResult(BaseModel):
    total_score: float
    score_breakdown: dict[str, InceptionFitDimension]
    confidence: ConfidenceLevel
    detected_gaps: list[TechnicalGap]
    recommended_motion_hint: str
    reasoning: str
    evidence_used: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)

def _cv(c):
    s=str(c).lower(); return 1.0 if "high" in s else 0.6 if "medium" in s else 0.3

def _avg(e): return sum(_cv(getattr(x,"confidence",None)) for x in e)/len(e) if e else 0.0

def compute_inception_fit_score(profile: StartupProfile, classification: ClassificationResult, defensibility_score: float, evidence: list) -> InceptionFitScoreResult:
    text=" ".join([profile.sector,profile.description,profile.product_summary,*profile.ai_signals,*profile.tech_stack_signals]).lower()
    gaps=[]
    if any(k in text for k in ["llm","gpt","generative","inference"]): gaps.append(TechnicalGap.HIGH_INFERENCE_COST)
    if any(k in text for k in ["computer vision","real-time","latency"]): gaps.append(TechnicalGap.HIGH_LATENCY)
    if "health" in text or "medical" in text: gaps.append(TechnicalGap.HEALTHCARE_COMPLIANCE_NEED)
    if any(k in text for k in ["data pipeline","etl","kafka"]): gaps.append(TechnicalGap.SLOW_DATA_PIPELINE)
    if any(k in text for k in ["gpu","cuda","pytorch","tensorflow"]): gaps.append(TechnicalGap.HIGH_INFERENCE_COST)
    gaps=list(dict.fromkeys(gaps))
    conf=_avg(evidence)
    level_score={AINativeLevel.AI_NATIVE_SERVICE:100,AINativeLevel.AI_NATIVE:85,AINativeLevel.AI_ENABLED:50,AINativeLevel.AI_ASSISTED:35,AINativeLevel.NON_AI:10}.get(classification.classification,30)
    d={
      "ai_maturity":level_score,
      "nvidia_gap_fit":min(100,len(gaps)*28),
      "business_traction":min(100,len(profile.customers)*20+len(profile.funding_signals)*15),
      "technical_stack_fit":min(100,sum(k in text for k in ["pytorch","tensorflow","kubernetes","gpu","cuda","inference"])*18),
      "sector_fit":70 if any(k in text for k in ["health","robot","cyber","vision","llm","finance"]) else 30,
    }
    weights={"ai_maturity":0.25,"nvidia_gap_fit":0.25,"business_traction":0.15,"technical_stack_fit":0.2,"sector_fit":0.15}
    bd={k:InceptionFitDimension(dimension_name=k,raw_score=float(v),adjusted_score=float(v*(0.7+0.3*conf)),weight=weights[k],confidence=ConfidenceLevel.from_score(conf) if conf else ConfidenceLevel.LOW,reasoning=k) for k,v in d.items()}
    score=sum(x.adjusted_score*x.weight for x in bd.values())
    if classification.classification == AINativeLevel.NON_AI and len(profile.ai_signals)==0: score*=0.6
    score=max(0,min(100,score))
    if score>=70 and conf>=0.8: motion="approach_now"
    elif score>=45: motion="validate_manually"
    elif score>=25: motion="monitor"
    elif TechnicalGap.HEALTHCARE_COMPLIANCE_NEED in gaps and evidence: motion="monitor"
    else: motion="discard_for_now"
    missing=[]
    if not evidence: missing += ["validated_evidence","technical_gap_evidence"]
    elif conf < 0.55: missing.append("high_confidence_evidence")
    if not profile.customers: missing.append("customer_evidence")
    return InceptionFitScoreResult(total_score=float(score),score_breakdown=bd,confidence=ConfidenceLevel.HIGH if conf>=0.8 and score>=70 else ConfidenceLevel.MEDIUM if conf>=0.55 else ConfidenceLevel.LOW,detected_gaps=gaps,recommended_motion_hint=motion,reasoning="Quantitative NVIDIA Inception fit score from maturity, gap fit, traction, stack fit and sector fit.",evidence_used=[getattr(e,"claim",str(e)) for e in evidence],missing_evidence=missing)
