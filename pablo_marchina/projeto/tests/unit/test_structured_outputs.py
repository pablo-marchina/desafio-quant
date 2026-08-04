from __future__ import annotations

from pydantic import BaseModel, Field

from src.evaluation.structured_outputs import (
    StructuredOutputResult,
    ValidationErrorDetail,
    build_structured_output_result,
    parse_json_output,
    quality_metrics_from_results,
    readiness_check_payload_from_result,
    repair_json_if_safe,
    run_validation_with_repair,
    validate_output,
)


class SampleSchema(BaseModel):
    name: str = ""
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)


class TestParseJsonOutput:
    def test_valid_json_dict(self) -> None:
        parsed = parse_json_output('{"name": "test", "score": 0.85}')
        assert isinstance(parsed, dict)
        assert parsed["name"] == "test"

    def test_invalid_json(self) -> None:
        parsed = parse_json_output("{invalid}")
        assert parsed is None

    def test_empty_string(self) -> None:
        assert parse_json_output("") is None

    def test_none_input(self) -> None:
        assert parse_json_output(None) is None

    def test_valid_json_list(self) -> None:
        parsed = parse_json_output('[{"a": 1}]')
        assert parsed is None  # function only returns dict, not list


class TestRepairJsonIfSafe:
    def test_unescape_backslashes(self) -> None:
        repaired = repair_json_if_safe(r'{"key": "value\\with\\backslashes"}')
        assert repaired is not None
        assert repaired["key"] == "value\\with\\backslashes"

    def test_valid_json_returns_dict(self) -> None:
        repaired = repair_json_if_safe('{"a": 1}')
        assert repaired == {"a": 1}

    def test_trailing_comma(self) -> None:
        repaired = repair_json_if_safe('{"a": 1,}')
        assert repaired is not None
        assert repaired["a"] == 1

    def test_single_quotes(self) -> None:
        repaired = repair_json_if_safe("{'a': 'b'}")
        assert repaired is not None
        assert repaired["a"] == "b"

    def test_unquoted_keys_not_repaired(self) -> None:
        assert repair_json_if_safe("{a: 1}") is None

    def test_none_text_returns_none(self) -> None:
        assert repair_json_if_safe(None) is None
        assert repair_json_if_safe("") is None


class TestValidateOutput:
    def test_valid_dict(self) -> None:
        result = validate_output(SampleSchema, {"name": "x", "score": 0.5})
        assert result.status == "valid"
        assert result.parsed_object is not None

    def test_missing_field_uses_default(self) -> None:
        result = validate_output(SampleSchema, {"name": "x"})
        assert result.status == "valid"
        obj = result.parsed_object
        assert obj is not None
        assert obj["name"] == "x"

    def test_wrong_type(self) -> None:
        result = validate_output(SampleSchema, {"name": 123, "score": "bad"})
        assert result.status == "invalid"
        assert len(result.validation_errors) > 0

    def test_valid_json_string(self) -> None:
        result = validate_output(SampleSchema, '{"name": "x", "score": 0.5}')
        assert result.status == "valid"

    def test_invalid_json_string(self) -> None:
        result = validate_output(SampleSchema, "{bad}")
        assert result.status == "invalid"

    def test_valid_base_model(self) -> None:
        model = SampleSchema(name="x", score=0.5)
        result = validate_output(SampleSchema, model)
        assert result.status == "valid"

    def test_validation_errors_structured(self) -> None:
        result = validate_output(SampleSchema, {"name": [], "score": "x"})
        for err in result.validation_errors:
            assert isinstance(err, ValidationErrorDetail)
            assert err.field != ""

    def test_metadata_preserved(self) -> None:
        result = validate_output(
            SampleSchema,
            {"name": "x"},
            output_type="test",
            schema_name="SampleSchema",
            provider="test_provider",
        )
        assert result.output_type == "test"
        assert result.schema_name == "SampleSchema"
        assert result.provider == "test_provider"


class TestRunValidationWithRepair:
    def test_valid_input_passes(self) -> None:
        result = run_validation_with_repair(SampleSchema, '{"name": "x", "score": 0.5}')
        assert result.status == "valid"
        assert result.retry_count == 0
        assert not result.repaired

    def test_valid_dict_input(self) -> None:
        result = run_validation_with_repair(SampleSchema, {"name": "x", "score": 0.5})
        assert result.status == "valid"
        assert result.retry_count == 0

    def test_invalid_after_repair(self) -> None:
        result = run_validation_with_repair(SampleSchema, "{bad}", max_retries=1)
        assert result.status in ("invalid", "failed")

    def test_metadata_applied(self) -> None:
        result = run_validation_with_repair(
            SampleSchema,
            '{"name": "x"}',
            metadata={"source": "test"},
        )
        assert result.metadata_json.get("source") == "test"

    def test_max_retries_zero(self) -> None:
        result = run_validation_with_repair(SampleSchema, "{bad}", max_retries=0)
        assert result.status == "invalid"

    def test_pre_parsed_dict_skips_repair(self) -> None:
        result = run_validation_with_repair(SampleSchema, {"name": "x"})
        assert result.status == "valid"
        assert result.retry_count == 0


