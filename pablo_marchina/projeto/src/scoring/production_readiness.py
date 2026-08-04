from __future__ import annotations
from pydantic import BaseModel, Field
from src.extraction.schemas import AINativeLevel, ConfidenceLevel, StartupProfile
from src.classification.ai_native_classifier import ClassificationResult

class ReadinessDimension(BaseModel):
    dimension_name: str
    raw_score: float
    adjusted_score: float
    weight: float
    confidence: ConfidenceLevel
    reasoning: str = ""
DimensionScore = ReadinessDimension
class ProductionReadinessResult(BaseModel):
    production_readiness_score: float
    score_breakdown: dict[str, ReadinessDimension]
    confidence: ConfidenceLevel
    reasoning: str
    evidence_used: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)

def _cv(c):
    s=str(c).lower(); return 1.0 if "high" in s else 0.6 if "medium" in s else 0.3

def _avg(e): return sum(_cv(getattr(x,"confidence",None)) for x in e)/len(e) if e else 0.0

def compute_production_readiness(profile: StartupProfile, classification: ClassificationResult, evidence: list) -> ProductionReadinessResult:
    text=" ".join([profile.description,profile.product_summary,*profile.ai_signals,*profile.tech_stack_signals]).lower()
    scores={
      "real_users_and_deployment": min(100,len(profile.customers)*20 + (30 if any(k in text for k in ["production","deployed","customers","real-time"]) else 0)),
      "scale_and_inference": min(100,sum(k in text for k in ["low latency","real-time","inference","kubernetes","docker","gpu"])*18),
      "privacy_and_governance": min(100,sum(k in text for k in ["privacy","compliance","controlled","healthcare","governance"])*22 + (20 if profile.sector.lower().endswith("tech") else 0)),
      "data_infrastructure": min(100,sum(k in text for k in ["data pipeline","kafka","spark","postgresql","etl","database"])*18),
    }
    weights={"real_users_and_deployment":0.3,"scale_and_inference":0.25,"privacy_and_governance":0.2,"data_infrastructure":0.25}
    conf=_avg(evidence)
    mult=0.6+0.4*conf if evidence else 0.55
    bd={k:ReadinessDimension(dimension_name=k,raw_score=float(v),adjusted_score=float(max(0,min(100,v*mult))),weight=weights[k],confidence=ConfidenceLevel.from_score(conf) if conf else ConfidenceLevel.LOW,reasoning=k) for k,v in scores.items()}
    total=sum(d.adjusted_score*d.weight for d in bd.values())
    missing=[]
    if not evidence: missing.append("validated_evidence")
    if not profile.customers: missing.append("customer_or_deployment_evidence")
    if not any(k in text for k in ["privacy","compliance","governance"]): missing.append("governance_evidence")
    return ProductionReadinessResult(production_readiness_score=float(total),score_breakdown=bd,confidence=ConfidenceLevel.HIGH if conf>=0.8 and total>=50 else ConfidenceLevel.MEDIUM if conf>=0.55 else ConfidenceLevel.LOW,reasoning="Quantitative production readiness from deployment, inference scale, governance and data infrastructure.",evidence_used=[getattr(e,"claim",str(e)) for e in evidence],missing_evidence=missing)
