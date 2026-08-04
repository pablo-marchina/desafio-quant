from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeStartupRequest(BaseModel):
    startup_name: str = Field(min_length=2, description="Nome da startup a ser analisada")


class ChatRequest(BaseModel):
    startup_id: str | None = None
    startup_name: str | None = None
    message: str = Field(min_length=1, description="Pergunta do usuário")

