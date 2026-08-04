from __future__ import annotations

import re
from dataclasses import dataclass

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|system|developer)\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?(system prompt|developer message|hidden instructions)", re.IGNORECASE),
    re.compile(r"(print|show|display|repeat|reveal)\s+(the\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(
        r"(send|post|upload|exfiltrate|leak|dump)\s+(the\s+)?(api[_ -]?key|secret|token|password)",
        re.IGNORECASE,
    ),
    re.compile(r"call\s+tool|execute\s+(shell|powershell|bash)|run\s+command", re.IGNORECASE),
    re.compile(r"rank\s+.*because\s+.*paid\s+partnership|manipulate\s+recommendation", re.IGNORECASE),
)

UNTRUSTED_CONTENT_PATTERNS = (
    re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*(iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bon\w+\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
)

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_\-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)


@dataclass(frozen=True)
class SecurityFinding:
    finding_type: str
    matched: str
    action: str


def detect_prompt_injection(text: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(
                SecurityFinding(
                    finding_type="prompt_injection",
                    matched=match.group(0),
                    action="quarantine_external_instruction",
                )
            )
    return findings


def detect_secret_leakage(text: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                SecurityFinding(
                    finding_type="secret_leakage",
                    matched=match.group(0),
                    action="block_and_redact",
                )
            )
    return findings


def detect_untrusted_active_content(text: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for pattern in UNTRUSTED_CONTENT_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                SecurityFinding(
                    finding_type="untrusted_active_content",
                    matched=match.group(0),
                    action="strip_untrusted_active_content",
                )
            )
    return findings


def sanitize_untrusted_rag_context(text: str) -> tuple[str, list[SecurityFinding]]:
    findings = detect_prompt_injection(text) + detect_secret_leakage(text) + detect_untrusted_active_content(text)
    sanitized = text
    for finding in findings:
        sanitized = sanitized.replace(finding.matched, "[BLOCKED_UNTRUSTED_CONTENT]")
    return sanitized, findings


def assert_tool_request_allowed(tool_name: str, allowed_tools: set[str]) -> bool:
    normalized = tool_name.strip().casefold()
    return normalized in {tool.casefold() for tool in allowed_tools}
