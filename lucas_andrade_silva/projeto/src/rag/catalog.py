from collections import defaultdict
import re

from rag.catalog_data import SERVICES

SERVICE_ALIASES = {
    "NIM Microservices": ("NVIDIA NIM", "NIM"),
}


def build_url_registry() -> dict[str, dict]:
    registry = defaultdict(lambda: {"services": [], "categories": []})

    for service, config in SERVICES.items():
        category = config["categoria"]
        for url in config["urls"]:
            if service not in registry[url]["services"]:
                registry[url]["services"].append(service)
            if category not in registry[url]["categories"]:
                registry[url]["categories"].append(category)

    return dict(registry)


def service_names() -> list[str]:
    return list(SERVICES)


def category_names() -> list[str]:
    return sorted({config["categoria"] for config in SERVICES.values()})


def normalize_name(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def detect_services(query: str) -> list[str]:
    normalized_query = f" {normalize_name(query)} "
    detected = []

    for service in service_names():
        aliases = (service, *SERVICE_ALIASES.get(service, ()))
        if any(
            f" {normalize_name(alias)} " in normalized_query
            for alias in aliases
        ):
            detected.append(service)

    return detected
