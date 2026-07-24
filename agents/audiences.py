"""Аудитории: ретаргетинг и lookalike.

Профессиональный таргетинг строится не только на «холодных» интересах, но и на:
  * ретаргетинге — тёплые посетители сайта (по пикселю);
  * lookalike — люди, похожие на вашу аудиторию/покупателей.
Обычно это самые дешёвые источники конверсий.
"""
from __future__ import annotations

from typing import Optional

from config.settings import get_settings
from services.logger import get_logger
from tools.facebook_api import FacebookAdsClient

log = get_logger("audiences")


def create_retargeting(
    name: str,
    *,
    retention_days: int = 180,
    client: Optional[FacebookAdsClient] = None,
) -> dict:
    """Аудитория ретаргетинга: посетители сайта за N дней (нужен META_PIXEL_ID)."""
    settings = get_settings()
    if not settings.meta_pixel_id:
        raise ValueError("Для ретаргетинга нужен META_PIXEL_ID в .env.")
    fb = client or FacebookAdsClient()
    return fb.create_custom_audience_website(name, settings.meta_pixel_id, retention_days)


def create_lookalike(
    name: str,
    source_audience_id: str,
    country: str,
    *,
    ratio: float = 0.01,
    client: Optional[FacebookAdsClient] = None,
) -> dict:
    """Lookalike на основе аудитории-источника (напр. ретаргетинга или покупателей)."""
    fb = client or FacebookAdsClient()
    return fb.create_lookalike_audience(name, source_audience_id, country, ratio=ratio)


def list_audiences(client: Optional[FacebookAdsClient] = None) -> list[dict]:
    """Все аудитории кабинета."""
    return (client or FacebookAdsClient()).list_custom_audiences()
