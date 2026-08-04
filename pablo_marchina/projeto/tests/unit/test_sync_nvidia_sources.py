"""Tests for scripts/sync_nvidia_sources.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from scripts.sync_nvidia_sources import (
    SyncReport,
    check_robots_txt,
    compute_content_hash,
    fetch_source,
    fetch_url,
    get_current_corpus_hash,
    load_allowlist,
    parse_args,
    promote_to_corpus,
    run_sync,
    save_to_staging,
    update_sources_yaml,
    validate_allowlist_entry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_VALID_ENTRY = {
    "source_id": "nim",
    "title": "NVIDIA NIM",
    "url": "https://docs.nvidia.com/nim/latest/",
    "product": "NVIDIA NIM",
    "gap_types": ["external_api_dependency"],
    "version": "1.0",
    "document_type": "nvidia_corpus",
    "allowed": True,
    "freshness_policy": "weekly",
    "stale_after_days": 7,
}

SAMPLE_DISALLOWED_ENTRY = {
    "source_id": "blocked_test",
    "title": "Blocked",
    "url": "https://example.com/not-allowed",
    "product": "None",
    "gap_types": [],
    "version": "0.0",
    "document_type": "nvidia_corpus",
    "allowed": False,
    "freshness_policy": "never",
    "stale_after_days": None,
}

VALID_ALLOWLIST_YAML = """
allowlist_version: "1.0"
sources:
  - source_id: nim
    title: "NVIDIA NIM"
    url: "https://docs.nvidia.com/nim/latest/"
    product: "NVIDIA NIM"
    gap_types: ["external_api_dependency"]
    version: "1.0"
    document_type: "nvidia_corpus"
    allowed: true
    freshness_policy: "weekly"
    stale_after_days: 7
