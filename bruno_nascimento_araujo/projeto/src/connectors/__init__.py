"""Conectores de extracao direta (Scraper 1)."""
from .abria import AbriaConnector
from .astella import AstellaConnector
from .base import BaseConnector
from .cubo import CuboConnector
from .monashees import MonasheesConnector
from .open_startups import OpenStartupsConnector

ALL_CONNECTORS: list[type[BaseConnector]] = [
    CuboConnector,
    OpenStartupsConnector,
    AbriaConnector,
    AstellaConnector,
    MonasheesConnector,
]

__all__ = [
    "BaseConnector",
    "CuboConnector",
    "OpenStartupsConnector",
    "AbriaConnector",
    "AstellaConnector",
    "MonasheesConnector",
    "ALL_CONNECTORS",
]
