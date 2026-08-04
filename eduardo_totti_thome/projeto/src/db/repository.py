"""Funções de leitura e gravação no banco (camada de "repositório").

Mantém a lógica de banco separada do resto do código: quem quiser salvar um
documento coletado chama save_scraped_document(...) e não precisa saber de
sessões, commits, etc.
"""

from __future__ import annotations

from db.models import Analysis, ScrapedDocument
from db.session import SessionLocal


def save_scraped_document(
    startup_name: str,
    source_url: str,
    raw_text: str,
    source_type: str = "site_oficial",
) -> int:
    """Insere uma linha em scraped_documents e devolve o id gerado pelo banco.

    Args:
        startup_name: nome da startup.
        source_url: URL de onde o texto veio (a fonte rastreável).
        raw_text: o texto limpo já extraído.
        source_type: tipo da fonte (padrão: "site_oficial").
    """
    # "with" abre a sessão e garante que ela seja fechada no fim, mesmo se
    # acontecer um erro no meio do caminho.
    with SessionLocal() as session:
        # 1) Cria o objeto Python que representa a futura linha da tabela.
        doc = ScrapedDocument(
            startup_name=startup_name,
            source_url=source_url,
            raw_text=raw_text,
            source_type=source_type,
        )
        # 2) Adiciona o objeto à sessão e dá commit (confirma a gravação).
        session.add(doc)
        session.commit()
        # 3) Após o commit, o banco já gerou o id (e o fetched_at). O refresh
        #    recarrega esses valores do banco para dentro do objeto.
        session.refresh(doc)
        return doc.id


def save_analysis(state: dict) -> int:
    """Salva o resultado de uma análise do grafo (o estado final) e devolve o id.

    Recebe o dicionário de estado final do grafo e mapeia os campos relevantes
    para a tabela 'analyses'. Campos ausentes viram vazio/None.
    """
    # Extrai os nomes únicos das tecnologias NVIDIA recuperadas (para a macro agregar).
    techs: list[str] = []
    for chunk in state.get("nvidia_context") or []:
        t = chunk.get("technology")
        if t and t not in techs:
            techs.append(t)

    with SessionLocal() as session:
        analysis = Analysis(
            startup_name=state.get("startup_name", ""),
            url=state.get("url", "") or "",
            level=state.get("level"),
            level_name=state.get("level_name") or "",
            rationale=state.get("rationale") or "",
            checklist=state.get("checklist") or [],
            structured=state.get("structured") or {},
            recommendations=state.get("recommendations") or "",
            briefing=state.get("briefing") or "",
            technologies=techs,
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        return analysis.id


def get_latest_analysis(startup_name: str) -> dict | None:
    """Devolve a análise mais recente salva para uma startup (ou None se não houver).

    Usado pelo frontend para CARREGAR uma análise já feita, sem rodar o grafo de
    novo (economiza LLM e é instantâneo).
    """
    with SessionLocal() as session:
        a = (
            session.query(Analysis)
            .filter(Analysis.startup_name == startup_name)
            .order_by(Analysis.created_at.desc())
            .first()
        )
        if a is None:
            return None
        return {
            "startup_name": a.startup_name,
            "url": a.url,
            "level": a.level,
            "level_name": a.level_name,
            "rationale": a.rationale,
            "checklist": a.checklist,
            "structured": a.structured,
            "recommendations": a.recommendations,
            "briefing": a.briefing,
        }


def list_analyses(limit: int = 50) -> list[dict]:
    """Lista as análises já salvas (mais recentes primeiro), em forma resumida.

    Serve de base para o catálogo/seletor de startups no frontend: o usuário
    escolhe uma startup já analisada sem precisar informar a URL de novo.
    """
    with SessionLocal() as session:
        linhas = (
            session.query(Analysis)
            .order_by(Analysis.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": a.id,
                "startup_name": a.startup_name,
                "url": a.url,
                "level": a.level,
                "level_name": a.level_name,
            }
            for a in linhas
        ]
