"""Stream full packages into explicit empty targets, without production fallback."""
from __future__ import annotations

import hashlib
import tempfile
from itertools import islice
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from .package import create_schema, identifier, read_manifest, iter_rows
from .policy import TABLES


def initialize(directory, target_url, apply=False, allow_remote=False, bulk_load=False):
    manifest, schema = read_manifest(directory)
    url = make_url(target_url)
    if url.drivername != 'mysql+pymysql' or not url.database:
        raise ValueError('A named MySQL database is required')
    if not allow_remote and url.host not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Remote targets require explicit --allow-remote-target')
    package_hash = hashlib.sha256((Path(directory) / 'manifest.json').read_bytes()).hexdigest()
    engine = create_engine(url, connect_args={'connect_timeout': 10, 'local_infile': bulk_load})
    with engine.connect() as conn:
        existing = set(conn.execute(text('SELECT table_name FROM information_schema.tables '
                                         'WHERE table_schema=DATABASE()')).scalars())
        if existing == set(TABLES) | {'demo_seed_state'}:
            stamp = conn.execute(text('SELECT package_hash FROM demo_seed_state')).scalars().all()
            if stamp != [package_hash]:
                raise ValueError('Target contains a different demo version')
            validate_target(conn, manifest)
            return {'status': 'already_initialized', 'tables': len(TABLES)}
        if existing:
            raise ValueError('Target must be empty; objects will not be overwritten')
        if not apply:
            return {'status': 'plan', 'tables': len(TABLES),
                    'rows': sum(r['rows'] for r in manifest['tables'].values())}
        conn.execute(text("SET time_zone = '+00:00'"))
        conn.execute(text("SET SESSION sql_mode = CONCAT(@@sql_mode, ',NO_AUTO_VALUE_ON_ZERO')"))
        for sql in create_schema(schema):
            conn.execute(text(sql))
        conn.commit()
        for table in TABLES:
            item = manifest['tables'][table]
            columns = item['columns']
            sql = text(f'INSERT INTO {identifier(table)} (' +
                       ','.join(identifier(c) for c in columns) + ') VALUES (' +
                       ','.join(f':{c}' for c in columns) + ')')
            iterator = iter_rows(directory, item)
            count = 0
            batch_size = 20000 if bulk_load else 1000
            while chunk := list(islice(iterator, batch_size)):
                with conn.begin():
                    if bulk_load:
                        load_batch(conn, table, columns, chunk)
                    else:
                        conn.execute(sql, chunk)
                count += len(chunk)
                if count % 500000 < len(chunk):
                    print(f'Importing {table}: {count}/{item["rows"]}', flush=True)
            if count != item['rows']:
                raise ValueError(f'Imported row mismatch: {table}')
            print(f'Imported {table}: {count} rows', flush=True)
        for i, fk in enumerate(schema['foreign_keys']):
            conn.execute(text(f'ALTER TABLE {identifier(fk["table_name"])} '
                              f'ADD CONSTRAINT demo_fk_{i} FOREIGN KEY '
                              f'({identifier(fk["column_name"])}) REFERENCES '
                              f'{identifier(fk["referenced_table_name"])} '
                              f'({identifier(fk["referenced_column_name"])})'))
        validate_target(conn, manifest)
        conn.execute(text('CREATE TABLE demo_seed_state (package_hash CHAR(64) PRIMARY KEY)'))
        conn.execute(text('INSERT INTO demo_seed_state VALUES (:hash)'), {'hash': package_hash})
        conn.commit()
    engine.dispose()
    return {'status': 'initialized', 'tables': len(TABLES),
            'rows': sum(r['rows'] for r in manifest['tables'].values())}


def validate_target(conn, manifest):
    for table, item in manifest['tables'].items():
        if conn.execute(text(f'SELECT COUNT(*) FROM {identifier(table)}')).scalar_one() != item['rows']:
            raise ValueError(f'Imported count mismatch: {table}')


def load_batch(conn, table, columns, rows):
    """Optional native bulk copy: only sanitized package rows in a private temp file."""
    with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', prefix='mod-demo-', suffix='.tsv') as handle:
        for row in rows:
            values = []
            for column in columns:
                value = row[column]
                if value is None:
                    values.append(r'\N')
                else:
                    values.append(str(value).replace('\\', '\\\\').replace('\0', r'\0')
                                  .replace('\t', r'\t').replace('\n', r'\n')
                                  .replace('\r', r'\r').replace('\x1a', r'\Z'))
            handle.write('\t'.join(values) + '\n')
        handle.flush()
        sql = (f'LOAD DATA LOCAL INFILE :file INTO TABLE {identifier(table)} '
               "CHARACTER SET utf8mb4 FIELDS TERMINATED BY '\\t' ESCAPED BY '\\\\' "
               "LINES TERMINATED BY '\\n' (" + ','.join(identifier(c) for c in columns) + ')')
        conn.execute(text(sql), {'file': handle.name})
        if conn.execute(text('SHOW WARNINGS')).first():
            raise ValueError(f'Bulk load reported a data warning: {table}')
