"""Тесты автозаполнения брифа — парсинг лендинга и сборка ProductBrief на моках."""
from __future__ import annotations

import pytest

from agents import brief_builder
from agents.brief_builder import autofill_brief, fetch_landing_text
from services.state import ProductBrief


class FakeResp:
    status_code = 200
    text = (
        "<html><head><style>.x{color:red}</style>"
        "<script>alert('secret')</script></head>"
        "<body><h1>Курс по SMM</h1><p>Научим таргету за 4 недели</p></body></html>"
    )


def test_fetch_landing_strips_tags_and_scripts(monkeypatch):
    monkeypatch.setattr(brief_builder.requests, "get", lambda *a, **k: FakeResp())
    text = fetch_landing_text("http://x.kz")
    assert "Курс по SMM" in text
    assert "Научим таргету" in text
    assert "secret" not in text      # script вырезан
    assert "<" not in text and ">" not in text


def test_autofill_requires_some_input():
    with pytest.raises(ValueError):
        autofill_brief(note="", url="")


def test_autofill_builds_brief(monkeypatch):
    monkeypatch.setattr(brief_builder, "complete_json", lambda *a, **k: {
        "name": "Курс по SMM",
        "description": "Онлайн-курс для новичков",
        "landing_url": "https://smm.kz",
        "geo": ["KZ", "RU"],
        "price": "50000 ₸",
        "goal": "LEAD_GENERATION",
        "extra": "Старт каждый месяц",
    })
    brief = autofill_brief(note="курс по смм")
    assert isinstance(brief, ProductBrief)
    assert brief.name == "Курс по SMM"
    assert brief.geo == ["KZ", "RU"]
    assert brief.goal == "LEAD_GENERATION"


def test_autofill_normalizes_geo_string_and_bad_goal(monkeypatch):
    monkeypatch.setattr(brief_builder, "complete_json", lambda *a, **k: {
        "name": "X", "description": "Y", "landing_url": "",
        "geo": "kz, ru", "price": None, "goal": "НЕПОНЯТНО", "extra": None,
    })
    brief = autofill_brief(note="что-то")
    assert brief.geo == ["KZ", "RU"]     # строка -> список, апперкейс
    assert brief.goal == "TRAFFIC"       # невалидная цель -> дефолт


def test_autofill_falls_back_to_note_when_landing_unreadable(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("404")

    monkeypatch.setattr(brief_builder, "fetch_landing_text", boom)
    monkeypatch.setattr(brief_builder, "complete_json", lambda *a, **k: {
        "name": "N", "description": "D", "landing_url": "http://x.kz",
        "geo": ["KZ"], "price": None, "goal": "TRAFFIC", "extra": None,
    })
    # не должно падать: лендинг недоступен, но есть заметка
    brief = autofill_brief(note="описание", url="http://x.kz")
    assert brief.name == "N"
