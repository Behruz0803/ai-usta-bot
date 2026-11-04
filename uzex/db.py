# -*- coding: utf-8 -*-
"""
DB helper: get connection, execute safe SELECT queries
"""
import gzip
import os
import sqlite3
import pathlib
import re
import time

DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "uzex.db"
BUNDLE_GZ = pathlib.Path(__file__).resolve().parent.parent / "data" / "uzex.db.gz"
# Vercel/serverless can only write to /tmp
RUNTIME_DB = pathlib.Path("/tmp/uzex.db")
ALT_DB2 = pathlib.Path("./uzex.db")
MIN_DB_BYTES = 5_000_000

def _valid_sqlite(path: pathlib.Path) -> bool:
    try:
        if not path.exists() or path.stat().st_size < MIN_DB_BYTES:
            return False
        with open(path, "rb") as f:
            return f.read(16).startswith(b"SQLite format 3")
    except OSError:
        return False

def _candidate_paths():
    return [DB_PATH, pathlib.Path("data/uzex.db"), RUNTIME_DB, ALT_DB2]

def db_is_ready() -> bool:
    return any(_valid_sqlite(p) for p in _candidate_paths())

def _bundled_gz() -> pathlib.Path | None:
    for p in [BUNDLE_GZ, pathlib.Path("data/uzex.db.gz"), pathlib.Path("/var/task/data/uzex.db.gz")]:
        if p.exists() and p.stat().st_size > 1_000_000:
            return p
    return None

def _gunzip_to(src: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    part = dest.with_suffix(dest.suffix + ".part")
    print(f"UZEX DB ochilmoqda: {src} ({src.stat().st_size/1024/1024:.1f} MB gz) -> {dest}")
    t0 = time.time()
    with gzip.open(src, "rb") as inp, open(part, "wb") as out:
        while True:
            chunk = inp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    if not _valid_sqlite(part):
        part.unlink(missing_ok=True)
        raise RuntimeError("Ochilgan fayl SQLite emas")
    part.replace(dest)
    print(f"UZEX DB tayyor: {dest.stat().st_size/1024/1024:.1f} MB, {time.time()-t0:.1f}s")
    return dest

def ensure_db() -> pathlib.Path:
    """Return a readable SQLite path. On Vercel, unpack bundled uzex.db.gz into /tmp."""
    for p in _candidate_paths():
        if _valid_sqlite(p):
            return p
    gz = _bundled_gz()
    if gz is not None:
        return _gunzip_to(gz, RUNTIME_DB)
    url = os.getenv("UZEX_DB_URL", "").strip()
    if url:
        import urllib.request
        gz_part = pathlib.Path("/tmp/uzex.db.gz.part")
        gz_path = pathlib.Path("/tmp/uzex.db.gz")
        print(f"UZEX DB yuklanmoqda: {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "uzex-ai-agent"})
        with urllib.request.urlopen(req, timeout=45) as resp, open(gz_part, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        gz_part.replace(gz_path)
        return _gunzip_to(gz_path, RUNTIME_DB)
    raise FileNotFoundError(
        "UZEX bazasi topilmadi. Lokal: python -m uzex.etl --src /tmp/uzex_spot_data --db ./data/uzex.db"
    )

def get_db_path():
    return ensure_db()

def get_connection(read_only=True):
    db_path = ensure_db()
    if read_only:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA query_only=ON;" if read_only else "PRAGMA query_only=OFF;")
    conn.row_factory = sqlite3.Row
    return conn

# Whitelist for SQL validation
ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
FORBIDDEN_KEYWORDS = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|reindex)\b", re.IGNORECASE)

def is_safe_select(sql: str) -> tuple[bool, str]:
    """Validate that SQL is safe read-only SELECT/WITH"""
    if not sql or not isinstance(sql, str):
        return False, "Empty SQL"
    s = sql.strip()
    if not s:
        return False, "Empty SQL"
    # Must start with SELECT or WITH
    if not ALLOWED_START.match(s):
        return False, "Only SELECT/WITH queries allowed (must start with SELECT)"
    # No forbidden keywords
    # Allow CREATE inside WITH? But forbid overall
    # We check for dangerous statements beyond SELECT
    # Remove string literals to avoid false positives? Simple check:
    # Forbid multiple statements with ;
    # Allow trailing semicolon but not multiple statements
    # Count semicolons not inside quotes
    # Simple: if sql contains ';' not at end, reject
    # But we allow one trailing semicolon
    # Let's implement simple parser: split by ';' and check non-empty parts
    parts = [p.strip() for p in s.split(";") if p.strip()]
    if len(parts) > 1:
        return False, "Multiple statements not allowed (remove extra ';')"
    if FORBIDDEN_KEYWORDS.search(s):
        # Allow if it's inside product_name? But keyword check is strict
        # We need to ensure we don't block legitimate WHERE clauses containing these words as data
        # However these keywords as standalone should not appear in SELECT except maybe column names
        # Safer to check for statement-level keywords at start: INSERT etc.
        # Already checked start, so now check for embedded dangerous: e.g., "; DELETE"
        # Since we already block multiple statements, this check is for injection like "SELECT * FROM deals; DROP TABLE"
        # So if keyword appears, we block
        return False, f"Forbidden keyword detected: {FORBIDDEN_KEYWORDS.search(s).group(0)}"
    return True, "OK"

def execute_sql(sql: str, params=None, limit: int = 100):
    """Execute SQL and return rows, column names, rowcount, error"""
    safe, msg = is_safe_select(sql)
    if not safe:
        return None, None, 0, msg

    # Enforce LIMIT if not present for non-aggregation queries to prevent huge results
    # Heuristic: if no LIMIT and not aggregation (COUNT,SUM,AVG etc without GROUP BY?), we will add LIMIT
    # But we leave to LLM to include LIMIT; we just cap results to `limit` rows in Python
    conn = get_connection(read_only=True)
    try:
        cur = conn.cursor()
        # Set timeout 5 seconds
        cur.execute(f"PRAGMA busy_timeout=5000;")
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchmany(limit + 1)  # fetch one extra to detect truncation
        truncated = len(rows) > limit
        if truncated:
            rows = rows[:limit]
        columns = [desc[0] for desc in cur.description] if cur.description else []
        # Also get total count if truncated? We can just note truncated
        return rows, columns, len(rows), None if not truncated else f"Results truncated to {limit} rows (add LIMIT or aggregation)"
    except sqlite3.Error as e:
        return None, None, 0, f"SQLite error: {e}"
    finally:
        conn.close()

def get_schema_summary():
    """Return quick schema stats for debugging"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM deals;")
        deals = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM contracts;")
        contracts = cur.fetchone()[0]
        conn.close()
        return f"deals={deals}, contracts={contracts}"
    except Exception as e:
        return f"DB error: {e}"
