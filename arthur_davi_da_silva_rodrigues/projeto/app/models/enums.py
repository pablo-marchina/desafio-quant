from enum import StrEnum


class AiMaturityLabel(StrEnum):
    AI_NATIVE = "ai_native"
    AI_ENABLED = "ai_enabled"
    NON_AI = "non_ai"


class ClaimValidationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class RecommendationPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImplementationComplexity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceType(StrEnum):
    OFFICIAL_SITE = "official_site"
    BLOG = "blog"
    CAREERS = "careers"
    NEWS = "news"
    DIRECTORY = "directory"
    FOUNDER_PROFILE = "founder_profile"
    NVIDIA_DOC = "nvidia_doc"
    OTHER = "other"


class WorkflowRunType(StrEnum):
    DISCOVERY = "discovery"
    ANALYZE_URL = "analyze_url"


class WorkflowRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
