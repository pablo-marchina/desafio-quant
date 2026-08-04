"""Popula o Postgres com a coorte real do SQLite (`data/cohort.db`) p/ a UI ter dados (F0.2).

Chamado por `scripts/run.ps1` depois do `alembic upgrade head`. **Best-effort**: sem
`cohort.db` (coorte ainda não rodada) ou sem Postgres de pé, sai limpo (a UI sobe vazia, sem
quebrar o `up`). Copia via ORM (fidelidade de tipos: datetime/enum) construindo instâncias só
com as colunas (sem relationship/cascade), preservando os PKs, e reajusta as sequences.

**Nota de FK (descoberta 2026-06-13):** o cohort builder (F1.14) grava `company/score/
recommendation` com `run_id`, mas **não cria a linha `run`**. O SQLite não força FK (dangling
passa); o Postgres força. Então sintetizamos uma linha `run` mínima p/ cada `run_id` referenciado
que falte na origem, antes de copiar o resto — a FK fecha sem perder dado.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete as sa_delete  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402

from packages.config import get_settings  # noqa: E402
from packages.db.models import (  # noqa: E402
    Company,
    Evidence,
    Founder,
    Recommendation,
    Run,
    Score,
)
from packages.schemas.enums import RunStatus  # noqa: E402

_SQLITE = Path(__file__).resolve().parents[1] / "data" / "cohort.db"
# `run` é tratado à parte (síntese de FK); o resto copia em ordem de FK (parents antes).
_COPY = [Company, Founder, Score, Recommendation, Evidence]


def _row_dict(obj: object, model: type) -> dict:
    """Valores só das colunas de tabela (sem relationships) — type-safe (datetime/enum)."""
    return {c.name: getattr(obj, c.name) for c in model.__table__.columns}


def main() -> int:
    if not _SQLITE.exists():
        print(f"[seed] {_SQLITE.name} não existe → UI sobe vazia (rode a coorte p/ popular).")
        return 0

    src = create_engine(f"sqlite:///{_SQLITE.as_posix()}")
    dst = create_engine(get_settings().sqlalchemy_url)
    with Session(src) as ssrc, Session(dst) as sdst:
        # idempotente: zera o destino (filhos antes, `run` por último).
        for model in (*reversed(_COPY), Run):
            sdst.execute(sa_delete(model))
        sdst.commit()

        # 1) Runs: copia os existentes + sintetiza os run_id referenciados que faltam (a FK
        #    company/score/recommendation → run.id precisa fechar; o cohort builder não os grava).
        existing = {r.id for r in ssrc.exec(select(Run)).all()}
        referenced: set[str] = set()
        for model in _COPY:
            if "run_id" in model.__table__.columns:
                referenced |= {
                    rid for obj in ssrc.exec(select(model)).all() if (rid := obj.run_id)
                }
        for r in ssrc.exec(select(Run)).all():
            sdst.add(Run(**_row_dict(r, Run)))
        for rid in sorted(referenced - existing):
            sdst.add(Run(id=rid, query="cohort (F1.14)", status=RunStatus.COMPLETED))
        sdst.commit()

        # 2) copia o resto preservando PKs.
        copied = 0
        for model in _COPY:
            for obj in ssrc.exec(select(model)).all():
                sdst.add(model(**_row_dict(obj, model)))
                copied += 1
        sdst.commit()

        # 3) sequences do Postgres → próximo id não colide com os PKs copiados. Só as tabelas de
        #    PK INTEIRO (a `run` tem PK string/uuid, sem sequence — e seu MAX(id)::text quebraria o
        #    COALESCE com o int do plano, então fica de fora).
        if dst.dialect.name == "postgresql":
            for model in _COPY:
                t = model.__tablename__
                sdst.execute(
                    text(
                        f"SELECT setval(seq, COALESCE((SELECT MAX(id) FROM {t}), 1)) "
                        f"FROM pg_get_serial_sequence('{t}', 'id') AS seq WHERE seq IS NOT NULL"
                    )
                )
            sdst.commit()

    n_runs = len(existing | referenced)
    print(f"[seed] {copied} linhas + {n_runs} runs copiadas de {_SQLITE.name} → Postgres.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
