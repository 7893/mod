"""Full-table XZ streams split into ordinary Git files; no LFS or external storage."""
from __future__ import annotations

import hashlib
import io
import json
import lzma
import re
from bisect import bisect_right
from pathlib import Path

from .policy import TABLES, ArchiveAudit

SHARD_BYTES = 49_500_000  # Decimal MB; below GitHub's 50 MiB warning threshold.
MAX_SUPPORTED_SHARD_BYTES = 95 * 1024 * 1024  # Read previous local candidates.


class ShardSink:
    """One shared byte container, retaining independent per-table stream offsets."""
    def __init__(self, directory, maximum=SHARD_BYTES):
        self.directory, self.maximum = Path(directory), maximum
        self.files, self.handle, self.used, self.total = [], None, 0, 0

    def write(self, data):
        while data:
            if self.handle is None:
                name = f'simulation.pack.{len(self.files):04d}'
                self.handle = (self.directory / name).open('wb')
                self.files.append(name)
                self.used = 0
            n = min(len(data), self.maximum - self.used)
            self.handle.write(data[:n])
            data = data[n:]
            self.used += n
            self.total += n
            if self.used == self.maximum:
                self.handle.close()
                self.handle = None

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None


def identifier(value):
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', value):
        raise ValueError('Invalid SQL identifier')
    return f'`{value}`'


def create_schema(schema):
    statements = []
    for table in TABLES:
        columns = [r for r in schema['columns'] if r['table_name'] == table]
        if not columns:
            raise ValueError(f'Missing source schema: {table}')
        fields = []
        for r in columns:
            typ = r['column_type']
            if not re.fullmatch(r'(?:tinyint|smallint|int|bigint|float|double|decimal|varchar|char|text|mediumtext|json|datetime|timestamp|date)(?:\([0-9,]+\))?(?: unsigned)?', typ):
                raise ValueError('Unsupported column type')
            field = f"{identifier(r['column_name'])} {typ} " + ('NOT NULL' if r['is_nullable'] == 'NO' else 'NULL')
            extra = r.get('extra', '').lower()
            default = r.get('column_default')
            if default is not None:
                expression = str(default).lower()
                if typ.startswith(('timestamp', 'datetime')) and re.fullmatch(r'current_timestamp(?:\([0-6]?\))?', expression):
                    field += f' DEFAULT {expression}'
                else:
                    literal = str(default).replace('\\', '\\\\').replace("'", "''")
                    field += f" DEFAULT ('{literal}')" if typ in {'json', 'text', 'mediumtext'} else f" DEFAULT '{literal}'"
            if 'auto_increment' in extra:
                field += ' AUTO_INCREMENT'
            update = re.search(r'on update (current_timestamp(?:\([0-6]?\))?)', extra)
            if update:
                field += f' ON UPDATE {update.group(1)}'
            fields.append(field)
        indexes = {}
        for r in schema['indexes']:
            if r['table_name'] == table:
                indexes.setdefault(r['index_name'], []).append(r)
        for i, (name, members) in enumerate(indexes.items()):
            cols = ','.join(identifier(r['column_name']) for r in members)
            if name == 'PRIMARY':
                fields.append(f'PRIMARY KEY ({cols})')
            else:
                unique = 'UNIQUE ' if not members[0]['non_unique'] else ''
                fields.append(f'{unique}KEY demo_idx_{i} ({cols})')
        statements.append(f'CREATE TABLE {identifier(table)} (\n' + ',\n'.join(fields) +
                          '\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')
    return statements


class ShardWriter:
    def __init__(self, directory, table, maximum=SHARD_BYTES):
        self.directory, self.table, self.maximum = Path(directory), table, maximum
        self.compressor = lzma.LZMACompressor(preset=3)
        self.files = []
        self.handle = None
        self.used = 0
        self.raw_bytes = 0
        self.data_hash = hashlib.sha256()

    def _write(self, data):
        while data:
            if self.handle is None:
                name = f'{self.table}.jsonl.xz.{len(self.files):04d}'
                self.handle = (self.directory / name).open('wb')
                self.files.append(name)
                self.used = 0
            n = min(len(data), self.maximum - self.used)
            self.handle.write(data[:n])
            data = data[n:]
            self.used += n
            if self.used == self.maximum:
                self.handle.close()
                self.handle = None

    def row(self, values):
        data = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode() + b'\n'
        self.raw_bytes += len(data)
        self.data_hash.update(data)
        self._write(self.compressor.compress(data))

    def close(self):
        self._write(self.compressor.flush())
        if self.handle:
            self.handle.close()
        return {'parts': self.files, 'raw_bytes': self.raw_bytes,
                'data_sha256': self.data_hash.hexdigest()}


