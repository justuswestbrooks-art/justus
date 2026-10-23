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
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def recent_lessons(limit: int = 30) -> list[dict]:
    with connect() as conn:
        return rows(
            conn.execute(
                "SELECT area, lesson, created_at FROM lessons ORDER BY id DESC LIMIT ?", (limit,)
            )
        )


def scoreboard() -> dict:
    """Quick totals used in the system prompt so Jarvis knows where things stand."""
    with connect() as conn:
        flips = conn.execute(
            "SELECT COUNT(*) AS sold, COALESCE(SUM(sold_price - bought_price), 0) AS profit "
            "FROM deals WHERE status = 'sold' AND sold_price IS NOT NULL AND bought_price IS NOT NULL"
        ).fetchone()
        leads = rows(conn.execute("SELECT status, COUNT(*) AS n FROM leads GROUP BY status"))
        running = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE status = 'running'"
        ).fetchone()[0]
    return {
        "flips_sold": flips["sold"],
        "flip_profit": round(flips["profit"], 2),
        "leads_by_status": {r["status"]: r["n"] for r in leads},
        "running_experiments": running,
    }
