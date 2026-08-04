from app.evaluation.acceptance import stratified_sample


def _item(index, classification, status="completed"):
    return {
        "id": str(index),
        "startup_name": f"Startup {index}",
        "status": status,
        "result_summary": {"classificacao": classification},
    }


def test_stratified_sample_is_deterministic_and_covers_classes():
    items = [
        _item(1, "AI-native"),
        _item(2, "AI-native"),
        _item(3, "AI-enabled"),
        _item(4, "AI-enabled"),
        _item(5, "API-consumer"),
        _item(6, "Non-AI"),
    ]

    first = stratified_sample(items, sample_size=4, seed=42)
    second = stratified_sample(items, sample_size=4, seed=42)

    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert {item["result_summary"]["classificacao"] for item in first} == {
        "AI-native",
        "AI-enabled",
        "API-consumer",
        "Non-AI",
    }


def test_stratified_sample_rejects_invalid_size():
    try:
        stratified_sample([_item(1, "AI-native")], sample_size=2, seed=1)
    except ValueError as exc:
        assert "sample_size" in str(exc)
    else:
        raise AssertionError("Tamanho invalido deveria falhar")
