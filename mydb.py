import re
import urllib.parse

import pandas as pd
import pyodbc
from sqlalchemy import create_engine, text

SERVER = r"DELL\SQLEXPRESS"
DRIVER = "{ODBC Driver 17 for SQL Server}"

_engines = {}


def _build_conn_str(database):
    return (
        f"DRIVER={DRIVER};"
        f"SERVER={SERVER};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes;"
    )


def get_connection(database):
    return pyodbc.connect(_build_conn_str(database))


def get_engine(database):
    if database not in _engines:
        params = urllib.parse.quote_plus(_build_conn_str(database))
        _engines[database] = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    return _engines[database]


def clean_sql(query):
    """Strips markdown code fences (```sql ... ```) that LLMs often wrap SQL in."""
    query = query.strip()
    query = re.sub(r"^```(?:sql)?\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s*```$", "", query)
    return query.strip()


class UnsafeQueryError(ValueError):
    pass


_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "MERGE",
    "EXEC", "EXECUTE", "CREATE", "GRANT", "REVOKE", "sp_", "xp_",
)


def validate_select_only(query):
    """Raises UnsafeQueryError unless query is a single SELECT/WITH statement."""
    stripped = query.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeQueryError("Empty query.")
    if ";" in stripped:
        raise UnsafeQueryError("Multiple statements are not allowed.")

    first_word_match = re.match(r"^\s*(\w+)", stripped)
    first_word = first_word_match.group(1).upper() if first_word_match else ""
    if first_word not in ("SELECT", "WITH"):
        raise UnsafeQueryError(f"Only SELECT queries are allowed (got '{first_word}').")

    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", stripped, re.IGNORECASE):
            raise UnsafeQueryError(f"Forbidden keyword detected: {keyword}")

    return stripped


def execute_query(query, database):
    safe_query = validate_select_only(clean_sql(query))
    with get_engine(database).connect() as conn:
        return pd.read_sql(text(safe_query), conn)


def list_databases():
    conn = get_connection("master")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sys.databases WHERE database_id > 4 AND state = 0 ORDER BY name"
    )
    names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return names


def list_tables(database):
    conn = get_connection(database)
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 5 * FROM information_schema.tables")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_columns(database):
    query = """
        SELECT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.IS_NULLABLE,
            c.CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
            ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
    """
    return execute_query(query, database)


def get_relationships(database):
    query = """
        SELECT
            fk.name AS foreign_key_name,
            tp.name AS parent_table,
            cp.name AS parent_column,
            tr.name AS referenced_table,
            cr.name AS referenced_column
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
        JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
        JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
        JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
        ORDER BY tp.name
    """
    return execute_query(query, database)


def get_schema_summary(database):
    """Formats columns + relationships as readable text, e.g. for an LLM prompt."""
    columns = get_columns(database)
    relationships = get_relationships(database)

    lines = []
    for table_name, group in columns.groupby("TABLE_NAME"):
        lines.append(f"Table: {table_name}")
        for _, col in group.iterrows():
            nullable = "NULL" if col["IS_NULLABLE"] == "YES" else "NOT NULL"
            lines.append(f"  - {col['COLUMN_NAME']} ({col['DATA_TYPE']}, {nullable})")
        lines.append("")

    if not relationships.empty:
        lines.append("Relationships:")
        for _, rel in relationships.iterrows():
            lines.append(
                f"  - {rel['parent_table']}.{rel['parent_column']} -> "
                f"{rel['referenced_table']}.{rel['referenced_column']}"
            )

    return "\n".join(lines)


if __name__ == "__main__":
    db_name = input("Enter database name: ")
    for row in list_tables(db_name):
        print(row)