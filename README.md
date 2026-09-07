# DataIQ

Ask a SQL Server database questions in plain English. An LLM (GPT-4.1-mini)
translates the question into a T-SQL `SELECT` statement using the database's
schema, runs it, and returns the result as a table.

Two interfaces share the same backend:
- **`main.py`** — command-line prompt (enter database name, then a question).
- **`app.py`** — Streamlit web UI with a database picker and results table.

## How it works

1. `mydb.get_schema_summary(db_name)` reads `INFORMATION_SCHEMA` and
   `sys.foreign_keys` to build a text summary of every table's columns and
   relationships.
2. That summary plus the user's question are sent to `gpt-4.1-mini`, which is
   instructed to return a single raw T-SQL `SELECT` statement (no markdown,
   no explanation).
3. `mydb.execute_query()` strips any markdown fences, **validates that the
   query is a single, non-destructive `SELECT`/`WITH` statement**, and runs
   it via SQLAlchemy against SQL Server, returning a pandas DataFrame.

## Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point |
| `app.py` | Streamlit UI entry point |
| `mydb.py` | DB connection, schema introspection, query validation and execution |
| `.env` | Local secrets (not committed) |

## Setup

**Prerequisites:** Python 3.10+, a running SQL Server instance (default
config targets `DELL\SQLEXPRESS` via Windows auth — edit `SERVER` in
`mydb.py` if yours differs), and the "ODBC Driver 17 for SQL Server" installed.

```bash
pip install openai python-dotenv pandas pyodbc sqlalchemy streamlit
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
```

## Usage

CLI:
```bash
python main.py
```
Prompts for a database name, then a question, then prints the query result.

Web UI:
```bash
streamlit run app.py
```
Pick a database from the sidebar, type a question, click **Run**.

## Security: read-only by design

Users cannot use this tool to modify data. `execute_query()` in `mydb.py`
rejects any generated SQL that:
- is not a single `SELECT` or `WITH` (CTE) statement,
- contains more than one statement (`;`-separated),
- contains a data-modifying or admin keyword (`INSERT`, `UPDATE`, `DELETE`,
  `DROP`, `ALTER`, `TRUNCATE`, `MERGE`, `EXEC`/`EXECUTE`, `CREATE`, `GRANT`,
  `REVOKE`, `sp_`, `xp_`).

The system prompt also explicitly instructs the model to only ever produce
a `SELECT`. This is a secondary layer, not the enforcement — the LLM's
output is never trusted on its own.

**Recommended hardening (not yet applied):** the app currently connects
using Windows Trusted Authentication, which likely has write access to the
database. For a true defense-in-depth guarantee, create a SQL Server login
scoped to `db_datareader` only on each target database, and point
`_build_conn_str` in `mydb.py` at that login instead. That way, even a bug
in the validation logic above can't result in a write — SQL Server itself
would refuse it.

## Known limitations

- Single-statement validation is regex-based; treat it as a safety net, not
  a formal SQL parser.
- Schema summary is rebuilt per database selection; large schemas will
  produce a large prompt (and cost/latency) per question.
- No conversation history — each question is independent.