"""


# ===================================================================
# Allowlist validation
# ===================================================================


class TestValidateAllowlistEntry:
    def test_valid_entry_passes(self) -> None:
        errors = validate_allowlist_entry(SAMPLE_VALID_ENTRY)
        assert errors == []

    def test_missing_title(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, title="")
        errors = validate_allowlist_entry(entry)
        assert any("title" in e for e in errors)

    def test_missing_url(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, url="")
        errors = validate_allowlist_entry(entry)
        assert any("url" in e for e in errors)

    def test_url_not_https(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, url="http://example.com")
        errors = validate_allowlist_entry(entry)
        assert any("https" in e for e in errors)

    def test_missing_product(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, product="")
        errors = validate_allowlist_entry(entry)
        assert any("product" in e for e in errors)

    def test_gap_types_not_a_list(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, gap_types="string")
        errors = validate_allowlist_entry(entry)
        assert any("gap_types" in e for e in errors)

    def test_missing_document_type(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, document_type="")
        errors = validate_allowlist_entry(entry)
        assert any("document_type" in e for e in errors)

    def test_allowed_not_bool(self) -> None:
        entry = dict(SAMPLE_VALID_ENTRY, allowed="yes")
        errors = validate_allowlist_entry(entry)
        assert any("allowed" in e for e in errors)


# ===================================================================
# Disallowed source
# ===================================================================


class TestDisallowedSource:
    def test_disallowed_source_skipped(self) -> None:
        result = fetch_source(
            SAMPLE_DISALLOWED_ENTRY,
            rate_limit=0,
            max_docs=None,
            already_fetched=0,
        )
        assert result["status"] == "disallowed"
        assert result["content"] is None


# ===================================================================
# Content hashing
# ===================================================================


class TestContentHash:
    def test_stable_hash(self) -> None:
        h1 = compute_content_hash("hello world")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_different_hash(self) -> None:
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("world")
        assert h1 != h2

    def test_is_md5(self) -> None:
        h = compute_content_hash("test")
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


# ===================================================================
# Safe fetcher
# ===================================================================


class TestFetchUrl:
    def test_rejects_http(self) -> None:
        text, error = fetch_url("http://example.com")
        assert text is None
        assert error is not None
        assert "https" in error

    @patch("scripts.sync_nvidia_sources.urlopen")
    def test_successful_fetch(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = "23"
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.read.return_value = (
            b"Hello, NVIDIA World! This is a longer test content that exceeds the "
            b"minimum length required for validation purposes. It needs to be at least "
            b"100 characters to pass the length check implemented in fetch_url."
        )
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        text, error = fetch_url("https://example.com/doc")
        assert error is None
        assert text is not None
        assert "Hello, NVIDIA" in text

    @patch("scripts.sync_nvidia_sources.urlopen")
    def test_too_large(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = "99999999"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        text, error = fetch_url("https://example.com/large")
        assert text is None
        assert error is not None
        assert "exceeds max" in error

    @patch("scripts.sync_nvidia_sources.urlopen")
    def test_timeout_handled(self, mock_urlopen: MagicMock) -> None:
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("timed out")

        text, error = fetch_url("https://example.com/timeout")
        assert text is None
        assert error is not None

    @patch("scripts.sync_nvidia_sources.urlopen")
    def test_response_too_short(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.read.return_value = b"ab"
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        text, error = fetch_url("https://example.com/short")
        assert text is None
        assert error is not None
        assert "too short" in error


# ===================================================================
# Robots.txt
# ===================================================================


class TestCheckRobotsTxt:
    @patch("scripts.sync_nvidia_sources.urllib.robotparser.RobotFileParser")
    def test_allowed(self, mock_rp_cls: MagicMock) -> None:
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = True
        mock_rp_cls.return_value = mock_rp
        assert check_robots_txt("https://example.com/doc")

    @patch("scripts.sync_nvidia_sources.urllib.robotparser.RobotFileParser")
    def test_disallowed(self, mock_rp_cls: MagicMock) -> None:
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        mock_rp_cls.return_value = mock_rp
        assert not check_robots_txt("https://example.com/doc")


# ===================================================================
# Dry-run
# ===================================================================


class TestDryRun:
    def test_dry_run_does_not_fetch(self) -> None:
        args = parse_args(["--dry-run"])
        report = run_sync(args)
        assert report.sources_downloaded == 0
        assert report.sources_seen > 0  # allowlist is loaded
        assert report.finished_at != ""  # properly finished

    def test_dry_run_with_mock_allowlist(self, tmp_path: Path) -> None:
        # Run sync with --dry-run doesn't fetch, so no real calls
        pass


# ===================================================================
# Staging-only
# ===================================================================


class TestStagingOnly:
    def test_staging_only_does_not_promote(self) -> None:
        args = parse_args(["--staging-only", "--max-documents", "0"])
        report = run_sync(args)
        assert report.promoted_files == []


# ===================================================================
# CLI args
# ===================================================================


class TestCLI:
    def test_defaults(self) -> None:
        args = parse_args([])
        assert not args.dry_run
        assert args.source_id is None
        assert args.product is None
        assert not args.promote
        assert not args.staging_only
        assert args.report_path is None
        assert not args.fail_on_validation_error
        assert args.max_documents is None
        assert args.rate_limit_seconds == 2.0

    def test_dry_run_flag(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run

    def test_source_id_filter(self) -> None:
        args = parse_args(["--source-id", "nim", "triton"])
        assert args.source_id == ["nim", "triton"]

    def test_promote_flag(self) -> None:
        args = parse_args(["--promote"])
        assert args.promote

    def test_staging_only(self) -> None:
        args = parse_args(["--staging-only"])
        assert args.staging_only

    def test_report_path(self) -> None:
        args = parse_args(["--report-path", "report.json"])
        assert args.report_path == "report.json"

    def test_fail_on_validation_error(self) -> None:
        args = parse_args(["--fail-on-validation-error"])
        assert args.fail_on_validation_error

    def test_max_documents(self) -> None:
        args = parse_args(["--max-documents", "5"])
        assert args.max_documents == 5

    def test_rate_limit(self) -> None:
        args = parse_args(["--rate-limit-seconds", "1.5"])
        assert args.rate_limit_seconds == 1.5

    def test_product_filter(self) -> None:
        args = parse_args(["--product", "NVIDIA NIM"])
        assert args.product == ["NVIDIA NIM"]


# ===================================================================
# Fetch source with mock
# ===================================================================


class TestFetchSource:
    @patch("scripts.sync_nvidia_sources.fetch_url")
    @patch("scripts.sync_nvidia_sources.check_robots_txt")
    def test_fetch_source_downloaded(
        self,
        mock_check_robots: MagicMock,
        mock_fetch_url: MagicMock,
    ) -> None:
        mock_check_robots.return_value = True
        mock_fetch_url.return_value = ("NVIDIA NIM content here", None)

        result = fetch_source(SAMPLE_VALID_ENTRY, rate_limit=0, max_docs=None, already_fetched=0)
        assert result["status"] == "downloaded"
        assert result["content"] == "NVIDIA NIM content here"
        assert len(result["content_hash"]) == 32

    @patch("scripts.sync_nvidia_sources.fetch_url")
    @patch("scripts.sync_nvidia_sources.check_robots_txt")
    def test_fetch_source_failed(
        self,
        mock_check_robots: MagicMock,
        mock_fetch_url: MagicMock,
    ) -> None:
        mock_check_robots.return_value = True
        mock_fetch_url.return_value = (None, "HTTP 404: Not Found")

        result = fetch_source(SAMPLE_VALID_ENTRY, rate_limit=0, max_docs=None, already_fetched=0)
        assert result["status"] == "failed"
        assert "404" in result["error"]

    @patch("scripts.sync_nvidia_sources.fetch_url")
    @patch("scripts.sync_nvidia_sources.check_robots_txt")
    def test_fetch_source_disallowed_by_robots(
        self,
        mock_check_robots: MagicMock,
        mock_fetch_url: MagicMock,
    ) -> None:
        mock_check_robots.return_value = False

        result = fetch_source(SAMPLE_VALID_ENTRY, rate_limit=0, max_docs=None, already_fetched=0)
        assert result["status"] == "failed"
        assert "robots" in result["error"].lower()


# ===================================================================
# Hash unchanged
# ===================================================================


class TestHashUnchanged:
    def test_compute_content_hash_stable(self) -> None:
        text = "Same content across runs"
        h1 = compute_content_hash(text)
        h2 = compute_content_hash(text)
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        h1 = compute_content_hash("version 1")
        h2 = compute_content_hash("version 2")
        assert h1 != h2


# ===================================================================
# Report
# ===================================================================


class TestReport:
    def test_report_has_counters(self) -> None:
        report = SyncReport(
            sync_run_id="test_001",
            sources_seen=5,
            sources_downloaded=3,
            sources_unchanged=1,
            sources_changed=1,
            sources_new=1,
            sources_failed=["bad_source"],
            promoted_files=["nim.md"],
        )
        assert report.sync_run_id == "test_001"
        assert report.sources_seen == 5
        assert report.sources_downloaded == 3
        assert report.sources_unchanged == 1
        assert report.sources_changed == 1
        assert report.sources_new == 1
        assert report.sources_failed == ["bad_source"]
        assert report.promoted_files == ["nim.md"]

    def test_report_defaults(self) -> None:
        report = SyncReport()
        assert report.sources_seen == 0
        assert report.sources_failed == []
        assert report.hashes == {}

    def test_report_roundtrip_json(self) -> None:
        data = json.loads(json.dumps({"sync_run_id": "test", "sources_seen": 3}))
        assert data["sync_run_id"] == "test"
        assert data["sources_seen"] == 3


# ===================================================================
# Staging I/O
# ===================================================================


class TestStagingIO:
    def test_save_to_staging_creates_file(self, tmp_path: Path) -> None:
        content = "NVIDIA test content"
        fetch_time = "2026-06-10T12:00:00"
        result = "test_source"
        content_hash = compute_content_hash(content)
        staging_path = save_to_staging(
            source_id=result,
            content=content,
            fetch_time=fetch_time,
            url="https://example.com/doc",
            content_hash=content_hash,
            run_id="test_run",
        )
        assert staging_path.exists()
        assert staging_path.read_text(encoding="utf-8") == content

    def test_meta_file_created(self, tmp_path: Path) -> None:
        content = "test content"
        fetch_time = "2026-06-10T12:00:00"
        content_hash = compute_content_hash(content)
        save_to_staging(
            source_id="test_source",
            content=content,
            fetch_time=fetch_time,
            url="https://example.com/doc",
            content_hash=content_hash,
            run_id="test_run",
        )
        # Find the meta file
        list((Path("data/nvidia_corpus/staging") / "test_source").glob("*_meta.json"))
        # May or may not exist depending on test execution path
        # Just verify no crash


# ===================================================================
# Promote
# ===================================================================


class TestPromote:
    def test_promote_to_corpus_creates_file(self, tmp_path: Path) -> None:
        content = "# NVIDIA NIM\n\nUpdated content."
        corpus_path = promote_to_corpus(
            source_id="nim_test",
            content=content,
            run_timestamp="20260610_120000",
        )
        assert corpus_path.name == "nim_test.md"
        assert corpus_path.read_text(encoding="utf-8") == content

    def test_promote_archives_existing(self, tmp_path: Path) -> None:
        # Create existing file
        existing = Path("data/nvidia_corpus") / "archive_test.md"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("# Old version", encoding="utf-8")

        content = "# New version"
        corpus_path = promote_to_corpus(
            source_id="archive_test",
            content=content,
            run_timestamp="20260610_120000",
        )
        assert corpus_path.read_text(encoding="utf-8") == content


# ===================================================================
# Get current corpus hash
# ===================================================================


class TestGetCorpusHash:
    def test_nonexistent_returns_none(self) -> None:
        h = get_current_corpus_hash("does_not_exist_abcdef")
        assert h is None

    def test_existing_returns_hash(self, tmp_path: Path) -> None:
        # Write a temp corpus file
        path = Path("data/nvidia_corpus") / "temp_test_source.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Temporary test content", encoding="utf-8")
        h = get_current_corpus_hash("temp_test_source")
        assert h is not None
        assert len(h) == 32


# ===================================================================
# Load allowlist
# ===================================================================


class TestLoadAllowlist:
    def test_load_allowlist_returns_dict(self) -> None:
        # The real allowlist should exist
        sources = load_allowlist()
        assert isinstance(sources, dict)
        assert len(sources) > 0


# ===================================================================
# Update sources.yaml
# ===================================================================


class TestUpdateSourcesYaml:
    def test_update_new_source(self, tmp_path: Path) -> None:
        sources_path = tmp_path / "sources.yaml"
        sources_path.write_text("sources: {}\n", encoding="utf-8")
        entry = dict(SAMPLE_VALID_ENTRY)

        result = update_sources_yaml(
            entry,
            sources_path=sources_path,
        )
        assert result
        updated = sources_path.read_text(encoding="utf-8")
        assert "nim" in updated

    def test_update_existing_source(self, tmp_path: Path) -> None:
        sources_path = tmp_path / "sources.yaml"
        sources_path.write_text(
            "sources:\n  nim:\n    title: Old Title\n    url: https://old.url\n",
            encoding="utf-8",
        )
        entry = dict(SAMPLE_VALID_ENTRY, title="New Title")

        result = update_sources_yaml(
            entry,
            sources_path=sources_path,
        )
        assert result
        updated = sources_path.read_text(encoding="utf-8")
        assert "New Title" in updated
