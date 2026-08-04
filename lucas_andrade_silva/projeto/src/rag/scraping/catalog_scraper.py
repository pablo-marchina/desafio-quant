import argparse
import json
from datetime import datetime

from firecrawl import FirecrawlApp

from rag.catalog import build_url_registry, service_names
from rag.settings import (
    DOCUMENTS_PATH,
    SCRAPE_FAILURES_PATH,
    required_env,
)

MIN_CONTENT_CHARS = 100


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def select_registry(service: str | None, limit: int | None) -> list[tuple[str, dict]]:
    registry = build_url_registry()
    selected = [
        (url, metadata)
        for url, metadata in registry.items()
        if service is None or service in metadata["services"]
    ]
    return selected[:limit] if limit else selected


def scrape_url(app: FirecrawlApp, url: str, metadata: dict) -> dict:
    result = app.scrape(
        url,
        formats=["markdown"],
        only_main_content=True,
        wait_for=5000,
    )
    content = result.markdown or ""
    if len(content) <= MIN_CONTENT_CHARS:
        raise ValueError(f"conteudo insuficiente: {len(content)} caracteres")

    return {
        "url": url,
        "content": content,
        "chars": len(content),
        "services": metadata["services"],
        "categories": metadata["categories"],
        "scraper_source": "firecrawl",
        "scraped_at": datetime.now().isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coleta o catalogo de servicos NVIDIA.")
    parser.add_argument("--service", choices=service_names())
    parser.add_argument("--limit", type=int)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = FirecrawlApp(api_key=required_env("FIRECRAWL_API_KEY"))
    registry = build_url_registry()
    initial_documents = load_json(
        DOCUMENTS_PATH,
        [],
    )
    existing = {
        document["url"]: document
        for document in initial_documents
    }
    failures = {
        failure["url"]: failure
        for failure in load_json(SCRAPE_FAILURES_PATH, [])
    }
    selected = select_registry(args.service, args.limit)

    print(f"URLs selecionadas: {len(selected)}")
    for position, (url, metadata) in enumerate(selected, start=1):
        if url in existing and not args.refresh:
            existing[url]["services"] = metadata["services"]
            existing[url]["categories"] = metadata["categories"]
            print(f"[{position}/{len(selected)}] SKIP {url}")
            continue

        print(f"[{position}/{len(selected)}] Coletando: {url}")
        try:
            existing[url] = scrape_url(app, url, metadata)
            failures.pop(url, None)
            print(f"  OK - {existing[url]['chars']} caracteres")
        except Exception as error:
            failures[url] = {
                "url": url,
                "services": metadata["services"],
                "categories": metadata["categories"],
                "error": str(error),
                "failed_at": datetime.now().isoformat(),
            }
            print(f"  ERRO - {error}")

        # Checkpoint apos cada chamada para permitir retomada segura.
        save_json(DOCUMENTS_PATH, list(existing.values()))
        save_json(SCRAPE_FAILURES_PATH, list(failures.values()))

    save_json(DOCUMENTS_PATH, list(existing.values()))
    save_json(SCRAPE_FAILURES_PATH, list(failures.values()))
    print(f"\nDocumentos armazenados: {len(existing)}")
    print(f"Falhas pendentes: {len(failures)}")


if __name__ == "__main__":
    main()
