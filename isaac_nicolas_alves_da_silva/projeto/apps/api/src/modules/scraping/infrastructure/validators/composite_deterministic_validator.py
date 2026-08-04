"""Composicao dos validadores determinísticos especializados."""

from apps.api.src.modules.scraping.application.dto import (
    DeterministicValidationResult,
    ScrapingOutput,
)
from apps.api.src.modules.scraping.application.ports import DeterministicValidator

from .evidence_validator import EvidenceValidator
from .technical_validator import TechnicalValidator
from .textual_validator import TextualValidator


class CompositeDeterministicValidator(DeterministicValidator):
    """Reune validacoes tecnica, textual e evidencial em um unico contrato."""

    def __init__(
        self,
        technical_validator: TechnicalValidator,
        textual_validator: TextualValidator,
        evidence_validator: EvidenceValidator,
    ) -> None:
        self.technical_validator = technical_validator
        self.textual_validator = textual_validator
        self.evidence_validator = evidence_validator

    async def validate(
        self,
        output: ScrapingOutput,
    ) -> DeterministicValidationResult:
        """Executa os componentes e combina seus sinais sem recalcula-los."""

        technical = self.technical_validator.validate(output)
        textual = self.textual_validator.validate(output)
        evidence = self.evidence_validator.validate(output)

        return DeterministicValidationResult(
            technical_score=technical.score,
            text_score=textual.score,
            evidence_score=evidence.score,
            problems=(
                technical.problems
                | textual.problems
                | evidence.problems
            ),
            warnings=(
                technical.warnings
                | textual.warnings
                | evidence.warnings
            ),
        )
