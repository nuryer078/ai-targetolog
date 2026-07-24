"""История прогонов: SQLite по умолчанию, Postgres (Neon) при заданном DATABASE_URL.

Сохраняет запуски кампаний и снимки метрик — на дашборде видно историю.
- SQLite: локальный файл targetolog.db (в .gitignore). На эфемерных хостингах
  (Streamlit Cloud) сбрасывается при перезапуске.
- Postgres (Neon): постоянное хранилище. Включается, если DATABASE_URL начинается
  с postgres:// или postgresql://.

Публичный API (используется панелью и CLI) не меняется: save_run, save_metrics,
list_runs, get_run.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from config.settings import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
#  Бэкенды
# ============================================================
class _SqliteStore:
    """Хранилище на sqlite3 (плейсхолдер '?', AUTOINCREMENT, lastrowid)."""

    def __init__(self, path: str) -> None:
        self.path = path

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE IF NOT EXISTS runs ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, product TEXT,"
            " campaign_id TEXT, status TEXT, dry_run INTEGER, brief_json TEXT, campaign_json TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS metric_snapshots ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, created_at TEXT NOT NULL,"
            " spend REAL, leads INTEGER, revenue REAL, metrics_json TEXT)"
        )
        return conn

    def save_run(self, brief, campaign) -> int:
        with self._connect() as c:
            cur = c.execute(
                "INSERT INTO runs(created_at, product, campaign_id, status, dry_run, brief_json, campaign_json)"
                " VALUES(?,?,?,?,?,?,?)",
                (_now(), brief.name, campaign.campaign_id, campaign.status,
                 1 if campaign.dry_run else 0, brief.model_dump_json(), campaign.model_dump_json()),
            )
            return int(cur.lastrowid)

    def save_metrics(self, run_id, metrics) -> None:
        totals = _totals(metrics)
        with self._connect() as c:
            c.execute(
                "INSERT INTO metric_snapshots(run_id, created_at, spend, leads, revenue, metrics_json)"
                " VALUES(?,?,?,?,?,?)",
                (run_id, _now(), totals["spend"], totals["leads"], totals["revenue"], _metrics_json(metrics)),
            )

    def list_runs(self, limit) -> list[dict]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT id, created_at, product, campaign_id, status, dry_run"
                " FROM runs ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_run(self, run_id) -> Optional[dict]:
        with self._connect() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return None
            run = dict(row)
            snaps = c.execute(
                "SELECT created_at, spend, leads, revenue FROM metric_snapshots"
                " WHERE run_id=? ORDER BY id", (run_id,),
            ).fetchall()
            run["snapshots"] = [dict(s) for s in snaps]
            return run


class _PostgresStore:
    """Хранилище на Postgres/Neon (плейсхолдер '%s', SERIAL, RETURNING id)."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(self.dsn, row_factory=dict_row)
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS runs ("
                " id SERIAL PRIMARY KEY, created_at TEXT NOT NULL, product TEXT,"
                " campaign_id TEXT, status TEXT, dry_run INTEGER, brief_json TEXT, campaign_json TEXT)"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS metric_snapshots ("
                " id SERIAL PRIMARY KEY, run_id INTEGER, created_at TEXT NOT NULL,"
                " spend DOUBLE PRECISION, leads INTEGER, revenue DOUBLE PRECISION, metrics_json TEXT)"
            )
        conn.commit()
        return conn

    def save_run(self, brief, campaign) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO runs(created_at, product, campaign_id, status, dry_run, brief_json, campaign_json)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (_now(), brief.name, campaign.campaign_id, campaign.status,
                 1 if campaign.dry_run else 0, brief.model_dump_json(), campaign.model_dump_json()),
            )
            rid = cur.fetchone()["id"]
            conn.commit()
            return int(rid)

    def save_metrics(self, run_id, metrics) -> None:
        totals = _totals(metrics)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO metric_snapshots(run_id, created_at, spend, leads, revenue, metrics_json)"
                " VALUES(%s,%s,%s,%s,%s,%s)",
                (run_id, _now(), totals["spend"], totals["leads"], totals["revenue"], _metrics_json(metrics)),
            )
            conn.commit()

    def list_runs(self, limit) -> list[dict]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, product, campaign_id, status, dry_run"
                " FROM runs ORDER BY id DESC LIMIT %s", (limit,),
            )
            return list(cur.fetchall())

    def get_run(self, run_id) -> Optional[dict]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE id=%s", (run_id,))
            run = cur.fetchone()
            if not run:
                return None
            cur.execute(
                "SELECT created_at, spend, leads, revenue FROM metric_snapshots"
                " WHERE run_id=%s ORDER BY id", (run_id,),
            )
            run["snapshots"] = list(cur.fetchall())
            return run


# ============================================================
#  Общее
# ============================================================
def _totals(metrics) -> dict:
    return {
        "spend": sum(m.spend for m in metrics),
        "leads": sum(m.leads for m in metrics),
        "revenue": sum(m.revenue for m in metrics),
    }


def _metrics_json(metrics) -> str:
    return json.dumps([m.model_dump() for m in metrics], ensure_ascii=False, default=str)


def _store(path: Optional[str] = None):
    """Выбирает бэкенд: явный path -> SQLite; иначе Postgres, если задан DATABASE_URL."""
    settings = get_settings()
    if path is None and settings.database_url.lower().startswith(("postgres://", "postgresql://")):
        return _PostgresStore(settings.database_url)
    return _SqliteStore(path or settings.db_path)


# --- Публичный API (не меняется) ---
def save_run(brief, campaign, *, path: Optional[str] = None) -> int:
    return _store(path).save_run(brief, campaign)


def save_metrics(run_id: int, metrics, *, path: Optional[str] = None) -> None:
    _store(path).save_metrics(run_id, metrics)


def list_runs(limit: int = 50, *, path: Optional[str] = None) -> list[dict]:
    return _store(path).list_runs(limit)


def get_run(run_id: int, *, path: Optional[str] = None) -> Optional[dict]:
    return _store(path).get_run(run_id)
