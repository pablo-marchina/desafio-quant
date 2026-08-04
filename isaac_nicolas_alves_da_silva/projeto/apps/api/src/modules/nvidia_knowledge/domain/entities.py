"""Entidades do dominio do modulo NVIDIA Knowledge."""

from dataclasses import dataclass, field

from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaKnowledgeSourceType,
    NvidiaTechnologyCategory,
)


def _normalize_slug(value: str) -> str:
    return value.strip().lower()


@dataclass(frozen=True)
class NvidiaTechnology:
    """Tecnologia NVIDIA disponivel para recomendacao futura."""

    slug: str
    name: str
    category: NvidiaTechnologyCategory
    description: str
    use_cases: tuple[str, ...]
    keywords: tuple[str, ...]
    official_url: str
    complexity: str = "medium"
    supported_workloads: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "slug", _normalize_slug(self.slug))
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(
            self,
            "use_cases",
            tuple(item.strip() for item in self.use_cases if item.strip()),
        )
        object.__setattr__(
            self,
            "keywords",
            tuple(item.strip().lower() for item in self.keywords if item.strip()),
        )
        object.__setattr__(self, "official_url", self.official_url.strip())

        if not self.slug:
            raise ValueError("Tecnologia NVIDIA precisa ter slug.")
        if not self.name:
            raise ValueError("Tecnologia NVIDIA precisa ter nome.")
        if not self.description:
            raise ValueError("Tecnologia NVIDIA precisa ter descricao.")
        if not self.use_cases:
            raise ValueError("Tecnologia NVIDIA precisa ter casos de uso.")
        if not self.official_url:
            raise ValueError("Tecnologia NVIDIA precisa ter fonte oficial.")

    def matches_query(self, query: str) -> bool:
        """Retorna True quando a query aparece em campos pesquisaveis."""

        normalized_query = query.strip().lower()
        if not normalized_query:
            return True

        searchable_text = " ".join(
            [
                self.slug,
                self.name.lower(),
                self.category.value,
                self.description.lower(),
                " ".join(self.use_cases).lower(),
                " ".join(self.keywords),
            ]
        )
        return normalized_query in searchable_text


@dataclass(frozen=True)
class NvidiaKnowledgeSource:
    """Fonte planejada para ingestao da base NVIDIA Knowledge V2."""

    slug: str
    title: str
    url: str
    source_type: NvidiaKnowledgeSourceType
    priority: NvidiaKnowledgeSourcePriority
    technology_slug: str | None
    description: str
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "slug", _normalize_slug(self.slug))
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "url", self.url.strip())
        object.__setattr__(
            self,
            "technology_slug",
            _normalize_slug(self.technology_slug) if self.technology_slug else None,
        )
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(
            self,
            "tags",
            tuple(item.strip().lower() for item in self.tags if item.strip()),
        )

        if not self.slug:
            raise ValueError("Fonte NVIDIA precisa ter slug.")
        if not self.title:
            raise ValueError("Fonte NVIDIA precisa ter titulo.")
        if not self.url.startswith("https://"):
            raise ValueError("Fonte NVIDIA precisa ter URL HTTPS.")
        if not self.description:
            raise ValueError("Fonte NVIDIA precisa ter descricao.")
        if not self.tags:
            raise ValueError("Fonte NVIDIA precisa ter tags.")

    def matches_query(self, query: str) -> bool:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return True

        searchable_text = " ".join(
            [
                self.slug,
                self.title.lower(),
                self.url.lower(),
                self.source_type.value,
                self.priority.value,
                self.technology_slug or "",
                self.description.lower(),
                " ".join(self.tags),
            ]
        )
        return normalized_query in searchable_text
