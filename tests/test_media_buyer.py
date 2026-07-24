"""Тесты Media Buyer на фейковом Meta-клиенте: порядок и предохранители."""
from __future__ import annotations

import pytest

from agents.media_buyer import (
    append_utm,
    build_targeting,
    launch,
    resolve_campaign_config,
    resolve_interests,
)
from services.state import Creative, ProductBrief


class FakeFB:
    """Фейковый клиент Meta: возвращает предсказуемые id, ничего не шлёт в сеть."""

    def __init__(self):
        self.created = {"campaign": 0, "adset": 0, "creative": 0, "ad": 0, "image": 0}

    def create_campaign(self, **kw):
        self.created["campaign"] += 1
        self.campaign_kw = kw
        return {"id": "camp_1"}

    def create_adset(self, **kw):
        self.created["adset"] += 1
        self.adset_kw = kw
        return {"id": "adset_1"}

    def upload_image_from_url(self, url):
        self.created["image"] += 1
        return "HASH"

    def create_ad_creative(self, **kw):
        self.created["creative"] += 1
        self.creative_kw = kw
        return {"id": f"creative_{self.created['creative']}"}

    def create_ad(self, **kw):
        self.created["ad"] += 1
        return {"id": f"ad_{self.created['ad']}"}


def _brief():
    return ProductBrief(name="Курс", description="desc", landing_url="https://x.kz", geo=["KZ"])


def _creative(with_image=True):
    return Creative(
        idea_angle="angle", framework="AIDA", primary_text="text",
        headline="head", description="desc", image_prompt="prompt",
        image_url="http://img/1.jpg" if with_image else None,
    )


def test_build_targeting_valid():
    t = build_targeting(_brief())
    assert t["geo_locations"]["countries"] == ["KZ"]
    assert t["age_min"] == 18 and t["age_max"] == 65
    assert "flexible_spec" not in t  # без интересов


def test_build_targeting_with_interests():
    t = build_targeting(_brief(), interests=[{"id": "6003", "name": "Coffee"}])
    assert t["flexible_spec"] == [{"interests": [{"id": "6003", "name": "Coffee"}]}]


def test_resolve_campaign_config_awareness():
    obj, opt, promoted = resolve_campaign_config("AWARENESS", pixel_id="")
    assert obj == "OUTCOME_AWARENESS" and opt == "REACH" and promoted is None


def test_resolve_campaign_config_leads_with_pixel():
    obj, opt, promoted = resolve_campaign_config("LEAD_GENERATION", pixel_id="999")
    assert obj == "OUTCOME_LEADS"
    assert opt == "OFFSITE_CONVERSIONS"
    assert promoted == {"pixel_id": "999", "custom_event_type": "LEAD"}


def test_resolve_campaign_config_sales_with_pixel():
    obj, opt, promoted = resolve_campaign_config("SALES", pixel_id="999")
    assert obj == "OUTCOME_SALES"
    assert promoted["custom_event_type"] == "PURCHASE"


def test_resolve_campaign_config_leads_without_pixel_falls_back_to_clicks():
    obj, opt, promoted = resolve_campaign_config("LEAD_GENERATION", pixel_id="")
    assert obj == "OUTCOME_TRAFFIC" and opt == "LINK_CLICKS" and promoted is None


def test_resolve_interests_dedup_and_limit():
    class FakeSearch:
        def search_interests(self, kw, limit=1):
            return {"coffee": [{"id": "1", "name": "Coffee"}],
                    "tea": [{"id": "2", "name": "Tea"}],
                    "dup": [{"id": "1", "name": "Coffee"}]}.get(kw, [])

    res = resolve_interests(["coffee", "tea", "dup", "unknown"], FakeSearch())
    assert [r["id"] for r in res] == ["1", "2"]  # без дублей, unknown пропущен


def test_launch_builds_full_structure():
    fb = FakeFB()
    camp = launch(_brief(), [_creative(), _creative()], daily_budget=5.0, client=fb)
    assert camp.campaign_id == "camp_1"
    assert len(camp.ad_ids) == 2
    assert fb.created == {"campaign": 1, "adset": 1, "creative": 2, "ad": 2, "image": 2}


def test_launch_forces_paused_in_dry_run():
    fb = FakeFB()
    camp = launch(_brief(), [_creative()], daily_budget=5.0, activate=True, client=fb)
    assert camp.status == "PAUSED"
    assert camp.dry_run is True


def test_launch_without_images_raises():
    fb = FakeFB()
    with pytest.raises(ValueError):
        launch(_brief(), [_creative(with_image=False)], daily_budget=5.0, client=fb)


def test_launch_without_creatives_raises():
    with pytest.raises(ValueError):
        launch(_brief(), [], daily_budget=5.0, client=FakeFB())


def test_launch_with_pixel_sends_promoted_object(set_env):
    set_env(META_PIXEL_ID="999")  # goal брифа = LEAD_GENERATION по умолчанию
    fb = FakeFB()
    launch(_brief(), [_creative()], daily_budget=5.0, client=fb)
    assert fb.adset_kw["promoted_object"] == {"pixel_id": "999", "custom_event_type": "LEAD"}


def test_launch_without_pixel_no_promoted_object():
    fb = FakeFB()
    launch(_brief(), [_creative()], daily_budget=5.0, client=fb)
    assert fb.adset_kw["promoted_object"] is None


# ---------- UTM ----------

def test_append_utm_adds_params():
    url = append_utm("https://shop.kz/page", "Курс SMM")
    assert "utm_source=facebook" in url
    assert "utm_medium=paid_social" in url
    assert "utm_campaign=" in url


def test_append_utm_preserves_existing():
    url = append_utm("https://shop.kz/p?utm_source=custom&ref=1", "Кампания")
    assert "utm_source=custom" in url   # своё не перетёрли
    assert "ref=1" in url


def test_launch_uses_utm_link():
    fb = FakeFB()
    launch(_brief(), [_creative()], daily_budget=5.0, client=fb)
    assert "utm_source=facebook" in fb.creative_kw["link"]


# ---------- CBO + аудитории ----------

def test_launch_cbo_puts_budget_on_campaign():
    fb = FakeFB()
    launch(_brief(), [_creative()], daily_budget=5.0, campaign_budget=7.0, client=fb)
    assert fb.campaign_kw["daily_budget"] == 7.0   # бюджет на кампании
    assert fb.adset_kw["daily_budget"] is None      # у группы бюджета нет


def test_launch_non_cbo_budget_on_adset():
    fb = FakeFB()
    launch(_brief(), [_creative()], daily_budget=5.0, client=fb)
    assert fb.campaign_kw["daily_budget"] is None
    assert fb.adset_kw["daily_budget"] == 5.0


def test_build_targeting_with_audiences():
    t = build_targeting(_brief(), custom_audiences=["a1"], excluded_audiences=["a2"])
    assert t["custom_audiences"] == [{"id": "a1"}]
    assert t["excluded_custom_audiences"] == [{"id": "a2"}]
