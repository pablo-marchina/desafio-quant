from app.rag.catalog import NVIDIA_TECHNOLOGY_CATALOG


def main() -> None:
    for catalog_item in NVIDIA_TECHNOLOGY_CATALOG:
        print(catalog_item.source_url)


if __name__ == "__main__":
    main()
