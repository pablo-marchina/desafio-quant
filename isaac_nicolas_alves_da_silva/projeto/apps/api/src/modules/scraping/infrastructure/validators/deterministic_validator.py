"""Validação objetiva do conteúdo coletado, sem uso de inteligência artificial."""

import re

from apps.api.src.modules.scraping.application.dto import (
    DeterministicValidationResult,
    ScrapingOutput,
)
from apps.api.src.modules.scraping.application.ports import DeterministicValidator


class BasicDeterministicValidator(DeterministicValidator):
    """Calcula scores técnicos, textuais e evidenciais básicos.

    Os limites desta primeira versão são pontos de partida documentados. Depois,
    deverão ser calibrados usando páginas reais e resultados revisados.
    """

    minimum_text_characters = 300
    good_text_characters = 800
    minimum_word_count = 80

    # Termos simples usados apenas como sinal evidencial inicial. Encontrá-los
    # não prova que uma startup utiliza IA; serve somente para compor um score.
    evidence_keywords = {
        "ai",
        "artificial intelligence",
        "inteligência artificial",
        "inteligencia artificial",
        "machine learning",
        "deep learning",
        "generative ai",
        "ia generativa",
        "computer vision",
        "visão computacional",
        "visao computacional",
        "language model",
        "modelo de linguagem",
    }

    async def validate(
        self,
        output: ScrapingOutput,
    ) -> DeterministicValidationResult:
        """Executa as três medições e reúne problemas e alertas."""

        technical_score, technical_problems = self._validate_technical(output)
        text_score, text_problems, text_warnings = self._validate_text(output)
        evidence_score, evidence_warnings = self._validate_evidence(output)

        return DeterministicValidationResult(
            technical_score=technical_score,
            text_score=text_score,
            evidence_score=evidence_score,
            problems=technical_problems | text_problems,
            warnings=text_warnings | evidence_warnings,
        )

    def _validate_technical(
        self,
        output: ScrapingOutput,
    ) -> tuple[float, set[str]]:
        """Avalia se a coleta funcionou tecnicamente."""

        score = 1.0
        problems: set[str] = set()

        if not output.source_url:
            problems.add("missing_source_url")
            score -= 0.40

        if output.status_code >= 400:
            problems.add("blocked_status")
            score -= 0.60

        if "text/html" not in output.content_type.lower():
            problems.add("unsupported_content_type")
            score -= 0.40

        if not output.raw_html.strip():
            problems.add("empty_content")
            score -= 0.60

        lowered_html = output.raw_html.lower()
        if "captcha" in lowered_html:
            problems.add("captcha")
            score -= 0.60

        return self._bounded(score), problems

    def _validate_text(
        self,
        output: ScrapingOutput,
    ) -> tuple[float, set[str], set[str]]:
        """Avalia quantidade e repetição do texto extraído."""

        text = output.raw_text.strip()
        problems: set[str] = set()
        warnings: set[str] = set()

        if not text:
            return 0.0, {"empty_content"}, warnings

        character_count = len(text)
        words = re.findall(r"\b[\wÀ-ÿ'-]+\b", text.lower())
        word_count = len(words)

        if character_count < self.minimum_text_characters:
            problems.add("insufficient_text")
        elif character_count < self.good_text_characters:
            warnings.add("limited_text")

        if word_count < self.minimum_word_count:
            problems.add("insufficient_text")

        # A proporção de palavras únicas é uma aproximação simples para detectar
        # textos muito repetitivos. Validadores mais sofisticados virão depois.
        unique_word_ratio = len(set(words)) / word_count if word_count else 0.0
        if unique_word_ratio < 0.25:
            problems.add("high_repetition")

        character_score = min(character_count / self.good_text_characters, 1.0)
        word_score = min(word_count / self.minimum_word_count, 1.0)
        repetition_score = min(unique_word_ratio / 0.50, 1.0)

        text_score = (
            character_score * 0.40
            + word_score * 0.40
            + repetition_score * 0.20
        )

        return self._bounded(text_score), problems, warnings

    def _validate_evidence(
        self,
        output: ScrapingOutput,
    ) -> tuple[float, set[str]]:
        """Calcula sinais básicos de relevância para o objetivo do projeto."""

        text = output.raw_text.lower()
        matched_keywords = {
            keyword for keyword in self.evidence_keywords if keyword in text
        }

        if not matched_keywords:
            return 0.20, {"no_ai_evidence_signal"}

        # Mais termos distintos aumentam o score, limitado a 1.0.
        evidence_score = 0.40 + min(len(matched_keywords) * 0.15, 0.60)
        return self._bounded(evidence_score), set()

    @staticmethod
    def _bounded(score: float) -> float:
        """Garante que todo score permaneça no intervalo de zero a um."""

        return round(max(0.0, min(score, 1.0)), 4)
