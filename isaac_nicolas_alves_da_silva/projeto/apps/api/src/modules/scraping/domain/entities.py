"""Entidades que representam os principais conceitos do módulo de scraping.

Neste primeiro momento, o arquivo contém somente ``ScrapingJob``. As entidades
``ScrapingAttempt`` e ``ScrapingResult`` serão adicionadas depois que o ciclo
de vida do job estiver compreendido.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .enums import AttemptStatus, JobStatus, ScrapingMethod, ValidationDecision
from .exceptions import InvalidJobTransitionError


def utc_now() -> datetime:
    """Retorna o horário atual com informação explícita de fuso horário.

    Guardar datas em UTC evita ambiguidades quando API, worker e banco forem
    executados em máquinas ou regiões diferentes.
    """

    return datetime.now(UTC)


@dataclass
class ScrapingJob:
    """Representa o processo completo de scraping de uma URL.

    A entidade guarda seus dados e protege suas próprias regras. Assim, outras
    partes do sistema não podem alterar o status livremente e criar estados
    impossíveis.
    """

    # A URL é obrigatória, então aparece antes dos campos que possuem padrão.
    url: str

    # Cada job recebe um identificador único no momento em que é criado.
    id: UUID = field(default_factory=uuid4)

    # Todo job novo começa aguardando execução.
    status: JobStatus = JobStatus.PENDING

    # Este campo será preenchido apenas quando houver um resultado aprovado.
    result_id: UUID | None = None

    # Em caso de falha, guardaremos uma mensagem controlada neste campo.
    error_message: str | None = None

    # Preserva o tipo da fonte (ex: "nvidia_knowledge") ate a pipeline de
    # validacao, mesmo padrao de ``ingestion_jobs.source_type``. Fontes
    # curadas (fora de "startup_evidence") pulam a avaliacao "evidencia de
    # IA de uma startup" — ver ``QualityScoringService``/``ScrapingPipeline``.
    source_type: str = "startup_evidence"

    # Datas importantes para auditoria e medição do tempo de execução.
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        """Inicia um job que ainda está pendente."""

        if self.status is not JobStatus.PENDING:
            raise InvalidJobTransitionError(
                f"Somente jobs pendentes podem iniciar. Estado atual: {self.status}."
            )

        self.status = JobStatus.RUNNING
        self.started_at = utc_now()

    def complete(self, result_id: UUID) -> None:
        """Conclui um job em execução e associa seu resultado aprovado."""

        if self.status is not JobStatus.RUNNING:
            raise InvalidJobTransitionError(
                f"Somente jobs em execução podem concluir. Estado atual: {self.status}."
            )

        self.status = JobStatus.COMPLETED
        self.result_id = result_id
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        """Finaliza com falha um job que estava sendo executado."""

        if self.status is not JobStatus.RUNNING:
            raise InvalidJobTransitionError(
                f"Somente jobs em execução podem falhar. Estado atual: {self.status}."
            )

        self.status = JobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()


    def fail_dispatch(self, reason: str) -> None:
        """Falha um job pendente que nao conseguiu chegar ate a fila."""

        if self.status is not JobStatus.PENDING:
            raise InvalidJobTransitionError(
                "Somente jobs pendentes podem falhar durante o dispatch."
            )

        self.status = JobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()


@dataclass
class ScrapingAttempt:
    """Representa uma tentativa feita com uma estratégia de scraping.

    Um mesmo job pode possuir várias tentativas. Por exemplo, BeautifulSoup
    pode terminar em fallback e uma tentativa posterior com Playwright pode
    produzir o conteúdo aprovado.
    """

    # Toda tentativa pertence a um job já existente.
    job_id: UUID

    # Indica qual tecnologia foi utilizada nesta tentativa.
    method: ScrapingMethod

    # Cada tentativa possui seu próprio identificador para auditoria.
    id: UUID = field(default_factory=uuid4)

    # A tentativa começa em execução assim que é criada pela pipeline.
    status: AttemptStatus = AttemptStatus.RUNNING

    # A decisão será preenchida depois da validação do conteúdo coletado.
    decision: ValidationDecision | None = None

    # Os scores começam vazios porque ainda não houve validação.
    technical_score: float | None = None
    text_score: float | None = None
    evidence_score: float | None = None
    quality_score: float | None = None

    # Problems bloqueiam ou prejudicam a coleta; warnings apenas alertam.
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Este campo é usado quando a própria execução técnica gera uma exceção.
    error_message: str | None = None

    # --- Campos da investigação com agentes (v8) ---
    #
    # ``semantic_confidence`` guarda o valor calculado pelo
    # SemanticConfidenceService quando a revisão semântica simples rodou,
    # mesmo que a decisão final tenha vindo do agente.
    semantic_confidence: float | None = None

    # ``agent_reviewed`` marca que esta tentativa passou pela investigação
    # de um agente (módulo ``agents``), e não apenas pela validação
    # determinística + LLM simples.
    agent_reviewed: bool = False

    # ``agent_reason`` guarda a justificativa textual de uma decisão tomada
    # pelo agente (rejeição ou pedido de mais fontes). É um campo de negócio,
    # diferente de ``error_message``, que é reservado para falhas técnicas.
    agent_reason: str | None = None

    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None

    def finish_validation(
        self,
        *,
        decision: ValidationDecision,
        technical_score: float,
        text_score: float,
        evidence_score: float,
        quality_score: float,
        problems: list[str],
        warnings: list[str],
        semantic_confidence: float | None = None,
        agent_reviewed: bool = False,
        agent_reason: str | None = None,
    ) -> None:
        """Finaliza a tentativa usando a decisão produzida pela validação.

        Os três últimos parâmetros (``semantic_confidence``, ``agent_reviewed``
        e ``agent_reason``) existem para o caminho da v8: quando um agente
        investiga o caso e confirma (``accepted``) ou descarta
        (``rejected``) o conteúdo, esses campos registram que a decisão
        ``ACCEPT``/``REJECT`` recebida aqui já passou pela investigação,
        junto com a confiança semântica e o motivo do agente.
        """

        if self.status is not AttemptStatus.RUNNING:
            raise InvalidJobTransitionError(
                "Somente tentativas em execução podem ser finalizadas."
            )

        # A decisão determina como registramos o estado final da tentativa.
        status_by_decision = {
            ValidationDecision.ACCEPT: AttemptStatus.ACCEPTED,
            ValidationDecision.FALLBACK: AttemptStatus.FALLBACK,
            ValidationDecision.REJECT: AttemptStatus.REJECTED,
        }

        self.status = status_by_decision[decision]
        self.decision = decision
        self.technical_score = technical_score
        self.text_score = text_score
        self.evidence_score = evidence_score
        self.quality_score = quality_score
        self.problems = problems
        self.warnings = warnings
        self.semantic_confidence = semantic_confidence
        self.agent_reviewed = agent_reviewed
        self.agent_reason = agent_reason
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        """Registra uma falha técnica ocorrida antes da decisão de validação."""

        if self.status is not AttemptStatus.RUNNING:
            raise InvalidJobTransitionError(
                "Somente tentativas em execução podem falhar."
            )

        self.status = AttemptStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()

    def accept(
        self,
        *,
        technical_score: float,
        text_score: float,
        evidence_score: float,
        quality_score: float,
        problems: list[str] | None = None,
        warnings: list[str] | None = None,
        semantic_confidence: float | None = None,
        agent_reviewed: bool = False,
    ) -> None:
        """Aceita a tentativa depois que um agente confirma o conteúdo.

        ``finish_validation`` continua sendo o caminho usado quando a decisão
        final vem direto da validação determinística ou da revisão semântica
        simples (v7). Este método é o caminho alternativo usado quando a
        tentativa só foi aceita depois da investigação de um agente (v8): o
        agente analisou o caso, decidiu ``accepted`` e a pipeline registra
        esse resultado aqui, junto com a confiança semântica que motivou a
        investigação e a marca ``agent_reviewed=True`` para auditoria.
        """

        if self.status is not AttemptStatus.RUNNING:
            raise InvalidJobTransitionError(
                "Somente tentativas em execução podem ser aceitas."
            )

        self.status = AttemptStatus.ACCEPTED
        self.decision = ValidationDecision.ACCEPT
        self.technical_score = technical_score
        self.text_score = text_score
        self.evidence_score = evidence_score
        self.quality_score = quality_score
        self.problems = problems or []
        self.warnings = warnings or []
        self.semantic_confidence = semantic_confidence
        self.agent_reviewed = agent_reviewed
        self.finished_at = utc_now()

    def reject(self, reason: str, *, agent_reviewed: bool = False) -> None:
        """Rejeita a tentativa com base em uma decisão de negócio.

        Usado quando o agente investiga o caso e conclui que o conteúdo deve
        ser rejeitado (``decision = rejected``). Diferente de ``fail``, que
        registra um problema técnico, ``reject`` registra uma decisão: o
        conteúdo foi entendido, mas não deve ser aproveitado. O motivo fica
        em ``agent_reason`` para auditoria.
        """

        if self.status is not AttemptStatus.RUNNING:
            raise InvalidJobTransitionError(
                "Somente tentativas em execução podem ser rejeitadas."
            )

        self.status = AttemptStatus.REJECTED
        self.decision = ValidationDecision.REJECT
        self.agent_reason = reason
        self.agent_reviewed = agent_reviewed
        self.finished_at = utc_now()

    def finish_needs_more_sources(self, reason: str) -> None:
        """Registra que o agente pediu mais fontes para decidir.

        Esta tentativa específica não produz um ``ScrapingResult``, mas
        também não é uma rejeição definitiva: o fluxo global pode usar
        ``agent_reason`` para criar novos jobs de scraping para a mesma
        startup e tentar novamente mais tarde.
        """

        if self.status is not AttemptStatus.RUNNING:
            raise InvalidJobTransitionError(
                "Somente tentativas em execução podem pedir mais fontes."
            )

        self.status = AttemptStatus.NEEDS_MORE_SOURCES
        self.agent_reason = reason
        self.agent_reviewed = True
        self.finished_at = utc_now()


@dataclass
class ScrapingResult:
    """Representa o conteúdo bruto aprovado pelo módulo de scraping.

    Esta entidade é a saída pública do módulo para a futura etapa de ingestion.
    Ela não realiza limpeza profunda, extração estruturada ou chunking.
    """

    # Liga o resultado ao processo que realizou a coleta.
    job_id: UUID

    # URL solicitada originalmente pelo usuário.
    url: str

    # URL final após possíveis redirecionamentos HTTP.
    final_url: str

    # Título extraído da página, quando disponível.
    title: str | None

    # HTML original permite auditoria e reprocessamento futuro.
    raw_html: str

    # Texto bruto extraído, pronto para ser entregue à ingestion.
    raw_text: str

    # Tecnologia que produziu o resultado aceito.
    method: ScrapingMethod

    # Código HTTP retornado pela página final.
    status_code: int

    # Scores que justificaram a aceitação deste conteúdo.
    technical_score: float
    text_score: float
    evidence_score: float
    quality_score: float

    # Hash permite identificar conteúdos repetidos sem comparar todo o texto.
    content_hash: str

    # Metadados opcionais comportam informações extras sem alterar a entidade.
    metadata: dict[str, str | int | float | bool | None] = field(
        default_factory=dict
    )

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
