"""Enumerações compartilhadas dos contratos TAPI (F0.5).

Valores fixos referenciados em todo o grafo (ARQUITETURA §2) e na rubrica AIMI
(`docs/ARQUITETURA.md §3.6`). Strings em PT-BR onde viram saída de produto (F0.13);
identificadores técnicos em snake_case.
"""

from __future__ import annotations

from enum import Enum


class Classification(str, Enum):
    """Classe de maturidade da startup (§5.1). Coerente com o AIMI total."""

    AI_NATIVE = "AI-native"
    AI_ENABLED = "AI-enabled"
    NON_AI = "non-AI"


class AIMIPillar(str, Enum):
    """Os 4 pilares do AI-Native Maturity Index (`docs/ARQUITETURA.md §3.6`)."""

    DATA_MOAT = "data_moat"
    WORKFLOW_DEPTH = "workflow_depth"
    TECHNICAL_OPTIMIZATION = "technical_optimization"
    DISTRIBUTION_MOAT = "distribution_moat"


class AIMIBand(str, Enum):
    """Faixas genéricas da escala 0–25 (RUBRICA §1)."""

    AUSENTE = "ausente"  # 0–6
    EMERGENTE = "emergente"  # 7–12
    ESTABELECIDO = "estabelecido"  # 13–18
    FORTE = "forte"  # 19–25


class PlaneRegion(str, Enum):
    """Regiões do plano `classe × AIMI` — o "Mapa de decisão" canônico
    (`docs/ARQUITETURA.md §3.6`). Rótulo de anotação do eval set (F1.12) e
    leitura de prioridade para o Inception. **Wrapper não é classe, é região.**"""

    FORA_ESCOPO = "fora_escopo"  # non-AI — não é alvo (briefing fora_de_escopo, F2.13)
    PERIFERICO = "periferico"  # AI-enabled — IA não é o núcleo, baixa prioridade
    WRAPPER = "wrapper"  # AI-native + AIMI baixo em ~todos — frágil/substituível
    ALVO_GRADUACAO = "alvo_graduacao"  # ★ AI-native + P1/P2 alto · P3 baixo = maior upside (F6.13)
    MADURO = "maduro"  # AI-native + alto em todos — já defensável (foco P4)


class LegalBasis(str, Enum):
    """Base legal LGPD registrada na evidência (F1.13). Coleta de dado de founder se
    apoia em **legítimo interesse** (Art. 7, IX) sobre **dado profissional manifestamente
    público** (Art. 7, §4). Dado sensível (Art. 5, II) nunca é coletado."""

    LEGITIMO_INTERESSE = "legitimo_interesse"  # Art. 7, IX — dado profissional público
    DADO_PUBLICO = "dado_publico"  # Art. 7, §4 — manifestamente tornado público pelo titular
    CONSENTIMENTO = "consentimento"  # Art. 7, I — não usado no sourcing público (reservado)


class Priority(str, Enum):
    """Prioridade de uma recomendação (§5.5)."""

    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class Complexity(str, Enum):
    """Complexidade de adoção de uma recomendação (§5.5)."""

    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"


class ExecutionMode(str, Enum):
    """Modo de consulta ao grafo (F2.3)."""

    SINGLE_COMPANY = "single_company"  # lookup de uma empresa
    DISCOVERY = "discovery"  # descoberta por setor/região (alimenta F1.14)


class HITLMode(str, Enum):
    """Modo de revisão humana do interrupt (F2.8)."""

    SYNC = "sync"  # interrupt bloqueante (single-company)
    AUTO = "auto"  # não bloqueia a fila (batch/cohort)


class RunStatus(str, Enum):
    """Estado de um run do grafo (tabela `run`, F0.6)."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"  # HITL interrupt (F2.8)
    COMPLETED = "completed"
    INSUFFICIENT_DATA = "insufficient_data"  # estado terminal de baixa confiança (F2.12)
    OUT_OF_SCOPE = "out_of_scope"  # non-AI de alta confiança (F2.13)
    FAILED = "failed"


class BriefingStatus(str, Enum):
    """Natureza do briefing emitido (F2.12 / F2.13)."""

    NORMAL = "normal"
    DADOS_INSUFICIENTES = "dados_insuficientes"  # F2.12
    FORA_DE_ESCOPO = "fora_de_escopo"  # F2.13 (non-AI de alta confiança)
