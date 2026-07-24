"""Тесты клиента Meta Ads на моках — без реальных сетевых вызовов."""
from __future__ import annotations

import json

import pytest

from services.guardrails import BudgetExceeded
from tools.facebook_api import FacebookAdsClient, extract_leads


class FakeClient(FacebookAdsClient):
    """Клиент, у которого перехвачен _request: копит вызовы, отдаёт заготовки."""

    def __init__(self):
        super().__init__()
        self.calls = []

    def _request(self, method, path, *, data=None, params=None, files=None):
        self.calls.append({"method": method, "path": path, "data": data or {}, "params": params or {}})
        if path.endswith("/campaigns"):
            return {"id": "camp_1"}
        if path.endswith("/adsets"):
            return {"id": "adset_1"}
        if path.endswith("/adcreatives"):
            return {"id": "creative_1"}
        if path.endswith("/ads"):
            return {"id": "ad_1"}
        if path.endswith("/adimages"):
            return {"images": {"creative.jpg": {"hash": "HASH123"}}}
        if path == "search":
            return {"data": [
                {"id": "6003", "name": "Coffee", "audience_size_lower_bound": 12000},
                {"id": "6004", "name": "Espresso", "audience_size_lower_bound": 8000},
            ]}
        return {"id": "obj"}


def test_minor_units_usd():
    c = FacebookAdsClient()
    assert c._to_minor_units(5.0) == 500      # USD -> центы
    assert c._to_minor_units(4.99) == 499


def test_minor_units_zero_decimal(set_env):
    set_env(CURRENCY="JPY")
    c = FacebookAdsClient()
    assert c._to_minor_units(500) == 500      # иена без дробной части


def test_create_campaign_forced_paused_in_dry_run():
    c = FakeClient()
    c.create_campaign("Test", status="ACTIVE")
    call = c.calls[-1]
    assert call["data"]["status"] == "PAUSED"


def test_create_adset_within_limit_builds_correct_payload():
    c = FakeClient()
    c.create_adset(
        "AdSet", "camp_1", daily_budget=5.0,
        targeting={"geo_locations": {"countries": ["KZ"]}},
        status="ACTIVE",
    )
    call = c.calls[-1]
    assert call["path"].endswith("/adsets")
    assert call["data"]["daily_budget"] == 500       # 5.0 USD -> 500 центов
    assert call["data"]["status"] == "PAUSED"        # dry-run
    # targeting сериализован в JSON-строку
    assert json.loads(call["data"]["targeting"])["geo_locations"]["countries"] == ["KZ"]


def test_create_adset_over_budget_blocked():
    c = FakeClient()
    with pytest.raises(BudgetExceeded):
        c.create_adset("AdSet", "camp_1", daily_budget=100.0, targeting={})
    # ни одного вызова к API не должно уйти
    assert not any(call["path"].endswith("/adsets") for call in c.calls)


def test_upload_image_returns_hash(monkeypatch):
    c = FakeClient()

    class FakeResp:
        status_code = 200
        content = b"\xff\xd8\xff"  # jpeg-заголовок

    monkeypatch.setattr("tools.facebook_api.requests.get", lambda *a, **k: FakeResp())
    assert c.upload_image_from_url("http://x/y.jpg") == "HASH123"


def test_search_interests_parses_results():
    c = FakeClient()
    res = c.search_interests("coffee")
    assert len(res) == 2
    assert res[0] == {"id": "6003", "name": "Coffee", "audience": 12000, "topic": None}


def test_extract_leads():
    insights = {"actions": [
        {"action_type": "lead", "value": "3"},
        {"action_type": "link_click", "value": "50"},
        {"action_type": "offsite_conversion.fb_pixel_lead", "value": "2"},
    ]}
    assert extract_leads(insights) == 5
    assert extract_leads({}) == 0
