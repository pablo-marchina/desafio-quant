"""Structured Output Reliability Layer — adapter comum para parsing, validacao,
reparo e rastreamento de outputs estruturados.

Pydantic é o contrato principal. A camada responde:
- Qual schema o output deveria seguir?
- O output validou?
- Quais campos falharam?
- Houve retry?
- O retry corrigiu?
- O output final foi persistido?
- A falha virou degraded/readiness check?
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

OutputStatus = Literal["valid", "invalid", "repaired", "failed", "skipped"]


class ValidationErrorDetail(BaseModel):
    field: str
    error_type: str
    message: str
    input_value: Any = None


@dataclass
class StructuredOutputResult:
    output_type: str
    schema_name: str
    status: OutputStatus
    parsed_object: dict[str, Any] | None = None
    raw_output: str | None = None
    validation_errors: list[ValidationErrorDetail] = field(default_factory=list)
    retry_count: int = 0
    repaired: bool = False
    provider: str | None = None
    model_name: str | None = None
    latency_ms: float | None = None
    token_usage_json: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.status in ("valid", "repaired")

    @property
    def raw_output_hash(self) -> str | None:
        if self.raw_output is None:
            return None
        return hashlib.sha256(self.raw_output.encode("utf-8")).hexdigest()

    @property
    def raw_output_preview(self) -> str | None:
        if self.raw_output is None:
            return None
        if len(self.raw_output) <= 200:
            return self.raw_output
        return self.raw_output[:100] + "..." + self.raw_output[-97:]


def parse_json_output(raw_text: str) -> dict[str, Any] | None:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    try:
        result = json.loads(raw_text)
        if isinstance(result, dict):
            return result
        return None
    except json.JSONDecodeError:
        return None


def repair_json_if_safe(raw_text: str) -> dict[str, Any] | None:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
        return None
    except json.JSONDecodeError:
        pass

    if "'" in cleaned:
        double_quoted = cleaned.replace("'", '"')
        try:
            result = json.loads(double_quoted)
            if isinstance(result, dict):
                return result
            return None
        except json.JSONDecodeError:
            pass

    return None


def validate_output(
    schema: type[BaseModel],
    raw_or_obj: str | dict[str, Any] | BaseModel,
    output_type: str = "",
    schema_name: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
) -> StructuredOutputResult:
    start = time.monotonic()
    schema_name = schema_name or schema.__name__
    raw_str: str | None = None

    if isinstance(raw_or_obj, BaseModel):
        parsed = raw_or_obj.model_dump()
        raw_str = raw_or_obj.model_dump_json()
    elif isinstance(raw_or_obj, dict):
        parsed = dict(raw_or_obj)
        raw_str = json.dumps(parsed)
    elif isinstance(raw_or_obj, str):
        raw_str = raw_or_obj
        parsed_or_none = parse_json_output(raw_str)
        if parsed_or_none is None:
            latency = (time.monotonic() - start) * 1000
            return StructuredOutputResult(
                output_type=output_type,
                schema_name=schema_name,
                status="invalid",
                raw_output=raw_str,
                validation_errors=[
                    ValidationErrorDetail(
                        field="root",
                        error_type="json_decode_error",
                        message="Input is not valid JSON",
                    )
                ],
                provider=provider,
                model_name=model_name,
                latency_ms=latency,
            )
        parsed = parsed_or_none
    else:
        latency = (time.monotonic() - start) * 1000
        return StructuredOutputResult(
            output_type=output_type,
            schema_name=schema_name,
            status="invalid",
            raw_output=str(raw_or_obj) if raw_or_obj is not None else None,
            validation_errors=[
                ValidationErrorDetail(
                    field="root",
                    error_type="type_error",
                    message=f"Expected str, dict, or BaseModel, got {type(raw_or_obj).__name__}",
                )
            ],
            provider=provider,
            model_name=model_name,
            latency_ms=latency,
        )

    try:
        schema(**parsed)
    except ValidationError as exc:
        errors = _convert_validation_errors(exc)
        latency = (time.monotonic() - start) * 1000
        return StructuredOutputResult(
            output_type=output_type,
            schema_name=schema_name,
            status="invalid",
            parsed_object=parsed,
            raw_output=raw_str,
            validation_errors=errors,
            provider=provider,
            model_name=model_name,
            latency_ms=latency,
        )

    latency = (time.monotonic() - start) * 1000
    return StructuredOutputResult(
        output_type=output_type,
        schema_name=schema_name,
        status="valid",
        parsed_object=parsed,
        raw_output=raw_str,
        provider=provider,
        model_name=model_name,
        latency_ms=latency,
    )


def run_validation_with_repair(
    schema: type[BaseModel],
    raw_text: str | dict[str, Any] | BaseModel,
    output_type: str = "",
    schema_name: str | None = None,
    max_retries: int = 1,
    provider: str | None = None,
    model_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputResult:
    start = time.monotonic()
    schema_name = schema_name or schema.__name__

    is_pre_parsed = not isinstance(raw_text, str)

    result = validate_output(
        schema=schema,
        raw_or_obj=raw_text,
        output_type=output_type,
        schema_name=schema_name,
        provider=provider,
        model_name=model_name,
    )

    if result.status == "valid":
        result.latency_ms = (time.monotonic() - start) * 1000
        if metadata:
            result.metadata_json.update(metadata)
        return result

    if is_pre_parsed:
        result.latency_ms = (time.monotonic() - start) * 1000
        if metadata:
            result.metadata_json.update(metadata)
        return result

    retry_count = 0
    current_text = result.raw_output

    while retry_count < max_retries and current_text and result.status == "invalid":
        repaired = repair_json_if_safe(current_text)
        if repaired is None:
            break
        retry_count += 1
        result = validate_output(
            schema=schema,
            raw_or_obj=repaired,
            output_type=output_type,
            schema_name=schema_name,
            provider=provider,
            model_name=model_name,
        )
        result.retry_count = retry_count
        result.latency_ms = (time.monotonic() - start) * 1000
        if result.status == "valid":
            result.repaired = True
            if metadata:
                result.metadata_json.update(metadata)
            return result
        current_text = result.raw_output

    if result.status == "invalid" and retry_count >= max_retries and max_retries > 0:
        result.status = "failed"
        result.retry_count = retry_count
    result.latency_ms = (time.monotonic() - start) * 1000
    if metadata:
        result.metadata_json.update(metadata)
    return result


def build_structured_output_result(
    output_type: str,
    schema_name: str,
    status: OutputStatus,
    parsed_object: dict[str, Any] | None = None,
    raw_output: str | None = None,
    validation_errors: list[ValidationErrorDetail] | None = None,
    retry_count: int = 0,
    repaired: bool = False,
    provider: str | None = None,
    model_name: str | None = None,
    latency_ms: float | None = None,
    token_usage: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputResult:
    return StructuredOutputResult(
        output_type=output_type,
        schema_name=schema_name,
        status=status,
        parsed_object=parsed_object,
        raw_output=raw_output,
        validation_errors=validation_errors or [],
        retry_count=retry_count,
        repaired=repaired,
        provider=provider,
        model_name=model_name,
        latency_ms=latency_ms,
        token_usage_json=token_usage or {},
        metadata_json=metadata or {},
    )


def _convert_validation_errors(exc: ValidationError) -> list[ValidationErrorDetail]:
    errors: list[ValidationErrorDetail] = []
    for err in exc.errors():
        field_path = ".".join(str(loc) for loc in err.get("loc", []))
        errors.append(
            ValidationErrorDetail(
                field=field_path or "root",
                error_type=err.get("type", "unknown"),
                message=err.get("msg", ""),
                input_value=err.get("input"),
            )
        )
    return errors


def readiness_check_payload_from_result(
    result: StructuredOutputResult,
    analysis_run_id: str | None = None,
) -> dict[str, Any] | None:
    if result.status in ("valid", "skipped"):
        return None

    code_map: dict[str, str] = {
        "invalid": "STRUCTURED_OUTPUT_INVALID",
        "repaired": "STRUCTURED_OUTPUT_REPAIRED",
        "failed": "STRUCTURED_OUTPUT_RETRY_EXHAUSTED",
    }
    severity_map: dict[str, str] = {
        "invalid": "error",
        "repaired": "warning",
        "failed": "error",
    }

    code = code_map.get(result.status, "STRUCTURED_OUTPUT_INVALID")
    severity = severity_map.get(result.status, "error")

    field_errors = result.validation_errors[:3]
    error_summary = "; ".join(f"{e.field}: {e.error_type}" for e in field_errors)

    return {
        "analysis_run_id": analysis_run_id,
        "code": code,
        "severity": severity,
        "status": "degraded" if severity == "error" else "warning",
        "user_message": (
            f"Structured output '{result.output_type}' "
            f"({result.schema_name}) status={result.status}. "
            f"Errors: {error_summary or 'none'}"
        ),
        "internal_detail": (
            f"output_type={result.output_type}, "
            f"schema={result.schema_name}, "
            f"retry_count={result.retry_count}, "
            f"repaired={result.repaired}"
        ),
        "recommended_action": (
            "Inspect the output generator and schema for drift."
            if result.status in ("invalid", "failed")
            else "Review the repair to confirm correctness."
        ),
        "metadata": {
            "output_type": result.output_type,
            "schema_name": result.schema_name,
            "retry_count": result.retry_count,
            "validation_error_count": len(result.validation_errors),
            "repaired": result.repaired,
        },
    }


def quality_metrics_from_results(
    results: list[StructuredOutputResult],
) -> dict[str, float]:
    if not results:
        return {
            "structured_output_valid_rate": 1.0,
            "structured_output_repair_rate": 0.0,
            "structured_output_failure_rate": 0.0,
            "avg_retry_count": 0.0,
            "schema_validation_error_count": 0.0,
            "missing_required_field_count": 0.0,
        }

    total = len(results)
    valid_count = sum(1 for r in results if r.status == "valid")
    repaired_count = sum(1 for r in results if r.repaired)
    failed_count = sum(1 for r in results if r.status == "failed")
    invalid_count = sum(1 for r in results if r.status == "invalid")
    total_errors = sum(len(r.validation_errors) for r in results)
    missing_fields = sum(
        1 for r in results for e in r.validation_errors if e.error_type in ("missing", "value_error.missing")
    )
    avg_retry = sum(r.retry_count for r in results) / total

    return {
        "structured_output_valid_rate": valid_count / total,
        "structured_output_repair_rate": repaired_count / total if total > 0 else 0.0,
        "structured_output_failure_rate": (failed_count + invalid_count) / total,
        "avg_retry_count": avg_retry,
        "schema_validation_error_count": float(total_errors),
        "missing_required_field_count": float(missing_fields),
    }
