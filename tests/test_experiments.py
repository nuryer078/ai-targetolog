"""Тесты статистики A/B — чистые функции, детерминированно."""
from __future__ import annotations

from agents.experiments import auto_select_winner, evaluate_ab, two_proportion_pvalue
from services.state import AdMetrics


def test_pvalue_identical_rates_high():
    # одинаковые доли -> p близок к 1 (нет разницы)
    assert two_proportion_pvalue(50, 100, 50, 100) > 0.9


def test_pvalue_big_difference_low():
    # 90% против 10% на больших выборках -> p очень мал
    assert two_proportion_pvalue(90, 100, 10, 100) < 0.001


def test_evaluate_needs_two_variants():
    res = evaluate_ab([AdMetrics(ad_id="a", clicks=100, leads=10)])
    assert res["significant"] is False
    assert "2 варианта" in res["reason"]


def test_evaluate_not_enough_data():
    # мало испытаний -> не значимо, причина про данные
    m = [
        AdMetrics(ad_id="a", clicks=20, leads=10),
        AdMetrics(ad_id="b", clicks=20, leads=1),
    ]
    res = evaluate_ab(m, min_trials=100)
    assert res["significant"] is False
    assert res["enough_data"] is False


def test_evaluate_picks_significant_winner():
    # чёткий победитель на большом объёме
    m = [
        AdMetrics(ad_id="win", clicks=1000, leads=200),   # CVR 20%
        AdMetrics(ad_id="lose", clicks=1000, leads=50),   # CVR 5%
    ]
    res = evaluate_ab(m, min_trials=100)
    assert res["significant"] is True
    assert res["winner"] == "win"
    assert res["metric"] == "lead_per_click"


def test_evaluate_falls_back_to_ctr_without_leads():
    m = [
        AdMetrics(ad_id="a", impressions=1000, clicks=100, leads=0),
        AdMetrics(ad_id="b", impressions=1000, clicks=20, leads=0),
    ]
    res = evaluate_ab(m, min_trials=100)
    assert res["metric"] == "ctr"


def test_auto_select_pauses_losers_when_significant():
    m = [
        AdMetrics(ad_id="win", clicks=1000, leads=200),
        AdMetrics(ad_id="lose", clicks=1000, leads=50),
    ]
    res, decisions = auto_select_winner(m, execute=False)
    actions = {d.ad_id: d.action for d in decisions}
    assert actions == {"win": "KEEP", "lose": "PAUSE"}


def test_auto_select_keeps_all_when_not_significant():
    m = [
        AdMetrics(ad_id="a", clicks=30, leads=3),
        AdMetrics(ad_id="b", clicks=30, leads=2),
    ]
    res, decisions = auto_select_winner(m, execute=False, min_trials=100)
    assert all(d.action == "KEEP" for d in decisions)
