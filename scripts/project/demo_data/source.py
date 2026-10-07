"""Schema metadata and keyset SELECTs through the shared read-only boundary."""
from sqlalchemy import text


def select(conn, sql, params=None):
    if not sql.lstrip().upper().startswith('SELECT ') or ';' in sql:
        raise ValueError('Only a single SELECT is permitted')
    return [dict(row) for row in conn.execute(text(sql), params or {}).mappings()]


def describe(conn):
    queries = {
        'columns': 'SELECT table_name,column_name,column_type,is_nullable,column_key,extra,column_default '
                   'FROM information_schema.columns WHERE table_schema=DATABASE() '
                   'ORDER BY table_name,ordinal_position',
        'foreign_keys': 'SELECT table_name,column_name,referenced_table_name,referenced_column_name '
                        'FROM information_schema.key_column_usage WHERE table_schema=DATABASE() '
                        'AND referenced_table_name IS NOT NULL',
        'indexes': 'SELECT table_name,index_name,column_name,seq_in_index,non_unique '
                   'FROM information_schema.statistics WHERE table_schema=DATABASE() '
                   'ORDER BY table_name,index_name,seq_in_index',
    }
    return {name: [{k.lower(): v for k, v in row.items()} for row in select(conn, sql)]
            for name, sql in queries.items()}


def batches(conn, table, columns, primary, size=20000):
    from .package import identifier
    last = None
    while True:
        where = ''
        params = {}
        if last is not None:
            lhs = '(' + ','.join(identifier(c) for c in primary) + ')'
            rhs = '(' + ','.join(f':p{i}' for i in range(len(primary))) + ')'
            where = f' WHERE {lhs} > {rhs}'
            params = {f'p{i}': v for i, v in enumerate(last)}
        sql = ('SELECT ' + ','.join(identifier(c) for c in columns) + f' FROM {identifier(table)}' +
               where + ' ORDER BY ' + ','.join(identifier(c) for c in primary) + f' LIMIT {int(size)}')
        chunk = select(conn, sql, params)
        if not chunk:
            return
        yield chunk
        last = tuple(chunk[-1][c] for c in primary)
