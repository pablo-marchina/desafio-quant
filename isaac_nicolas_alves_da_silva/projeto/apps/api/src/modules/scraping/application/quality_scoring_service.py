"""Serviço responsável por calcular a nota final de qualidade."""

from dataclasses import replace

from .dto import DeterministicValidationResult


class QualityScoringService:
    """Calcula o ``quality_score`` usando os pesos definidos no projeto.

    Este serviço fica na camada de aplicação porque coordena scores produzidos
    por diferentes validadores. Ele não coleta páginas e não decide se o
    conteúdo será aceito; essa decisão continua pertencendo às políticas.
    """

    technical_weight = 0.30
    text_weight = 0.30
    evidence_weight = 0.40

    # Fontes curadas (ex: "nvidia_knowledge", vindas do source registry, nao
    # de scraping aberto) nao precisam provar "evidencia de IA de uma
    # startup" — essa nocao nao se aplica a documentacao de referencia da
    # propria NVIDIA. A qualidade dessas fontes e' so tecnica + textual.
    reference_technical_weight = 0.50
    reference_text_weight = 0.50

    def calculate(
        self,
        validation: DeterministicValidationResult,
        *,
        source_type: str = "startup_evidence",
    ) -> DeterministicValidationResult:
        """Retorna uma nova validação contendo o score final calculado."""

        if source_type == "startup_evidence":
            quality_score = (
                validation.technical_score * self.technical_weight
                + validation.text_score * self.text_weight
                + validation.evidence_score * self.evidence_weight
            )
        else:
            quality_score = (
                validation.technical_score * self.reference_technical_weight
                + validation.text_score * self.reference_text_weight
            )

        # O DTO é imutável. ``replace`` cria uma cópia, alterando somente o
        # quality_score e preservando scores, problemas e warnings originais.
        return replace(
            validation,
            quality_score=round(quality_score, 4),
        )
