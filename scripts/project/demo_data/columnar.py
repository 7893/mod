"""Lossless column encoding followed by XZ's extreme preset; bounded temporary files."""
from __future__ import annotations

import hashlib
import io
import json
import lzma
import shutil
import tempfile

DICT_BYTES = 512 * 1024 * 1024
GROUP_ROWS = 500000


def arrow_schema(columns):
    import pyarrow as pa
    fields = []
    for column in columns:
        typ = column['column_type']
        if typ.startswith(('tinyint', 'smallint', 'int', 'bigint')):
            arrow_type = pa.uint64() if 'unsigned' in typ else pa.int64()
        elif typ.startswith(('float', 'double')):
            arrow_type = pa.float64()
        else:
            # Decimal lexemes and all date/JSON/text values stay exact strings.
            arrow_type = pa.string()
        fields.append(pa.field(column['column_name'], arrow_type))
    return pa.schema(fields)


class ColumnWriter:
    def __init__(self, columns, sink, group_rows=GROUP_ROWS, dictionary_bytes=DICT_BYTES, preset=9 | lzma.PRESET_EXTREME):
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.schema, self.sink, self.group_rows = arrow_schema(columns), sink, group_rows
        self.dictionary_bytes, self.preset = dictionary_bytes, preset
        encoding = {}
        for field in self.schema:
            if pa.types.is_integer(field.type):
                encoding[field.name] = 'DELTA_BINARY_PACKED'
            elif pa.types.is_floating(field.type):
                encoding[field.name] = 'BYTE_STREAM_SPLIT'
            else:
                encoding[field.name] = 'DELTA_BYTE_ARRAY'
        self.handle = tempfile.TemporaryFile()
        self.writer = pq.ParquetWriter(self.handle, self.schema, compression='none',
                                       use_dictionary=False, column_encoding=encoding,
                                       write_statistics=False, write_page_checksum=True)
        self.buffer, self.raw_bytes = [], 0
        self.data_hash = hashlib.sha256()

    def row(self, values):
        data = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode() + b'\n'
        self.raw_bytes += len(data)
        self.data_hash.update(data)
        self.buffer.append(values)
        if len(self.buffer) >= self.group_rows:
            self._flush()

    def _flush(self):
        import pyarrow as pa
        if self.buffer:
            arrays = [pa.array([row[i] for row in self.buffer], type=field.type)
                      for i, field in enumerate(self.schema)]
            self.writer.write_table(pa.Table.from_arrays(arrays, schema=self.schema), row_group_size=self.group_rows)
            self.buffer.clear()

    def close(self):
        self._flush()
        self.writer.close()
        columnar_bytes = self.handle.tell()
        self.handle.seek(0)
        offset = self.sink.total
        compressor = lzma.LZMACompressor(filters=[{
            'id': lzma.FILTER_LZMA2, 'preset': self.preset,
            'dict_size': self.dictionary_bytes, 'nice_len': 273}])
        try:
            while data := self.handle.read(1024 * 1024):
                self.sink.write(compressor.compress(data))
            self.sink.write(compressor.flush())
        finally:
            self.handle.close()
        return {'encoding': 'parquet-xz', 'parts': self.sink.files,
                'compressed_offset': offset, 'compressed_bytes': self.sink.total - offset,
                'columnar_bytes': columnar_bytes, 'raw_bytes': self.raw_bytes,
                'data_sha256': self.data_hash.hexdigest()}


def iter_values(directory, item):
    import pyarrow.parquet as pq
    from .package import PartReader
    with tempfile.TemporaryFile() as decoded:
        with PartReader(directory, item['parts'], item['compressed_offset'], item['compressed_bytes']) as parts:
            with lzma.LZMAFile(io.BufferedReader(parts)) as stream:
                shutil.copyfileobj(stream, decoded, length=1024 * 1024)
        decoded.seek(0)
        parquet = pq.ParquetFile(decoded, page_checksum_verification=True)
        if parquet.schema_arrow.names != item['columns']:
            raise ValueError('Columnar field inventory mismatch')
        if set(parquet.metadata.metadata or {}) - {b'ARROW:schema'}:
            raise ValueError('Unexpected columnar metadata')
        if parquet.schema_arrow.metadata or any(field.metadata for field in parquet.schema_arrow):
            raise ValueError('Unexpected columnar schema annotations')
        for i in range(parquet.metadata.num_row_groups):
            for j in range(parquet.metadata.num_columns):
                if parquet.metadata.row_group(i).column(j).file_path:
                    raise ValueError('External columnar file reference is forbidden')
        for batch in parquet.iter_batches(batch_size=20000):
            columns = [column.to_pylist() for column in batch.columns]
            yield from map(list, zip(*columns))
