"""Transcrição dos vídeos do §10.1 -> texto p/ a KB (F3.1b).

Dogfood do **NVIDIA Riva (ASR)**: transforma o Riva de "só recomendável" (na KB, §5.5
voz/call center) em tecnologia NVIDIA **efetivamente usada** pelo TAPI — é o Riva que
transcreve os vídeos do §10.1 (playlist de tecnologias, vídeo da comunidade, live de
benefícios do Inception) para a base de conhecimento.

Decisões (F3.1b):

- **Interface plugável `Transcriber`** (o trade-off de infra de ASR que a task nomeia): o
  backend **preferido** é o **Riva NIM** (pela narrativa), com **fallback de de-risking**
  para legendas do YouTube ou Whisper — "não deixar o RAG bloqueado pela infra de ASR". A
  ordem de preferência (Riva -> YouTube -> Whisper) vive em `DEFAULT_PREFERENCE`/`transcribe`.
- **Os backends reais são hooks de rede/GPU** — como o refresh ao vivo da F3.1 e o
  `scraper_use_network` (F2.4) ficam *off* por default: cada `transcribe()` exige
  endpoint/credencial/deps e levanta `TranscriberUnavailable` quando a infra não está
  montada. O build/CI degrada para o snapshot curado e nunca trava na ASR.
- **O conteúdo que alimenta o RAG é offline e determinístico** (decisão travada na F3.1,
  espinha verde dos nós F2): a transcrição "não é valor central", então os 3 vídeos entram
  na KB como **snapshots curados** (`data/knowledge_base/docs/<id>.md`, `source_type:
  video_transcript`, `section: 10.1`), citáveis pela `url` canônica do YouTube +
  `captured_at` — os mesmos campos sustentam o refresh ao vivo via Riva (hook futuro).
- `transcript_to_markdown` rende um `Transcript` no **mesmo formato curado** que o `ingest`
  (F3.1) lê: liga o caminho ao vivo (futuro) ao snapshot offline sem rodar rede.

Nada aqui faz rede no caminho testado: a interface é exercitada com transcribers falsos
(injetáveis), e os backends reais provam apenas que **degradam limpo** quando a infra falta.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

# Ordem de preferência de de-risking (task F3.1b): Riva (narrativa/dogfood) primeiro;
# legendas do YouTube e Whisper como fallback para não bloquear o RAG na infra de ASR.
DEFAULT_PREFERENCE: tuple[str, ...] = ("riva", "youtube_captions", "whisper")


class TranscriberUnavailable(RuntimeError):
    """Backend de ASR sem infra (endpoint/credencial/deps).

    Sinaliza que aquele backend não pode transcrever **agora** — o `transcribe` cai para o
    próximo da cadeia e, esgotada a cadeia, o RAG usa o snapshot curado da KB. Não é erro de
    programação: é o ponto de degradação gracioso da infra de ASR.
    """


class TranscriptSegment(BaseModel):
    """Trecho transcrito, opcionalmente com marcação de tempo (segundos)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    start: float | None = Field(default=None, description="Início do trecho em segundos.")
    end: float | None = Field(default=None, description="Fim do trecho em segundos.")


