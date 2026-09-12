"""Local SQL transaction tests; SQLite checks rollback/visibility, not MySQL lock semantics."""
from datetime import UTC, datetime, timedelta
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.live_projection.outbox import OutboxReader
from app.live_projection import outbox_writer


class Cursor:
    def __init__(self, connection):
        self.cursor = connection.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, params=()):
        # SQLite local substitute only; production FOR UPDATE is verified separately on MySQL.
        self.cursor.execute(sql.replace(' FOR UPDATE', '').replace('%s', '?'),
                            tuple(v.isoformat(' ') if isinstance(v, datetime) else v for v in params))

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def get_autocommit(self):
        return False

    def cursor(self):
        return Cursor(self.raw)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'outbox.sqlite'
    raw = sqlite3.connect(path)
    raw.executescript('''
        CREATE TABLE business_document (id INTEGER PRIMARY KEY);
        CREATE TABLE sim_event_outbox_state (
            singleton_id INTEGER PRIMARY KEY, stream_id TEXT NOT NULL,
            last_sequence INTEGER DEFAULT 0, pruned_through INTEGER DEFAULT 0,
            documents INTEGER DEFAULT 0, vouchers INTEGER DEFAULT 0, integrations INTEGER DEFAULT 0);
        INSERT INTO sim_event_outbox_state (singleton_id, stream_id) VALUES (1, 'test-stream');
        CREATE TABLE sim_event_outbox (
            sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
            created_at TEXT NOT NULL, documents INTEGER NOT NULL, vouchers INTEGER NOT NULL,
            integrations INTEGER NOT NULL);
    ''')
    raw.commit()
    engine = create_engine(f'sqlite:///{path}')
    yield Connection(raw), OutboxReader(lambda: engine)
    raw.close()
    engine.dispose()


def record(number=1):
    return {'event_id': f'document-{number}', 'committed_at': '2026-09-13T00:00:00+00:00',
            'business_type': 'integration_completed',
            'increments': {'documents': 1, 'vouchers': 1, 'integrations': 1}}


def test_business_and_outbox_have_same_commit_visibility(database):
    conn, reader = database
    conn.raw.execute('INSERT INTO business_document VALUES (1)')
    outbox_writer.append_outbox(conn, [record()])
    assert reader.read_page(0).records == []
    conn.raw.commit()
    page = reader.read_page(0)
    assert page.head == 1
    assert page.records[0]['event_id'] == 'document-1'
    assert page.cumulative['documents'] == 1
    # A fresh reader after API restart reads the same committed event and stable sequence.
    assert reader.read_page(0) == page


def test_rollback_and_duplicate_id_do_not_leave_business_or_outbox_half_committed(database):
    conn, reader = database
    conn.raw.execute('INSERT INTO business_document VALUES (1)')
    outbox_writer.append_outbox(conn, [record()])
    with pytest.raises(sqlite3.IntegrityError):
        outbox_writer.append_outbox(conn, [record()])
    conn.raw.rollback()
    assert reader.read_page(0).head == 0
    assert conn.raw.execute('SELECT COUNT(*) FROM business_document').fetchone()[0] == 0
    assert reader.read_page(0).records == []
    # Transactional allocation has no rolled-back sequence gap.
    outbox_writer.append_outbox(conn, [record(2)])
    conn.raw.commit()
    assert reader.read_page(0).records[0]['sequence'] == 1


def test_missing_schema_rolls_back_business_transaction(database):
    conn, _ = database
    conn.raw.execute('DROP TABLE sim_event_outbox')
    conn.raw.commit()
    conn.raw.execute('INSERT INTO business_document VALUES (1)')
    with pytest.raises(sqlite3.OperationalError):
        outbox_writer.append_outbox(conn, [record()])
    conn.raw.rollback()
    assert conn.raw.execute('SELECT COUNT(*) FROM business_document').fetchone()[0] == 0


def test_pruning_advances_floor_and_preserves_persistent_totals(database, monkeypatch):
    conn, reader = database
    monkeypatch.setattr(outbox_writer, 'MAX_RETAINED_EVENTS', 3)
    outbox_writer.append_outbox(conn, [record(i) for i in range(1, 6)])
    conn.raw.commit()
    page = reader.read_page(0)
    assert page.floor == 2 and page.head == 5
    assert [r['sequence'] for r in page.records] == [3, 4, 5]
    assert page.cumulative['documents'] == 5
    assert reader.read_page(None).records == []


def test_retention_cutoff_and_pruning_are_rolled_back_together(database):
    conn, reader = database
    now = datetime.now(UTC)
    outbox_writer.append_outbox(conn, [record()], now=now - timedelta(days=31))
    conn.raw.commit()
    outbox_writer.append_outbox(conn, [record(2)], now=now)
    conn.raw.rollback()
    assert reader.read_page(0).floor == 0
    assert len(reader.read_page(0).records) == 1
    outbox_writer.append_outbox(conn, [record(2)], now=now)
    conn.raw.commit()
    assert reader.read_page(0).floor == 1
    assert [r['sequence'] for r in reader.read_page(0).records] == [2]


def test_reader_pages_are_bounded(database):
    conn, reader = database
    outbox_writer.append_outbox(conn, [record(i) for i in range(1, 106)])
    conn.raw.commit()
    assert len(reader.read_page(0).records) == 100
    assert len(reader.read_page(100).records) == 5
    with pytest.raises(ValueError):
        reader.read_page(0, limit=1000)


def test_autocommit_connection_is_rejected(database, monkeypatch):
    conn, _ = database
    monkeypatch.setattr(conn, 'get_autocommit', lambda: True)
    with pytest.raises(ValueError, match='explicit transaction'):
        outbox_writer.append_outbox(conn, [record()])


def test_large_write_batch_is_rejected_before_any_sql(database, monkeypatch):
    conn, reader = database
    monkeypatch.setattr(outbox_writer, 'PRUNE_BATCH_SIZE', 2)
    with pytest.raises(ValueError, match='batch'):
        outbox_writer.append_outbox(conn, [record(i) for i in range(3)])
    assert reader.read_page(0).head == 0
