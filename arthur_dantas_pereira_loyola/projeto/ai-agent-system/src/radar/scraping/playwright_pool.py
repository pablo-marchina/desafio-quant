from __future__ import annotations

import logging
import threading
from typing import Any

_POOL: PlaywrightPool | None = None
_lock = threading.Lock()
_tls = threading.local()


class PlaywrightPool:
    """Thread-safe pool of reusable Playwright browser instances.

    Each thread gets its own dedicated browser, avoiding Playwright's
    restriction that browser objects cannot be shared across threads.
    A new browser is launched lazily per thread on first ``acquire()``.
    """

    def __init__(self) -> None:
        self._closed = False
        self._created: dict[int, int] = {}
        self._log = logging.getLogger("radar.pool")

    def _new_browser(self) -> Any:
        from playwright.sync_api import sync_playwright

        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        tid = threading.get_ident()
        count = self._created.get(tid, 0) + 1
        self._created[tid] = count
        self._log.info("Playwright browser #%d for thread %d launched", count, tid)
        return browser

    def acquire(self) -> Any:
        if self._closed:
            raise RuntimeError("PlaywrightPool is closed")
        browser = getattr(_tls, "_playwright_browser", None)
        if browser is not None and browser.is_connected():
            return browser
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        browser = self._new_browser()
        _tls._playwright_browser = browser
        return browser

    def release(self, browser: Any) -> None:
        pass

    def warmup(self) -> None:
        self._log.info("PlaywrightPool warmup skipped — per-thread lazy init.")

    def close(self) -> None:
        self._closed = True

    def close_thread_browsers(self) -> None:
        browser = getattr(_tls, "_playwright_browser", None)
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
            _tls._playwright_browser = None

    def size(self) -> int:
        return 0


def get_pool() -> PlaywrightPool:
    global _POOL
    if _POOL is None:
        with _lock:
            if _POOL is None:
                _POOL = PlaywrightPool()
    return _POOL


def warmup_pool() -> PlaywrightPool:
    pool = get_pool()
    pool.warmup()
    return pool


def close_pool() -> None:
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None
