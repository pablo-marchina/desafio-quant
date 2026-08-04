"""Testes do nó extractor (F2.5).

Tudo offline/determinista (a extração real é opt-in via `extractor_use_llm` + chave,
ou injetando um adapter `extract=`). Exercita:
- `parse_profile`: JSON do Super → `StartupProfile` tipado, com proveniência **ancorada
  nos docs** (fetched_at/content_hash reais, F1.9) e `source_policy` da política de ToS
  (F1.15); tolera valor cru ou `{value, evidence, confidence}`, cercas ```json```,
  campos/itens malformados, e cai na query quando falta o nome;
- `extract_profile`: tipagem da saída do adapter e **degradação p/ None** sem alucinar;
- o nó: no-op offline (sem docs / LLM off), update parcial com `extract` injetado,
  acúmulo de erro na não-extração, e o hook opcional de persistência (F1.10).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import packages.agents.extractor as ex
from packages.agents.extractor import extract_profile, extractor, parse_profile
from packages.schemas import GraphState, RawDocument
from packages.schemas.profile import StartupProfile

_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _doc(url: str = "https://acme.ai", text: str = "Acme constrói agentes de IA.") -> RawDocument:
    return RawDocument(url=url, content=text, fetched_at=_FETCHED, content_hash="hash-acme")


def _full_json() -> str:
    """JSON rico (com cercas + texto ao redor) cobrindo escalares, listas e funding."""
    return """Resultado:
    ```json
    {
      "nome": "Acme AI",
      "website": "https://acme.ai",
      "pais": "BR",
      "descricao": {
        "value": "Plataforma de agentes de IA para fintechs.",
        "evidence": [{"url": "https://acme.ai", "snippet": "Acme constrói agentes de IA."}],
        "confidence": 0.9
      },
      "setor": "Fintech",
      "ano_fundacao": "2021",
      "produtos": [
        {"nome": "Acme Copilot", "categoria": "LLM app",
         "evidence": [{"url": "https://acme.ai", "snippet": "Copilot para bancos."}]}
      ],
      "clientes": [{"nome": "BancoX", "enterprise": true}],
      "founders": [
        {"nome": "Ana Souza", "cargo": "CEO", "linkedin_url": "https://linkedin.com/in/ana"},
        {"nome": "Bia Lima", "cargo": "CTO", "linkedin_url": "nao-e-url"}
      ],
      "tecnologias": [{"nome": "LangGraph", "categoria": "framework", "uso": "orquestração"}],
      "funding": {"total_raised_usd": 5000000, "last_round_stage": "Série A",
                  "investors": ["Fundo Z"]},
      "campo_desconhecido": "ignorado"
    }
    ```"""


# ------------------------------------------------------------------------- parse_profile


def test_parse_profile_maps_all_dimensions() -> None:
    profile = parse_profile(_full_json(), query="Acme AI", docs=[_doc()], run_id="r1")
    assert isinstance(profile, StartupProfile)
    assert profile.nome == "Acme AI"
    assert str(profile.website) == "https://acme.ai/"
    assert profile.descricao.value.startswith("Plataforma")
    assert profile.descricao.confidence == 0.9
    assert profile.setor.value == "Fintech"
    assert profile.ano_fundacao.value == 2021  # string "2021" → int
    assert [p.nome for p in profile.produtos] == ["Acme Copilot"]
    assert profile.clientes[0].enterprise is True
    assert [t.nome for t in profile.tecnologias] == ["LangGraph"]
    assert profile.funding.total_raised_usd == 5000000
    assert profile.funding.investors == ["Fundo Z"]
    assert profile.run_id == "r1"


def test_parse_profile_tolerates_trailing_data_after_object() -> None:
    # Caso Birdie (diag 2026-06-13): o Super emite o objeto + lixo/2º objeto depois → antes
    # quebrava com JSONDecodeError("Extra data"); raw_decode para no 1º objeto e ignora o resto.
    raw = '```json\n{"nome": "Birdie", "setor": "Analytics"}\n```\n{"sobra": "ignorar"}\ntexto'
    profile = parse_profile(raw, query="Birdie", docs=[_doc()])
    assert profile.nome == "Birdie"
    assert profile.setor.value == "Analytics"


def test_user_payload_caps_docs_and_chars() -> None:
    # Fix do timeout (F7.6): payload capado em nº de docs e chars/doc p/ o Super não estourar 120s.
    docs = [_doc(url=f"https://e{i}.com", text="x" * 9000) for i in range(ex.DEFAULT_MAX_DOCS + 3)]
    payload = json.loads(ex._user_payload("Q", docs, doc_chars=ex.DEFAULT_DOC_CHARS))
    assert len(payload["documents"]) == ex.DEFAULT_MAX_DOCS
    assert all(len(d["content"]) <= ex.DEFAULT_DOC_CHARS for d in payload["documents"])


def test_parse_profile_grounds_evidence_in_docs() -> None:
    # proveniência (F1.9): a url citada casa o doc coletado → fetched_at/hash reais.
    profile = parse_profile(_full_json(), query="Acme AI", docs=[_doc()])
    ev = profile.descricao.evidence[0]
    assert ev.fetched_at == _FETCHED
    assert ev.content_hash == "hash-acme"
    assert ev.source_policy  # política de ToS travada carimbada (F1.15)


def test_parse_profile_unknown_field_does_not_break() -> None:
    # "campo_desconhecido" no JSON não derruba (montagem campo a campo, extra ignorado).
    profile = parse_profile(_full_json(), query="Acme AI", docs=[_doc()])
    assert profile.nome == "Acme AI"


def test_parse_profile_drops_invalid_founder_url() -> None:
    # founder com linkedin inválido é mantido, mas sem url (não derruba o perfil).
    profile = parse_profile(_full_json(), query="Acme AI", docs=[_doc()])
    bia = next(f for f in profile.founders if f.nome == "Bia Lima")
    assert bia.linkedin_url is None


def test_parse_profile_source_urls_from_docs_not_model() -> None:
    docs = [_doc("https://acme.ai"), _doc("https://braziljournal.com/acme", "cobertura")]
    profile = parse_profile('{"nome": "Acme"}', query="Acme", docs=docs)
    assert {str(u) for u in profile.source_urls} == {
        "https://acme.ai/",
        "https://braziljournal.com/acme",
    }


def test_parse_profile_missing_name_falls_back_to_query() -> None:
    profile = parse_profile('{"setor": "Fintech"}', query="Empresa X", docs=[_doc()])
    assert profile.nome == "Empresa X"


def test_parse_profile_evidence_without_url_or_snippet_skipped() -> None:
    raw = json.dumps(
        {
            "nome": "Acme",
            "descricao": {
                "value": "x",
                "evidence": [
                    {"snippet": "sem url"},
                    {"url": "https://acme.ai"},  # sem snippet
                    {"url": "https://acme.ai", "snippet": "ok"},
                ],
            },
        }
    )
    profile = parse_profile(raw, query="Acme", docs=[_doc()])
    assert len(profile.descricao.evidence) == 1


def test_parse_profile_evidence_url_not_collected_still_records() -> None:
    # url citada que não está entre os docs: evidência ainda existe, sem hash, com policy.
    raw = json.dumps(
        {
            "nome": "Acme",
            "setor": {
                "value": "Fintech",
                "evidence": [{"url": "https://outra.com", "snippet": "x"}],
            },
        }
    )
    profile = parse_profile(raw, query="Acme", docs=[_doc()])
    ev = profile.setor.evidence[0]
    assert ev.content_hash is None
    assert ev.source_policy


# ------------------------------------------------------------------------ extract_profile


def test_extract_profile_with_injected_adapter() -> None:
    profile = extract_profile(
        "Acme AI", [_doc()], extract=lambda q, d: _full_json(), run_id="r1"
    )
    assert profile is not None
    assert profile.nome == "Acme AI"


def test_extract_profile_returns_none_on_bad_json() -> None:
    assert extract_profile("Acme", [_doc()], extract=lambda q, d: "sem json aqui") is None


def test_extract_profile_returns_none_when_adapter_raises() -> None:
    def boom(q: str, d: list) -> str:
        raise RuntimeError("modelo fora do ar")

    assert extract_profile("Acme", [_doc()], extract=boom) is None


# ------------------------------------------------------------------------------- nó


def test_node_no_docs_is_noop() -> None:
    state = GraphState(run_id="r1", query="Acme")
    assert extractor(state) == {}


def test_node_offline_without_adapter_is_noop(monkeypatch) -> None:
    # docs presentes, mas LLM off e sem adapter injetado → no-op (espinha verde, M2).
    monkeypatch.setattr(ex, "get_settings", lambda: _FakeSettings(use_llm=False))
    state = GraphState(run_id="r1", query="Acme", raw_docs=[_doc()])
    assert extractor(state) == {}


def test_node_with_injected_extract_returns_profile() -> None:
    state = GraphState(run_id="r1", query="Acme AI", raw_docs=[_doc()])
    update = extractor(state, extract=lambda q, d: _full_json())
    assert update["profile"].nome == "Acme AI"
    assert "errors" not in update


def test_node_extraction_failure_accumulates_error() -> None:
    state = GraphState(run_id="r1", query="Acme", raw_docs=[_doc()], errors=["anterior"])
    update = extractor(state, extract=lambda q, d: "lixo sem json")
    assert "profile" not in update
    assert update["errors"][0] == "anterior"  # preserva os antigos
    assert any("extractor" in e for e in update["errors"][1:])


def test_node_persist_hook_is_called() -> None:
    saved: list[StartupProfile] = []
    state = GraphState(run_id="r1", query="Acme AI", raw_docs=[_doc()])
    update = extractor(state, extract=lambda q, d: _full_json(), persist=saved.append)
    assert update["profile"].nome == "Acme AI"
    assert saved and saved[0].nome == "Acme AI"


def test_node_persist_failure_is_recorded_not_fatal() -> None:
    def boom(profile: StartupProfile) -> None:
        raise RuntimeError("sem banco")

    state = GraphState(run_id="r1", query="Acme AI", raw_docs=[_doc()])
    update = extractor(state, extract=lambda q, d: _full_json(), persist=boom)
    assert update["profile"].nome == "Acme AI"  # perfil preservado
    assert any("persistência falhou" in e for e in update["errors"])


class _FakeSettings:
    def __init__(self, *, use_llm: bool) -> None:
        self.extractor_use_llm = use_llm
