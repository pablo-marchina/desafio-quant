from pathlib import Path

from rag import settings


def test_rag_data_paths_are_relative_to_project_root() -> None:
    project_root = Path(__file__).resolve().parents[1]

    assert settings.PROJECT_ROOT == project_root
    assert settings.DATA_DIR == project_root / "data"
    assert settings.CHUNKS_PATH == project_root / "data" / "processed" / "chunks.json"
