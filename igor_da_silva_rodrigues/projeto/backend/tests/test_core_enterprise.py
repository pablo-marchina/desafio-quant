import pytest
from pydantic import ValidationError

from app.core.cache import JsonFileCache
from app.core.contracts import validate_contract
from app.core.schemas import PipelineInput, SearchPlanOutput


def test_pipeline_input_rejects_relative_official_url():
    with pytest.raises(ValidationError):
        validate_contract(
            PipelineInput,
            {"startup_name": "Teste", "site_oficial": "/site"},
        )


def test_search_plan_contract_requires_18_queries():
    with pytest.raises(ValidationError, match="18 consultas"):
        validate_contract(
            SearchPlanOutput,
            {
                "startup": "Teste",
                "hipotese_maturidade": "Hipotese",
                "plano_consultas": [
                    {"consulta": "teste", "objetivo": "teste", "camada": 3}
                ],
                "tarefas": [],
            },
        )


def test_json_file_cache_is_deterministic_and_atomic(tmp_path):
    cache = JsonFileCache(tmp_path)
    key_a = cache.key_for("stage", {"b": 2, "a": 1})
    key_b = cache.key_for("stage", {"a": 1, "b": 2})

    cache.set(key_a, {"resultado": True})

    assert key_a == key_b
    assert cache.get(key_b) == {"resultado": True}
    assert not list(tmp_path.glob("*.tmp"))
