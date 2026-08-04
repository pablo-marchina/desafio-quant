"""Testes da transcrição dos vídeos do §10.1 (F3.1b).

Cobrem as duas metades da task, ambas offline (sem rede/credencial/GPU):

1. **Interface plugável `Transcriber`** (dogfood Riva + fallback de de-risking): a saída é
   tipada (`Transcript`), a cadeia respeita a ordem de preferência, o `transcribe` cai para o
   próximo backend e os backends reais **degradam limpo** (`TranscriberUnavailable`) sem infra.
2. **Ingestão dos snapshots curados** dos 3 vídeos: entram na KB como `video_transcript` na
   `section: 10.1`, com proveniência (url canônica do YouTube + content_sha256).
"""

from __future__ import annotations

import pytest

from packages.rag import (
    DEFAULT_PREFERENCE,
    RivaTranscriber,
    Transcriber,
    TranscriberUnavailable,
    Transcript,
    TranscriptSegment,
    WhisperTranscriber,
    YouTubeCaptionTranscriber,
    build_transcriber_chain,
    ingest,
    load_kb_sources,
    transcribe,
    transcript_to_markdown,
)
from packages.scraping.provenance import content_hash

# Os 3 vídeos do §10.1 que a F3.1b transcreve para a KB.
VIDEO_IDS = {
    "video-playlist-tecnologias",
    "video-comunidade-startups",
    "video-beneficios-inception",
}


class _StubTranscriber:
    """Transcriber falso (injetável) — prova o contrato sem rede."""

    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.calls: list[str] = []

    def transcribe(self, source: str, *, language: str | None = None) -> Transcript:
        self.calls.append(source)
        if self.fail:
            raise TranscriberUnavailable(f"{self.name}: indisponível (stub)")
        return Transcript(
            video_id="stub",
            url="https://youtu.be/stub",
            title="Stub",
            backend=self.name,
            segments=(TranscriptSegment(text="ola"), TranscriptSegment(text="mundo")),
        )


# --- Interface plugável -----------------------------------------------------------------


def test_transcript_text_and_count_derive_from_segments() -> None:
    t = Transcript(
        video_id="v",
        url="https://youtu.be/v",
        title="T",
        backend="riva",
        segments=(TranscriptSegment(text=" a "), TranscriptSegment(text="b")),
    )
    assert t.text == "a\nb"
    assert t.char_count == len(t.text)


def test_default_preference_is_riva_first() -> None:
    # De-risking da task: Riva (dogfood/narrativa) primeiro, depois os fallbacks.
    assert DEFAULT_PREFERENCE[0] == "riva"
    assert set(DEFAULT_PREFERENCE) == {"riva", "youtube_captions", "whisper"}


def test_build_chain_respects_preference_order() -> None:
    chain = build_transcriber_chain()
    assert [b.name for b in chain] == list(DEFAULT_PREFERENCE)
    assert all(isinstance(b, Transcriber) for b in chain)
    assert isinstance(chain[0], RivaTranscriber)


def test_build_chain_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="desconhecido"):
        build_transcriber_chain(["riva", "nao-existe"])


@pytest.mark.parametrize(
    "backend",
    [RivaTranscriber(), YouTubeCaptionTranscriber(), WhisperTranscriber()],
)
def test_real_backends_degrade_cleanly_offline(backend: Transcriber) -> None:
    # Hooks de rede/GPU: sem infra, levantam TranscriberUnavailable (não travam o build).
    with pytest.raises(TranscriberUnavailable):
        backend.transcribe("https://youtu.be/x")


def test_transcribe_returns_first_success() -> None:
    ok = _StubTranscriber("riva")
    out = transcribe("audio", chain=[ok])
    assert out.backend == "riva"
    assert ok.calls == ["audio"]


def test_transcribe_falls_back_to_next_backend() -> None:
    # De-risking: Riva falha -> cai para o próximo da cadeia e tem sucesso.
    riva = _StubTranscriber("riva", fail=True)
    youtube = _StubTranscriber("youtube_captions")
    out = transcribe("audio", chain=[riva, youtube])
    assert out.backend == "youtube_captions"
    assert riva.calls and youtube.calls  # tentou os dois, em ordem


def test_transcribe_raises_when_whole_chain_unavailable() -> None:
    chain = [_StubTranscriber("a", fail=True), _StubTranscriber("b", fail=True)]
    with pytest.raises(TranscriberUnavailable, match="nenhum backend"):
        transcribe("audio", chain=chain)


def test_real_chain_is_unavailable_offline() -> None:
    # A cadeia default (backends reais) também degrada limpo sem infra de ASR.
    with pytest.raises(TranscriberUnavailable):
        transcribe("https://youtu.be/x")


def test_transcript_to_markdown_is_ingestible() -> None:
    t = _StubTranscriber("riva").transcribe("audio")
    md = transcript_to_markdown(t)
    assert t.title in md
    assert t.url in md  # fonte citável no snapshot
    assert "ola" in md and "mundo" in md  # corpo da transcrição


# --- Ingestão dos snapshots curados (§10.1) ---------------------------------------------


def test_section_10_1_videos_are_in_manifest() -> None:
    by_id = {s.id: s for s in load_kb_sources()}
    assert VIDEO_IDS <= set(by_id)
    for vid in VIDEO_IDS:
        src = by_id[vid]
        assert src.section == "10.1"
        assert src.source_type == "video_transcript"
        assert "youtu" in src.url  # vídeo do YouTube (§10.1)


def test_video_transcripts_ingest_with_provenance() -> None:
    docs = {d.id: d for d in ingest() if d.id in VIDEO_IDS}
    assert set(docs) == VIDEO_IDS
    for d in docs.values():
        assert d.text.strip()  # snapshot curado não-vazio
        assert d.url.startswith("http")  # fonte rastreável (§8)
        assert d.content_sha256 == content_hash(d.text)
