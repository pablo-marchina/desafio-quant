from __future__ import annotations

from radar.schemas.base import RadarModel


class ContactSource(RadarModel):
    source_url: str
    found_at: str


class ContactEntry(RadarModel):
    value: str
    confidence: float
    sources: list[ContactSource]


class CompanyContact(RadarModel):
    startup_id: str
    startup_name: str
    emails: list[ContactEntry]
    phones: list[ContactEntry]
    linkedin_urls: list[ContactEntry]
    addresses: list[ContactEntry]
    primary_name: str | None = None
    primary_role: str | None = None
    raw_text_snippets: list[str]
    collected_at: str | None = None
