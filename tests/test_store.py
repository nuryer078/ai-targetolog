"""Тесты истории в SQLite на временной БД (реального файла проекта не трогаем)."""
from __future__ import annotations

from services import store
from services.state import AdMetrics, LaunchedCampaign, ProductBrief


def _db(tmp_path):
    return str(tmp_path / "test.db")


def _brief():
    return ProductBrief(name="Курс", description="d", landing_url="https://x.kz", geo=["KZ"])


def _campaign():
    return LaunchedCampaign(
        campaign_id="camp_1", adset_ids=["set1"], ad_ids=["ad1", "ad2"],
        status="PAUSED", dry_run=True, note="ok",
    )


def test_save_and_list_run(tmp_path):
    db = _db(tmp_path)
    run_id = store.save_run(_brief(), _campaign(), path=db)
    assert run_id == 1
    runs = store.list_runs(path=db)
    assert len(runs) == 1
    assert runs[0]["product"] == "Курс"
    assert runs[0]["campaign_id"] == "camp_1"
    assert runs[0]["dry_run"] == 1


def test_save_metrics_and_get_run(tmp_path):
    db = _db(tmp_path)
    run_id = store.save_run(_brief(), _campaign(), path=db)
    metrics = [
        AdMetrics(ad_id="ad1", spend=3.0, leads=2, revenue=10.0),
        AdMetrics(ad_id="ad2", spend=1.5, leads=0, revenue=0.0),
    ]
    store.save_metrics(run_id, metrics, path=db)
    run = store.get_run(run_id, path=db)
    assert run is not None
    assert len(run["snapshots"]) == 1
    snap = run["snapshots"][0]
    assert snap["spend"] == 4.5      # 3.0 + 1.5
    assert snap["leads"] == 2
    assert snap["revenue"] == 10.0


def test_runs_ordered_newest_first(tmp_path):
    db = _db(tmp_path)
    store.save_run(_brief(), _campaign(), path=db)
    store.save_run(_brief(), _campaign(), path=db)
    runs = store.list_runs(path=db)
    assert [r["id"] for r in runs] == [2, 1]


def test_get_missing_run_returns_none(tmp_path):
    assert store.get_run(999, path=_db(tmp_path)) is None
