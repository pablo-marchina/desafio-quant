"""Eval set rotulado de startups — schema + loader (F1.12).

Conjunto de ground-truth (~20–30 startups) com **classificação** (§5.1) e **AIMI
esperado** (4 pilares × 0–25) por empresa, criado **cedo** porque F6.4 (correlação do
índice) e F7.1/F7.2 (métricas) o **consomem** — F7 só consolida/expande, não cria do
zero. Os rótulos seguem a **definição** de `docs/ARQUITETURA.md §3.6` (F0.11), nunca a
heurística de pontuação (v0 F2.6 / v1 F6.1): a escala 0–25 é imutável, então mudar a
heurística não invalida o ground-truth.

A anotação carrega também a **região do plano `classe × AIMI`** (`PlaneRegion`, o "Mapa
de decisão" da RUBRICA §6 / ALINHAMENTO) — separa explicitamente *wrapper* (região,
não classe) do *alvo de graduação* ★ (AI-native, P1/P2 alto, **P3 baixo** = maior
upside NVIDIA, F6.13). `expected_techs` é opcional e antecipa o contrato do eval de
recomendação (F7.2b: techs esperadas por empresa), cada uma com **prioridade** opcional
(F7.7: ALTA = a alavanca que importa, base do `recall@ALTA`; MÉDIA/BAIXA = leque). O YAML
aceita a forma chapada (`"NVIDIA NIM"`) e a rica (`{tech: ..., prioridade: alta}`); a view
só-nomes fica em `expected_nvidia_techs` (retrocompat + métrica de presença).

Os dados vivem em `data/eval/*.yaml` (versionados, human-reviewed). O loader valida a
**coerência direcional** da anotação (ex.: um `non-AI` não pode ter Workflow Depth alto
*por IA*; um alvo de graduação tem P3 baixo) — checagem de sanidade da rotulagem, **não**
o corte calibrado da decisão (esse é F6.4). Puro/offline, como o loader de seeds (F0.9).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.aimi import band_for
from packages.schemas.enums import AIMIBand, AIMIPillar, Classification, PlaneRegion, Priority

# data/eval/ na raiz do repo (packages/eval/dataset.py -> parents[2] == raiz).
EVAL_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"

# Limiares **direcionais** da anotação (sanidade da rotulagem, NÃO o corte de decisão —
# esse é calibrado no eval, F6.4). "Estabelecido" começa em 13; P3 "baixo" = ≤ 8.
_ESTABELECIDO_MIN = 13
_P3_BAIXO_MAX = 8

# Classe estruturalmente exigida por região (definicional, não numérico).
_REGION_CLASS: dict[PlaneRegion, Classification] = {
    PlaneRegion.FORA_ESCOPO: Classification.NON_AI,
    PlaneRegion.PERIFERICO: Classification.AI_ENABLED,
    PlaneRegion.WRAPPER: Classification.AI_NATIVE,
    PlaneRegion.ALVO_GRADUACAO: Classification.AI_NATIVE,
    PlaneRegion.MADURO: Classification.AI_NATIVE,
}


class ExpectedPillars(BaseModel):
    """AIMI esperado: 4 pilares × 0–25 (RUBRICA §§2–5). `total` = soma (0–100)."""

    model_config = ConfigDict(extra="forbid")

    data_moat: int = Field(ge=0, le=25)
    workflow_depth: int = Field(ge=0, le=25)
    technical_optimization: int = Field(ge=0, le=25)
    distribution_moat: int = Field(ge=0, le=25)

    @property
    def total(self) -> int:
        """AIMI total esperado (0–100) — fonte de verdade da correlação F6.4."""
        return (
            self.data_moat
            + self.workflow_depth
            + self.technical_optimization
            + self.distribution_moat
        )

    def band(self, pillar: AIMIPillar) -> AIMIBand:
        """Faixa (RUBRICA §1) do pilar — `pillar.value` casa o nome do campo."""
        return band_for(getattr(self, pillar.value))


class ExpectedTech(BaseModel):
    """Uma tech NVIDIA esperada no rótulo (F7.2b) com **prioridade** opcional (F7.7).

    `prioridade=None` é a forma chapada legada (só presença, sem rank). Quando presente, ALTA marca a
    **alavanca que importa** (entra no `recall@ALTA`, o headline knob-free) e MÉDIA/BAIXA o leque que o
    §5.5/F4.8 obriga a regra a emitir — distinção que a métrica priority-aware (F7.7) usa para parar de
    penalizar o leque BAIXA como FP. A prioridade do rótulo vem do **gap do perfil**, nunca da saída da
    regra (anti-circularidade, a lição de 2026-06-21).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tech: str = Field(description="Nome do produto/tech NVIDIA (casa o rótulo F7.2b por substring).")
    prioridade: Priority | None = Field(
        default=None,
        description="ALTA/MÉDIA/BAIXA do rótulo (F7.7); None = forma chapada (sem rank).",
    )


