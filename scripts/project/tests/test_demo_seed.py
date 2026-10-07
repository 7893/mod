"""Full-seed regression tests: preserve simulation data and redact infrastructure."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_data.package import ShardWriter, ShardSink, PartReader, iter_rows, read_manifest, create_schema
from demo_data.policy import Sanitizer, TABLES, ArchiveAudit


class DemoSeedTests(unittest.TestCase):
    def test_shared_container_windows_seek_across_arbitrary_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = ShardSink(directory, maximum=7)
            sink.write(b'header-FIRST-SECOND-trailer')
            sink.close()
            with PartReader(directory, sink.files, offset=7, length=12) as reader:
                self.assertEqual(reader.read(), b'FIRST-SECOND')
                reader.seek(-6, 2)
                self.assertEqual(reader.read(), b'SECOND')
                with self.assertRaises(ValueError):
                    reader.seek(13)

    @unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'demo optional dependency is required')
    def test_extreme_columnar_shared_frames_preserve_full_scalar_values(self):
        from demo_data.columnar import ColumnWriter
        schema = [{'column_name': n, 'column_type': t} for n, t in [
            ('id', 'bigint unsigned'), ('amount', 'decimal(15,4)'),
            ('value', 'double'), ('body', 'json')]]
        expected = [[0, '-0.0000', -0.0, '{"name":"李华","text":"\\t"}'],
                    [(1 << 64) - 1, '123456.7890', 0.831234567891, None]]
        with tempfile.TemporaryDirectory() as directory:
            sink = ShardSink(directory, maximum=31)
            items = []
            for rows in [expected, []]:
                writer = ColumnWriter(schema, sink, group_rows=1, dictionary_bytes=4 * 1024 * 1024, preset=0)
                for row in rows:
                    writer.row(row)
                item = writer.close()
                item['columns'] = [c['column_name'] for c in schema]
                items.append(item)
            sink.close()
            actual = list(iter_rows(directory, items[0]))
            self.assertEqual(actual, [dict(zip(items[0]['columns'], row)) for row in expected])
            self.assertEqual(json.dumps(actual[0]['value']), '-0.0')
            self.assertEqual(list(iter_rows(directory, items[1])), [])

    def test_schema_preserves_timestamp_defaults_and_auto_increment(self):
        columns = []
        for table in TABLES:
            columns.extend([
                {'table_name': table, 'column_name': 'id', 'column_type': 'bigint',
                 'is_nullable': 'NO', 'extra': 'auto_increment'},
                {'table_name': table, 'column_name': 'updated_at', 'column_type': 'timestamp',
                 'is_nullable': 'NO', 'column_default': 'CURRENT_TIMESTAMP',
                 'extra': 'DEFAULT_GENERATED on update CURRENT_TIMESTAMP'},
                {'table_name': table, 'column_name': 'label', 'column_type': 'varchar(50)',
                 'is_nullable': 'YES', 'column_default': "模拟'文字"}])
        statements = create_schema({'columns': columns, 'indexes': []})
        self.assertIn('AUTO_INCREMENT', statements[0])
        self.assertIn('DEFAULT current_timestamp ON UPDATE current_timestamp', statements[0])
        self.assertIn("DEFAULT '模拟''文字'", statements[0])

    def test_simulation_identity_amount_date_and_narrative_are_preserved(self):
        sanitizer = Sanitizer()
        for value in ['紫禁能源有限公司', '张明', '费用报销单', '正式业务·拟真审批链',
                      '培训已完成，等待双轨核对。', 12345, None]:
            self.assertEqual(sanitizer.value(value), value)
        self.assertEqual(sanitizer.value(Decimal('23.45')), '23.45')
        self.assertEqual(sanitizer.value(datetime(2027, 2, 28)), '2027-02-28 00:00:00')

    def test_exact_secret_and_host_path_are_removed(self):
        secret = 'fixture-secret-0123456789'  # pragma: allowlist secret (synthetic fixture)
        sanitizer = Sanitizer([secret])
        result = sanitizer.value(f'error {secret} in /home/operator/app/file.py')
        self.assertNotIn(secret, result)
        self.assertNotIn('/home/operator', result)
        self.assertEqual(sanitizer.replacements, 1)

    def test_json_is_valid_after_nested_environment_redaction(self):
        source = json.dumps({'error': 'in /srv/app/test.py', 'probabilities': {'1': 0.83},
                             'people': ['李华']})
        result = json.loads(Sanitizer().value(source))
        self.assertEqual(result['people'], ['李华'])
        self.assertEqual(result['probabilities'], {'1': 0.83})
        self.assertNotIn('/srv/', result['error'])

    def test_unknown_token_is_removed_without_private_inventory(self):
        token = 'ghp_' + 'A' * 36
        self.assertNotIn(token, Sanitizer().value(token))
        address = ':'.join(['fd00', '1', '2', '3', '4', '5', '6', '7'])
        self.assertEqual(Sanitizer().value(address), '[ip]')

    def test_decoded_archive_audit_rejects_hidden_environment_values(self):
        audit = ArchiveAudit(['fixture-secret-0123456789'])
        audit.check(json.dumps(['张明', 23.45, '2027-02-28 00:00:00']).encode())
        addresses = [':'.join(['fd00', '1', '2', '3', '4', '5', '6', '7']),
                     '.'.join(str(n) for n in range(10, 14))]
        for value in ['fixture-secret-0123456789', '/home/operator/app',
                      *addresses, 'ghp_' + 'A' * 36]:
            with self.assertRaises(ValueError):
                audit.check(json.dumps([value]).encode())

    def test_non_boundary_shards_restore_all_rows_and_nulls(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ShardWriter(directory, 'test_doc', maximum=31)
            expected = [[i, None, '模拟数据' * i] for i in range(12)]
            for row in expected:
                writer.row(row)
            item = writer.close()
            item['columns'] = ['id', 'nullable', 'content']
            self.assertGreater(len(item['parts']), 1)
            self.assertTrue(all((Path(directory) / name).stat().st_size <= 31 for name in item['parts']))
            actual = list(iter_rows(directory, item))
            self.assertEqual(actual, [dict(zip(item['columns'], r)) for r in expected])

    def test_missing_shard_or_modified_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'schema.json').write_text('{}')
            metadata = {'bytes': 2, 'sha256': hashlib.sha256(b'{}').hexdigest()}
            manifest = {'format_version': 2, 'tables': {t: {'parts': []} for t in TABLES},
                        'files': {'schema.json': metadata}}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            read_manifest(root)
            (root / 'schema.json').write_text('[]')
            with self.assertRaisesRegex(ValueError, 'Checksum'):
                read_manifest(root)


if __name__ == '__main__':
    unittest.main()
