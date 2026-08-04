"""create langgraph checkpoint tables

Revision ID: 9e1f3b5c8a2d
Revises: 7c9f2a1b4d6e
Create Date: 2026-06-16 12:00:00.000000

Cria as tabelas usadas pelo AsyncPostgresSaver do langgraph-checkpoint-postgres.
Estas tabelas persistem o estado de cada grafo LangGraph entre nodes, permitindo:
  - retomada apos falha do worker
  - human-in-the-loop (interrupcao + aprovacao)
  - auditoria do estado interno de cada execucao

As tabelas sao proprias do LangGraph e nao referenciam nossas tabelas de negocio.
O vinculo com agent_runs e feito por convencao: thread_id = str(agent_run.id).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9e1f3b5c8a2d"
down_revision: str | None = "7c9f2a1b4d6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tabela de controle de versao das migrations do LangGraph.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_migrations (
            v INTEGER PRIMARY KEY
        )
        """
    )

    # Checkpoint principal: estado serializado do grafo por thread_id.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint JSONB NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        )
        """
    )

    # Blobs de canal: conteudo serializado por versao de canal.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_blobs (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL,
            version TEXT NOT NULL,
            type TEXT NOT NULL,
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
        )
        """
    )

    # Escritas pendentes: resultado de cada task antes do proximo checkpoint.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            type TEXT,
            blob BYTEA NOT NULL,
            task_path TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        )
        """
    )

    # Indices para busca rapida por thread_id.
    op.execute(
        "CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id)"
    )

    # Registra a versao atual das migrations do LangGraph (10 migracoes na v3.1.0).
    op.execute(
        """
        INSERT INTO checkpoint_migrations (v)
        SELECT s.v FROM generate_series(0, 10) AS s(v)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS checkpoint_writes_thread_id_idx")
    op.execute("DROP INDEX IF EXISTS checkpoint_blobs_thread_id_idx")
    op.execute("DROP INDEX IF EXISTS checkpoints_thread_id_idx")
    op.execute("DROP TABLE IF EXISTS checkpoint_writes")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs")
    op.execute("DROP TABLE IF EXISTS checkpoints")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations")
