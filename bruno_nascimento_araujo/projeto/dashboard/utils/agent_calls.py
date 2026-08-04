"""Wrapper de execução assíncrona segura para o Streamlit.

Streamlit reexecuta o script inteiro a cada interação (rerun) sem manter um
event loop persistente. Se um recurso assíncrono (ex: asyncpg.Pool) for cacheado
via @st.cache_resource mas criado com asyncio.run() — que cria e FECHA um loop
novo a cada chamada — a próxima reutilização do recurso cacheado falha com
"RuntimeError: Future attached to a different loop" (erro conhecido de
asyncpg + Streamlit + cache_resource). A solução: manter um único loop de
background, cacheado, vivo durante todo o processo, e rotear toda chamada
assíncrona por ele via run_coroutine_threadsafe — assim qualquer recurso criado
através de run_async() permanece válido entre reruns.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

import streamlit as st

T = TypeVar("T")


class _BackgroundLoop:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()


@st.cache_resource
def _background_loop() -> _BackgroundLoop:
    return _BackgroundLoop()


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Executa uma coroutine no loop de background persistente do dashboard."""
    return _background_loop().run(coro)
