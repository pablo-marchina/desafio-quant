from __future__ import annotations

from typing import Any, TypeVar

from jsonschema import Draft202012Validator
from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def validate_contract(model_type: type[ModelT], payload: BaseModel | dict[str, Any]) -> ModelT:
    raw = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    model = model_type.model_validate(raw)
    serialized = model.model_dump(mode="json")
    schema = model_type.model_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(serialized)
    return model
