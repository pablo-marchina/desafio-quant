"""Composicao das dependencias concretas do modulo agents.

Assim como ``ScrapingFactory``, este e o unico lugar do modulo ``agents`` que
conhece tipos concretos (hoje, o adaptador Gemini). Outros modulos nunca
instanciam ``GeminiEvidenceValidator`` diretamente — eles recebem o contrato
publico ``EvidenceValidationService`` atraves desta factory.
"""

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.agents.application.ports import AgentTaskDispatcher
from apps.api.src.modules.agents.application.ports import SearchExecutorPort
from apps.api.src.modules.agents.application.public.briefing_agent import (
    BriefingAgentService,
)
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.agents.application.public.nvidia_rag import (
    NvidiaRagService,
)
from apps.api.src.modules.agents.application.public.recommendation_agent import (
    RecommendationAgentService,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.application.public.startup_classifier import (
    StartupClassifierService,
)
from apps.api.src.modules.agents.application.use_cases.create_agent_run import (
    CreateAgentRun,
)
from apps.api.src.modules.agents.application.use_cases.execute_agent_job import (
    ExecuteAgentJob,
)
from apps.api.src.modules.agents.application.use_cases.get_agent_run import (
    GetAgentRun,
)
from apps.api.src.modules.agents.application.use_cases.resume_agent_job import (
    ResumeAgentJob,
)
from apps.api.src.modules.agents.graphs.briefing.graph import BriefingAgentGraph
from apps.api.src.modules.agents.graphs.evidence_validation.graph import (
    EvidenceValidationGraph,
)
from apps.api.src.modules.agents.graphs.extraction.graph import ExtractionGraph
from apps.api.src.modules.agents.graphs.nvidia_rag.graph import NvidiaRagGraph
from apps.api.src.modules.agents.graphs.recommendation.graph import (
    RecommendationAgentGraph,
)
from apps.api.src.modules.agents.graphs.search_planning.graph import (
    SearchPlanningGraph,
)
from apps.api.src.modules.agents.graphs.startup_classification.graph import (
    StartupClassificationGraph,
)
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_briefing_prose_rewriter import (
    LangChainGeminiBriefingProseRewriter,
)
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_evidence_judge import (
    LangChainGeminiEvidenceJudge,
)
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_extractor import (
    LangChainGeminiExtractor,
)
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_search_planner import (
    LangChainGeminiSearchPlanner,
)
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_recommendation_reviewer import (
    LangChainGeminiRecommendationReviewer,
)
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_startup_classifier import (
    LangChainGeminiStartupClassifier,
)
from apps.api.src.modules.agents.infrastructure.checkpoints.postgres_checkpointer import (
    PostgresCheckpointer,
)
from apps.api.src.modules.agents.infrastructure.database.postgres_unit_of_work import (
    PostgresAgentsUnitOfWork,
)
from apps.api.src.modules.agents.infrastructure.queue.dramatiq_agent_dispatcher import (
    DramatiqAgentJobPublisher,
    DramatiqAgentTaskDispatcher,
)
from apps.api.src.modules.agents.infrastructure.search_adapters.tavily_search_executor import (
    TavilySearchExecutor,
)
from apps.api.src.modules.agents.infrastructure.briefing_adapters.briefing_generator_adapter import (
    BriefingGeneratorAdapter,
)
from apps.api.src.modules.agents.infrastructure.rag_adapters.rag_question_answerer_adapter import (
    RagQuestionAnswererAdapter,
)
from apps.api.src.modules.agents.infrastructure.recommendations_adapters.recommendation_generator_adapter import (
    RecommendationGeneratorAdapter,
)
from apps.api.src.modules.rag.factories.rag_factory import RagFactory
from apps.api.src.shared.queue.dramatiq_broker import broker


class AgentsFactory:
    """Ponto de composicao do modulo agents."""

    @staticmethod
    def create_checkpointer() -> PostgresCheckpointer | None:
        """Cria o checkpointer PostgreSQL para LangGraph.

        Devolve ``None`` quando DATABASE_URL nao esta configurado para que o
        sistema suba em ambientes sem banco (ex: testes unitarios sem infra).
        """

        settings = get_settings()
        if not settings.database_url:
            return None
        return PostgresCheckpointer(settings.database_url)

    @staticmethod
    def create_evidence_validation_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> EvidenceValidationService | None:
        """Cria o servico publico de validacao de evidencias.

        Devolve ``None`` quando o Gemini nao esta configurado, da mesma forma
        que ``ScrapingFactory.create_pipeline`` faz para o
        ``semantic_validator`` da v7. Isso permite que o sistema continue
        funcionando (sem investigacao por agente) em ambientes sem a chave de
        API configurada.
        """

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        # V2: o servico publico agora e um grafo LangGraph. O Gemini fica
        # escondido atras de um avaliador LangChain, e o scraping continua
        # chamando o mesmo contrato ``EvidenceValidationService``.
        evidence_judge = LangChainGeminiEvidenceJudge(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

        return EvidenceValidationGraph(
            evidence_judge=evidence_judge,
            checkpointer=checkpointer,
            interrupt_on_uncertain=checkpointer is not None,
        )

    @staticmethod
    def create_search_planning_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> SearchPlanningService | None:
        """Cria o servico publico do Search Planner Agent.

        Assim como a validacao de evidencias, este agente depende de Gemini.
        Sem chave configurada, devolvemos ``None`` para evitar custo acidental e
        permitir que o sistema suba em ambientes locais.
        """

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        planner = LangChainGeminiSearchPlanner(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

        return SearchPlanningGraph(planner=planner, checkpointer=checkpointer)

    @staticmethod
    def create_search_executor() -> SearchExecutorPort | None:
        """Cria o executor de busca web usado pelo enriquecimento.

        Sem ``TAVILY_API_KEY``, devolve ``None`` para manter ambientes locais e
        testes sem custo/rede externa.
        """

        settings = get_settings()
        if not settings.tavily_api_key:
            return None

        return TavilySearchExecutor(
            api_key=settings.tavily_api_key,
            search_url=settings.tavily_search_url,
        )

    @staticmethod
    def create_startup_classification_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> StartupClassifierService | None:
        """Cria o servico publico do Startup Classifier Agent (V9).

        Mesma regra dos demais agentes: sem chave Gemini configurada,
        devolve ``None`` para evitar custo acidental.
        """

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        classifier = LangChainGeminiStartupClassifier(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

        return StartupClassificationGraph(
            classifier=classifier, checkpointer=checkpointer
        )

    @staticmethod
    def create_extraction_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> ExtractionService | None:
        """Cria o servico publico do Extraction Agent (V8).

        Mesma regra dos demais agentes: sem chave Gemini configurada,
        devolve ``None`` para evitar custo acidental.
        """

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        extractor = LangChainGeminiExtractor(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

        return ExtractionGraph(extractor=extractor, checkpointer=checkpointer)

    @staticmethod
    def create_nvidia_rag_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> NvidiaRagService | None:
        """Cria o servico publico do NVIDIA RAG Agent (V10).

        Mesma regra dos demais agentes: sem chave Gemini configurada,
        devolve ``None`` para evitar custo acidental. A "tool" chamada pelo
        grafo e' o contrato publico de ``rag`` (``RagFactory``), nao um
        cliente Gemini proprio — a geracao de resposta com citacoes ja
        existe em ``rag`` V4.
        """

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        rag_tool = RagQuestionAnswererAdapter(
            RagFactory.create_question_answerer()
        )

        return NvidiaRagGraph(rag_tool=rag_tool, checkpointer=checkpointer)

    @staticmethod
    def create_recommendation_agent_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> RecommendationAgentService | None:
        """Cria o servico publico do Recommendation Agent (V11).

        Mesma regra dos demais agentes: sem chave Gemini configurada,
        devolve ``None`` para evitar custo acidental. A "tool" determinística
        e' o contrato publico de ``recommendations``
        (``RecommendationsFactory``); o LLM so julga candidatos ambiguos e
        reescreve a justificativa em linguagem de negocio — nao recalcula
        score nem reimplementa ``match_technologies()``.
        """

        # Import local: recommendations -> startups -> agents (adapters de
        # classificacao/extracao) fecharia um ciclo se importado no topo do
        # arquivo. Mesmo padrao de import lazy usado em
        # ``nvidia_knowledge_factory.py`` para chamar ``orchestration``.
        from apps.api.src.modules.recommendations.factories.recommendations_factory import (
            RecommendationsFactory,
        )

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        recommendation_tool = RecommendationGeneratorAdapter(
            RecommendationsFactory.create_recommendation_generator(),
            RecommendationsFactory.create_recommendation_justification_updater(),
        )
        reviewer = LangChainGeminiRecommendationReviewer(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

        return RecommendationAgentGraph(
            recommendation_tool=recommendation_tool,
            reviewer=reviewer,
            checkpointer=checkpointer,
        )

    @staticmethod
    def create_briefing_agent_service(
        checkpointer: PostgresCheckpointer | None = None,
    ) -> BriefingAgentService | None:
        """Cria o servico publico do Briefing Agent (V12).

        Mesma regra dos demais agentes: sem chave Gemini configurada,
        devolve ``None`` para evitar custo acidental. A "tool" determinística
        e' o contrato publico de ``briefing`` (``BriefingFactory``); o LLM
        so reescreve a prosa em linguagem executiva — nao decide riscos,
        proximas acoes nem monta secoes (isso continua em
        ``build_briefing_markdown()``).
        """

        # Import local: briefing -> startups -> agents (adapters de
        # classificacao/extracao) fecharia um ciclo se importado no topo do
        # arquivo. Mesmo padrao de import lazy usado em
        # ``create_recommendation_agent_service()``.
        from apps.api.src.modules.briefing.factories.briefing_factory import (
            BriefingFactory,
        )

        settings = get_settings()

        if not settings.gemini_api_key:
            return None

        briefing_tool = BriefingGeneratorAdapter(
            BriefingFactory.create_briefing_generator(),
            BriefingFactory.create_briefing_content_updater(),
        )
        prose_rewriter = LangChainGeminiBriefingProseRewriter(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

        return BriefingAgentGraph(
            briefing_tool=briefing_tool,
            prose_rewriter=prose_rewriter,
            checkpointer=checkpointer,
        )

    @staticmethod
    def create_agent_task_dispatcher() -> AgentTaskDispatcher:
        """Cria dispatcher para publicar execucoes na fila ``agents``."""

        return DramatiqAgentTaskDispatcher(
            DramatiqAgentJobPublisher(broker),
        )

    @staticmethod
    def create_execute_agent_job() -> ExecuteAgentJob:
        """Cria o caso de uso chamado pelo agent_worker.

        Injeta checkpointer PostgreSQL e os dois servicos de grafo. Quando a
        chave Gemini nao esta configurada, ``create_*_service`` devolve ``None``
        e o worker marca o run como ``failed`` com mensagem clara.
        """

        checkpointer = AgentsFactory.create_checkpointer()
        return ExecuteAgentJob(
            uow_factory=PostgresAgentsUnitOfWork,
            evidence_validation_service=AgentsFactory.create_evidence_validation_service(
                checkpointer
            ),
            search_planning_service=AgentsFactory.create_search_planning_service(
                checkpointer
            ),
            startup_classification_service=AgentsFactory.create_startup_classification_service(
                checkpointer
            ),
            extraction_service=AgentsFactory.create_extraction_service(checkpointer),
            nvidia_rag_service=AgentsFactory.create_nvidia_rag_service(checkpointer),
            recommendation_agent_service=AgentsFactory.create_recommendation_agent_service(
                checkpointer
            ),
            briefing_agent_service=AgentsFactory.create_briefing_agent_service(
                checkpointer
            ),
        )

    @staticmethod
    def create_resume_agent_job() -> ResumeAgentJob:
        """Cria o caso de uso para retomar runs pausados por interrupcao humana."""

        checkpointer = AgentsFactory.create_checkpointer()
        return ResumeAgentJob(
            uow_factory=PostgresAgentsUnitOfWork,
            evidence_validation_service=AgentsFactory.create_evidence_validation_service(
                checkpointer
            ),
            search_planning_service=AgentsFactory.create_search_planning_service(
                checkpointer
            ),
            startup_classification_service=AgentsFactory.create_startup_classification_service(
                checkpointer
            ),
            extraction_service=AgentsFactory.create_extraction_service(checkpointer),
            nvidia_rag_service=AgentsFactory.create_nvidia_rag_service(checkpointer),
            recommendation_agent_service=AgentsFactory.create_recommendation_agent_service(
                checkpointer
            ),
            briefing_agent_service=AgentsFactory.create_briefing_agent_service(
                checkpointer
            ),
        )

    @staticmethod
    def create_agent_run_use_case() -> CreateAgentRun:
        """Cria o caso de uso que persiste e publica um AgentRun."""

        return CreateAgentRun(
            uow_factory=PostgresAgentsUnitOfWork,
            task_dispatcher=AgentsFactory.create_agent_task_dispatcher(),
        )

    @staticmethod
    def create_get_agent_run_use_case() -> GetAgentRun:
        """Cria o caso de uso de consulta de AgentRun."""

        return GetAgentRun(PostgresAgentsUnitOfWork)
