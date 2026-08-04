"""Worker (RQ) que executa runs longos do grafo LangGraph — F2.10.

`from apps.worker import run_graph_job, enqueue_run, default_queue`. A API (F5.2)
enfileira com `enqueue_run`; um worker RQ (`rq worker tapi`) roda `run_graph_job`,
que executa o grafo persistido (F2.2) e publica o progresso no canal Redis pub/sub
do run (F2.10) consumido pelo SSE (F5.3).
"""

from .jobs import (
    default_queue,
    enqueue_resume,
    enqueue_run,
    resume_graph_job,
    resume_job_id,
    run_graph_job,
)

__all__ = [
    "run_graph_job",
    "resume_graph_job",
    "enqueue_run",
    "enqueue_resume",
    "resume_job_id",
    "default_queue",
]
