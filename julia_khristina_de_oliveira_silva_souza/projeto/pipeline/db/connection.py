import os
import sqlite3
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nvidia_radar.db")
_db_type = "sqlite"


def _get_sqlite_conn():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_sqlite(conn)
    return conn


def _init_sqlite(conn=None):
    if conn is None:
        conn = _get_sqlite_conn()
        should_close = True
    else:
        should_close = False
    for col in ["email_contato", "email_enviado_em"]:
        try:
            conn.execute(f"ALTER TABLE startups ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE recomendacoes ADD COLUMN melhor_encaixe TEXT")
    except sqlite3.OperationalError:
        pass
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_startups_email ON startups(email_contato);
        CREATE INDEX IF NOT EXISTS idx_startups_cidade ON startups(cidade);
    """)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS startups (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            website TEXT,
            linkedin_url TEXT,
            email_contato TEXT,
            setor TEXT,
            descricao TEXT,
            produto_principal TEXT,
            fundacao_ano INTEGER,
            pais TEXT DEFAULT 'Brasil',
            cidade TEXT,
            estagio TEXT,
            ultima_rodada_valor REAL,
            ultima_rodada_data TEXT,
            numero_funcionarios_faixa TEXT,
            tecnologias_detectadas TEXT,
            fontes_url TEXT,
            email_enviado_em TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS evidencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            startup_id TEXT REFERENCES startups(id) ON DELETE CASCADE,
            tipo TEXT,
            url TEXT,
            titulo TEXT,
            conteudo_bruto TEXT,
            conteudo_limpo TEXT,
            data_publicacao TEXT,
            score_qualidade REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS classificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            startup_id TEXT REFERENCES startups(id) ON DELETE CASCADE,
            ai_classification TEXT,
            ramo_principal TEXT,
            usa_nvidia INTEGER,
            nvidia_confidence REAL,
            nvidia_techs_detectadas TEXT,
            gaps_identificados TEXT,
            score_fit_nvidia REAL,
            justificativa TEXT,
            classificado_em TEXT DEFAULT (datetime('now')),
            modelo_versao TEXT
        );

        CREATE TABLE IF NOT EXISTS recomendacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            startup_id TEXT REFERENCES startups(id) ON DELETE CASCADE,
            rank INTEGER,
            tecnologia TEXT,
            categoria TEXT,
            justificativa_tecnica TEXT,
            justificativa_negocio TEXT,
            nivel_prioridade TEXT,
            complexidade_implementacao TEXT,
            melhor_encaixe TEXT,
            proxima_acao_sugerida TEXT,
            evidencias_usadas TEXT,
            relevance_score REAL,
            url_referencia TEXT,
            gerado_em TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            startup_id TEXT REFERENCES startups(id) ON DELETE CASCADE,
            conteudo_json TEXT,
            conteudo_markdown TEXT,
            gerado_em TEXT DEFAULT (datetime('now')),
            exportado_em TEXT,
            formato_exportacao TEXT
        );
    """)
    conn.commit()
    if should_close:
        conn.close()


def get_connection():
    return _get_sqlite_conn()


def return_connection(conn):
    conn.close()


def execute_query(query: str, params: tuple = ()) -> None:
    conn = get_connection()
    try:
        conn.execute(query, params)
        conn.commit()
    finally:
        return_connection(conn)


def fetch_one(query: str, params: tuple = ()) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        return_connection(conn)


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        return_connection(conn)


_init_sqlite()