class PartReader(io.RawIOBase):
    def __init__(self, directory, parts, offset=0, length=None):
        self.paths = [Path(directory) / name for name in parts]
        self.ends = [0]
        for path in self.paths:
            self.ends.append(self.ends[-1] + path.stat().st_size)
        self.start, self.length = offset, self.ends[-1] - offset if length is None else length
        if offset < 0 or self.length < 0 or offset + self.length > self.ends[-1]:
            raise ValueError('Invalid container window')
        self.position, self.handle, self.current = 0, None, None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        position = offset + (self.position if whence == io.SEEK_CUR else self.length if whence == io.SEEK_END else 0)
        if whence not in (io.SEEK_SET, io.SEEK_CUR, io.SEEK_END) or not 0 <= position <= self.length:
            raise ValueError('Invalid container seek')
        self.position = position
        return position

    def readinto(self, buffer):
        if self.position == self.length:
            return 0
        absolute = self.start + self.position
        index = bisect_right(self.ends, absolute) - 1
        if index != self.current:
            if self.handle:
                self.handle.close()
            self.handle, self.current = self.paths[index].open('rb'), index
        self.handle.seek(absolute - self.ends[index])
        n = min(len(buffer), self.length - self.position, self.ends[index + 1] - absolute)
        n = self.handle.readinto(memoryview(buffer)[:n])
        self.position += n
        return n

    def close(self):
        if self.handle:
            self.handle.close()
        super().close()


def iter_lines(directory, item):
    if item.get('encoding') == 'parquet-xz':
        from .columnar import iter_values
        for values in iter_values(directory, item):
            yield json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode() + b'\n', values
        return
    with PartReader(directory, item['parts'], item.get('compressed_offset', 0), item.get('compressed_bytes')) as parts:
        with lzma.LZMAFile(io.BufferedReader(parts)) as stream:
            for line in stream:
                values = json.loads(line)
                if len(values) != len(item['columns']):
                    raise ValueError('Invalid row width')
                yield line, values


def iter_rows(directory, item):
    for _, values in iter_lines(directory, item):
        yield dict(zip(item['columns'], values))


def read_manifest(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['format_version'] not in {2, 3} or set(manifest['tables']) != set(TABLES):
        raise ValueError('Unsupported full package inventory')
    expected = {'schema.json'} | {p for v in manifest['tables'].values() for p in v['parts']}
    if set(manifest['files']) != expected:
        raise ValueError('Incomplete file inventory')
    maximum = manifest.get('shard_maximum_bytes', MAX_SUPPORTED_SHARD_BYTES)
    if not isinstance(maximum, int) or not 0 < maximum <= MAX_SUPPORTED_SHARD_BYTES:
        raise ValueError('Invalid declared shard maximum')
    for name, metadata in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('Invalid package path')
        p = directory / name
        if p.stat().st_size != metadata['bytes'] or p.stat().st_size > maximum:
            raise ValueError('Invalid shard size')
        with p.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != metadata['sha256']:
            raise ValueError(f'Checksum mismatch: {name}')
    if manifest['format_version'] == 3:
        parts = manifest['tables'][TABLES[0]]['parts']
        position = 0
        for table in TABLES:
            item = manifest['tables'][table]
            if item['parts'] != parts or item['compressed_offset'] != position or item['compressed_bytes'] <= 0:
                raise ValueError('Invalid shared container inventory')
            if item.get('encoding') != 'parquet-xz':
                raise ValueError('Unsupported columnar encoding')
            position += item['compressed_bytes']
        if position != sum(manifest['files'][name]['bytes'] for name in parts):
            raise ValueError('Shared container extent mismatch')
    return manifest, json.loads((directory / 'schema.json').read_text())


def verify(directory, private_assets=()):
    manifest, _ = read_manifest(directory)
    audit = ArchiveAudit(private_assets)
    audit.check((Path(directory) / 'schema.json').read_bytes())
    audit.check((Path(directory) / 'manifest.json').read_bytes())
    for table, item in manifest['tables'].items():
        count, digest = 0, hashlib.sha256()
        for line, _ in iter_lines(directory, item):
            audit.check(line)
            digest.update(line)
            count += 1
        if count != item['rows'] or digest.hexdigest() != item['data_sha256']:
            raise ValueError(f'Logical data mismatch: {table}')
        print(f'Verified {table}: {count} rows', flush=True)
    return manifest
