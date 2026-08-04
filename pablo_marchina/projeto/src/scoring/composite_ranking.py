from __future__ import annotations
from pydantic import BaseModel, Field
from src.extraction.schemas import AINativeLevel, ConfidenceLevel
from src.classification.ai_native_classifier import ClassificationResult
from src.scoring.defensibility_score import DefensibilityScoreResult
from src.scoring.inception_fit_score import InceptionFitScoreResult
from src.scoring.production_readiness import ProductionReadinessResult

class CompositeResult(BaseModel):
    startup_id: str
    composite_score: float
    confidence: ConfidenceLevel
    defensibility_score: float = 0.0
    inception_fit_score: float = 0.0
    production_readiness_score: float = 0.0
    classification_score: float = 0.0
    missing_components: list[str] = Field(default_factory=list)
    confidence_penalty_applied: float = 0.0

class RankedStartup(BaseModel):
    startup_id: str
    startup_name: str
    sector: str
    composite_score: float
    confidence: ConfidenceLevel
    motion: str
    rank: int


def _cls_score(c: ClassificationResult | None) -> float:
    if c is None: return 0.0
    return {AINativeLevel.AI_NATIVE_SERVICE:90,AINativeLevel.AI_NATIVE:80,AINativeLevel.AI_ENABLED:55,AINativeLevel.AI_ASSISTED:35,AINativeLevel.NON_AI:0}.get(c.classification,0)

def _conf_num(c: ConfidenceLevel) -> float:
    return 1.0 if c == ConfidenceLevel.HIGH else 0.7 if c == ConfidenceLevel.MEDIUM else 0.4

def _conf_level(v: float) -> ConfidenceLevel:
    if v >= 0.8: return ConfidenceLevel.HIGH
    if v >= 0.55: return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW

def compute_composite_score(startup_id: str, defensibility: DefensibilityScoreResult | None, inception_fit: InceptionFitScoreResult | None, production_readiness: ProductionReadinessResult | None, classification: ClassificationResult | None) -> CompositeResult:
    parts=[]; missing=[]; confs=[]
    if defensibility is not None:
        parts.append((float(defensibility.total_score),0.30)); confs.append(_conf_num(defensibility.confidence))
    else: missing.append("defensibility_score")
    if inception_fit is not None:
        parts.append((float(inception_fit.total_score),0.30)); confs.append(_conf_num(inception_fit.confidence))
    else: missing.append("inception_fit_score")
    if production_readiness is not None:
        parts.append((float(production_readiness.production_readiness_score),0.25)); confs.append(_conf_num(production_readiness.confidence))
    else: missing.append("production_readiness")
    if classification is not None:
        parts.append((_cls_score(classification),0.15)); confs.append(_conf_num(classification.confidence))
    else: missing.append("classification")
    if not parts:
        return CompositeResult(startup_id=startup_id,composite_score=0.0,confidence=ConfidenceLevel.LOW,missing_components=missing,confidence_penalty_applied=1.0)
    total_w=sum(w for _,w in parts)
    score=sum(s*w for s,w in parts)/total_w
    penalty=0.08*len(missing)
    score=max(0,min(100,score*(1-penalty)))
    avg_conf=sum(confs)/len(confs) if confs else 0.0
    if missing: avg_conf=min(avg_conf,0.74)
    if score < 30:
        avg_conf = min(avg_conf, 0.54)
    return CompositeResult(startup_id=startup_id,composite_score=float(score),confidence=_conf_level(avg_conf),defensibility_score=float(defensibility.total_score) if defensibility else 0.0,inception_fit_score=float(inception_fit.total_score) if inception_fit else 0.0,production_readiness_score=float(production_readiness.production_readiness_score) if production_readiness else 0.0,classification_score=_cls_score(classification),missing_components=missing,confidence_penalty_applied=penalty)

def _motion(r: CompositeResult, cls: ClassificationResult | None) -> str:
    if cls and cls.classification == AINativeLevel.NON_AI and r.composite_score < 20: return "not_recommended"
    if r.composite_score >= 75: return "immediate_outreach"
    if r.composite_score >= 60: return "high_priority_outreach"
    if r.composite_score >= 35: return "monitor_and_nurture"
    if r.missing_components: return "lack_evidence_more_research"
    return "not_recommended"

def build_ranked_list(scores: list[CompositeResult], names: dict[str, tuple[str,str]], classifications: dict[str, ClassificationResult]) -> list[RankedStartup]:
    ordered=sorted(scores,key=lambda r:r.composite_score,reverse=True)
    out=[]
    for i,r in enumerate(ordered, start=1):
        name,sector=names.get(r.startup_id,(r.startup_id,"Unknown"))
        out.append(RankedStartup(startup_id=r.startup_id,startup_name=name,sector=sector,composite_score=r.composite_score,confidence=r.confidence,motion=_motion(r,classifications.get(r.startup_id)),rank=i))
    return out
