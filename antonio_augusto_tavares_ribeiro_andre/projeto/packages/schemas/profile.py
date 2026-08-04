"""StartupProfile e sub-modelos (F0.5).

Cobre **todas** as dimensões do §2 do brief (empresa, produto, setor, clientes,
funding, founders, tecnologias), cada campo com proveniência via `Claim`. Alimenta
o classifier/AIMI (F2.6) e a coorte (F6): `funding` → prontidão de coorte (F6.7);
`clientes`/distribuição → pilares Distribution e Data Moat; `tecnologias` →
Technical Optimization.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .evidence import Claim, Evidence


class Founder(BaseModel):
    """Fundador/liderança — apenas info profissional pública (ARQUITETURA §2 / LGPD)."""

    nome: str
    cargo: str | None = Field(default=None, description="Papel (CEO, CTO, ...).")
    linkedin_url: HttpUrl | None = None
    background: str | None = Field(
        default=None, description="Histórico profissional público resumido."
    )
    evidence: list[Evidence] = Field(default_factory=list)


class Funding(BaseModel):
    """Captação — alimenta a prontidão de coorte (F6.7)."""

    total_raised_usd: float | None = Field(default=None, ge=0)
    last_round_stage: str | None = Field(
        default=None, description="Estágio do último round (Seed, Série A, ...)."
    )
    last_round_date: str | None = Field(default=None, description="Data/ano do último round.")
    investors: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class Product(BaseModel):
    """Produto/oferta da startup."""

    nome: str
    descricao: str | None = None
    categoria: str | None = Field(default=None, description="Categoria/segmento do produto.")
    evidence: list[Evidence] = Field(default_factory=list)


class Customer(BaseModel):
    """Cliente/logo público — alimenta Distribution & Moat (P4) e Data Moat (P1)."""

    nome: str
    segmento: str | None = None
    enterprise: bool | None = Field(
        default=None, description="Indício de cliente enterprise (sinal de P4)."
    )
    evidence: list[Evidence] = Field(default_factory=list)


class Technology(BaseModel):
    """Tecnologia/stack identificada — sinal-chave de Technical Optimization (P3)."""

    nome: str
    categoria: str | None = Field(
        default=None,
        description="Ex.: LLM provider, framework, serving, infra, data.",
    )
    uso: str | None = Field(default=None, description="Como a startup usa a tecnologia.")
    evidence: list[Evidence] = Field(default_factory=list)


class StartupProfile(BaseModel):
    """Perfil estruturado de uma startup, com proveniência por campo (§2).

    Saída do nó `extractor` (F2.5); persistido nas tabelas `company`/`founder`/...
    (F0.6). Campos escalares ricos vêm como `Claim` (valor + evidência); coleções
    carregam evidência por item.
    """

    model_config = ConfigDict(extra="forbid")

    # Identidade
    nome: str = Field(description="Nome da empresa.")
    website: HttpUrl | None = None
    pais: str = Field(default="BR", description="País-sede (escopo v1 = BR, F1.10).")
    cnpj: Claim[str] | None = Field(
        default=None, description="CNPJ (registro BR) — chave de dedup e sinal de escopo (F1.10)."
    )

    # Dimensões do §2 (com proveniência)
    descricao: Claim[str] | None = Field(default=None, description="O que a empresa faz.")
    setor: Claim[str] | None = Field(default=None, description="Setor/vertical de atuação.")
    ano_fundacao: Claim[int] | None = None

    produtos: list[Product] = Field(default_factory=list)
    clientes: list[Customer] = Field(default_factory=list)
    founders: list[Founder] = Field(default_factory=list)
    tecnologias: list[Technology] = Field(default_factory=list)
    funding: Funding | None = None

    # Rastreabilidade do run
    run_id: str | None = Field(default=None, description="Run do grafo que gerou o perfil.")
    source_urls: list[HttpUrl] = Field(
        default_factory=list, description="Fontes consultadas (proveniência agregada)."
    )

    @property
    def all_evidence(self) -> list[Evidence]:
        """Achata toda a evidência do perfil (auditoria/persistência)."""
        ev: list[Evidence] = []
        for claim in (self.cnpj, self.descricao, self.setor, self.ano_fundacao):
            if claim is not None:
                ev.extend(claim.evidence)
        for coll in (self.produtos, self.clientes, self.founders, self.tecnologias):
            for item in coll:
                ev.extend(item.evidence)
        if self.funding is not None:
            ev.extend(self.funding.evidence)
        return ev
