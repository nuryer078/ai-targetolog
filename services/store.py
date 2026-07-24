"""История прогонов в SQLite (без внешних сервисов).

Сохраняет запуски кампаний и снимки метрик, чтобы на дашборде видеть историю.
Локальный файл targetolog.db (в .gitignore). На эфемерных хостингах (Streamlit Cloud)
файл сбрасывается при перезапуске — для долговременного хранения позже подключим Postgres.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from config.settings import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(path: Optional[str]) -> str:
    return path or get_settings().db_path


@contextmanager
def _conn(path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_path(path))
    conn.row_factory = sqlite3.Row
    try:
        _init(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            product TEXT,
            campaign_id TEXT,
            status TEXT,
            dry_run INTEGER,
            brief_json TEXT,
            campaign_json TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS metric_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            created_at TEXT NOT NULL,
            spend REAL, leads INTEGER, revenue REAL,
            metrics_json TEXT
        )"""
    )


def save_run(brief, campaign, *, path: Optional[str] = None) -> int:
    """Сохраняет запуск кампании. Возвращает run_id."""
    with _conn(path) as c:
        cur = c.execute(
            "INSERT INTO runs(created_at, product, campaign_id, status, dry_run, brief_json, campaign_json)"
            " VALUES(?,?,?,?,?,?,?)",
            (
                _now(), brief.name, campaign.campaign_id, campaign.status,
                1 if campaign.dry_run else 0,
                brief.model_dump_json(), campaign.model_dump_json(),
            ),
        )
        return int(cur.lastrowid)


def save_metrics(run_id: int, metrics, *, path: Optional[str] = None) -> None:
    """Сохраняет снимок метрик по прогону."""
    total_spend = sum(m.spend for m in metrics)
    total_leads = sum(m.leads for m in metrics)
    total_rev = sum(m.revenue for m in metrics)
    payload = json.dumps([m.model_dump() for m in metrics], ensure_ascii=False, default=str)
    with _conn(path) as c:
        c.execute(
            "INSERT INTO metric_snapshots(run_id, created_at, spend, leads, revenue, metrics_json)"
            " VALUES(?,?,?,?,?,?)",
            (run_id, _now(), total_spend, total_leads, total_rev, payload),
        )


def list_runs(limit: int = 50, *, path: Optional[str] = None) -> list[dict]:
    """Последние прогоны (для истории на дашборде)."""
    with _conn(path) as c:
        rows = c.execute(
            "SELECT id, created_at, product, campaign_id, status, dry_run"
            " FROM runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int, *, path: Optional[str] = None) -> Optional[dict]:
    """Полная карточка прогона + его снимки метрик."""
    with _conn(path) as c:
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        run = dict(row)
        snaps = c.execute(
            "SELECT created_at, spend, leads, revenue FROM metric_snapshots"
            " WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        run["snapshots"] = [dict(s) for s in snaps]
        return run
