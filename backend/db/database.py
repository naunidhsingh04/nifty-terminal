"""
Database layer using:
- Python built-in sqlite3 for local development
- Turso HTTP API for production (no binary dependencies needed)
"""
import os
import json
import sqlite3
import aiohttp

TURSO_URL   = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")
IS_TURSO    = bool(TURSO_URL and TURSO_TOKEN)

_local_conn = None  # local sqlite3 connection

# ── Turso HTTP API wrapper ─────────────────────────────────────────────────────
async def _turso_execute(sql: str, params: tuple = ()):
    """Execute a single statement on Turso via HTTP API."""
    # Convert libsql:// to https:// for HTTP API calls
    base = TURSO_URL.replace("libsql://", "https://")
    url = f"{base}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json",
    }
    # Convert params to Turso format
    args = []
    for p in params:
        if p is None:
            args.append({"type": "null"})
        elif isinstance(p, int):
            args.append({"type": "integer", "value": str(p)})
        elif isinstance(p, float):
            args.append({"type": "float", "value": str(p)})
        else:
            args.append({"type": "text", "value": str(p)})

    body = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": args}},
            {"type": "close"},
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers) as resp:
            data = await resp.json()
            return data

async def _turso_query(sql: str, params: tuple = ()):
    """Execute a query and return rows."""
    data = await _turso_execute(sql, params)
    try:
        result = data["results"][0]["response"]["result"]
        cols   = [c["name"] for c in result["cols"]]
        rows   = []
        for row in result["rows"]:
            rows.append(tuple(
                v.get("value") if v.get("type") != "null" else None
                for v in row
            ))
        return rows
    except Exception:
        return []

async def _turso_run(sql: str, params: tuple = ()):
    """Execute a write statement on Turso."""
    await _turso_execute(sql, params)

async def _turso_script(sql: str):
    """Run multiple statements separated by semicolons."""
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    base = TURSO_URL.replace("libsql://", "https://")
    url = f"{base}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json",
    }
    requests = []
    for stmt in statements:
        requests.append({"type": "execute", "stmt": {"sql": stmt}})
    requests.append({"type": "close"})

    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"requests": requests}, headers=headers)

# ── DB interface — same API for both local and Turso ──────────────────────────
class DB:
    """Unified interface — wraps sqlite3 locally, Turso HTTP in production."""

    def execute(self, sql: str, params: tuple = ()):
        """Sync execute for local sqlite3."""
        if IS_TURSO:
            raise RuntimeError("Use async methods for Turso")
        return _local_conn.execute(sql, params)

    def executescript(self, sql: str):
        if IS_TURSO:
            raise RuntimeError("Use async methods for Turso")
        _local_conn.executescript(sql)

    def commit(self):
        if not IS_TURSO:
            _local_conn.commit()

    async def aexecute(self, sql: str, params: tuple = ()):
        """Async execute — works for both local and Turso."""
        if IS_TURSO:
            await _turso_run(sql, params)
        else:
            _local_conn.execute(sql, params)
            _local_conn.commit()

    async def afetchall(self, sql: str, params: tuple = ()):
        """Async fetch rows — works for both local and Turso."""
        if IS_TURSO:
            return await _turso_query(sql, params)
        else:
            return _local_conn.execute(sql, params).fetchall()

    async def afetchone(self, sql: str, params: tuple = ()):
        """Async fetch single row."""
        rows = await self.afetchall(sql, params)
        return rows[0] if rows else None

_db = DB()

def get_db() -> DB:
    return _db

async def connect():
    global _local_conn
    if IS_TURSO:
        print(f"✅ Turso connected → {TURSO_URL}")
    else:
        _local_conn = sqlite3.connect("nifty_terminal.db", check_same_thread=False)
        _local_conn.row_factory = sqlite3.Row
        print("✅ SQLite connected → nifty_terminal.db")

    await create_tables()

async def disconnect():
    if not IS_TURSO and _local_conn:
        _local_conn.close()

async def create_tables():
    schema = """
        CREATE TABLE IF NOT EXISTS candles (
            symbol   TEXT    NOT NULL,
            interval TEXT    NOT NULL,
            time     INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (symbol, interval, time)
        );
        CREATE INDEX IF NOT EXISTS idx_candles_lookup
            ON candles (symbol, interval, time);
        CREATE TABLE IF NOT EXISTS rsi_states (
            symbol              TEXT PRIMARY KEY,
            closes              TEXT NOT NULL DEFAULT '[]',
            bucket              INTEGER NOT NULL DEFAULT 0,
            open                REAL NOT NULL DEFAULT 0,
            high                REAL NOT NULL DEFAULT 0,
            low                 REAL NOT NULL DEFAULT 0,
            close               REAL NOT NULL DEFAULT 0,
            consecutive_below30 INTEGER NOT NULL DEFAULT 0,
            qualified           INTEGER NOT NULL DEFAULT 0,
            alert_fired         INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ticks (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol  TEXT NOT NULL,
            time    INTEGER NOT NULL,
            price   REAL NOT NULL,
            volume  INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_ticks_lookup
            ON ticks (symbol, time)
    """
    if IS_TURSO:
        await _turso_script(schema)
    else:
        _local_conn.executescript(schema)
        _local_conn.commit()
    print("✅ Tables ready")