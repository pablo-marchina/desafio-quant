"""Factory do CallbackHandler do Langfuse para chamadas LangChain.

O SDK do Langfuse so encontra o client default via os.environ
(``get_client()``/``CallbackHandler()`` sem argumentos) - um client
``Langfuse(public_key=..., ...)`` construido manualmente NAO fica
disponivel para ``CallbackHandler()`` resolver depois (testado: e' uma
instancia separada, sem registro cruzado). Por isso, diferente do resto
do projeto (que injeta credenciais via construtor, nunca le os.environ),
aqui exportamos os valores de ``Settings`` para os.environ uma vez por
processo - e' o unico jeito do SDK funcionar do jeito documentado.

Sem LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY configurados,
``get_langfuse_callbacks()`` devolve lista vazia: a chamada LangChain
segue sem tracing, mesmo padrao de degradacao graciosa do Cohere Rerank
(RAG V4) - observabilidade nunca bloqueia o caminho principal.
"""

import os

from apps.api.src.config.settings import get_settings

_env_exported = False


def _ensure_env_exported() -> bool:
    global _env_exported

    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return False

    if not _env_exported:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
        if settings.langfuse_host:
            os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
        _env_exported = True

    return True


def get_langfuse_callbacks() -> list:
    """Devolve ``[CallbackHandler()]`` se Langfuse estiver configurado, senao ``[]``.

    Uso: ``model.ainvoke(messages, config={"callbacks": get_langfuse_callbacks()})``.
    """

    if not _ensure_env_exported():
        return []

    from langfuse.langchain import CallbackHandler

    return [CallbackHandler()]
