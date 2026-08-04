"""Modelos de dados (tabelas) do projeto, descritos com SQLAlchemy.

Em vez de escrever SQL na mão, descrevemos cada tabela como uma CLASSE Python.
A SQLAlchemy traduz essa classe para o SQL equivalente e cuida de criar a
tabela, inserir, consultar, etc.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe-base de todos os modelos.

    Toda tabela do projeto herda dela. A SQLAlchemy usa essa base para saber
    quais tabelas existem (útil na hora de criar todas de uma vez).
    """


class ScrapedDocument(Base):
    """Um pedaço de conteúdo público coletado sobre uma startup.

    Cada linha = um texto limpo extraído de UMA fonte (ex.: o site oficial).
    """

    # Nome da tabela no banco de dados.
    __tablename__ = "scraped_documents"

    # Cada coluna é um atributo. "Mapped[tipo]" diz o tipo em Python e
    # "mapped_column(...)" descreve como a coluna é no banco.

    # Chave primária: id único gerado automaticamente (1, 2, 3, ...).
    id: Mapped[int] = mapped_column(primary_key=True)

    # Nome da startup. index=True cria um índice, que acelera buscas por ele.
    startup_name: Mapped[str] = mapped_column(String(255), index=True)

    # A FONTE rastreável: de qual URL este texto veio.
    source_url: Mapped[str] = mapped_column(String(2048))

    # Tipo da fonte (ex.: "site_oficial"). Tem um valor padrão por enquanto.
    source_type: Mapped[str] = mapped_column(String(50), default="site_oficial")

    # O texto limpo em si. "Text" = string longa, sem limite de tamanho.
    raw_text: Mapped[str] = mapped_column(Text)

    # Quando foi coletado. server_default=func.now() faz o PRÓPRIO banco
    # preencher a data/hora atual no momento da inserção.
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        # Exibição amigável ao imprimir um objeto desses (útil para debug).
        return (
            f"<ScrapedDocument id={self.id} "
            f"startup={self.startup_name!r} url={self.source_url!r}>"
        )


class Analysis(Base):
    """O resultado de UMA análise completa do grafo para uma startup.

    Guarda o que o radar produziu (classificação + checklist + recomendações +
    briefing), para não reprocessar, para o catálogo listar startups já analisadas
    e para o frontend exibir sem rodar tudo de novo.
    """

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    startup_name: Mapped[str] = mapped_column(String(255), index=True)
    url: Mapped[str] = mapped_column(String(2048), default="")

    # Classificação (level pode ser nulo no caminho de "dados insuficientes").
    level: Mapped[int | None] = mapped_column(nullable=True, default=None)
    level_name: Mapped[str] = mapped_column(String(100), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")

    # Estruturas ricas guardadas como JSON (checklist preenchido e perfil extraído).
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    structured: Mapped[dict] = mapped_column(JSON, default=dict)

    # Tecnologias NVIDIA recuperadas para a startup (nomes únicos) — o Radar de
    # Mercado (macro) agrega isto para ver as tecnologias mais demandadas.
    technologies: Mapped[list] = mapped_column(JSON, default=list)

    recommendations: Mapped[str] = mapped_column(Text, default="")
    briefing: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Analysis id={self.id} startup={self.startup_name!r} "
            f"level={self.level}>"
        )
