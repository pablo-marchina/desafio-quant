"""Ponto de entrada do processo worker de orchestration (url ingestion)."""

from dramatiq.cli import main as dramatiq_main
from dramatiq.cli import make_argument_parser


def build_worker_arguments() -> list[str]:
    return [
        "workers.orchestration_worker.tasks",
        "--processes",
        "1",
        "--threads",
        "4",
        "--queues",
        "url_ingestion",
    ]


def main() -> int:
    arguments = make_argument_parser().parse_args(build_worker_arguments())
    return dramatiq_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