class TestBuildStructuredOutputResult:
    def test_valid_result(self) -> None:
        result = build_structured_output_result(
            status="valid",
            parsed_object={"key": "value"},
            raw_output='{"key": "value"}',
            output_type="test",
            schema_name="TestSchema",
        )
        assert result.status == "valid"
        assert result.parsed_object == {"key": "value"}

    def test_invalid_with_errors(self) -> None:
        errors: list[ValidationErrorDetail] = [
            ValidationErrorDetail(
                field="name",
                error_type="missing",
                message="required",
            )
        ]
        result = build_structured_output_result(
            status="invalid",
            parsed_object=None,
            raw_output="bad",
            validation_errors=errors,
            output_type="test",
            schema_name="TestSchema",
        )
        assert result.status == "invalid"
        assert len(result.validation_errors) == 1


class TestReadinessCheckPayload:
    def test_invalid_result_returns_payload(self) -> None:
        result = StructuredOutputResult(
            status="invalid",
            parsed_object=None,
            raw_output="bad",
            output_type="test",
            schema_name="TestSchema",
            validation_errors=[
                ValidationErrorDetail(
                    field="name",
                    error_type="missing",
                    message="required",
                )
            ],
        )
        payload = readiness_check_payload_from_result(result, "run-1")
        assert payload is not None
        assert payload["analysis_run_id"] == "run-1"
        assert "STRUCTURED_OUTPUT_INVALID" in payload["code"]

    def test_valid_result_returns_none(self) -> None:
        result = StructuredOutputResult(
            status="valid",
            parsed_object={"ok": True},
            raw_output='{"ok": true}',
            output_type="test",
            schema_name="TestSchema",
        )
        assert readiness_check_payload_from_result(result, "run-1") is None

    def test_failed_result_returns_payload(self) -> None:
        result = StructuredOutputResult(
            status="failed",
            parsed_object=None,
            raw_output="bad",
            output_type="test",
            schema_name="TestSchema",
            retry_count=2,
        )
        payload = readiness_check_payload_from_result(result, "run-1")
        assert payload is not None
        assert "STRUCTURED_OUTPUT_RETRY_EXHAUSTED" in payload["code"]


class TestQualityMetrics:
    def test_empty_results(self) -> None:
        metrics = quality_metrics_from_results([])
        assert metrics["structured_output_valid_rate"] == 1.0

    def test_all_valid(self) -> None:
        results = [
            StructuredOutputResult(
                status="valid",
                parsed_object={"a": 1},
                raw_output='{"a":1}',
                output_type="t",
                schema_name="S",
            ),
            StructuredOutputResult(
                status="valid",
                parsed_object={"b": 2},
                raw_output='{"b":2}',
                output_type="t",
                schema_name="S",
            ),
        ]
        metrics = quality_metrics_from_results(results)
        assert metrics["structured_output_valid_rate"] == 1.0
        assert metrics["structured_output_failure_rate"] == 0.0

    def test_mixed_results(self) -> None:
        results = [
            StructuredOutputResult(
                status="valid",
                parsed_object={"a": 1},
                raw_output='{"a":1}',
                output_type="t",
                schema_name="S",
            ),
            StructuredOutputResult(
                status="invalid",
                parsed_object=None,
                raw_output="bad",
                output_type="t",
                schema_name="S",
            ),
            StructuredOutputResult(
                status="failed",
                parsed_object=None,
                raw_output="bad",
                output_type="t",
                schema_name="S",
                retry_count=2,
            ),
        ]
        metrics = quality_metrics_from_results(results)
        assert metrics["structured_output_valid_rate"] == 1.0 / 3.0
        assert metrics["structured_output_failure_rate"] == 2.0 / 3.0

    def test_with_repairs(self) -> None:
        results = [
            StructuredOutputResult(
                status="valid",
                parsed_object={"a": 1},
                raw_output='{"a":1}',
                output_type="t",
                schema_name="S",
                repaired=True,
            ),
            StructuredOutputResult(
                status="valid",
                parsed_object={"b": 2},
                raw_output='{"b":2}',
                output_type="t",
                schema_name="S",
            ),
        ]
        metrics = quality_metrics_from_results(results)
        assert metrics["structured_output_repair_rate"] == 0.5
