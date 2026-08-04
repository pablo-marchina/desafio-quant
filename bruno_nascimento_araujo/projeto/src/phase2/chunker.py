"""Modulo 3 - Chunking configuravel e sinais AI-Native.

Prepara o conteudo extraido para insercao na tabela startups_content.
O RecursiveCharacterTextSplitter e carregado lazily para nao exigir langchain
no core do pipeline.

Constantes AI_SIGNAL_TERMS e AI_SIGNAL_THRESHOLD ficam no topo do arquivo:
ajuste aqui sem tocar na logica de negocio.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ..logging_conf import get_logger

if TYPE_CHECKING:
    from .tools.extractor import ExtractedStartupData

logger = get_logger("phase2.chunker")

# =============================================================================
# Constantes ajustaveis — edite aqui sem tocar na logica
# =============================================================================

AI_SIGNAL_TERMS: dict[str, float] = {
    "dados proprietários": 1.0,
    "workflow agêntico": 1.0,
    "llm fine-tuning": 1.0,
    "modelos in-house": 1.0,
    "fine-tuning": 0.9,
    "rag": 0.9,
    "visão computacional": 0.9,
    "agentes autônomos": 0.9,
    "treinamento de modelos": 0.9,
    "redes neurais": 0.8,
    "embeddings": 0.8,
    "inferência": 0.7,
    "pipeline de dados": 0.6,
    "mlops": 0.7,
    "deep learning": 0.7,
    "machine learning": 0.5,
    "gpu": 0.5,
    "inteligência artificial": 0.4,
}

# Pontuacao minima (0.0-1.0) para marcar has_ai_signals=True no chunk.
# Calibrado para que ~3 termos fortes (peso >= 0.9) em um chunk resultem em score >= 0.30.
AI_SIGNAL_THRESHOLD: float = 0.30

# Divisor de normalizacao: sum(pesos) / DENSITY_NORMALIZER = score bruto.
# Com DENSITY_NORMALIZER=3.0: 3 termos de peso 1.0 → score 1.0.
DENSITY_NORMALIZER: float = 3.0

# =============================================================================


def _score_ai_signals(text: str) -> float:
    """Densidade ponderada de sinais AI-Native sobre o corpus de termos.

    Formula: min(1.0, soma_pesos_encontrados / DENSITY_NORMALIZER)
    Medida por chunk (nao pelo documento inteiro) para reduzir falsos positivos
    em startups com marketing pesado mas sem uso estrutural de IA.
    """
    if not text:
        return 0.0
    text_lower = text.lower()
    weighted_hits = sum(
        weight for term, weight in AI_SIGNAL_TERMS.items() if term in text_lower
    )
    return min(1.0, weighted_hits / DENSITY_NORMALIZER)


class ChunkProcessor:
    """Divide ExtractedStartupData em chunks prontos para insert_chunks()."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._splitter = None  # lazy init

    def _get_splitter(self):
        if self._splitter is None:
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter

                self._splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self._chunk_size,
                    chunk_overlap=self._chunk_overlap,
                )
            except ImportError:
                logger.warning(
                    "langchain-text-splitters ausente: usando divisao simples por tamanho. "
                    "Instale requirements-phase2.txt para chunking avancado."
                )
                self._splitter = _FallbackSplitter(self._chunk_size, self._chunk_overlap)
        return self._splitter

    def _split(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        return self._get_splitter().split_text(text) or []

    def process(
        self,
        data: ExtractedStartupData,
        startup_id: int,
    ) -> list[tuple]:
        """Retorna lista de tuplas para db.insert_chunks().

        Tupla: (startup_id, chunk_type, content, source_url, has_ai_signals, collected_at)
        has_ai_signals e calculado individualmente por chunk (nao herdado do documento).
        """
        now = data.collected_at or datetime.utcnow()
        src = data.source_url or data.url
        rows: list[tuple] = []

        def _add_chunk(chunk_type: str, text: str) -> None:
            text = text.strip()
            if not text:
                return
            score = _score_ai_signals(text)
            has_signals = score >= AI_SIGNAL_THRESHOLD
            rows.append((startup_id, chunk_type, text, src, has_signals, now))

        # core_business / main_text: chunked pelo splitter
        main = data.raw_text or data.core_business
        if main:
            for chunk in self._split(main):
                _add_chunk("main_text", chunk)

        # use_cases: cada item e um chunk proprio (geralmente curtos)
        for uc in data.use_cases:
            for chunk in self._split(uc):
                _add_chunk("use_case", chunk)

        # tech_stack: lista inteira como um unico chunk (preserva contexto)
        if data.tech_stack_raw:
            tech_text = "; ".join(data.tech_stack_raw)
            _add_chunk("tech_stack", tech_text)

        # founders: lista inteira como um unico chunk
        if data.founders_names:
            _add_chunk("founders", "; ".join(data.founders_names))

        # funding: lista inteira como um unico chunk
        if data.funding_rounds:
            _add_chunk("funding", "; ".join(data.funding_rounds))

        if not rows:
            logger.info(
                "Startup id=%d nao gerou chunks (sem conteudo extraido).", startup_id
            )
        return rows


class _FallbackSplitter:
    """Divisor simples por tamanho fixo, usado quando langchain nao esta instalado."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._size = chunk_size
        self._overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + self._size
            chunks.append(text[start:end])
            start += self._size - self._overlap
        return [c for c in chunks if c.strip()]
