"""Proveniência: `FetchResult` → registro citável na tabela `evidence` (F1.9).

Fecha o ciclo do scraping: o roteador (F1.7) entrega o conteúdo de uma página
(`FetchResult`), e este módulo o transforma no **átomo de proveniência** do §8 da
ARQUITETURA — um registro `evidence` com **url + fetched_at + hash do conteúdo +
snippet** — para sustentar o princípio "nenhuma afirmação/score sem fonte rastreável".

Três peças, todas **puras/offline** (sem rede; persistência só via sessão injetada,
exercitável em SQLite):

- **`content_hash`**: sha256 do texto **normalizado** (whitespace colapsado) — estável
  a reformatações triviais. Serve a integridade e à **dedup** de evidência (mesma URL +
  mesmo conteúdo + mesmo alvo não vira linha repetida a cada run).
- **`make_snippet`**: recorta um trecho citável e limitado do conteúdo. Por padrão pega o
  início; com `around=<termo>` **centraliza** a janela no termo (a afirmação que a
  evidência sustenta), aparando nas bordas de palavra e marcando o corte com reticências.
- **`to_evidence` / `record_evidence`**: montam (e persistem) a linha `evidence`,
  ligando-a a qualquer entidade via (`entity_type`, `entity_id`, `field`) — a chave
  polimórfica da tabela (F0.6). `fetched_at` é injetável: o caller passa o instante real
  do fetch; o default `datetime.now(UTC)` é só o fallback do momento do registro.

`strategy`/`rendered` do `FetchResult` (qual cadeia de adapters produziu o texto) ficam
fora da linha por ora — a tabela `evidence` não tem coluna p/ isso; a auditoria de
*qual caminho* é responsabilidade do tracing (F0.8), não da proveniência da fonte.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from packages.db.models import Evidence

if TYPE_CHECKING:
    from sqlmodel import Session

    from .router import FetchResult

# Tamanho default do trecho citado: longo o bastante p/ dar contexto, curto p/ não copiar
# a página inteira (a fonte canônica é a `url`; o snippet só ancora a citação).
DEFAULT_SNIPPET_CHARS = 320

_WS = re.compile(r"\s+")


def content_hash(content: str) -> str:
    """sha256 (hex) do conteúdo com whitespace normalizado — integridade + dedup.

    Normaliza antes de hashear (colapsa espaços/quebras, apara as pontas) para que
    reformatações triviais da mesma página não gerem hashes diferentes.
    """
    normalized = _WS.sub(" ", content).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def make_snippet(
    text: str, *, around: str | None = None, max_chars: int = DEFAULT_SNIPPET_CHARS
) -> str:
    """Recorta um trecho citável de até `max_chars` (whitespace colapsado).

    Sem `around`, pega o início do conteúdo. Com `around`, **centraliza** a janela na
    primeira ocorrência do termo (case-insensitive) — assim o snippet mostra o contexto
    da afirmação que ele sustenta. Apara as bordas em limite de palavra e marca os cortes
    (início/fim) com reticências, sem quebrar tokens no meio.
    """
    flat = _WS.sub(" ", text).strip()
    if len(flat) <= max_chars:
        return flat

    start = 0
    if around:
        idx = flat.lower().find(around.lower())
        if idx != -1:
            center = idx + len(around) // 2
            start = max(0, min(center - max_chars // 2, len(flat) - max_chars))
    end = start + max_chars

    snippet = flat[start:end]
    # Apara o pedaço de palavra cortado em cada borda interna (só onde houve corte).
    if start > 0 and " " in snippet:
        snippet = snippet.split(" ", 1)[1]
    if end < len(flat) and " " in snippet:
        snippet = snippet.rsplit(" ", 1)[0]

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(flat) else ""
    return f"{prefix}{snippet.strip()}{suffix}"


def to_evidence(
    result: FetchResult,
    *,
    entity_type: str,
    entity_id: int,
    field: str | None = None,
    around: str | None = None,
    fetched_at: datetime | None = None,
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
    source_policy: str | None = None,
) -> Evidence:
    """Converte um `FetchResult` (F1.7) numa linha `evidence` (sem persistir).

    `entity_type`/`entity_id`/`field` ligam a evidência ao alvo (company/founder/score/
    recommendation + campo/pilar/lado). `around` opcionalmente centra o snippet na
    afirmação. `fetched_at` deve ser o instante real do fetch (default = agora, UTC).
    `source_policy` (F1.15) anota sob qual decisão de ToS a fonte foi coletada — o caller
    passa a anotação do gate de fonte (`source_policy.annotate(url)`). Levanta `ValueError`
    se o resultado veio vazio — sem texto não há o que citar.
    """
    if result.is_empty:
        raise ValueError("FetchResult sem texto não vira evidência (nada a citar)")
    return Evidence(
        url=result.url,
        snippet=make_snippet(result.text, around=around, max_chars=snippet_chars),
        fetched_at=fetched_at or datetime.now(UTC),
        content_hash=content_hash(result.text),
        source_title=result.title or None,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        source_policy=source_policy,
    )


def record_evidence(
    session: Session,
    result: FetchResult,
    *,
    entity_type: str,
    entity_id: int,
    field: str | None = None,
    around: str | None = None,
    fetched_at: datetime | None = None,
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
    source_policy: str | None = None,
    dedup: bool = True,
) -> Evidence:
    """Monta a evidência (F1.9) e a persiste na sessão (`flush`); devolve a linha.

    Com `dedup=True` (default), uma evidência já existente com a mesma (url, content_hash)
    para o mesmo alvo (`entity_type`/`entity_id`/`field`) é **reutilizada** em vez de
    duplicada — idempotente entre runs sobre a mesma fonte/conteúdo. `source_policy` (F1.15)
    anota a decisão de ToS da fonte. Faz `flush` (não `commit`): a transação fica a cargo do
    caller (nó do grafo / cohort builder F1.14).
    """
    evidence = to_evidence(
        result,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        around=around,
        fetched_at=fetched_at,
        snippet_chars=snippet_chars,
        source_policy=source_policy,
    )
    return persist_evidence(session, evidence, dedup=dedup)


def persist_evidence(session: Session, evidence: Evidence, *, dedup: bool = True) -> Evidence:
    """Persiste uma linha `evidence` já montada na sessão (dedup-or-add); devolve a linha.

    Metade de baixo nível de `record_evidence`, reusada pela persistência de perfil (F1.10):
    com `dedup=True`, uma linha já existente com a mesma (url, content_hash) para o mesmo
    alvo (`entity_type`/`entity_id`/`field`) é **reutilizada** em vez de duplicada. Faz
    `flush` (não `commit`): a transação fica a cargo do caller.
    """
    if dedup:
        from sqlmodel import select

        existing = session.exec(
            select(Evidence).where(
                Evidence.url == evidence.url,
                Evidence.content_hash == evidence.content_hash,
                Evidence.entity_type == evidence.entity_type,
                Evidence.entity_id == evidence.entity_id,
                Evidence.field == evidence.field,
            )
        ).first()
        if existing is not None:
            return existing

    session.add(evidence)
    session.flush()
    return evidence


__all__ = [
    "DEFAULT_SNIPPET_CHARS",
    "content_hash",
    "make_snippet",
    "to_evidence",
    "record_evidence",
    "persist_evidence",
]
