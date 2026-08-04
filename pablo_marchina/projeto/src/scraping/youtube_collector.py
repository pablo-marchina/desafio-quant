"""YouTube transcript collector.

Fetches captions/transcripts for a given video ID or playlist.
Uses ``youtube_transcript_api`` under the hood.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from src.scraping.strategies import register

logger = logging.getLogger(__name__)


@dataclass
class YouTubeTranscriptResult:
    video_id: str
    title: str | None
    snippets: list[dict[str, float | str]] = field(default_factory=list)
    full_text: str = ""
    language: str = "en"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


def extract_video_id(url: str) -> str | None:
    """Parse a YouTube URL and return the video ID, or ``None``."""
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("?")[0]
    if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("?")[0]
    return None


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en", "pt")) -> YouTubeTranscriptResult:
    """Fetch transcript for a single video.

    Tries the requested languages in order; falls back to any available.
    """
    result = YouTubeTranscriptResult(video_id=video_id, title=None)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                result.language = lang
                break
            except NoTranscriptFound:
                continue

        if transcript is None:
            try:
                transcript = transcript_list.find_transcript(["en"])
                result.language = "en"
            except NoTranscriptFound:
                try:
                    transcript = transcript_list.find_generated_transcript(["en"])
                    result.language = "en"
                except NoTranscriptFound:
                    result.error = f"No transcript available for {video_id}"
                    return result

        snippets = transcript.fetch()
        result.snippets = [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in snippets
        ]
        result.full_text = " ".join(s["text"] for s in result.snippets)  # type: ignore[typeddict-item]
        logger.info("YOUTUBE_OK  video=%s  lang=%s  segments=%d", video_id, result.language, len(result.snippets))

    except TranscriptsDisabled:
        result.error = f"Transcripts disabled for {video_id}"
    except VideoUnavailable:
        result.error = f"Video unavailable: {video_id}"
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def fetch_playlist(playlist_id: str, languages: tuple[str, ...] = ("en", "pt")) -> list[YouTubeTranscriptResult]:
    """Fetch transcripts for all videos in a playlist (pagination best-effort).

    Uses the public YouTube playlist page; this is inherently fragile.
    For production, prefer the YouTube Data API v3.
    """
    results: list[YouTubeTranscriptResult] = []
    try:
        from youtube_transcript_api._playlists import Playlist  # type: ignore[attr-defined]

        playlist = Playlist(f"https://www.youtube.com/playlist?list={playlist_id}")
        for video_id in playlist.video_ids:
            result = fetch_transcript(video_id, languages=languages)
            if result.full_text:
                results.append(result)
    except Exception as exc:
        logger.warning("YOUTUBE_PLAYLIST_ERR  playlist=%s  %s", playlist_id, exc)
    return results


@register("youtube")
def collect_youtube(source) -> YouTubeTranscriptResult | None:
    from src.scraping.source_registry import SourceRecord

    if not isinstance(source, SourceRecord):
        return None

    video_id = extract_video_id(source.base_url)
    if video_id is None:
        logger.warning("YOUTUBE_SKIP  no video_id in %s", source.base_url)
        return None

    return fetch_transcript(video_id, languages=("en", "pt"))
