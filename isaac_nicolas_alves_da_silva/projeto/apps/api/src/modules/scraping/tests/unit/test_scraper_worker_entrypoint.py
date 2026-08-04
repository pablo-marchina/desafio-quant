"""Testes da configuracao operacional do scraper worker."""

from workers.scraper_worker.run import build_worker_arguments


def test_worker_listens_only_to_scraping_queue() -> None:
    """O processo deve carregar as tasks e consumir somente sua propria fila."""

    arguments = build_worker_arguments()

    assert arguments[0] == "workers.scraper_worker.tasks"
    assert arguments[arguments.index("--queues") + 1] == "scraping"
    assert arguments[arguments.index("--processes") + 1] == "1"
