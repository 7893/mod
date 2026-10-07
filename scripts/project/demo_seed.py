#!/usr/bin/env python3
"""MOD full demo export/import. Owner: project. Local source SELECTs only.

Inputs: approved source environment or independent MOD_DEMO_DATABASE_URL.
Output: full compressed simulation records, redacting only real environment values.
No production writes, deployment, LFS, Release uploads or raw credential output.
Recovery: source stays untouched; failed isolated targets are discarded explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def export_full(destination):
    from safe_db_query import read_only_connection
    from demo_data.source import describe, batches, select
    from demo_data.policy import Sanitizer, TABLES, private_values
    from demo_data.package import ShardSink, identifier, SHARD_BYTES
    from demo_data.columnar import ColumnWriter, DICT_BYTES
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Output already exists; no files are overwritten')
    assets = private_values(os.environ)
    sanitizer = Sanitizer(assets)
    destination.mkdir(parents=True)
    manifest = {'format_version': 3, 'purpose': 'full_simulation_demo_seed',
                'shard_maximum_bytes': SHARD_BYTES,
                'compression': {'columnar': 'parquet_delta', 'codec': 'xz', 'preset': '9e',
                                'dictionary_bytes': DICT_BYTES, 'nice_length': 273},
                'source_snapshot': 'single_read_only_consistent_snapshot',
                'preserves': 'all tables and rows, IDs, amounts, dates, simulation names and text',
                'redacts': 'real infrastructure, credentials, email addresses and host paths',
                'model_results': 'frozen_synthetic_experiment', 'tables': {}, 'files': {}}
    sink = ShardSink(destination)
    with read_only_connection(60000) as conn:
        schema = describe(conn)
        for column in schema['columns']:
            column['column_default'] = sanitizer.value(column.get('column_default'))
        actual = {r['table_name'] for r in schema['columns']}
        if actual != set(TABLES):
            raise ValueError('Source table inventory changed; review before exporting')
        for table in TABLES:
            columns = [r['column_name'] for r in schema['columns'] if r['table_name'] == table]
            primary = [r['column_name'] for r in schema['columns']
                       if r['table_name'] == table and r['column_key'] == 'PRI']
            if not primary:
                raise ValueError(f'Missing primary key: {table}')
            expected = select(conn, f'SELECT COUNT(*) AS n FROM {identifier(table)}')[0]['n']
            table_columns = [c for c in schema['columns'] if c['table_name'] == table]
            writer, count = ColumnWriter(table_columns, sink), 0
            for chunk in batches(conn, table, columns, primary):
                for row in chunk:
                    writer.row([sanitizer.value(row[c]) for c in columns])
                count += len(chunk)
                if count % 500000 < len(chunk):
                    print(f'Exporting {table}: {count}/{expected}', flush=True)
            metadata = writer.close()
            if count != expected:
                raise ValueError(f'Snapshot row count mismatch: {table}')
            manifest['tables'][table] = {'columns': columns, 'rows': count, **metadata}
            print(f'Exported {table}: {count} rows', flush=True)
        anchor = select(conn, 'SELECT MAX(stat_date) AS d FROM daily_stats')[0]['d']
        manifest['business_as_of_date'] = str(anchor)
    sink.close()
    (destination / 'schema.json').write_text(json.dumps(schema, sort_keys=True, indent=2) + '\n')
    for p in destination.iterdir():
        with p.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        manifest['files'][p.name] = {'sha256': digest, 'bytes': p.stat().st_size}
    manifest['redacted_text_values'] = sanitizer.replacements
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': 'exported', 'rows': sum(v['rows'] for v in manifest['tables'].values()),
                      'compressed_bytes': sum(v['bytes'] for v in manifest['files'].values()),
                      'redacted_text_values': sanitizer.replacements}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--output', type=Path, required=True)
    repack_parser = sub.add_parser('repack', help='Extreme compression of an existing local package')
    repack_parser.add_argument('--source', type=Path, required=True)
    repack_parser.add_argument('--output', type=Path, required=True)
    reshard_parser = sub.add_parser('reshard', help='Split existing extreme streams without recompression')
    reshard_parser.add_argument('--source', type=Path, required=True)
    reshard_parser.add_argument('--output', type=Path, required=True)
    verify_parser = sub.add_parser('verify')
    verify_parser.add_argument('--package', type=Path, default=ROOT / 'demo-data')
    init = sub.add_parser('init')
    init.add_argument('--package', type=Path, default=ROOT / 'demo-data')
    init.add_argument('--apply', action='store_true')
    init.add_argument('--allow-remote-target', action='store_true')
    init.add_argument('--bulk-load', action='store_true', help='Use explicitly enabled MySQL LOCAL INFILE')
    args = parser.parse_args()
    if args.command == 'export':
        export_full(args.output)
    elif args.command == 'repack':
        from demo_data.repack import repack
        repack(args.source, args.output)
    elif args.command == 'reshard':
        from demo_data.repack import reshard
        reshard(args.source, args.output)
    elif args.command == 'verify':
        from demo_data.package import verify
        from demo_data.policy import private_values
        manifest = verify(args.package, private_values(os.environ))
        print(json.dumps({'status': 'verified', 'tables': len(manifest['tables'])}))
    else:
        from demo_data.importer import initialize
        target = os.environ.get('MOD_DEMO_DATABASE_URL')
        if not target:
            raise ValueError('MOD_DEMO_DATABASE_URL required; source settings are never reused')
        print(json.dumps(initialize(args.package, target, args.apply, args.allow_remote_target, args.bulk_load)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}), file=sys.stderr)
        sys.exit(1)
