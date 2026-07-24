"""Тесты бизнес-логики оптимизатора — чистые функции, деньги-критично."""
from __future__ import annotations

from agents.optimizer import decide, decide_scaling
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


# ---------- усталость креатива ----------

def test_pause_on_creative_fatigue():
    # высокая частота, много показов, лидов нет -> пауза по усталости
    m = AdMetrics(ad_id="f1", spend=2.0, impressions=5000, frequency=4.5, leads=0)
    d = decide([m])[0]
    assert d.action == "PAUSE"
    assert "сталость" in d.reason


def test_fatigue_does_not_pause_a_winner():
    # частота высокая, НО лид дешёвый -> победителя не трогаем
    m = AdMetrics(ad_id="f2", spend=6.0, impressions=5000, frequency=5.0, leads=3, cpl=2.0)
    assert decide([m])[0].action == "KEEP"


# ---------- масштабирование ----------

def test_scale_winner_capped_at_limit():
    # норма 5.0 -> порог 3.5; CPL 2.0 и 5 лидов -> масштабируем, но не выше лимита 10
    m = AdMetrics(ad_id="s1", adset_id="set1", spend=16.0, leads=5, cpl=2.0)
    d = decide_scaling([m], {"set1": 9.0}, step=1.3)[0]
    assert d.action == "SCALE"
    assert d.new_budget == 10.0            # 9*1.3=11.7 -> потолок 10


def test_no_scale_when_cpl_not_good():
    m = AdMetrics(ad_id="s2", adset_id="set2", spend=10.0, leads=3, cpl=4.5)  # > порога 3.5
    assert decide_scaling([m], {"set2": 5.0}) == []


def test_no_scale_when_already_at_cap():
    m = AdMetrics(ad_id="s3", adset_id="set3", spend=20.0, leads=6, cpl=1.5)
    assert decide_scaling([m], {"set3": 10.0}) == []  # уже на потолке
