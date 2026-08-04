"""Schemas for workspace output validation gates."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class OutputValidationStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class OutputValidationSeverity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"


class OutputValidationCheck(BaseModel):
    name: str
    status: OutputValidationStatus
    message: str
    severity: OutputValidationSeverity = OutputValidationSeverity.FAIL
    field: str | None = None


class OutputValidationResult(BaseModel):
    output_type: str
    status: OutputValidationStatus
    checks: list[OutputValidationCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls, output_type: str) -> OutputValidationResult:
        return cls(output_type=output_type, status=OutputValidationStatus.PASS)

    def add_check(
        self,
        name: str,
        status: OutputValidationStatus,
        message: str,
        *,
        severity: OutputValidationSeverity = OutputValidationSeverity.FAIL,
        field: str | None = None,
    ) -> None:
        self.checks.append(
            OutputValidationCheck(
                name=name,
                status=status,
                message=message,
                severity=severity,
                field=field,
            )
        )
        if status == OutputValidationStatus.FAIL:
            self.failures.append(message)
            self.status = OutputValidationStatus.FAIL
        elif status == OutputValidationStatus.WARN:
            self.warnings.append(message)
            if self.status != OutputValidationStatus.FAIL:
                self.status = OutputValidationStatus.WARN
