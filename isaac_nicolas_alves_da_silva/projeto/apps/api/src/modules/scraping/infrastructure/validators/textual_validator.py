"""Validacao deterministica da qualidade textual de uma coleta."""

import re

from bs4 import BeautifulSoup

from apps.api.src.modules.scraping.application.dto import (
    ScrapingOutput,
    ValidationComponentResult,
)


class TextualValidator:
    """Mede quantidade, repeticao, estrutura, links e idioma provavel."""

    minimum_text_characters = 300
    good_text_characters = 800
    minimum_word_count = 80

    high_boilerplate_ratio = 0.60
    elevated_boilerplate_ratio = 0.35
    high_link_ratio = 0.50
    critical_link_ratio = 0.70

    portuguese_function_words = {
        "a",
        "as",
        "com",
        "da",
        "de",
        "do",
        "e",
        "em",
        "para",
        "por",
        "que",
        "uma",
    }
    english_function_words = {
        "a",
        "and",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "that",
        "the",
        "to",
        "with",
    }

    # Regioes normalmente compostas por navegacao, formularios e rodapes.
    boilerplate_selectors = (
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "[role='navigation']",
        "[role='banner']",
        "[role='contentinfo']",
    )

    def validate(self, output: ScrapingOutput) -> ValidationComponentResult:
        """Calcula score textual e registra sinais de baixa qualidade."""

        text = output.raw_text.strip()
        problems: set[str] = set()
        warnings: set[str] = set()

        if not text:
            return ValidationComponentResult(
                score=0.0,
                problems={"empty_content"},
            )

        character_count = len(text)
        words = self._words(text)
        word_count = len(words)
        unique_word_ratio = len(set(words)) / word_count if word_count else 0.0
        # Extratores especializados, como Trafilatura, ja removeram menus,
        # rodapes e links laterais do raw_text. O HTML original permanece no
        # output apenas para auditoria e nao deve penalizar o texto extraido.
        if output.metadata.get("main_content_extracted") is True:
            boilerplate_ratio, link_ratio = 0.0, 0.0
        else:
            boilerplate_ratio, link_ratio = self._html_ratios(output.raw_html)
        detected_language = self._detect_language(words)

        if character_count < self.minimum_text_characters:
            problems.add("insufficient_text")
        elif character_count < self.good_text_characters:
            warnings.add("limited_text")

        if word_count < self.minimum_word_count:
            problems.add("insufficient_text")

        if unique_word_ratio < 0.25:
            problems.add("high_repetition")

        if boilerplate_ratio >= self.high_boilerplate_ratio:
            problems.add("high_boilerplate")
        elif boilerplate_ratio >= self.elevated_boilerplate_ratio:
            warnings.add("elevated_boilerplate")

        if link_ratio >= self.high_link_ratio:
            warnings.add("high_link_ratio")
        if link_ratio >= self.critical_link_ratio:
            problems.add("link_farm")

        warnings.add(f"language_{detected_language}")

        character_score = min(character_count / self.good_text_characters, 1.0)
        word_score = min(word_count / self.minimum_word_count, 1.0)
        repetition_score = min(unique_word_ratio / 0.50, 1.0)
        structure_score = self._structure_score(boilerplate_ratio, link_ratio)

        text_score = (
            character_score * 0.30
            + word_score * 0.30
            + repetition_score * 0.20
            + structure_score * 0.20
        )

        # Muito texto de menu pode inflar contagem de caracteres e palavras.
        # Penalidades explicitas impedem que volume de boilerplate seja
        # confundido com conteudo principal de boa qualidade.
        if boilerplate_ratio >= self.high_boilerplate_ratio:
            text_score -= 0.15
        if link_ratio >= self.critical_link_ratio:
            text_score -= 0.20
        elif link_ratio >= self.high_link_ratio:
            text_score -= 0.10

        return ValidationComponentResult(
            score=self._bounded(text_score),
            problems=problems,
            warnings=warnings,
        )

    def _html_ratios(self, raw_html: str) -> tuple[float, float]:
        """Calcula proporcao aproximada de boilerplate e texto em links."""

        soup = BeautifulSoup(raw_html, "html.parser")
        for element in soup(["script", "style", "noscript", "template"]):
            element.decompose()

        all_text = soup.get_text(separator=" ", strip=True)
        total_characters = max(len(all_text), 1)

        # Elementos podem estar aninhados, portanto limitamos a soma ao total
        # da pagina. Esta e uma metrica aproximada, nao uma extracao final.
        boilerplate_characters = sum(
            len(element.get_text(separator=" ", strip=True))
            for selector in self.boilerplate_selectors
            for element in soup.select(selector)
        )
        link_characters = sum(
            len(element.get_text(separator=" ", strip=True))
            for element in soup.select("a")
        )

        return (
            min(boilerplate_characters / total_characters, 1.0),
            min(link_characters / total_characters, 1.0),
        )

    @staticmethod
    def _structure_score(boilerplate_ratio: float, link_ratio: float) -> float:
        """Penaliza paginas dominadas por navegacao em vez de conteudo."""

        penalty = boilerplate_ratio * 0.70 + link_ratio * 0.30
        return max(0.0, 1.0 - penalty)

    @staticmethod
    def _words(text: str) -> list[str]:
        return re.findall(r"\b[\wÀ-ÿ'-]+\b", text.lower())

    def _detect_language(self, words: list[str]) -> str:
        """Identifica portugues ou ingles usando palavras funcionais comuns."""

        # Poucas palavras nao fornecem sinal suficiente para uma classificacao
        # confiavel e devem permanecer explicitamente desconhecidas.
        if len(words) < 20:
            return "unknown"

        portuguese_hits = sum(
            word in self.portuguese_function_words for word in words
        )
        english_hits = sum(word in self.english_function_words for word in words)

        minimum_hits = max(3, round(len(words) * 0.03))
        if max(portuguese_hits, english_hits) < minimum_hits:
            return "unknown"

        if portuguese_hits >= english_hits * 1.5:
            return "pt"
        if english_hits >= portuguese_hits * 1.5:
            return "en"

        return "unknown"

    @staticmethod
    def _bounded(score: float) -> float:
        return round(max(0.0, min(score, 1.0)), 4)
