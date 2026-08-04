"""Adaptador que liga o scraping ao contrato publico do modulo agents.

Esta e a UNICA peca do modulo ``scraping`` que conhece o modulo ``agents`` —
e mesmo assim, conhece apenas o contrato publico
(``agents/application/public/semantic_investigator.py``). Nenhum node, grafo
ou prompt interno de ``agents`` e importado aqui.

Responsabilidade desta classe:

```txt
implementar a porta SemanticInvestigator (scraping/application/ports.py)
traduzir InvestigationInput (scraping)   -> EvidenceValidationInput (agents)
traduzir EvidenceValidationResult (agents) -> InvestigationResult (scraping)
```

Cada modulo mantem seu proprio vocabulario (enums e DTOs). Esta classe e o
unico lugar onde os dois vocabularios se encontram.
"""

from apps.api.src.modules.agents.application.dto import EvidenceValidationInput
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.scraping.application.dto import (
    InvestigationInput,
    InvestigationResult,
)
from apps.api.src.modules.scraping.application.ports import SemanticInvestigator
from apps.api.src.modules.scraping.domain.enums import AgentInvestigationDecision


class AgentsSemanticInvestigator(SemanticInvestigator):
    """Implementa ``SemanticInvestigator`` chamando o modulo agents."""

    def __init__(self, evidence_validation_service: EvidenceValidationService) -> None:
        self.evidence_validation_service = evidence_validation_service

    async def investigate(
        self,
        investigation_input: InvestigationInput,
    ) -> InvestigationResult:
        """Traduz a entrada, chama o agente e traduz a saida de volta."""

        agents_input = self._build_agents_input(investigation_input)
        agents_result = await self.evidence_validation_service.investigate(
            agents_input
        )

        # Os dois enums (``agents.AgentDecision`` e
        # ``scraping.AgentInvestigationDecision``) compartilham os mesmos
        # valores de string ("accepted", "rejected", "needs_more_sources"),
        # de proposito, para que esta traducao seja so uma troca de tipo.
        decision = AgentInvestigationDecision(agents_result.decision.value)

        return InvestigationResult(
            decision=decision,
            reason=agents_result.reason,
        )

    def _build_agents_input(
        self,
        investigation_input: InvestigationInput,
    ) -> EvidenceValidationInput:
        """Achata os DTOs internos do scraping no formato publico de agents."""

        deterministic = investigation_input.deterministic
        semantic = investigation_input.semantic
        assessment = semantic.assessment

        return EvidenceValidationInput(
            url=investigation_input.url,
            title=investigation_input.title,
            raw_text=investigation_input.raw_text,
            technical_score=deterministic.technical_score,
            text_score=deterministic.text_score,
            evidence_score=deterministic.evidence_score,
            quality_score=deterministic.quality_score,
            deterministic_problems=sorted(deterministic.problems),
            deterministic_warnings=sorted(deterministic.warnings),
            startup_match_score=assessment.startup_match_score,
            evidence_clarity_score=assessment.evidence_clarity_score,
            source_reliability_score=assessment.source_reliability_score,
            statement_specificity_score=assessment.statement_specificity_score,
            context_completeness_score=assessment.context_completeness_score,
            contradiction_detected=assessment.contradiction_detected,
            semantic_decision=assessment.decision.value,
            semantic_reason=assessment.reason,
            semantic_confidence=semantic.semantic_confidence,
            startup_id=investigation_input.startup_id,
        )
