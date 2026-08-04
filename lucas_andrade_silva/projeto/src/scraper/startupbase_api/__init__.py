"""StartupBase API discovery, extraction and Supabase loading pipeline."""

from .client import StartupBaseClient, normalize_startup

__all__ = ["StartupBaseClient", "normalize_startup"]
