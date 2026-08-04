"""Nó **evidence_validator** (F2.7): regra de N fontes + aresta condicional de retry → scraper.

Quinto nó do grafo (ARQUITETURA §3), entre o classifier (F2.6) e o nvidia_rag (F3). Antes de
gastar RAG/recomendação/benchmark sobre o diagnóstico, ele confere que o diagnóstico se apoia
em **pelo menos N fontes independentes** (corroboração — princípio nº1 §8: nada de afirmar
sobre fonte única). Se a corroboração falta e ainda há orçamento de retry, **devolve o grafo
ao scraper (F2.4)** para ampliar a coleta; se há fontes suficientes — ou o retry esgotou —
segue em frente para o RAG.

**Profundidade × largura (complementar ao classifier):** o classifier (F2.6) já trava a
evidência **por sub-score** (`PillarScore`: > 6 exige evidência — *profundidade*). Aqui o gate
é de **largura**: quantas fontes *independentes* sustentam o conjunto do diagnóstico. As duas
travas juntas realizam o princípio nº1 (§8) sem se sobreporem.

**Fonte independente = host distinto.** Duas páginas do mesmo domínio são uma fonte (auto-relato);
o site oficial + uma notícia de outro veículo são duas (corroboração real). Por isso a contagem é
por **host normalizado** (minúsculo, sem `www.`) sobre a proveniência agregada do perfil
(`all_evidence` + `source_urls`), não por URL. `MIN_SOURCES = 2` é o piso de corroboração.

**Roteamento por `Command` (decisão de design b/d):** o nó devolve um `langgraph.types.Command`
que **atualiza o estado e roteia atomicamente** — em vez de um par `nó devolve dict` +
`add_conditional_edges`. Por quê: o retry incrementa `retry_count` e a rota (scraper vs.
nvidia_rag) dependem do *mesmo* veredito; com `Command` há uma única fonte de verdade e o
contador fica **limpo** (incrementa exatamente quando re-coleta, limitado por `can_retry` ⇒
nunca passa de `max_retries`). Uma aresta condicional separada releria `can_retry` já depois do
incremento, criando ambiguidade de fronteira (a 2ª e a última tentativa ficariam
indistinguíveis). Em troca, o `evidence_validator` **não** recebe aresta estática de saída na
montagem (graph.py): as duas pontas são alcançadas pelo `goto` do nó.

**Offline é o default (igual F2.3–F2.6):** sem `profile` **e sem coleta** (espinha offline, M2/DoD:
`raw_docs`/`errors` vazios) não há o que corroborar — o nó **segue limpo** para o nvidia_rag, sem
retry (re-coletar sem rede seria loop sem ganho) e sem alucinar. Determinista/puro: a contagem de
hosts é reprodutível (ethos F2.14), sem rede/LLM/GPU. **Distinto da extração que falhou:** quando a
coleta rodou (há `raw_docs`/`errors`) mas a extração (F2.5) não produziu perfil, o nó **não** segue
adiante — isso concluiria o run COMPLETED **sem briefing** (o `/briefings` 404 e o front ofereceria
um PDF inexistente); trata como "dados insuficientes" (F2.12, abaixo).

**Terminal de baixa confiança (F2.12):** quando o retry esgota e a evidência segue insuficiente,
o nó **não trava nem alucina** — marca o run `INSUFFICIENT_DATA`, deixa a nota rastreável em
`errors` e **salta direto ao `briefing`** (pulando RAG/recomendação/benchmark — sem corroboração
não há o que recomendar). O nó `briefing` (F4.4) despacha esse status para o briefing "dados
insuficientes" (`terminals.insufficient_data_briefing`).

**Terminal "fora de escopo" (F2.13):** o **outro** terminal lê o veredito do classifier (F2.6)
sem mudar a regra de N fontes. Só no ramo **já corroborado** (≥ N fontes) — onde *temos base* —,
se a empresa foi classificada **`non-AI` com confiança** (`classifier.is_confident_non_ai`), o nó
salta ao `briefing` marcando `OUT_OF_SCOPE` em vez de seguir ao RAG: não se força recomendação
NVIDIA sobre quem não é alvo Inception. Gatear pela corroboração mantém os dois terminais
disjuntos — `non-AI` **sem** corroboração cai em "dados insuficientes" (F2.12), não em "fora de
escopo". Ambos saltam ao `briefing` (mesmo `TERMINAL_TARGET`); o nó `briefing` despacha por status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from langgraph.types import Command

from packages.schemas import GraphState, RunStatus, StartupProfile

from .classifier import is_confident_non_ai

if TYPE_CHECKING:
    from collections.abc import Iterable

#: Piso de corroboração: o diagnóstico precisa de ao menos N fontes independentes (hosts
#: distintos) antes de seguir para o RAG/recomendação. 2 = "não afirmar sobre fonte única".
MIN_SOURCES = 2

#: Alvos de roteamento (espelham `graph.PIPELINE`): retry volta ao scraper (re-coleta), o
#: caminho normal segue ao nvidia_rag e os **terminais (F2.12 dados insuficientes / F2.13 fora
#: de escopo)** saltam direto ao briefing (pulam RAG/recomendação/benchmark — nada a recomendar).
#: Os dois terminais compartilham o `TERMINAL_TARGET`; quem distingue é o `status` no update do
#: `Command`. Constantes aqui evitam o ciclo de import com graph.py;
#: `tests/test_evidence_validator.py` guarda contra divergência da espinha.
RETRY_TARGET = "scraper"
CONTINUE_TARGET = "nvidia_rag"
TERMINAL_TARGET = "briefing"


def _host(url: str) -> str:
    """Host normalizado (minúsculo, sem `www.`) de uma URL; vazio se não der p/ parsear.

    Espelha `scraping.source_policy._host`: o `www.` não distingue fonte, então some, para que
    `site.com` e `www.site.com` contem como **uma** fonte.
    """
    raw = url if "://" in url else "//" + url
    host = (urlsplit(raw).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def evidence_sources(profile: StartupProfile) -> set[str]:
    """Hosts **independentes** que sustentam o perfil: proveniência citada + fontes agregadas.

    Une as URLs da evidência por campo (`all_evidence`, o que de fato ancora claims/sub-scores)
    com as fontes consultadas agregadas (`source_urls`), reduzidas a host normalizado. Conjunto
    ⇒ contagem de fontes *distintas* (corroboração), determinística.
    """
    urls: Iterable[object] = (
        *(ev.url for ev in profile.all_evidence),
        *profile.source_urls,
    )
    hosts = {_host(str(u)) for u in urls}
    hosts.discard("")  # URLs impossíveis de parsear não contam como fonte
    return hosts


def is_sufficient(profile: StartupProfile, *, min_sources: int = MIN_SOURCES) -> bool:
    """Regra de N fontes: o perfil se apoia em ≥ `min_sources` hosts independentes?"""
    return len(evidence_sources(profile)) >= min_sources


def evidence_validator(
    state: GraphState, *, min_sources: int = MIN_SOURCES
) -> Command[Literal["scraper", "nvidia_rag", "briefing"]]:
    """F2.7/F2.12/F2.13 — valida a corroboração (N fontes) e roteia: retry, segue ou terminal.

    - Sem perfil **e sem coleta** (espinha offline M2/DoD, `raw_docs`/`errors` vazios): segue limpo
      (nada a corroborar — não se entra em loop sem coleta nem se alucina; termina em COMPLETED).
    - Sem perfil mas **com coleta** (`raw_docs`/`errors` presentes — extração F2.5 falhou): salta ao
      `briefing` marcando `INSUFFICIENT_DATA` (F2.12), em vez de concluir COMPLETED sem briefing
      (que faria o `/briefings` 404 e o front oferecer um PDF inexistente).
    - Fontes suficientes (≥ N hosts) **e `non-AI` de alta confiança (F2.13)**: salta ao `briefing`
      marcando `OUT_OF_SCOPE` — corroborado o suficiente p/ dizer que não é alvo Inception, não se
      força recomendação NVIDIA (o nó emite o terminal "fora de escopo").
    - Fontes suficientes nos demais casos: segue para o RAG (`nvidia_rag`).
    - Insuficiente e ainda com orçamento (`can_retry`): consome um retry, marca `RUNNING` e volta
      ao scraper para ampliar a coleta (F2.4 substitui os `raw_docs` no re-scrape).
    - Insuficiente e retry esgotado (**F2.12**): **não trava nem alucina** — marca o run
      `INSUFFICIENT_DATA`, registra a nota rastreável em `errors` e **salta ao `briefing`**
      (pula RAG/recomendação/benchmark), onde o nó emite o terminal "dados insuficientes".
    """
    profile = state.profile
    if profile is None:
        # Sem perfil há dois casos distintos. A **espinha offline** (M2/DoD) não coletou nada
        # (sem `raw_docs` nem `errors`): não há o que corroborar → segue limpo (re-coletar sem
        # rede seria loop sem ganho; o run termina COMPLETED sem briefing). Mas quando a coleta
        # **rodou de verdade** e a extração (F2.5) não produziu um perfil utilizável — há
        # `raw_docs` coletados e/ou erro registrado —, seguir adiante deixaria o run concluir
        # COMPLETED **sem briefing**: o `GET /briefings/{id}` responde 404 ("briefing não
        # encontrado para o run") e o front oferece um PDF inexistente. Isso é "dados
        # insuficientes" (F2.12): salta ao briefing com o terminal honesto em vez de fingir que
        # concluiu um diagnóstico que não existe.
        if state.raw_docs or state.errors:
            note = (
                "evidência insuficiente: a coleta rodou mas a extração não produziu um perfil "
                "utilizável para diagnóstico (F2.5)"
            )
            return Command(
                goto=TERMINAL_TARGET,
                update={"status": RunStatus.INSUFFICIENT_DATA, "errors": [*state.errors, note]},
            )
        return Command(goto=CONTINUE_TARGET)

    sources = evidence_sources(profile)
    if len(sources) >= min_sources:
        # Corroborado. Antes de gastar RAG/recomendação, o terminal F2.13: empresa `non-AI`
        # cravada com confiança → fora de escopo (sem forçar recomendação NVIDIA). O briefing
        # carrega o porquê (classe + AIMI baixo com evidência); status, não nota de erro —
        # é desfecho legítimo, não falha.
        if is_confident_non_ai(state.aimi):
            return Command(goto=TERMINAL_TARGET, update={"status": RunStatus.OUT_OF_SCOPE})
        return Command(goto=CONTINUE_TARGET)

    if state.can_retry:
        return Command(
            goto=RETRY_TARGET,
            update={"retry_count": state.retry_count + 1, "status": RunStatus.RUNNING},
        )

    note = (
        f"evidência insuficiente: {len(sources)} fonte(s) independente(s) < {min_sources} "
        f"exigida(s) após {state.retry_count} retry(s) de coleta"
    )
    return Command(
        goto=TERMINAL_TARGET,
        update={"status": RunStatus.INSUFFICIENT_DATA, "errors": [*state.errors, note]},
    )


__all__ = [
    "MIN_SOURCES",
    "RETRY_TARGET",
    "CONTINUE_TARGET",
    "TERMINAL_TARGET",
    "evidence_sources",
    "is_sufficient",
    "evidence_validator",
]
