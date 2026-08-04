"""Ponto de entrada do processo worker de agentes."""

from dramatiq.cli import main as dramatiq_main
from dramatiq.cli import make_argument_parser


def build_worker_arguments() -> list[str]:
    """Define como o processo worker deve consumir tarefas de agentes."""

    return [
        # Este modulo registra o actor ``execute_agent_job``.
        "workers.agent_worker.tasks",
        "--processes",
        "1",
        "--threads",
        "4",
        # O agent_worker deve consumir somente a fila de agentes.
        "--queues",
        "agents",
    ]


def main() -> int:
    """Inicia o CLI Dramatiq com a configuracao do agent worker."""

    arguments = make_argument_parser().parse_args(build_worker_arguments())
    return dramatiq_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
