from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} nao foi definida no arquivo .env")
    return value


def json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} deve conter JSON valido") from exc


PORTAL_URL = os.getenv("STARTUPBASE_PORTAL_URL", "").strip()
API_URL = os.getenv("STARTUPBASE_API_URL", "").strip()
API_METHOD = os.getenv("STARTUPBASE_API_METHOD", "GET").upper()
PAGE_PARAM = os.getenv("STARTUPBASE_PAGE_PARAM", "page")
PAGE_SIZE_PARAM = os.getenv("STARTUPBASE_PAGE_SIZE_PARAM", "limit")
PAGE_SIZE = int(os.getenv("STARTUPBASE_PAGE_SIZE", "100"))
START_PAGE = int(os.getenv("STARTUPBASE_START_PAGE", "1"))
RESULTS_PATH = os.getenv("STARTUPBASE_RESULTS_PATH", "").strip()
TOTAL_PATH = os.getenv("STARTUPBASE_TOTAL_PATH", "").strip()
API_PARAMS = json_env("STARTUPBASE_API_PARAMS", {})
API_BODY = json_env("STARTUPBASE_API_BODY", {})
LOGIN_EMAIL = os.getenv("STARTUPBASE_EMAIL", "").strip()
LOGIN_PASSWORD = os.getenv("STARTUPBASE_PASSWORD", "").strip()
LOGIN_EMAIL_SELECTOR = os.getenv("STARTUPBASE_EMAIL_SELECTOR", 'input[type="email"]')
LOGIN_PASSWORD_SELECTOR = os.getenv("STARTUPBASE_PASSWORD_SELECTOR", 'input[type="password"]')
LOGIN_SUBMIT_SELECTOR = os.getenv("STARTUPBASE_SUBMIT_SELECTOR", 'button[type="submit"]')
LOGIN_SUCCESS_URL = os.getenv("STARTUPBASE_LOGIN_SUCCESS_URL", "").strip()
HTTP_TIMEOUT = float(os.getenv("STARTUPBASE_HTTP_TIMEOUT", "30"))
MAX_PAGES = int(os.getenv("STARTUPBASE_MAX_PAGES", "10000"))
