from app.models.enums import AiMaturityLabel, SourceType
from app.models.schema import Startup


def test_startup_model_defaults() -> None:
    startup = Startup(name="Example AI")

    assert startup.name == "Example AI"
    assert startup.country == "Brazil"


def test_domain_enums_are_stable() -> None:
    assert AiMaturityLabel.AI_NATIVE == "ai_native"
    assert SourceType.OFFICIAL_SITE == "official_site"
