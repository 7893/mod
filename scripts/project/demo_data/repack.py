"""Upgrade already exported local records without re-reading a source database."""
import hashlib
import json
import io
import shutil
from pathlib import Path

from .columnar import ColumnWriter, DICT_BYTES
from .package import ShardSink, PartReader, read_manifest, iter_lines, SHARD_BYTES
from .policy import TABLES


def reshard(source, destination):
    """Repartition verified extreme streams without changing compressed bytes."""
    source, destination = Path(source), Path(destination)
    manifest, _ = read_manifest(source)
    if manifest['format_version'] != 3:
        raise ValueError('Reshard requires a shared version 3 container')
    if destination.exists():
        raise ValueError('Output already exists; no files are overwritten')
    previous = manifest['tables'][TABLES[0]]['parts']
    destination.mkdir(parents=True)
    sink, original_hash = ShardSink(destination), hashlib.sha256()
    try:
        for name in previous:
            with (source / name).open('rb') as handle:
                while data := handle.read(1024 * 1024):
                    original_hash.update(data)
                    sink.write(data)
    finally:
        sink.close()
    with PartReader(destination, sink.files) as reader:
        copied_hash = hashlib.file_digest(io.BufferedReader(reader), 'sha256').hexdigest()
    if copied_hash != original_hash.hexdigest():
        raise ValueError('Reshard changed compressed container bytes')
    for item in manifest['tables'].values():
        item['parts'] = sink.files
    shutil.copyfile(source / 'schema.json', destination / 'schema.json')
    manifest['files'] = {}
    for path in destination.iterdir():
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        manifest['files'][path.name] = {'bytes': path.stat().st_size, 'sha256': digest}
    manifest['shard_maximum_bytes'] = SHARD_BYTES
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    read_manifest(destination)
    print(json.dumps({'status': 'resharded', 'parts': len(sink.files),
                      'maximum_bytes': SHARD_BYTES, 'container_sha256': copied_hash,
                      'rows': sum(t['rows'] for t in manifest['tables'].values())}))


def repack(source, destination):
    source, destination = Path(source), Path(destination)
    manifest, schema = read_manifest(source)
    if destination.exists():
        raise ValueError('Output already exists; no files are overwritten')
    destination.mkdir(parents=True)
    sink = ShardSink(destination)
    tables = {}
    for table in TABLES:
        previous = manifest['tables'][table]
        columns = [c for c in schema['columns'] if c['table_name'] == table]
        writer, count = ColumnWriter(columns, sink), 0
        for _, values in iter_lines(source, previous):
            writer.row(values)
            count += 1
            if count % 500000 == 0:
                print(f'Encoding {table}: {count}/{previous["rows"]}', flush=True)
        print(f'Extreme compression {table}: {count} rows', flush=True)
        item = writer.close()
        if count != previous['rows'] or item['data_sha256'] != previous['data_sha256']:
            raise ValueError(f'Repack changed data: {table}')
        tables[table] = {**item, 'columns': previous['columns'], 'rows': count}
        print(f'Packed {table}: {item["compressed_bytes"]} bytes', flush=True)
    sink.close()
    manifest.update(format_version=3, tables=tables, files={}, shard_maximum_bytes=SHARD_BYTES,
                    compression={'columnar': 'parquet_delta', 'codec': 'xz', 'preset': '9e',
                                 'dictionary_bytes': DICT_BYTES, 'nice_length': 273})
    (destination / 'schema.json').write_text(json.dumps(schema, sort_keys=True, indent=2) + '\n')
    for path in destination.iterdir():
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        manifest['files'][path.name] = {'bytes': path.stat().st_size, 'sha256': digest}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': 'repacked', 'rows': sum(t['rows'] for t in tables.values()),
                      'compressed_bytes': sum(f['bytes'] for f in manifest['files'].values()),
                      'parts': len(manifest['files']) - 1}))
