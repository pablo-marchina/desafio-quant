"""Guarda LGPD para dado de founder (F1.13).

A coleta de `founders` (§2) restringe-se a **informação profissional pública** — nome,
cargo, empresa, perfil público (LinkedIn) — sob **legítimo interesse** (LGPD Art. 7, IX)
sobre **dado manifestamente público** (Art. 7, §4). Este módulo é a barreira que faz
valer isso, em duas frentes, ambas **puras/offline** (regex sobre texto, sem rede):

- **`scan_sensitive`/`redact`**: detectam **dado pessoal sensível** (Art. 5, II — saúde,
  religião, opinião política, raça/etnia, vida sexual, filiação sindical, dado biométrico/
  genético) e **identificadores pessoais** que não são profissionais (CPF, contato pessoal,
  CEP, data de nascimento/idade, estado civil). `redact` substitui o trecho por um marcador.
- **`sanitize_founder`**: aplica a política — **descarta** o founder se o núcleo (nome/cargo)
  contém dado sensível (extração suspeita) e **redige** o `background` livre, removendo
  spans sensíveis sem perder a narrativa profissional. Devolve a base legal a carimbar na
  tabela `evidence` (a persistência F1.10/F1.13 grava `legal_basis`).

A guarda **não** substitui a compliance de fetch (robots/ToS, F1.8/F1.15) — é a camada de
*minimização de dado* sobre o que já foi licitamente acessado. Conservadora por design:
na dúvida, remove.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from packages.schemas.enums import LegalBasis
from packages.schemas.profile import Founder

# Base legal da coleta de founder: legítimo interesse sobre dado profissional público.
FOUNDER_LEGAL_BASIS = LegalBasis.LEGITIMO_INTERESSE

# Marcador que substitui um trecho removido (auditável no texto redigido).
REDACTION = "[removido: LGPD]"

SensitiveCategory = Literal[
    "saude",
    "religiao",
    "politica",
    "raca_etnia",
    "orientacao_sexual",
    "sindical",
    "biometrico_genetico",
    "cpf",
    "contato_pessoal",
    "vida_pessoal",
]

# Léxico/padrões por categoria. Dado sensível = LGPD Art. 5, II; identificadores pessoais =
# fora do escopo "profissional público". Termos curtos/ambíguos ficam de fora; padrões de
# idade exigem "de idade" p/ não casar "20 anos de experiência".
_PATTERNS: dict[SensitiveCategory, re.Pattern[str]] = {
    "saude": re.compile(
        r"\b(?:hiv|aids|câncer|cancer|depressão|depressao|ansiedade|transtorno|"
        r"deficiência|deficiencia|doença|doenca|diagnóstico|diagnostico|"
        r"saúde mental|saude mental)\b",
        re.IGNORECASE,
    ),
    "religiao": re.compile(
        r"\b(?:católic[oa]s?|catolic[oa]s?|evangélic[oa]s?|evangelic[oa]s?|"
        r"protestante|judeu|judia|judaic[oa]|muçulman[oa]|muculman[oa]|islâmic[oa]|"
        r"espírita|espirita|umbanda|candomblé|candomble|ateu|ateia|"
        r"convicção religiosa|conviccao religiosa)\b",
        re.IGNORECASE,
    ),
    "politica": re.compile(
        r"\b(?:filiação partidária|filiacao partidaria|partido político|"
        r"partido politico|opinião política|opiniao politica|ideologia política|"
        r"ideologia politica)\b",
        re.IGNORECASE,
    ),
    "raca_etnia": re.compile(
        r"\b(?:origem racial|raça|raca|etnia|étnic[oa]|etnic[oa]|indígena|indigena|"
        r"afrodescendente)\b",
        re.IGNORECASE,
    ),
    "orientacao_sexual": re.compile(
        r"\b(?:orientação sexual|orientacao sexual|vida sexual|homossexual|"
        r"heterossexual|bissexual|lgbtq?i?a?\+?|lésbic[oa]|lesbic[oa])\b",
        re.IGNORECASE,
    ),
    "sindical": re.compile(
        r"\b(?:sindicato|filiação sindical|filiacao sindical|sindicalizad[oa])\b",
        re.IGNORECASE,
    ),
    "biometrico_genetico": re.compile(
        r"\b(?:biométric[oa]|biometric[oa]|genétic[oa]|genetic[oa]|impressão digital|"
        r"impressao digital|reconhecimento facial|dna)\b",
        re.IGNORECASE,
    ),
    # CPF mascarado ou só-dígitos (formato canônico) — identificador pessoal, não profissional.
    "cpf": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\bcpf\b", re.IGNORECASE),
    # Telefone, e-mail de provedor pessoal, CEP — contato pessoal.
    "contato_pessoal": re.compile(
        r"\(\d{2}\)\s*\d{4,5}-?\d{4}"  # telefone (xx) xxxxx-xxxx
        r"|\b\d{5}-?\d{3}\b"  # CEP
        r"|@(?:gmail|hotmail|outlook|yahoo|live|icloud|bol|uol)\.com",  # e-mail pessoal
        re.IGNORECASE,
    ),
    # Data de nascimento, idade explícita, estado civil — vida privada, não profissional.
    "vida_pessoal": re.compile(
        r"\bdata de nascimento\b|\bnascid[oa] em\b|\b\d{1,2}\s+anos\s+de\s+idade\b"
        r"|\b(?:casad[oa]|solteir[oa]|divorciad[oa]|viúv[oa]|viuv[oa]|"
        r"união estável|uniao estavel)\b",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class SensitiveHit:
    """Um trecho de dado sensível/pessoal encontrado, com a categoria que o classifica."""

    category: SensitiveCategory
    matched: str


@dataclass(frozen=True)
class FounderResult:
    """Saída do guard: founder higienizado (ou descartado) + base legal + o que saiu.

    `founder is None` ⇒ descartado (dado sensível no núcleo nome/cargo). `removed` lista
    os trechos retirados do `background`. `legal_basis` é o que a evidência deve carimbar.
    """

    founder: Founder | None
    legal_basis: LegalBasis
    removed: tuple[SensitiveHit, ...]
    dropped: bool

    @property
    def kept(self) -> bool:
        """True se o founder pode ser coletado (não foi descartado)."""
        return self.founder is not None


def scan_sensitive(text: str | None) -> tuple[SensitiveHit, ...]:
    """Acha trechos sensíveis/pessoais em `text` (puro/offline). Vazio se nada casa."""
    if not text:
        return ()
    hits: list[SensitiveHit] = []
    for category, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            hits.append(SensitiveHit(category=category, matched=m.group(0)))
    return tuple(hits)


def redact(text: str) -> tuple[str, tuple[SensitiveHit, ...]]:
    """Substitui cada trecho sensível/pessoal por `REDACTION`; devolve (texto, hits)."""
    hits: list[SensitiveHit] = []
    cleaned = text
    for category, pattern in _PATTERNS.items():

        def repl(m: re.Match[str], _cat: SensitiveCategory = category) -> str:
            hits.append(SensitiveHit(category=_cat, matched=m.group(0)))
            return REDACTION

        cleaned = pattern.sub(repl, cleaned)
    return cleaned, tuple(hits)


def _has_signal(text: str) -> bool:
    """True se sobra texto com sentido (alguma palavra) após tirar os marcadores.

    Olha só por caractere de palavra: se o que restou é pontuação/espaços entre
    marcadores (ex.: ``"[…]. […]."``), não há narrativa profissional a manter.
    """
    return bool(re.search(r"\w", text.replace(REDACTION, "")))


def sanitize_founder(founder: Founder) -> FounderResult:
    """Aplica a política LGPD de founder (F1.13): descarta ou higieniza.

    1. **Núcleo (nome/cargo):** se contém dado sensível, **descarta** o founder — um nome
       ou cargo não carrega dado sensível; se carrega, a extração é suspeita.
    2. **`background` livre:** **redige** os spans sensíveis/pessoais; se sobrar só
       marcadores, zera o campo. Identidade profissional (LinkedIn/cargo) é preservada.

    Não toca em `evidence` (proveniência) — a base legal é carimbada na persistência.
    """
    core = " ".join(x for x in (founder.nome, founder.cargo) if x)
    core_hits = scan_sensitive(core)
    if core_hits:
        return FounderResult(
            founder=None, legal_basis=FOUNDER_LEGAL_BASIS, removed=core_hits, dropped=True
        )

    if not founder.background:
        return FounderResult(
            founder=founder, legal_basis=FOUNDER_LEGAL_BASIS, removed=(), dropped=False
        )

    cleaned, removed = redact(founder.background)
    new_background = cleaned if _has_signal(cleaned) else None
    clean_founder = (
        founder
        if not removed
        else founder.model_copy(update={"background": new_background})
    )
    return FounderResult(
        founder=clean_founder, legal_basis=FOUNDER_LEGAL_BASIS, removed=removed, dropped=False
    )


__all__ = [
    "FOUNDER_LEGAL_BASIS",
    "REDACTION",
    "SensitiveCategory",
    "SensitiveHit",
    "FounderResult",
    "scan_sensitive",
    "redact",
    "sanitize_founder",
]
