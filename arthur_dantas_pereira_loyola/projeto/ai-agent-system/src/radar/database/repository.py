from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from radar.database.connection import get_connection


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS startups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sector TEXT,
                product TEXT,
                description TEXT,
                founders TEXT DEFAULT '[]',
                customers TEXT DEFAULT '[]',
                funding TEXT,
                cited_technologies TEXT DEFAULT '[]',
                ai_usage_summary TEXT,
                classification_label TEXT,
                classification_confidence REAL,
                classification_rationale TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                startup_id TEXT REFERENCES startups(id),
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS source_documents (
                id TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                url TEXT NOT NULL,
                domain TEXT NOT NULL,
                source_type TEXT NOT NULL,
                title TEXT,
                text TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                collection_method TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence_claims (
                id TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                source_document_id TEXT NOT NULL REFERENCES source_documents(id),
                text TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                has_minimum_evidence INTEGER NOT NULL DEFAULT 0,
                source_quality TEXT NOT NULL DEFAULT 'weak',
                supporting_evidence_ids TEXT DEFAULT '[]',
                conflicts TEXT DEFAULT '[]',
                caveats TEXT DEFAULT '[]',
                requires_human_review INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                technology TEXT NOT NULL,
                target_gap TEXT NOT NULL,
                technical_justification TEXT NOT NULL,
                business_justification TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                implementation_complexity TEXT NOT NULL DEFAULT 'medium',
                suggested_next_action TEXT NOT NULL,
                startup_evidence_ids TEXT DEFAULT '[]',
                nvidia_knowledge_ids TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS run_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id),
                step_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle',
                detail TEXT,
                error_message TEXT,
                started_at TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_id TEXT NOT NULL REFERENCES startups(id),
                emails TEXT DEFAULT '[]',
                phones TEXT DEFAULT '[]',
                linkedin_urls TEXT DEFAULT '[]',
                addresses TEXT DEFAULT '[]',
                primary_name TEXT,
                primary_role TEXT,
                raw_text_snippets TEXT DEFAULT '[]',
                collected_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(startup_id)
            );

            CREATE TABLE IF NOT EXISTS contact_discovery_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_id TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS contact_discovery_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discovery_id INTEGER NOT NULL REFERENCES contact_discovery_runs(id),
                step_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle',
                detail TEXT,
                error_message TEXT,
                started_at TEXT,
                completed_at TEXT,
                UNIQUE(discovery_id, step_key)
            );
            CREATE INDEX IF NOT EXISTS idx_cd_steps_discovery ON contact_discovery_steps(discovery_id);

            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'running',
                total INTEGER NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS batch_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES batches(id),
                startup_name TEXT NOT NULL,
                query TEXT NOT NULL,
                run_id INTEGER REFERENCES runs(id),
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_batch_items_batch ON batch_items(batch_id);

            CREATE INDEX IF NOT EXISTS idx_run_steps_run_id ON run_steps(run_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_run_steps_run_step ON run_steps(run_id, step_key);
        """)


def save_run(query: str, startup_id: str | None = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO runs (query, startup_id) VALUES (?, ?)",
            (query, startup_id),
        )
        return cur.lastrowid or 0


def update_run_status(run_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = ?,
                completed_at = CASE
                    WHEN ? IN ('completed', 'failed') THEN datetime('now')
                    ELSE NULL
                END
            WHERE id = ?
            """,
            (status, status, run_id),
        )


