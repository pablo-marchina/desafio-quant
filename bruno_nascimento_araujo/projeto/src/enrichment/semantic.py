"""QFirst - priorizacao semantica neural focada em arquitetura AI-Native.

NAO buscamos a palavra "NVIDIA". O scorer mede similaridade contra um corpus de
sinais tecnicos de infraestrutura/arquitetura de IA. Pontuacao alta => high_priority.

sentence-transformers e OPCIONAL: o import e lazy e, se ausente, cai num fallback
lexical (contagem ponderada de keywords) emitindo aviso no log.
"""
from __future__ import annotations

import re

from ..config import Settings, get_settings
from ..logging_conf import get_logger
from ..models import STATUS_HIGH, STATUS_PENDING

logger = get_logger("qfirst")

# Corpus de referencia: sinais fortes de AI-Native (pt + en).
AI_NATIVE_CORPUS = [
    "LLM fine-tuning de modelos de linguagem",
    "RAG retrieval augmented generation integrado",
    "agentes autonomos e workflows agenticos",
    "visao computacional e deteccao de objetos",
    "treinamento de modelos proprietarios de deep learning",
    "dados proprietarios para treino de IA",
    "otimizacao de latencia de inferencia",
    "pipelines de dados e MLOps",
    "redes neurais e transformers",
    "embeddings vetoriais e busca semantica",
    "GPU acceleration para inferencia de modelos",
    "machine learning em producao",
]

# Termos negativos: SaaS/marketing generico sem uso estrutural de IA.
_NEGATIVE_HINTS = (
    "agencia de marketing",
    "revenda de ti",
    "loja virtual",
    "consultoria contabil",
    "landing page",
)

# Para o fallback lexical: keywords e pesos.
_LEXICAL_KEYWORDS = {
    "llm": 1.0, "fine-tuning": 1.0, "fine tuning": 1.0, "rag": 1.0,
    "agente": 0.8, "agentes": 0.8, "agentic": 1.0, "agentico": 1.0, "agenticos": 1.0,
    "visao computacional": 1.0, "computer vision": 1.0,
    "rede neural": 1.0, "redes neurais": 1.0, "neural network": 1.0,
    "deep learning": 1.0, "machine learning": 0.8, "aprendizado de maquina": 0.8,
    "inferencia": 0.8, "embedding": 0.9, "embeddings": 0.9, "transformer": 0.9,
    "modelo proprietario": 1.0, "dados proprietarios": 0.8,
    "mlops": 0.9, "pipeline de dados": 0.7, "gpu": 0.7,
    "inteligencia artificial": 0.6, "artificial intelligence": 0.6, "ia ": 0.4,
}

_TOKEN_RE = re.compile(r"[a-z0-9\-]+")


class QFirstScorer:
    """Pontua texto (titulo + descricao) por fit AI-Native em [0, 1]."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.threshold = self._settings.qfirst_threshold
        self._model = None
        self._corpus_emb = None
        self._backend = "lexical"
        self._init_model()

    def _init_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer, util  # noqa: F401

            self._model = SentenceTransformer(self._settings.sbert_model)
            self._corpus_emb = self._model.encode(
                AI_NATIVE_CORPUS, convert_to_tensor=True, normalize_embeddings=True
            )
            self._backend = "sbert"
            logger.info("QFirst usando SBERT '%s'.", self._settings.sbert_model)
        except ImportError:
            logger.warning(
                "sentence-transformers ausente: QFirst em fallback LEXICAL "
                "(instale requirements-ai.txt para o filtro neural)."
            )
        except Exception as exc:  # noqa: BLE001 - falha ao baixar/carregar modelo
            logger.warning("Falha ao carregar SBERT (%s): fallback lexical.", exc)

    @property
    def backend(self) -> str:
        return self._backend

    def score(self, text: str) -> float:
        text = (text or "").strip()
        if not text:
            return 0.0
        if self._backend == "sbert":
            return self._score_sbert(text)
        return self._score_lexical(text)

    def _score_sbert(self, text: str) -> float:
        from sentence_transformers import util

        emb = self._model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
        sims = util.cos_sim(emb, self._corpus_emb)
        score = float(sims.max())
        # Cosseno pode ser levemente negativo; clamp em [0, 1].
        return max(0.0, min(1.0, score))

    def _score_lexical(self, text: str) -> float:
        low = " " + text.lower() + " "
        if any(neg in low for neg in _NEGATIVE_HINTS):
            return 0.0
        hits = 0.0
        for kw, weight in _LEXICAL_KEYWORDS.items():
            if kw in low:
                hits += weight
        # Normaliza de forma saturante: ~3 termos fortes ja chegam perto de 1.
        return min(1.0, hits / 3.0)

    def status_for(self, text: str) -> tuple[str, float]:
        s = self.score(text)
        return (STATUS_HIGH if s >= self.threshold else STATUS_PENDING, s)
