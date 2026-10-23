"""SQLite memory for Jarvis: flip deals, website leads, experiments, and lessons learned."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "JARVIS_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jarvis.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    asking_price REAL,
    est_resale REAL,
    status TEXT DEFAULT 'watching',      -- watching, messaged, bought, listed, sold, passed
    bought_price REAL,
    sold_price REAL,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY,
    place_id TEXT UNIQUE,
    name TEXT NOT NULL,
    niche TEXT,
    address TEXT,
    phone TEXT,
    rating REAL,
    review_count INTEGER,
    maps_url TEXT,
    status TEXT DEFAULT 'new',           -- new, site_built, contacted, replied, won, lost
    site_path TEXT,
    touches INTEGER DEFAULT 0,
    last_contacted TEXT,
    next_followup TEXT,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY,
    area TEXT NOT NULL,                  -- shopify, flips, websites, youtube, products
    hypothesis TEXT NOT NULL,
    action TEXT,
    status TEXT DEFAULT 'running',       -- running, worked, failed
    result TEXT,
    created_at TEXT,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY,
    lane TEXT NOT NULL,                  -- flips, websites, shopify, youtube
    amount REAL NOT NULL DEFAULT 0,      -- profit in dollars (0 if you only logged time)
    hours REAL NOT NULL DEFAULT 0,
    recurring_monthly REAL NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY,
    area TEXT NOT NULL,
    lesson TEXT NOT NULL,
    experiment_id INTEGER,
    created_at TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn) -> None:
    """Add columns introduced after a database was first created."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(leads)")}
    for col, decl in (("touches", "INTEGER DEFAULT 0"), ("last_contacted", "TEXT"), ("next_followup", "TEXT")):
        if col not in have:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {decl}")


def rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def recent_lessons(limit: int = 30) -> list[dict]:
    with connect() as conn:
        return rows(
            conn.execute(
                "SELECT area, lesson, created_at FROM lessons ORDER BY id DESC LIMIT ?", (limit,)
            )
        )


def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def lane_stats(days: int = 30) -> list[dict]:
    """Profit, hours and dollars per hour for each lane over the last `days` days."""
    with connect() as conn:
        out = rows(conn.execute(
            "SELECT lane, ROUND(SUM(amount), 2) AS profit, ROUND(SUM(hours), 1) AS hours, "
            "ROUND(SUM(recurring_monthly), 2) AS new_recurring_monthly FROM income "
            "WHERE datetime(created_at) >= datetime('now', ?) GROUP BY lane",
            (f"-{int(days)} days",),
        ))
    for r in out:
        r["per_hour"] = round(r["profit"] / r["hours"], 2) if r["hours"] else None
    return sorted(out, key=lambda r: r["per_hour"] or 0, reverse=True)


def scoreboard() -> dict:
    """Quick totals used in the system prompt so Jarvis knows where things stand."""
    with connect() as conn:
        month = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM income WHERE datetime(created_at) >= datetime('now', 'start of month')"
        ).fetchone()[0]
        recurring = conn.execute("SELECT COALESCE(SUM(recurring_monthly), 0) FROM income").fetchone()[0]
        leads = rows(conn.execute("SELECT status, COUNT(*) AS n FROM leads GROUP BY status"))
        followups = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE next_followup <= ? AND status IN ('contacted', 'site_built')",
            (now(),),
        ).fetchone()[0]
        running = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE status = 'running'"
        ).fetchone()[0]
    goal = get_setting("monthly_goal")
    return {
        "monthly_goal": float(goal) if goal else None,
        "profit_this_month": round(month, 2),
        "recurring_monthly_revenue": round(recurring, 2),
        "lanes_last_30_days": lane_stats(30),
        "leads_by_status": {r["status"]: r["n"] for r in leads},
        "followups_due": followups,
        "running_experiments": running,
    }
