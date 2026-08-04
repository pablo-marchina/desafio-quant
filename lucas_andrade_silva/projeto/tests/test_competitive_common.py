from types import SimpleNamespace

from agents.nvidia.competitive import common


def test_call_json_satisfies_groq_json_object_requirement(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"validado": true}')
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )
    monkeypatch.setattr(common, "required_env", lambda _: "test-key")
    monkeypatch.setattr(common, "Groq", lambda **_: fake_client)

    result = common.call_json("Retorne um objeto.", {"entrada": "teste"})

    assert result == {"validado": True}
    assert "json" in captured["messages"][0]["content"]
    assert captured["response_format"] == {"type": "json_object"}
