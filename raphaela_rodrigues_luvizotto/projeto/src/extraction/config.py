from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

EXTRACTION_PROVIDER = os.environ.get("EXTRACTION_PROVIDER", "heuristic").strip().lower()
EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL") or os.environ.get(
    "GROQ_MODEL", "llama-3.3-70b-versatile"
)
EXTRACTION_MAX_EVIDENCES = int(os.environ.get("EXTRACTION_MAX_EVIDENCES", 4))
EXTRACTION_MAX_CHARS_PER_EVIDENCE = int(
    os.environ.get("EXTRACTION_MAX_CHARS_PER_EVIDENCE", 1800)
)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
