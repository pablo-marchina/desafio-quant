"""Testes das invariantes da entidade Briefing."""

from uuid import uuid4

import pytest

from apps.api.src.modules.briefing.domain.entities import Briefing
from apps.api.src.modules.briefing.domain.exceptions import BriefingError


def test_briefing_strips_content_whitespace() -> None:
    briefing = Briefing(startup_id=uuid4(), content="  # Titulo\nconteudo  ")

    assert briefing.content == "# Titulo\nconteudo"


def test_briefing_rejects_empty_content() -> None:
    with pytest.raises(BriefingError):
        Briefing(startup_id=uuid4(), content="   ")
