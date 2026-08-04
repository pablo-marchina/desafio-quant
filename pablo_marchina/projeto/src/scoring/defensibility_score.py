from __future__ import annotations

from pydantic import BaseModel, Field
from src.extraction.schemas import AINativeLevel, ConfidenceLevel, StartupProfile
from src.classification.ai_native_classifier import ClassificationResult

class DimensionScore(BaseModel):
    dimension_name: str
    raw_score: float
    adjusted_score: float
    weight: float
    confidence: ConfidenceLevel
    reasoning: str = ""

class DefensibilityScoreResult(BaseModel):
    total_score: float
    score_breakdown: dict[str, DimensionScore]
    confidence: ConfidenceLevel
    classification_boost: str
    reasoning: str
    evidence_used: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


def _conf_value(c):
    s=str(c).lower(); return 1.0 if "high" in s else 0.6 if "medium" in s else 0.3

def _avg_conf(evidence):
    if not evidence: return 0.0
    return sum(_conf_value(getattr(e,"confidence",None)) for e in evidence)/len(evidence)

def _level_boost(level):
    if level == AINativeLevel.AI_NATIVE_SERVICE: return 1.0
    if level == AINativeLevel.AI_NATIVE: return 0.85
    if level == AINativeLevel.AI_ENABLED: return 0.45
    if level == AINativeLevel.AI_ASSISTED: return 0.25
    return 0.05

def _score_profile(profile: StartupProfile, classification: ClassificationResult):
    text=" ".join([profile.description,profile.product_summary,*profile.ai_signals,*profile.tech_stack_signals]).lower()
    ai_core=min(100, len(profile.ai_signals)*10 + (30 if classification.classification in {AINativeLevel.AI_NATIVE,AINativeLevel.AI_NATIVE_SERVICE} else 5))
    proprietary=40 if any(k in text for k in ["proprietary", "dados", "data", "workflow", "records"]) else 10
    replication=min(100, len(profile.tech_stack_signals)*15 + len(profile.customers)*10 + len(profile.funding_signals)*15)
    distribution=min(100, len(profile.customers)*20 + len(profile.funding_signals)*15)
    technical=min(100, sum(k in text for k in ["pytorch","tensorflow","kubernetes","gpu","deep learning","computer vision","llm"])*15)
    service=min(100, (30 if "workflow" in text or "production" in text else 0)+len(profile.customers)*15)
    return {"ai_core_dependency":ai_core,"proprietary_data_workflow":proprietary,"replication_complexity":replication,"distribution_or_customers":distribution,"technical_depth":technical,"ai_native_service_potential":service}

def compute_defensibility_score(profile: StartupProfile, classification: ClassificationResult, evidence: list) -> DefensibilityScoreResult:
    weights={"ai_core_dependency":0.22,"proprietary_data_workflow":0.18,"replication_complexity":0.18,"distribution_or_customers":0.14,"technical_depth":0.16,"ai_native_service_potential":0.12}
    conf=_avg_conf(evidence)
    scores=_score_profile(profile,classification)
    breakdown={}
    for k,raw in scores.items():
        adj=raw*(0.6+0.4*conf)
        breakdown[k]=DimensionScore(dimension_name=k,raw_score=float(raw),adjusted_score=float(max(0,min(100,adj))),weight=weights[k],confidence=ConfidenceLevel.from_score(conf) if conf else ConfidenceLevel.LOW,reasoning=k)
    total=sum(d.adjusted_score*d.weight for d in breakdown.values())
    total=total*(0.85+0.3*_level_boost(classification.classification))
    total=max(0,min(100,total))
    missing=[]
    if not evidence: missing += ["validated_evidence","customer_evidence","technical_evidence"]
    elif conf < 0.5: missing.append("high_confidence_evidence")
    if not profile.customers: missing.append("customer_evidence")
    if not profile.funding_signals: missing.append("funding_evidence")
    confidence = ConfidenceLevel.HIGH if conf>=0.8 and total>=50 else ConfidenceLevel.MEDIUM if conf>=0.55 else ConfidenceLevel.LOW
    return DefensibilityScoreResult(total_score=float(total),score_breakdown=breakdown,confidence=confidence,classification_boost=classification.classification.name,reasoning="Quantitative defensibility score from AI dependency, data/workflow, replication complexity, distribution and technical depth.",evidence_used=[getattr(e,"claim",str(e)) for e in evidence],missing_evidence=missing)
