"""Camada relacional (SQLAlchemy + SQLite por enquanto).

Reusa `settings.database_url` de app/config.py — trocar SQLite por PostgreSQL é
só mudar a `DATABASE_URL`. Tipos portáveis (String/Text/JSON/DateTime), sem
JSONB/ARRAY (convenção do CLAUDE.md), para a migração ser config, não reescrita.

`Empresa` guarda os dados raspados e o resultado da análise (classificação,
score, recomendação, briefing). `salvar_resultado` faz upsert por nome — uma linha
por empresa, sem duplicar (a gravação acontece uma vez, no fim do pipeline).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    setor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    dados: Mapped[dict] = mapped_column(JSON, default=dict)        # dump do DadosEmpresa
    fontes: Mapped[list] = mapped_column(JSON, default=list)       # URLs usadas
    # resultado da análise
    classificacao: Mapped[str | None] = mapped_column(String(32), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)   # composto
    notas: Mapped[dict | None] = mapped_column(JSON, nullable=True)     # 4 sub-notas
    recomendacao: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    briefing: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Descoberta(Base):
    """Histórico da aba Descoberta: um registro por tema pesquisado.

    `empresas` guarda a lista [{nome, descricao}] devolvida na época, para o
    analista reabrir uma pesquisa antiga sem refazer busca + LLM.
    """

    __tablename__ = "descobertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tema: Mapped[str] = mapped_column(String(255))
    empresas: Mapped[list] = mapped_column(JSON, default=list)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


def init_db() -> None:
    """Cria as tabelas (idempotente). Chamado antes do primeiro uso."""
    Base.metadata.create_all(engine)


def salvar_resultado(final: dict) -> None:
    """Upsert por nome do State final do grafo. Atualiza só os campos presentes
    (o caminho `non-ai` não tem score/recomendação/briefing)."""
    init_db()
    dados = final.get("dados_estruturados")
    alvos = final.get("alvos") or []
    nome = (dados.nome if dados and dados.nome else (alvos[0] if alvos else final.get("consulta")))
    if not nome:
        return

    rec = final.get("recomendacao")
    sc = final.get("score")

    with SessionLocal() as sessao:
        e = sessao.query(Empresa).filter_by(nome=nome).first()
        if e is None:
            e = Empresa(nome=nome)
            sessao.add(e)
        if dados:
            e.setor = dados.setor
            e.descricao = dados.descricao
            e.dados = dados.model_dump()
            e.fontes = dados.fontes
        if final.get("classificacao"):
            e.classificacao = final["classificacao"]
        if sc:
            e.score = sc.composto
            e.notas = sc.model_dump()
        if rec:
            e.recomendacao = rec.model_dump()
        if final.get("briefing"):
            e.briefing = final["briefing"]
        sessao.commit()
