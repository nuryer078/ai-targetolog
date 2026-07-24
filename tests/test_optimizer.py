"""Тесты бизнес-логики оптимизатора — чистые функции, деньги-критично."""
from __future__ import annotations

from agents.optimizer import decide
from services.state import AdMetrics


def test_pause_when_cpl_over_norm():
    m = AdMetrics(ad_id="a1", spend=20.0, leads=2, cpl=10.0)  # норма 5.0
    d = decide([m])[0]
    assert d.action == "PAUSE"
    assert "CPL" in d.reason


def test_keep_when_cpl_under_norm():
    m = AdMetrics(ad_id="a2", spend=8.0, leads=4, cpl=2.0)
    d = decide([m])[0]
    assert d.action == "KEEP"


def test_pause_when_no_leads_and_high_spend():
    # норма 5.0 -> порог 15.0; потрачено 20 без лидов
    m = AdMetrics(ad_id="a3", spend=20.0, leads=0, cpl=None)
    d = decide([m])[0]
    assert d.action == "PAUSE"
    assert "0 лидов" in d.reason


def test_keep_when_no_leads_but_low_spend():
    m = AdMetrics(ad_id="a4", spend=3.0, leads=0, cpl=None)
    d = decide([m])[0]
    assert d.action == "KEEP"


def test_custom_target_cpl_overrides():
    m = AdMetrics(ad_id="a5", spend=10.0, leads=2, cpl=5.0)
    assert decide([m], target_cpl=3.0)[0].action == "PAUSE"
    assert decide([m], target_cpl=10.0)[0].action == "KEEP"
