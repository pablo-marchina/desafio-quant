"""Testes da camada relacional (SQLite temporário, tipos portáveis)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db
from app.db import Base, Empresa
from app.state import DadosEmpresa, Recomendacao, Score


def test_empresa_persiste_e_le(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as s:
        s.add(
            Empresa(
                nome="Tractian",
                setor="Indústria",
                descricao="manutenção preditiva",
                dados={"nome": "Tractian", "tecnologias": ["IoT"]},
                fontes=["https://tractian.com"],
            )
        )
        s.commit()

    with Session() as s:
        e = s.query(Empresa).first()
        assert e.nome == "Tractian"
        assert e.dados["tecnologias"] == ["IoT"]   # JSON portável funciona
        assert e.fontes == ["https://tractian.com"]
        assert e.created_at is not None


def _final(briefing="## Briefing", score_composto=8.1):
    return {
        "alvos": ["Tractian"],
        "dados_estruturados": DadosEmpresa(nome="Tractian", setor="Indústria", descricao="x", fontes=["u"]),
        "classificacao": "ai-native",
        "score": Score(ai_native=9, nvidia_fit=8, tracao=8, time_ia=7, composto=score_composto),
        "recomendacao": Recomendacao(tecnologias=["Triton"], evidencias=["https://x"]),
        "briefing": briefing,
    }


def test_salvar_resultado_faz_upsert(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))

    db.salvar_resultado(_final(score_composto=8.1))
    db.salvar_resultado(_final(briefing="## Briefing v2", score_composto=9.0))  # mesma empresa

    with db.SessionLocal() as s:
        rows = s.query(Empresa).all()
        assert len(rows) == 1                       # upsert: não duplicou
        assert rows[0].score == 9.0                 # atualizou
        assert rows[0].briefing == "## Briefing v2"
        assert rows[0].classificacao == "ai-native"
        assert rows[0].recomendacao["tecnologias"] == ["Triton"]