def update_run_step_status(
    run_id: int,
    step_key: str,
    status: str | None = None,
    detail: str | None = None,
    error_message: str | None = None,
) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, status FROM run_steps WHERE run_id = ? AND step_key = ?",
            (run_id, step_key),
        ).fetchone()
        if existing:
            sets = []
            params: list = []
            if status is not None:
                sets.append("status = ?")
                params.append(status)
            if detail is not None:
                sets.append("detail = ?")
                params.append(detail)
            if error_message is not None:
                sets.append("error_message = ?")
                params.append(error_message)
            if status == "running":
                sets.append("started_at = datetime('now')")
                sets.append("completed_at = NULL")
            if status in ("completed", "error"):
                sets.append("completed_at = datetime('now')")
            if sets:
                params.append(existing["id"])
                conn.execute(
                    f"UPDATE run_steps SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
        else:
            conn.execute(
                """INSERT INTO run_steps
                   (run_id, step_key, status, detail, error_message, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?,
                           CASE WHEN ? = 'running' THEN datetime('now') ELSE NULL END,
                           CASE WHEN ? IN ('completed','error') THEN datetime('now') ELSE NULL END)""",
                (
                    run_id, step_key,
                    status or "idle",
                    detail, error_message,
                    status, status,
                ),
            )


def get_run_steps(run_id: int) -> list[dict[str, object]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT step_key, status, detail, error_message, started_at, completed_at "
            "FROM run_steps WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_run_startup(run_id: int, startup_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE runs SET startup_id = ? WHERE id = ?",
            (startup_id, run_id),
        )


def get_runs_by_startup(startup_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, query, startup_id, status, created_at, completed_at FROM runs WHERE startup_id = ? ORDER BY created_at DESC",
            (startup_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_startup(data: dict[str, Any]) -> str:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM startups WHERE name = ?", (data["name"],)
        ).fetchone()
        if existing:
            stmt = """
                UPDATE startups SET
                    sector=?, product=?, description=?, founders=?, customers=?,
                    funding=?, cited_technologies=?, ai_usage_summary=?,
                    classification_label=?, classification_confidence=?,
                    classification_rationale=?, updated_at=datetime('now')
                WHERE id=?
            """
            conn.execute(
                stmt,
                (
                    data.get("sector"),
                    data.get("product"),
                    data.get("description"),
                    json.dumps(data.get("founders", [])),
                    json.dumps(data.get("customers", [])),
                    data.get("funding"),
                    json.dumps(data.get("cited_technologies", [])),
                    data.get("ai_usage_summary"),
                    data.get("classification_label"),
                    data.get("classification_confidence"),
                    data.get("classification_rationale"),
                    existing["id"],
                ),
            )
            return existing["id"]
        stmt = """
            INSERT INTO startups
                (id, name, sector, product, description, founders, customers,
                 funding, cited_technologies, ai_usage_summary,
                 classification_label, classification_confidence, classification_rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(
            stmt,
            (
                data.get("id"),
                data["name"],
                data.get("sector"),
                data.get("product"),
                data.get("description"),
                json.dumps(data.get("founders", [])),
                json.dumps(data.get("customers", [])),
                data.get("funding"),
                json.dumps(data.get("cited_technologies", [])),
                data.get("ai_usage_summary"),
                data.get("classification_label"),
                data.get("classification_confidence"),
                data.get("classification_rationale"),
            ),
        )
        return data["id"]


def save_source_document(run_id: int, data: dict[str, Any]) -> str:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO source_documents
               (id, run_id, url, domain, source_type, title, text, retrieved_at, collection_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["id"],
                run_id,
                str(data["url"]),
                data["domain"],
                data["source_type"],
                data.get("title"),
                data["text"],
                data["retrieved_at"].isoformat()
                if isinstance(data["retrieved_at"], datetime)
                else data["retrieved_at"],
                data["collection_method"],
            ),
        )
    return data["id"]


def save_evidence_claim(run_id: int, data: dict[str, Any]) -> str:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO evidence_claims
               (id, run_id, source_document_id, text, claim_type, confidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["id"],
                run_id,
                data["source_document_id"],
                data["text"],
                data["claim_type"],
                data["confidence"],
            ),
        )
    return data["id"]


def save_validation(run_id: int, data: dict[str, Any]) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO validations
               (run_id, has_minimum_evidence, source_quality, supporting_evidence_ids, conflicts, caveats, requires_human_review)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                1 if data.get("has_minimum_evidence") else 0,
                data.get("source_quality", "weak"),
                json.dumps(data.get("supporting_evidence_ids", [])),
                json.dumps(data.get("conflicts", [])),
                json.dumps(data.get("caveats", [])),
                1 if data.get("requires_human_review") else 0,
            ),
        )
        return cur.lastrowid or 0


def get_run_validation(run_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT has_minimum_evidence, source_quality, supporting_evidence_ids,
                   conflicts, caveats, requires_human_review
            FROM validations
            WHERE run_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        if not row:
            return None

    validation = dict(row)
    validation["has_minimum_evidence"] = bool(validation["has_minimum_evidence"])
    validation["requires_human_review"] = bool(validation["requires_human_review"])
    for key in ("supporting_evidence_ids", "conflicts", "caveats"):
        value = validation.get(key)
        validation[key] = json.loads(value) if isinstance(value, str) and value else []
    return validation

def save_recommendation(run_id: int, data: dict[str, Any]) -> str:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO recommendations
               (id, run_id, technology, target_gap, technical_justification,
                business_justification, priority, implementation_complexity,
                suggested_next_action, startup_evidence_ids, nvidia_knowledge_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["id"],
                run_id,
                data["technology"],
                data.get("target_gap", ""),
                data.get("technical_justification", ""),
                data.get("business_justification", ""),
                data.get("priority", "medium"),
                data.get("implementation_complexity", "medium"),
                data.get("suggested_next_action", ""),
                json.dumps(data.get("startup_evidence_ids", [])),
                json.dumps(data.get("nvidia_knowledge_ids", [])),
            ),
        )
    return data["id"]


def get_all_source_documents() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                sd.*,
                COUNT(ec.id) AS claim_count,
                AVG(ec.confidence) AS average_claim_confidence
            FROM source_documents sd
            LEFT JOIN evidence_claims ec ON ec.source_document_id = sd.id
            GROUP BY sd.id
            ORDER BY sd.retrieved_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_run_source_documents(run_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                sd.*,
                COUNT(ec.id) AS claim_count,
                AVG(ec.confidence) AS average_claim_confidence
            FROM source_documents sd
            LEFT JOIN evidence_claims ec ON ec.source_document_id = sd.id
            WHERE sd.run_id = ?
            GROUP BY sd.id
            ORDER BY sd.retrieved_at DESC
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_run_evidence_claims(run_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM evidence_claims
            WHERE run_id = ?
            ORDER BY confidence DESC, id ASC
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_runs() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, query, startup_id, status, created_at, completed_at FROM runs ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_run_by_id(run_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def create_batch(items: list[dict[str, str]]) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO batches (status, total) VALUES ('running', ?)",
            (len(items),),
        )
        batch_id = cur.lastrowid or 0
        for item in items:
            conn.execute(
                "INSERT INTO batch_items (batch_id, startup_name, query) VALUES (?, ?, ?)",
                (batch_id, item["startup_name"], item["query"]),
            )
        return batch_id


def get_batch(batch_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        items = conn.execute(
            "SELECT * FROM batch_items WHERE batch_id = ? ORDER BY id ASC",
            (batch_id,),
        ).fetchall()
        result["items"] = [dict(r) for r in items]
        return result


def update_batch_item(item_id: int, run_id: int | None = None, status: str | None = None, error_message: str | None = None) -> None:
    with get_connection() as conn:
        sets: list[str] = []
        params: list = []
        if run_id is not None:
            sets.append("run_id = ?")
            params.append(run_id)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
            sets.append("completed_at = CASE WHEN ? IN ('completed','failed') THEN datetime('now') ELSE NULL END")
            params.append(status)
        if error_message is not None:
            sets.append("error_message = ?")
            params.append(error_message)
        if sets:
            params.append(item_id)
            conn.execute(f"UPDATE batch_items SET {', '.join(sets)} WHERE id = ?", params)


def complete_batch(batch_id: int) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed FROM batch_items WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        total = row["total"]
        done = row["completed"] + row["failed"]
        status = "completed" if done >= total else "running"
        conn.execute(
            "UPDATE batches SET status = ?, completed = ?, failed = ?, completed_at = CASE WHEN ? IN ('completed','failed') THEN datetime('now') ELSE NULL END WHERE id = ?",
            (status, row["completed"], row["failed"], status, batch_id),
        )


def get_run_recommendations(run_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE run_id = ? ORDER BY priority",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_run_briefing(run_id: int, briefing_json: str) -> None:
    with get_connection() as conn:
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN briefing TEXT")
        except Exception:
            pass
        conn.execute("UPDATE runs SET briefing = ? WHERE id = ?", (briefing_json, run_id))


_STARTUP_SELECT = """
    SELECT s.*,
      ROUND(
        (COALESCE(s.classification_confidence, 0) * 0.4 +
         MIN(COALESCE((
           SELECT COUNT(*) FROM evidence_claims ec
           JOIN source_documents sd ON sd.id = ec.source_document_id
           JOIN runs r ON r.id = sd.run_id
           WHERE r.startup_id = s.id
         ), 0) / 5.0, 1.0) * 0.3 +
         MIN(COALESCE((
           SELECT COUNT(*) FROM recommendations rec
           JOIN runs r ON r.id = rec.run_id
           WHERE r.startup_id = s.id
         ), 0) / 3.0, 1.0) * 0.3
        ) * 100, 0
      ) AS radar_score,
      COALESCE((
        SELECT COUNT(*) FROM evidence_claims ec
        JOIN source_documents sd ON sd.id = ec.source_document_id
        JOIN runs r ON r.id = sd.run_id
        WHERE r.startup_id = s.id
      ), 0) AS evidence_count,
      COALESCE((
        SELECT COUNT(*) FROM recommendations rec
        JOIN runs r ON r.id = rec.run_id
        WHERE r.startup_id = s.id
      ), 0) AS recommendation_count
    FROM startups s
"""


def get_all_startups() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            _STARTUP_SELECT + "ORDER BY radar_score DESC, s.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_startup_by_id(startup_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            _STARTUP_SELECT + "WHERE s.id = ?", (startup_id,)
        ).fetchone()
        return dict(row) if row else None


def save_contacts(startup_id: str, data: dict[str, Any]) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM contacts WHERE startup_id = ?", (startup_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE contacts SET
                    emails=?, phones=?, linkedin_urls=?, addresses=?,
                    primary_name=?, primary_role=?, raw_text_snippets=?,
                    collected_at=?
                WHERE startup_id=?""",
                (
                    json.dumps(data.get("emails", [])),
                    json.dumps(data.get("phones", [])),
                    json.dumps(data.get("linkedin_urls", [])),
                    json.dumps(data.get("addresses", [])),
                    data.get("primary_name"),
                    data.get("primary_role"),
                    json.dumps(data.get("raw_text_snippets", [])),
                    data.get("collected_at"),
                    startup_id,
                ),
            )
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO contacts
               (startup_id, emails, phones, linkedin_urls, addresses,
                primary_name, primary_role, raw_text_snippets, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                startup_id,
                json.dumps(data.get("emails", [])),
                json.dumps(data.get("phones", [])),
                json.dumps(data.get("linkedin_urls", [])),
                json.dumps(data.get("addresses", [])),
                data.get("primary_name"),
                data.get("primary_role"),
                json.dumps(data.get("raw_text_snippets", [])),
                data.get("collected_at"),
            ),
        )
        return cur.lastrowid or 0


