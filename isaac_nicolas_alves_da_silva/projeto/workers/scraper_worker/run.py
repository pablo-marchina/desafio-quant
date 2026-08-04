"""Ponto de entrada do processo worker de scraping."""

from dramatiq.cli import main as dramatiq_main
from dramatiq.cli import make_argument_parser


def build_worker_arguments() -> list[str]:
    """Define como o processo worker deve consumir tarefas de scraping."""

    return [
        # Este modulo expoe o broker configurado e registra o actor.
        "workers.scraper_worker.tasks",
        # Durante o desenvolvimento, um processo evita criar muitos processos
        # filhos automaticamente, especialmente no Windows.
        "--processes",
        "1",
        # Threads permitem consumir mais de uma mensagem no mesmo processo.
        "--threads",
        "4",
        # Este worker deve consumir somente tarefas do modulo de scraping.
        "--queues",
        "scraping",
    ]


def main() -> int:
    """Inicia o CLI Dramatiq com a configuracao do scraper worker."""

    arguments = make_argument_parser().parse_args(build_worker_arguments())
    return dramatiq_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
