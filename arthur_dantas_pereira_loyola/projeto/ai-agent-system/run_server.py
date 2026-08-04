"""Wrapper to start the Radar API server with correct Python path."""
import sys
import logging
from pathlib import Path

_src = str(Path(__file__).resolve().parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

import uvicorn
from radar.api.app import app
from radar.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.info(
        "Modo: %s | Search: %s | Page: %s | LLM: %s",
        settings.provider_mode,
        settings.search_provider,
        settings.page_provider,
        settings.llm_provider,
    )
    if not settings.enable_external_providers:
        logging.warning("Provedores externos desabilitados — usando dados fixture (mock)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