class Transcript(BaseModel):
    """Saída tipada de um `Transcriber`: a transcrição de um vídeo do §10.1 + proveniência.

    `text`/`char_count` são derivados dos segmentos (fonte única) — o `transcript_to_markdown`
    os usa para gerar o snapshot curado que a KB ingere (F3.1).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    video_id: str = Field(description="Slug estável do vídeo (casa com o `id` do manifesto).")
    url: str = Field(description="URL canônica do vídeo (§10.1) — proveniência citável.")
    title: str
    backend: str = Field(description="Backend de ASR que produziu a transcrição (ex.: 'riva').")
    language: str = Field(default="en", description="Idioma falado no vídeo (não o de saída).")
    segments: tuple[TranscriptSegment, ...] = Field(default_factory=tuple)

    @property
    def text(self) -> str:
        """Transcrição completa: segmentos unidos por quebra de linha."""
        return "\n".join(seg.text.strip() for seg in self.segments).strip()

    @property
    def char_count(self) -> int:
        return len(self.text)


@runtime_checkable
class Transcriber(Protocol):
    """Contrato de um backend de ASR (peça plugável). `name` identifica o backend no trace."""

    name: str

    def transcribe(self, source: str, *, language: str | None = None) -> Transcript:
        """Transcreve `source` (URL/arquivo de áudio) -> `Transcript`.

        Deve levantar `TranscriberUnavailable` se a infra (endpoint/credencial/deps) faltar.
        """
        ...


class _NetworkBackend:
    """Base dos backends reais: hook de rede/GPU que degrada limpo offline.

    O caminho ao vivo (chamar o serviço de ASR) é trabalho de infra futura — aqui ele apenas
    levanta `TranscriberUnavailable` com a instrução do que montar, para o `transcribe` cair
    no próximo backend e, no fim, o RAG usar o snapshot curado (F3.1).
    """

    name = "network"
    requirement = "infra de ASR"

    def transcribe(self, source: str, *, language: str | None = None) -> Transcript:
        raise TranscriberUnavailable(
            f"{self.name}: {self.requirement} não configurada — backend de rede/GPU (hook "
            "F3.1b). Offline o RAG usa o snapshot curado do §10.1."
        )


class RivaTranscriber(_NetworkBackend):
    """Backend **preferido** (dogfood): ASR via NVIDIA Riva NIM. Hook de rede/GPU."""

    name = "riva"
    requirement = "endpoint do Riva ASR NIM (+ nvidia-riva-client)"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url


class YouTubeCaptionTranscriber(_NetworkBackend):
    """Fallback de de-risking: legendas oficiais do YouTube. Hook de rede."""

    name = "youtube_captions"
    requirement = "acesso às legendas do YouTube (youtube-transcript-api)"


class WhisperTranscriber(_NetworkBackend):
    """Fallback de de-risking: ASR open-source (Whisper). Hook de GPU/CPU + deps."""

    name = "whisper"
    requirement = "modelo Whisper (openai-whisper / faster-whisper)"


# Registro dos backends conhecidos — `build_transcriber_chain` instancia na ordem pedida.
_BACKENDS: dict[str, type[_NetworkBackend]] = {
    "riva": RivaTranscriber,
    "youtube_captions": YouTubeCaptionTranscriber,
    "whisper": WhisperTranscriber,
}


def build_transcriber_chain(prefer: Sequence[str] = DEFAULT_PREFERENCE) -> tuple[Transcriber, ...]:
    """Monta a cadeia de transcribers na ordem de preferência (Riva -> fallback).

    Levanta `ValueError` se um nome de backend for desconhecido (erro de config, não de infra).
    """
    chain: list[Transcriber] = []
    for name in prefer:
        cls = _BACKENDS.get(name)
        if cls is None:
            raise ValueError(f"backend de ASR desconhecido: {name!r}")
        chain.append(cls())
    return tuple(chain)


def transcribe(
    source: str,
    *,
    language: str | None = None,
    chain: Sequence[Transcriber] | None = None,
    prefer: Sequence[str] = DEFAULT_PREFERENCE,
) -> Transcript:
    """Transcreve `source` tentando os backends em ordem, com fallback de de-risking.

    Devolve a primeira transcrição bem-sucedida. Cada `TranscriberUnavailable` faz cair para o
    próximo backend; esgotada a cadeia, levanta `TranscriberUnavailable` agregando as falhas
    (o caller — futura ingestão ao vivo — então degrada para o snapshot curado da KB). `chain`
    injeta transcribers (p/ teste offline); `prefer` escolhe a ordem dos backends reais.
    """
    backends = tuple(chain) if chain is not None else build_transcriber_chain(prefer)
    if not backends:
        raise ValueError("cadeia de transcrição vazia — nenhum backend para tentar")

    failures: list[str] = []
    for backend in backends:
        try:
            return backend.transcribe(source, language=language)
        except TranscriberUnavailable as exc:
            failures.append(str(exc))
    raise TranscriberUnavailable(
        "nenhum backend de ASR disponível (" + " | ".join(failures) + ")"
    )


def transcript_to_markdown(transcript: Transcript) -> str:
    """Rende um `Transcript` no formato curado `docs/<id>.md` que o `ingest` (F3.1) lê.

    Mantém o snapshot offline e o caminho ao vivo (Riva) na MESMA forma: cabeçalho com título
    e fonte citável (url + backend) seguido do corpo da transcrição. Determinístico e sem rede.
    """
    header = (
        f"# {transcript.title}\n\n"
        f"> Transcrição do vídeo do §10.1 ({transcript.backend}) — fonte: {transcript.url}\n"
    )
    return f"{header}\n{transcript.text}\n"


__all__ = [
    "DEFAULT_PREFERENCE",
    "TranscriberUnavailable",
    "TranscriptSegment",
    "Transcript",
    "Transcriber",
    "RivaTranscriber",
    "YouTubeCaptionTranscriber",
    "WhisperTranscriber",
    "build_transcriber_chain",
    "transcribe",
    "transcript_to_markdown",
]
