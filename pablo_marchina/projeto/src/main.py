"""Re-export the API app from src/api/main.py for backward compatibility."""

from src.api.main import app

__all__ = ["app"]