class LabeledStartup(BaseModel):
    """Uma startup rotulada do eval set (ground-truth).

    `label_source` distingue a origem do rótulo: **human** = revisado por humano (headline, default do
    `load_eval_set`) — as reais curadas contra evidência pública (F7.1) e as fixtures sintéticas
    escritas à mão sobre a rubrica (`docs/ARQUITETURA.md §3.6`); **model** = auto-rotulada pelo pipeline (F7.1),
    baseline **circular**, fora do headline (só com `include_model=True`). Nem toda entrada é human-reviewed.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    nome: str
    setor: str
    descricao: str
    pais: str = "BR"
    classificacao: Classification
    region: PlaneRegion
    aimi: ExpectedPillars
    model_aimi: ExpectedPillars | None = Field(
        default=None,
        description="AIMI que a heurística (F6.1) computou sobre a EVIDÊNCIA RASPADA COMPLETA na "
        "produção (F1.14) — só nas entradas reais. O eval usa isto como **predito**, porque a "
        "produção vê a evidência inteira, não a `descricao`-resumo de 1 linha (que faz a "
        "heurística afundar no piso e falsear a correlação). Ausente nas fixtures sintéticas "
        "(prosa rica = a descrição já É o sinal). Distinto do `aimi` (rótulo/ground-truth).",
    )
    expected_techs: list[ExpectedTech] = Field(
        default_factory=list,
        validation_alias="expected_nvidia_techs",
        description=(
            "Techs NVIDIA esperadas por empresa (eval de recomendação, F7.2b), cada uma com "
            "`prioridade` opcional (F7.7). No YAML aceita a forma chapada ('NVIDIA NIM') e a rica "
            "({tech: 'NVIDIA NIM', prioridade: alta}); o validator normaliza as duas. A view "
            "só-nomes fica em `expected_nvidia_techs` (retrocompat + métrica de presença)."
        ),
    )

    @field_validator("expected_techs", mode="before")
    @classmethod
    def _normalize_expected_techs(cls, raw: object) -> object:
        """Forma chapada ('NVIDIA NIM') e rica ({tech, prioridade}) → dicts normalizados (F7.7).

        Mantém o YAML legado válido (string = tech sem rank) e habilita o rótulo priorizado sem uma
        segunda chave que pudesse dessincronizar — tech e prioridade vivem no mesmo item.
        """
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return [{"tech": item} if isinstance(item, str) else item for item in raw]
        return raw  # tipo inesperado: deixa o erro p/ a validação do campo
    rationale: str = Field(description="Justificativa do rótulo, ancorada na RUBRICA.")
    evidence_urls: list[str] = Field(
        default_factory=list, description="Fontes públicas que sustentam o rótulo (rastreável)."
    )
    synthetic: bool = Field(
        default=False,
        description="True = fixture-semente ancorada na rubrica (sem fonte ao vivo); "
        "False = empresa real e exige evidence_urls.",
    )
    label_source: Literal["human", "model"] = Field(
        default="human",
        description="human = ground-truth revisado (headline); model = rótulo proposto pelo "
        "pipeline sobre empresa real (F7.1) — baseline **circular**, reportado à parte.",
    )
    notes: str = ""

    @property
    def expected_nvidia_techs(self) -> list[str]:
        """Nomes das techs esperadas (view chapada) — retrocompat + métrica de presença (F7.2b).

        O rótulo rico (com `prioridade`, F7.7) vive em `expected_techs`; este atalho devolve só os
        nomes, que é o que a métrica de presença (`recommendation_metrics`) e o serializer do
        `cohort_to_eval` consomem — assim introduzir a prioridade não muda nenhum número.
        """
        return [t.tech for t in self.expected_techs]

    @model_validator(mode="after")
    def _check_coherence(self) -> LabeledStartup:
        # Estrutural: a região fixa a classe (definicional).
        expected = _REGION_CLASS[self.region]
        if self.classificacao is not expected:
            raise ValueError(
                f"{self.id}: região {self.region.value} exige classe {expected.value}, "
                f"veio {self.classificacao.value}."
            )
        wf = self.aimi.workflow_depth
        p3 = self.aimi.technical_optimization
        p1p2 = max(self.aimi.data_moat, wf)  # o "P1 ou P2" do alvo de graduação
        # Direcional (sanidade, não o corte F6.4): non-AI não é AI-native "por IA".
        if self.classificacao is Classification.NON_AI and wf > _P3_BAIXO_MAX:
            raise ValueError(
                f"{self.id}: non-AI não pode ter Workflow Depth alto por IA (coerência direcional)."
            )
        if self.region in (PlaneRegion.WRAPPER, PlaneRegion.ALVO_GRADUACAO) and p3 > _P3_BAIXO_MAX:
            raise ValueError(
                f"{self.id}: região {self.region.value} pressupõe P3 baixo (≤{_P3_BAIXO_MAX}); "
                f"veio {p3} (100% API externa é o gap NVIDIA)."
            )
        if self.region is PlaneRegion.ALVO_GRADUACAO and p1p2 < _ESTABELECIDO_MIN:
            raise ValueError(
                f"{self.id}: alvo de graduação exige P1 ou P2 ≥ {_ESTABELECIDO_MIN} (estabelecido)."
            )
        if self.region is PlaneRegion.MADURO and p3 < _ESTABELECIDO_MIN:
            raise ValueError(
                f"{self.id}: maduro exige P3 estabelecido (≥{_ESTABELECIDO_MIN}): stack própria."
            )
        # Rastreabilidade: empresa real precisa de fonte; fixture-semente é dispensada.
        if not self.synthetic and not self.evidence_urls:
            raise ValueError(f"{self.id}: entrada real (synthetic=false) exige ≥1 evidence_url.")
        return self


@lru_cache
def load_eval_set(include_model: bool = False) -> tuple[LabeledStartup, ...]:
    """Carrega (cacheado) as entradas de `data/eval/*.yaml`. IDs são únicos.

    Por padrão devolve **só o ground-truth human-reviewed** (`label_source='human'`) — é o que
    sustenta os números headline e os gates do §7. `include_model=True` inclui as entradas
    reais **auto-rotuladas** pelo pipeline (F7.1), mantidas à parte porque medir o modelo contra
    o próprio rótulo é um **baseline circular** (reportado como tal, não fundido no headline).
    """
    entries: list[LabeledStartup] = []
    seen: set[str] = set()
    for path in sorted(EVAL_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in data.get("entries", []):
            entry = LabeledStartup.model_validate(raw)
            if entry.id in seen:
                raise ValueError(f"id de eval duplicado: {entry.id!r}")
            seen.add(entry.id)
            entries.append(entry)
    if not entries:
        raise ValueError(f"nenhuma entrada de eval carregada de {EVAL_DIR}")
    if not include_model:
        entries = [e for e in entries if e.label_source == "human"]
    return tuple(entries)


def by_classification(classificacao: Classification) -> tuple[LabeledStartup, ...]:
    """Entradas de uma classe (§5.1) — base do macro-F1 (F7.2)."""
    return tuple(e for e in load_eval_set() if e.classificacao is classificacao)


def by_region(region: PlaneRegion) -> tuple[LabeledStartup, ...]:
    """Entradas de uma região do plano `classe × AIMI` (RUBRICA §6)."""
    return tuple(e for e in load_eval_set() if e.region is region)


def by_label_source(source: Literal["human", "model"]) -> tuple[LabeledStartup, ...]:
    """Entradas por origem do rótulo: `human` (headline) ou `model` (real auto, F7.1)."""
    return tuple(e for e in load_eval_set(include_model=True) if e.label_source == source)


def class_distribution() -> dict[Classification, int]:
    """Contagem por classe — diagnóstico de balanceamento do conjunto."""
    dist = dict.fromkeys(Classification, 0)
    for e in load_eval_set():
        dist[e.classificacao] += 1
    return dist


__all__ = [
    "EVAL_DIR",
    "ExpectedPillars",
    "ExpectedTech",
    "LabeledStartup",
    "load_eval_set",
    "by_classification",
    "by_region",
    "by_label_source",
    "class_distribution",
]
