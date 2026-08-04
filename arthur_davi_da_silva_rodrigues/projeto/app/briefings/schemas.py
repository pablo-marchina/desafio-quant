from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutiveBriefingDraft:
    title: str
    markdown: str
    source_urls: tuple[str, ...]
