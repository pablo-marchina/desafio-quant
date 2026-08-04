from __future__ import annotations

from src.security.llm_security import detect_secret_leakage, sanitize_untrusted_rag_context


def test_secret_leakage_is_detected_and_redacted() -> None:
    text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"

    findings = detect_secret_leakage(text)
    sanitized, _ = sanitize_untrusted_rag_context(text)

    assert findings
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in sanitized
