from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx

from . import config

LIST_KEYS = ("data", "results", "items", "startups", "companies", "content", "rows")
TOTAL_KEYS = ("total", "totalCount", "total_count", "count", "recordsTotal")


def _pick(row: Mapping[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, "", []):
            return value
    return None


def _scalar(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = _pick(value, "name", "nome", "label", "title", "value")
    if isinstance(value, list):
        return ", ".join(filter(None, (_scalar(item) for item in value))) or None
    return str(value).strip() if value not in (None, "") else None


def _founding_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    match = re.search(r"(?:19|20)\d{2}", text)
    if not match:
        return None
    if re.fullmatch(r"(?:19|20)\d{2}", text):
        return f"{text}-01-01"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return f"{match.group(0)}-01-01"


def normalize_startup(row: Mapping[str, Any]) -> dict[str, Any] | None:
    name = _scalar(_pick(row, "name", "nome", "company_name", "companyName", "trade_name", "fantasyName"))
    if not name:
        return None
    description = _scalar(_pick(row, "description", "descricao", "summary", "about", "pitch"))
    segment = _scalar(_pick(row, "segment", "segmento", "sector", "setor", "industry", "category", "vertical"))
    stage = _scalar(_pick(row, "stage", "estagio", "maturity", "maturidade", "startupStage"))
    location = _scalar(_pick(row, "location", "localizacao", "city", "cidade", "address", "state", "estado"))
    founding_date = _founding_date(_pick(row, "founded_at", "foundation_date", "founding_date", "data_fundacao", "founded", "foundationYear", "ano_fundacao"))
    remote_id = _scalar(_pick(row, "id", "_id", "uuid", "startup_id", "startupId", "slug"))
    source_url = _scalar(_pick(row, "source_url", "profile_url", "url", "website", "site", "homepage"))
    identity = remote_id or f"{name.lower()}|{(location or '').lower()}"
    return {
        "startupbase_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "remote_id": remote_id,
        "name": name,
        "company_name": name,
        "description": description,
        "segment": segment,
        "stage": stage,
        "location": location,
        "founding_date": founding_date,
        "source_url": source_url,
        "source_name": "StartupBase",
        "raw_data": dict(row),
    }


def _at_path(payload: Any, path: str) -> Any:
    current = payload
    for part in filter(None, path.split(".")):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _find_rows(payload: Any, configured_path: str = "") -> list[dict[str, Any]]:
    if configured_path:
        value = _at_path(payload, configured_path)
        return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in LIST_KEYS:
            if key in payload:
                found = _find_rows(payload[key])
                if found or isinstance(payload[key], list):
                    return found
        for value in payload.values():
            if isinstance(value, dict):
                found = _find_rows(value)
                if found:
                    return found
    return []


def _find_total(payload: Any, configured_path: str = "") -> int | None:
    if configured_path:
        value = _at_path(payload, configured_path)
        return int(value)
    if isinstance(payload, dict):
        for key in TOTAL_KEYS:
            if key in payload and isinstance(payload[key], (int, float, str)):
                try:
                    return int(payload[key])
                except ValueError:
                    pass
        for value in payload.values():
            if isinstance(value, dict):
                total = _find_total(value)
                if total is not None:
                    return total
    return None


def _looks_like_startup_response(payload: Any) -> bool:
    rows = _find_rows(payload)
    if not rows:
        return False
    keys = {str(key).lower() for row in rows[:5] for key in row}
    return bool(keys & {"name", "nome", "companyname", "description", "descricao", "segmento", "industry"})


class StartupBaseClient:
    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=config.HTTP_TIMEOUT, follow_redirects=True)
        self.api_url = config.API_URL
        self.method = config.API_METHOD
        self.params = dict(config.API_PARAMS)
        self.body = dict(config.API_BODY)

    def discover_session(self) -> None:
        """Observe JSON traffic in a real browser and transfer auth to httpx."""
        if not config.PORTAL_URL:
            raise RuntimeError("Defina STARTUPBASE_PORTAL_URL para descobrir a API")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Instale Playwright e execute: playwright install chromium") from exc

        candidates: list[dict[str, Any]] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            def inspect(response) -> None:
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type:
                    return
                try:
                    payload = response.json()
                except Exception:
                    return
                if _looks_like_startup_response(payload):
                    request = response.request
                    try:
                        post_data = request.post_data_json if request.post_data else {}
                    except Exception:
                        post_data = {}
                    candidates.append({"url": response.url, "method": request.method, "headers": request.all_headers(), "body": post_data, "payload": payload})

            page.on("response", inspect)
            page.goto(config.PORTAL_URL, wait_until="domcontentloaded")
            if config.LOGIN_EMAIL and config.LOGIN_PASSWORD:
                page.locator(config.LOGIN_EMAIL_SELECTOR).fill(config.LOGIN_EMAIL)
                page.locator(config.LOGIN_PASSWORD_SELECTOR).fill(config.LOGIN_PASSWORD)
                page.locator(config.LOGIN_SUBMIT_SELECTOR).click()
                page.wait_for_load_state("networkidle")
                if config.LOGIN_SUCCESS_URL:
                    page.wait_for_url(re.compile(config.LOGIN_SUCCESS_URL))
            else:
                page.wait_for_timeout(3000)
            page.reload(wait_until="networkidle")
            cookies = context.cookies()
            browser.close()

        if not candidates:
            raise RuntimeError("Nenhuma resposta JSON com startups foi observada; navegue para a listagem ou defina STARTUPBASE_API_URL")
        candidate = candidates[-1]
        parsed = urlsplit(candidate["url"])
        self.api_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        self.method = candidate["method"]
        self.params.update(dict(parse_qsl(parsed.query, keep_blank_values=True)))
        if isinstance(candidate["body"], dict):
            self.body.update(candidate["body"])
        self.client.cookies.update({cookie["name"]: cookie["value"] for cookie in cookies})
        for name, value in candidate["headers"].items():
            if name.lower() in {"authorization", "x-api-key", "x-csrf-token", "accept", "content-type"}:
                self.client.headers[name] = value

    def _request_page(self, page: int) -> tuple[list[dict[str, Any]], int | None]:
        if not self.api_url:
            self.discover_session()
        params = dict(self.params)
        body = dict(self.body)
        target = params if self.method == "GET" else body
        target[config.PAGE_PARAM] = page
        target[config.PAGE_SIZE_PARAM] = config.PAGE_SIZE
        response = self.client.request(self.method, self.api_url, params=params, json=body if self.method != "GET" else None)
        response.raise_for_status()
        payload = response.json()
        return _find_rows(payload, config.RESULTS_PATH), _find_total(payload, config.TOTAL_PATH)

    def iter_startups(self) -> Iterator[dict[str, Any]]:
        seen: set[str] = set()
        collected = 0
        for page in range(config.START_PAGE, config.START_PAGE + config.MAX_PAGES):
            rows, total = self._request_page(page)
            if not rows:
                return
            new_on_page = 0
            for raw in rows:
                normalized = normalize_startup(raw)
                if normalized and normalized["startupbase_id"] not in seen:
                    seen.add(normalized["startupbase_id"])
                    collected += 1
                    new_on_page += 1
                    yield normalized
            if (total is not None and collected >= total) or len(rows) < config.PAGE_SIZE or new_on_page == 0:
                return
        raise RuntimeError(f"STARTUPBASE_MAX_PAGES ({config.MAX_PAGES}) atingido; revise a paginacao")
