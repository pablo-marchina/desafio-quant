from pathlib import Path
from typing import Sequence, List

from .config import EMBEDDING_MODEL, HF_CACHE_DIR, RAG_EMBEDDINGS_LOCAL_ONLY

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


def _resolve_local_model_path(model_name: str) -> str:
    if not RAG_EMBEDDINGS_LOCAL_ONLY:
        return model_name

    direct_path = Path(model_name)
    if direct_path.exists():
        return str(direct_path)

    model_cache_dir = Path(HF_CACHE_DIR) / "hub" / f"models--{model_name.replace('/', '--')}"
    if not model_cache_dir.exists():
        return model_name

    ref_path = model_cache_dir / "refs" / "main"
    snapshot_name = None
    if ref_path.exists():
        snapshot_name = ref_path.read_text(encoding="utf-8").strip()

    if snapshot_name:
        snapshot_path = model_cache_dir / "snapshots" / snapshot_name
        if (snapshot_path / "config.json").exists():
            return str(snapshot_path)

    snapshots_dir = model_cache_dir / "snapshots"
    if snapshots_dir.exists():
        for snapshot_path in sorted(snapshots_dir.iterdir(), reverse=True):
            if snapshot_path.is_dir() and (snapshot_path / "config.json").exists():
                return str(snapshot_path)

    return model_name

class EmbeddingClient:
    """
    Cliente simples para gerar embeddings usando sentence-transformers.
    Instancie e chame `embed(texts)` para obter vetores.
    """
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers não está instalado")
        resolved_model_name = _resolve_local_model_path(model_name)
        self.model = SentenceTransformer(
            resolved_model_name,
            cache_folder=HF_CACHE_DIR,
            local_files_only=RAG_EMBEDDINGS_LOCAL_ONLY,
        )

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self.model.encode(list(texts), show_progress_bar=False)
        return vectors.tolist()
