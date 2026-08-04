"""
Modelos de dados compartilhados entre os módulos do pipeline.

Mantemos isso simples e centralizado desde o Dia 1 para que Scraper,
Extractor e os Agents (Dia 3) falem a mesma "língua" de dados.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ScrapedDocument:
    """
    Representa um documento bruto coletado da web, com metadados
    suficientes para rastreabilidade (exigência do TAPI: toda informação
    coletada deve ser rastreável até a fonte original).
    """
    url: str
    titulo: Optional[str]
    texto: str
    fonte_tipo: str  # ex: "site_oficial", "noticia", "diretorio"
    coletado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metodo_coleta: str = "requests_bs4"  # vai evoluir: playwright, firecrawl, etc.
    status_http: Optional[int] = None
    erro: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "titulo": self.titulo,
            "texto": self.texto,
            "fonte_tipo": self.fonte_tipo,
            "coletado_em": self.coletado_em,
            "metodo_coleta": self.metodo_coleta,
            "status_http": self.status_http,
            "erro": self.erro,
        }
