"""Registra todos os models relacionais no metadata compartilhado.

SQLAlchemy resolve FKs entre tabelas pelo `Base.metadata`. Importar este modulo
garante que fluxos executados isoladamente conhecam as tabelas referenciadas,
sem depender da ordem incidental de imports dos testes ou das rotas.
"""

from apps.api.src.modules.agents.infrastructure.database.models import (  # noqa: F401
    agent_run_model,
    agent_step_model,
)
from apps.api.src.modules.briefing.infrastructure.database.models import (  # noqa: F401
    briefing_model,
)
from apps.api.src.modules.embeddings.infrastructure.database.models import (  # noqa: F401
    embedding_job_chunk_model,
    embedding_job_model,
)
from apps.api.src.modules.ingestion.infrastructure.database.models import (  # noqa: F401
    chunk_model,
    document_model,
    ingestion_job_model,
)
from apps.api.src.modules.orchestration.infrastructure.database.models import (  # noqa: F401
    analysis_job_model,
    url_ingestion_job_model,
)
from apps.api.src.modules.recommendations.infrastructure.database.models import (  # noqa: F401
    recommendation_model,
)
from apps.api.src.modules.scraping.infrastructure.database.models import (  # noqa: F401
    scraping_attempt_model,
    scraping_job_model,
    scraping_result_model,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.models import (  # noqa: F401
    discovery_candidate_model,
    discovery_run_model,
    discovery_submission_model,
)
from apps.api.src.modules.startups.infrastructure.database.models import (  # noqa: F401
    startup_evidence_model,
    startup_model,
)