def get_contacts_by_startup(startup_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE startup_id = ?", (startup_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in ("emails", "phones", "linkedin_urls", "addresses", "raw_text_snippets"):
            value = result.get(key)
            result[key] = json.loads(value) if isinstance(value, str) else []
        return result


_CONTACT_STEP_ORDER = [
    "preparing_queries",
    "searching_web",
    "extracting_contacts",
    "fallback_sources",
    "cross_referencing",
    "saving_result",
]


def create_contact_discovery_run(startup_id: str) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM contact_discovery_runs WHERE startup_id = ?",
            (startup_id,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE contact_discovery_runs SET status='pending', completed_at=NULL WHERE startup_id=?",
                (startup_id,),
            )
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO contact_discovery_runs (startup_id, status) VALUES (?, 'pending')",
            (startup_id,),
        )
        return cur.lastrowid or 0


def update_contact_discovery_status(discovery_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE contact_discovery_runs SET status=?,
               completed_at=CASE WHEN ? IN ('completed','failed') THEN datetime('now') ELSE NULL END
               WHERE id=?""",
            (status, status, discovery_id),
        )


def get_contact_discovery_run(startup_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contact_discovery_runs WHERE startup_id = ? ORDER BY id DESC LIMIT 1",
            (startup_id,),
        ).fetchone()
        return dict(row) if row else None


def get_contact_discovery_run_by_id(discovery_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contact_discovery_runs WHERE id = ?", (discovery_id,)
        ).fetchone()
        return dict(row) if row else None


def ensure_contact_discovery_steps_registered(discovery_id: int) -> None:
    with get_connection() as conn:
        for sk in _CONTACT_STEP_ORDER:
            conn.execute(
                """INSERT OR IGNORE INTO contact_discovery_steps
                   (discovery_id, step_key, status) VALUES (?, ?, 'idle')""",
                (discovery_id, sk),
            )


def update_contact_discovery_step(
    discovery_id: int,
    step_key: str,
    status: str | None = None,
    detail: str | None = None,
    error_message: str | None = None,
) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, status FROM contact_discovery_steps WHERE discovery_id=? AND step_key=?",
            (discovery_id, step_key),
        ).fetchone()
        if existing:
            sets: list[str] = []
            params: list = []
            if status is not None:
                sets.append("status = ?")
                params.append(status)
            if detail is not None:
                sets.append("detail = ?")
                params.append(detail)
            if error_message is not None:
                sets.append("error_message = ?")
                params.append(error_message)
            if status == "running":
                sets.append("started_at = datetime('now')")
                sets.append("completed_at = NULL")
            if status in ("completed", "error"):
                sets.append("completed_at = datetime('now')")
            if sets:
                params.append(existing["id"])
                conn.execute(
                    f"UPDATE contact_discovery_steps SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
        else:
            conn.execute(
                """INSERT INTO contact_discovery_steps
                   (discovery_id, step_key, status, detail, error_message, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?,
                           CASE WHEN ? = 'running' THEN datetime('now') ELSE NULL END,
                           CASE WHEN ? IN ('completed','error') THEN datetime('now') ELSE NULL END)""",
                (discovery_id, step_key, status or "idle", detail, error_message, status, status),
            )


def get_contact_discovery_steps(discovery_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT step_key, status, detail, error_message, started_at, completed_at "
            "FROM contact_discovery_steps WHERE discovery_id=? ORDER BY id ASC",
            (discovery_id,),
        ).fetchall()
        return [dict(r) for r in rows]


