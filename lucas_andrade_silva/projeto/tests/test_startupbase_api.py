from unittest.mock import MagicMock, Mock

from scraper.startupbase_api.client import StartupBaseClient, normalize_startup
from scraper.startupbase_api import config
from scraper.startupbase_api.database import SCHEMA_SQL, ensure_schema


def test_normaliza_campos_em_portugues():
    row = normalize_startup({"id": 7, "nome": "Acme AI", "descricao": "IA industrial", "segmento": {"nome": "SaaS"}, "estagio": "Seed", "cidade": "Recife", "ano_fundacao": 2021})
    assert row["name"] == "Acme AI"
    assert row["segment"] == "SaaS"
    assert row["founding_date"] == "2021-01-01"
    assert len(row["startupbase_id"]) == 64


def test_descarta_registro_sem_nome():
    assert normalize_startup({"description": "sem identificacao"}) is None


def test_pagina_ate_total(monkeypatch):
    monkeypatch.setattr(config, "PAGE_SIZE", 2)
    monkeypatch.setattr(config, "START_PAGE", 1)
    monkeypatch.setattr(config, "MAX_PAGES", 10)
    fake = Mock()
    responses = [
        Mock(status_code=200, json=lambda: {"data": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}], "total": 3}),
        Mock(status_code=200, json=lambda: {"data": [{"id": 3, "name": "C"}], "total": 3}),
    ]
    for response in responses:
        response.raise_for_status = Mock()
    fake.request.side_effect = responses
    client = StartupBaseClient(client=fake)
    client.api_url = "https://example.test/api/startups"
    assert [row["name"] for row in client.iter_startups()] == ["A", "B", "C"]
    assert fake.request.call_count == 2


def test_schema_migra_tabela_legada_antes_de_criar_indices():
    add_segment = "ADD COLUMN IF NOT EXISTS segment TEXT"
    segment_index = "CREATE INDEX IF NOT EXISTS startups_brazil_segment_idx"

    assert add_segment in SCHEMA_SQL
    assert SCHEMA_SQL.index(add_segment) < SCHEMA_SQL.index(segment_index)
    assert "CREATE UNIQUE INDEX IF NOT EXISTS startups_brazil_startupbase_id_uidx" in SCHEMA_SQL
    assert "ALTER COLUMN founding_year DROP NOT NULL" in SCHEMA_SQL
    assert "ALTER COLUMN location DROP NOT NULL" in SCHEMA_SQL
    assert "ALTER COLUMN source_url DROP NOT NULL" in SCHEMA_SQL


def test_ensure_schema_executa_migracao_e_confirma_transacao():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value

    ensure_schema(connection)

    cursor.execute.assert_called_once_with(SCHEMA_SQL)
    connection.commit.assert_called_once_with()
