"""Тесты helper'а аудиторий (ретаргетинг/lookalike) на фейковом клиенте."""
from __future__ import annotations

import pytest

from agents.audiences import create_lookalike, create_retargeting, list_audiences


class FakeAud:
    def __init__(self):
        self.calls = []

    def create_custom_audience_website(self, name, pixel_id, retention_days=180):
        self.calls.append(("website", name, pixel_id, retention_days))
        return {"id": "aud_rt"}

    def create_lookalike_audience(self, name, source_audience_id, country, ratio=0.01):
        self.calls.append(("lal", name, source_audience_id, country, ratio))
        return {"id": "aud_lal"}

    def list_custom_audiences(self):
        return [{"id": "aud_rt", "name": "RT", "subtype": "WEBSITE", "count": 100}]


def test_retargeting_requires_pixel(set_env):
    set_env(META_PIXEL_ID="")
    with pytest.raises(ValueError):
        create_retargeting("RT", client=FakeAud())


def test_retargeting_with_pixel(set_env):
    set_env(META_PIXEL_ID="777")
    fb = FakeAud()
    assert create_retargeting("RT", client=fb)["id"] == "aud_rt"
    assert fb.calls[0][2] == "777"


def test_lookalike_passes_args():
    fb = FakeAud()
    create_lookalike("LAL", "aud_rt", "KZ", ratio=0.02, client=fb)
    assert fb.calls[0] == ("lal", "LAL", "aud_rt", "KZ", 0.02)


def test_list_audiences():
    assert list_audiences(client=FakeAud())[0]["subtype"] == "WEBSITE"
