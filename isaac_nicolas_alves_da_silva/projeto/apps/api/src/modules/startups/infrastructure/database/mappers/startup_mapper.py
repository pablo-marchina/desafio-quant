"""Mapper entre Startup e StartupModel."""

from apps.api.src.modules.startups.domain.entities import Startup, StartupAIProfile
from apps.api.src.modules.startups.domain.enums import (
    AiDataModality,
    AiDeploymentStage,
    AiGpuNeed,
    AiInfraEnvironment,
    AiLatencyRequirement,
    AiMaturityLevel,
    AiModelType,
    AiWorkloadType,
    FundingStage,
)
from apps.api.src.modules.startups.infrastructure.database.models.startup_model import (
    StartupModel,
)


def _profile_to_dict(profile: StartupAIProfile) -> dict:
    return {
        "ai_workload_type": profile.ai_workload_type.value,
        "model_type": profile.model_type.value,
        "data_modality": profile.data_modality.value,
        "deployment_stage": profile.deployment_stage.value,
        "infra_environment": profile.infra_environment.value,
        "gpu_need": profile.gpu_need.value,
        "latency_requirement": profile.latency_requirement.value,
        "scale_signal": profile.scale_signal,
        "current_tools": list(profile.current_tools),
        "business_goal": profile.business_goal,
        "field_confidence": profile.field_confidence,
        "field_evidence_ids": profile.field_evidence_ids,
        "extracted_at": (
            profile.extracted_at.isoformat() if profile.extracted_at else None
        ),
    }


def _profile_from_dict(data: dict) -> StartupAIProfile:
    from datetime import datetime

    extracted_at_raw = data.get("extracted_at")
    extracted_at = datetime.fromisoformat(extracted_at_raw) if extracted_at_raw else None

    return StartupAIProfile(
        ai_workload_type=AiWorkloadType(data.get("ai_workload_type", "unknown")),
        model_type=AiModelType(data.get("model_type", "unknown")),
        data_modality=AiDataModality(data.get("data_modality", "unknown")),
        deployment_stage=AiDeploymentStage(data.get("deployment_stage", "unknown")),
        infra_environment=AiInfraEnvironment(data.get("infra_environment", "unknown")),
        gpu_need=AiGpuNeed(data.get("gpu_need", "unknown")),
        latency_requirement=AiLatencyRequirement(
            data.get("latency_requirement", "unknown")
        ),
        scale_signal=data.get("scale_signal"),
        current_tools=tuple(data.get("current_tools") or []),
        business_goal=data.get("business_goal"),
        field_confidence=data.get("field_confidence") or {},
        field_evidence_ids=data.get("field_evidence_ids") or {},
        extracted_at=extracted_at,
    )


class StartupMapper:

    @staticmethod
    def to_model(entity: Startup) -> StartupModel:
        return StartupModel(
            id=entity.id,
            name=entity.name,
            website_url=entity.website_url,
            description=entity.description,
            sector=entity.sector,
            country=entity.country,
            ai_maturity_level=(
                entity.ai_maturity_level.value
                if entity.ai_maturity_level is not None
                else None
            ),
            classification_reason=entity.classification_reason,
            classified_at=entity.classified_at,
            founders=list(entity.founders),
            funding_stage=(
                entity.funding_stage.value if entity.funding_stage is not None else None
            ),
            funding_amount_usd=entity.funding_amount_usd,
            customers=list(entity.customers),
            ai_profile=(
                _profile_to_dict(entity.ai_profile)
                if entity.ai_profile is not None
                else None
            ),
            field_confidence=dict(entity.field_confidence),
            field_evidence_ids=dict(entity.field_evidence_ids),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_entity(model: StartupModel) -> Startup:
        return Startup(
            id=model.id,
            name=model.name,
            website_url=model.website_url,
            description=model.description,
            sector=model.sector,
            country=model.country,
            ai_maturity_level=(
                AiMaturityLevel(model.ai_maturity_level)
                if model.ai_maturity_level is not None
                else None
            ),
            classification_reason=model.classification_reason,
            classified_at=model.classified_at,
            founders=tuple(model.founders),
            funding_stage=(
                FundingStage(model.funding_stage)
                if model.funding_stage is not None
                else None
            ),
            funding_amount_usd=model.funding_amount_usd,
            customers=tuple(model.customers),
            ai_profile=(
                _profile_from_dict(model.ai_profile)
                if model.ai_profile is not None
                else None
            ),
            field_confidence=dict(model.field_confidence or {}),
            field_evidence_ids=dict(model.field_evidence_ids or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def update_model(model: StartupModel, entity: Startup) -> None:
        model.name = entity.name
        model.website_url = entity.website_url
        model.description = entity.description
        model.sector = entity.sector
        model.country = entity.country
        model.ai_maturity_level = (
            entity.ai_maturity_level.value
            if entity.ai_maturity_level is not None
            else None
        )
        model.classification_reason = entity.classification_reason
        model.classified_at = entity.classified_at
        model.founders = list(entity.founders)
        model.funding_stage = (
            entity.funding_stage.value if entity.funding_stage is not None else None
        )
        model.funding_amount_usd = entity.funding_amount_usd
        model.customers = list(entity.customers)
        model.ai_profile = (
            _profile_to_dict(entity.ai_profile)
            if entity.ai_profile is not None
            else None
        )
        model.field_confidence = dict(entity.field_confidence)
        model.field_evidence_ids = dict(entity.field_evidence_ids)
        model.updated_at = entity.updated_at
