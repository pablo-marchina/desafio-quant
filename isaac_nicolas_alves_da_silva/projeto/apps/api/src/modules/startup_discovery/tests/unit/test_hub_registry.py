"""Testes do catalogo de fontes de discovery."""

from apps.api.src.modules.startup_discovery.domain.hub_registry import (
    DISCOVERY_SOURCE_CATALOG,
    HUB_SOURCES,
)


def test_catalog_documents_more_sources_than_runtime_hubs():
    assert len(DISCOVERY_SOURCE_CATALOG) > len(HUB_SOURCES)


def test_runtime_hubs_are_implemented_catalog_sources():
    implemented_names = {
        item.name
        for item in DISCOVERY_SOURCE_CATALOG
        if item.status == "implemented"
    }

    assert {hub.name for hub in HUB_SOURCES} == implemented_names


def test_planned_sources_do_not_enter_runtime_registry():
    runtime_names = {hub.name for hub in HUB_SOURCES}
    planned_names = {
        item.name for item in DISCOVERY_SOURCE_CATALOG if item.status == "planned"
    }

    assert planned_names
    assert runtime_names.isdisjoint(planned_names)
