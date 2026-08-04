"""Persistência de um `StartupProfile` nas tabelas relacionais (F1.10).

Ponte entre a extração (F2.5, que devolve `StartupProfile` com proveniência por campo) e
o schema relacional (F0.6: `company`/`founder`/`evidence`). Faz **upsert idempotente** —
chave que chega atualiza, não duplica — para que o **cohort builder** (F1.14) rode o mesmo
crawl em lote acumulando na tabela `company` sem inflar duplicatas; é essa tabela acumulada
que alimenta o clustering de coorte (F6) e o eval set (F1.12).

**Dedup (precedência forte → fraca):** `cnpj` (registro BR, identidade forte) → `domain`
(host do website, forte) → `(nome, país)` (heurística fraca de último recurso). A primeira
chave que casa identifica a empresa; só se nenhuma casa é que se insere. Em hit, **enriquece**
(preenche vazios, atualiza descritivos) mantendo a identidade — não renomeia uma empresa já
existente, o que mantém estável a chave `(nome, país)` e evita colisão com `uq_company_nome_pais`.

**Escopo geográfico = Brasil (F1.10):** o sourcing já é BR por construção (seeds §9), mas o
discovery por setor/região (F2.3) pode trazer candidata estrangeira. `br_scope` decide o
escopo de um perfil; fica **fora** só quando é *claramente* estrangeiro — `pais` declarado
não-BR **e** sem CNPJ **e** sem domínio `.br`. Conservador por design (na dúvida, mantém).
`persist_profile(enforce_scope=True)` filtra os fora-de-escopo (devolve `None`) p/ o caller
marcar o run `OUT_OF_SCOPE` (F2.12) com a razão da verdict.

Tudo **puro/offline** salvo a persistência, que roda via sessão injetada (testável em SQLite).
Faz `flush`, não `commit`: a transação é do caller (nó do grafo / cohort builder F1.14).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from sqlmodel import select

from packages.db.models import Company, Evidence, Founder

from .lgpd import FOUNDER_LEGAL_BASIS, sanitize_founder
from .provenance import persist_evidence
from .source_policy import annotate as source_policy_for

if TYPE_CHECKING:
    from sqlmodel import Session

    from packages.schemas.evidence import Evidence as EvidenceSchema
    from packages.schemas.profile import Founder as FounderSchema
    from packages.schemas.profile import StartupProfile

# `pais` aceitos como Brasil sem precisar de outro sinal (default do perfil é "BR").
_BR_ALIASES = {"", "BR", "BRA", "BRASIL", "BRAZIL"}

_NON_DIGITS = re.compile(r"\D+")


# --- normalização das chaves (puro) -------------------------------------------


def normalize_domain(url: str | None) -> str | None:
    """Host do `url` normalizado (minúsculo, sem `www.`) — chave de dedup por site.

    Não é eTLD+1 (não usa public-suffix list, sem dependência extra): é o host inteiro
    normalizado, suficiente p/ casar a mesma homepage entre runs. `None` se não houver host.
    """
    if not url or not url.strip():
        return None
    raw = url.strip()
    if "://" not in raw:
        raw = "//" + raw  # sem esquema, força o host a cair no netloc do urlsplit
    host = (urlsplit(raw).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_cnpj(raw: str | None) -> str | None:
    """CNPJ só-dígitos (14) e **válido** (dígitos verificadores), ou `None`.

    Remove a máscara, rejeita placeholders (todos os dígitos iguais) e confere os 2 DVs
    pelo módulo 11. Um CNPJ válido é a chave de dedup mais forte e, por si, sinal de
    operação no Brasil (escopo F1.10).
    """
    if not raw:
        return None
    digits = _NON_DIGITS.sub("", raw)
    if len(digits) != 14 or len(set(digits)) == 1:
        return None
    return digits if _cnpj_check_ok(digits) else None


def _cnpj_check_ok(digits: str) -> bool:
    """Valida os 2 dígitos verificadores do CNPJ (módulo 11)."""

    def dv(base: str) -> int:
        weights = list(range(2, 10)) * 2  # 2..9 repetido, do dígito menos significativo
        total = sum(int(d) * w for d, w in zip(reversed(base), weights, strict=False))
        rem = total % 11
        return 0 if rem < 2 else 11 - rem

    d1 = dv(digits[:12])
    d2 = dv(digits[:12] + str(d1))
    return digits[12:] == f"{d1}{d2}"


# --- escopo geográfico (Brasil) -----------------------------------------------


@dataclass(frozen=True)
class ScopeVerdict:
    """Resultado da decisão de escopo BR (F1.10): em escopo? por quê?"""

    in_scope: bool
    reason: str


def br_scope(profile: StartupProfile) -> ScopeVerdict:
    """Decide se o perfil está no escopo geográfico (Brasil) — F1.10.

    Em escopo por **qualquer** sinal BR: `pais` BR (ou default), CNPJ válido, ou domínio
    `.br`. Fora só quando *claramente* estrangeiro: `pais` declarado não-BR **e** sem CNPJ
    **e** sem domínio `.br`. Conservador (na dúvida, mantém) — barra o vazamento do
    discovery (F2.3), não filtra agressivamente o sourcing que já é BR por construção.
    """
    pais = (profile.pais or "").strip().upper()
    cnpj = normalize_cnpj(profile.cnpj.value) if profile.cnpj else None
    domain = normalize_domain(str(profile.website)) if profile.website else None

    if pais in _BR_ALIASES:
        return ScopeVerdict(True, "país BR (ou default)")
    if cnpj:
        return ScopeVerdict(True, f"CNPJ válido ({cnpj[:2]}…) — operação BR")
    if domain and domain.endswith(".br"):
        return ScopeVerdict(True, f"domínio .br ({domain})")
    return ScopeVerdict(False, f"país {pais!r} sem CNPJ nem domínio .br — fora de escopo BR")


# --- upsert -------------------------------------------------------------------


def upsert_company(
    session: Session, profile: StartupProfile, *, run_id: str | None = None
) -> Company:
    """Upsert idempotente da `company` (dedup CNPJ > domínio > nome,país) — F1.10.

    Procura a linha pela 1ª chave que casar (forte → fraca); em hit **enriquece** (preenche
    vazios + atualiza descritivos) mantendo a identidade (não renomeia); em miss insere.
    Faz `flush` p/ materializar o `id`. Devolve a `Company`.
    """
    cnpj = normalize_cnpj(profile.cnpj.value) if profile.cnpj else None
    website = str(profile.website) if profile.website else None
    domain = normalize_domain(website)
    pais = (profile.pais or "BR").strip().upper() or "BR"

    company = _find_company(session, cnpj=cnpj, domain=domain, nome=profile.nome, pais=pais)
    if company is None:
        company = Company(nome=profile.nome, pais=pais)
        session.add(company)

    # Chaves fortes: só preenche se ainda não fixadas (não sobrescreve identidade).
    company.cnpj = company.cnpj or cnpj
    company.domain = company.domain or domain
    company.website = company.website or website
    if run_id is not None:
        company.run_id = run_id

    # Descritivos: o perfil mais recente prevalece quando traz valor.
    if profile.descricao is not None:
        company.descricao = profile.descricao.value
    if profile.setor is not None:
        company.setor = profile.setor.value
    if profile.ano_fundacao is not None:
        company.ano_fundacao = profile.ano_fundacao.value
    if profile.produtos:
        company.produtos = [_product_row(p) for p in profile.produtos]
    if profile.clientes:
        company.clientes = [_customer_row(c) for c in profile.clientes]
    if profile.tecnologias:
        company.tecnologias = [_tech_row(t) for t in profile.tecnologias]
    if profile.funding is not None:
        company.funding = _funding_row(profile.funding)

    session.flush()
    return company


def upsert_founder(session: Session, company_id: int, founder: FounderSchema) -> Founder | None:
    """Upsert de um `founder` — só info profissional pública (§2 / LGPD / F1.13).

    Passa pela **guarda LGPD** (`sanitize_founder`) antes de gravar: founder com dado
    sensível no núcleo (nome/cargo) é **descartado** (devolve `None`, não coletado); o
    `background` livre é **redigido** (spans sensíveis/pessoais removidos). Dedup dentro da
    empresa por `linkedin_url` (quando houver), senão por nome normalizado (case-insensitive).
    Em hit preenche campos vazios; em miss insere. `flush` p/ o `id`.
    """
    clean = sanitize_founder(founder)
    if not clean.kept:
        return None  # dado sensível no núcleo → não coleta (LGPD F1.13)
    safe = clean.founder

    linkedin = str(safe.linkedin_url) if safe.linkedin_url else None
    row = _find_founder(session, company_id=company_id, linkedin=linkedin, nome=safe.nome)
    if row is None:
        row = Founder(company_id=company_id, nome=safe.nome)
        session.add(row)
    row.cargo = row.cargo or safe.cargo
    row.linkedin_url = row.linkedin_url or linkedin
    row.background = row.background or safe.background
    session.flush()
    return row


def persist_profile(
    session: Session,
    profile: StartupProfile,
    *,
    run_id: str | None = None,
    enforce_scope: bool = True,
) -> Company | None:
    """Persiste o perfil (company + founders + evidência) com dedup e escopo BR (F1.10).

    Com `enforce_scope`, um perfil **fora** do escopo BR (`br_scope`) não é persistido e
    devolve `None` — o caller marca o run `OUT_OF_SCOPE` (F2.12). Caso contrário: upsert da
    company, dos founders, e registro da evidência dos campos escalares e dos founders na
    tabela `evidence` (proveniência rastreável, §8). `flush` (não `commit`): transação do
    caller. As sub-estruturas ricas (produtos/clientes/tecnologias/funding) levam a
    proveniência inline no JSON da `company` (design F0.6).
    """
    if enforce_scope and not br_scope(profile).in_scope:
        return None

    rid = run_id if run_id is not None else profile.run_id
    company = upsert_company(session, profile, run_id=rid)
    _record_company_evidence(session, company, profile)

    for founder in profile.founders:
        row = upsert_founder(session, company.id, founder)
        if row is None:
            continue  # descartado pela guarda LGPD (F1.13)
        _record_founder_evidence(session, row, founder)

    return company


# --- helpers internos ---------------------------------------------------------


def _find_company(
    session: Session, *, cnpj: str | None, domain: str | None, nome: str, pais: str
) -> Company | None:
    """Acha a empresa pela 1ª chave que casar: cnpj → domínio → (nome, país)."""
    if cnpj:
        hit = session.exec(select(Company).where(Company.cnpj == cnpj)).first()
        if hit is not None:
            return hit
    if domain:
        hit = session.exec(select(Company).where(Company.domain == domain)).first()
        if hit is not None:
            return hit
    return session.exec(
        select(Company).where(Company.nome == nome, Company.pais == pais)
    ).first()


def _find_founder(
    session: Session, *, company_id: int, linkedin: str | None, nome: str
) -> Founder | None:
    """Acha o founder da empresa por LinkedIn (quando houver) ou nome normalizado."""
    existing = session.exec(select(Founder).where(Founder.company_id == company_id)).all()
    if linkedin:
        for f in existing:
            if f.linkedin_url == linkedin:
                return f
    key = nome.strip().lower()
    for f in existing:
        if f.nome.strip().lower() == key:
            return f
    return None


def _record_company_evidence(session: Session, company: Company, profile: StartupProfile) -> None:
    """Registra a evidência dos campos escalares da company na tabela `evidence`."""
    for field, claim in (
        ("cnpj", profile.cnpj),
        ("descricao", profile.descricao),
        ("setor", profile.setor),
        ("ano_fundacao", profile.ano_fundacao),
    ):
        if claim is None:
            continue
        for ev in claim.evidence:
            persist_evidence(
                session, _evidence_row(ev, entity_type="company", entity_id=company.id, field=field)
            )


def _record_founder_evidence(session: Session, row: Founder, founder: FounderSchema) -> None:
    """Registra a evidência de um founder na tabela `evidence`, com base legal LGPD (F1.13).

    Toda evidência de founder carrega `legal_basis` = legítimo interesse sobre dado
    profissional público (Art. 7 IX/§4) — o registro auditável que a F1.13 exige.
    """
    for ev in founder.evidence:
        persist_evidence(
            session,
            _evidence_row(
                ev,
                entity_type="founder",
                entity_id=row.id,
                field=None,
                legal_basis=FOUNDER_LEGAL_BASIS.value,
            ),
        )


def _evidence_row(
    ev: EvidenceSchema,
    *,
    entity_type: str,
    entity_id: int,
    field: str | None,
    legal_basis: str | None = None,
) -> Evidence:
    """Converte a `Evidence` do schema (proveniência do perfil) numa linha da tabela.

    `legal_basis` (F1.13) é carimbado pela política de coleta (founder = legítimo interesse);
    para os demais alvos preserva o que a própria evidência já trouxe (ou None).
    """
    return Evidence(
        url=str(ev.url),
        snippet=ev.snippet,
        fetched_at=ev.fetched_at,
        content_hash=ev.content_hash,
        source_title=ev.source_title,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        legal_basis=legal_basis or (ev.legal_basis.value if ev.legal_basis else None),
        # F1.15: carimba sob qual decisão de ToS a fonte foi coletada (auditável por linha).
        source_policy=ev.source_policy or source_policy_for(str(ev.url)),
    )


def _ev_dicts(evidence: list) -> list[dict]:
    """Serializa evidência inline (JSON-safe) p/ as sub-estruturas ricas da company."""
    return [
        {
            "url": str(e.url),
            "snippet": e.snippet,
            "fetched_at": e.fetched_at.isoformat(),
            "content_hash": e.content_hash,
            "source_title": e.source_title,
        }
        for e in evidence
    ]


def _product_row(p) -> dict:
    return {
        "nome": p.nome,
        "descricao": p.descricao,
        "categoria": p.categoria,
        "evidence": _ev_dicts(p.evidence),
    }


def _customer_row(c) -> dict:
    return {
        "nome": c.nome,
        "segmento": c.segmento,
        "enterprise": c.enterprise,
        "evidence": _ev_dicts(c.evidence),
    }


def _tech_row(t) -> dict:
    return {
        "nome": t.nome,
        "categoria": t.categoria,
        "uso": t.uso,
        "evidence": _ev_dicts(t.evidence),
    }


def _funding_row(f) -> dict:
    return {
        "total_raised_usd": f.total_raised_usd,
        "last_round_stage": f.last_round_stage,
        "last_round_date": f.last_round_date,
        "investors": list(f.investors),
        "evidence": _ev_dicts(f.evidence),
    }


__all__ = [
    "normalize_domain",
    "normalize_cnpj",
    "ScopeVerdict",
    "br_scope",
    "upsert_company",
    "upsert_founder",
    "persist_profile",
]
