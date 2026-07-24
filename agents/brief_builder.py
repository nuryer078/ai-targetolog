"""Автозаполнение брифа продукта.

Пользователь даёт минимум — ссылку на лендинг и/или пару слов о продукте, — а Claude
достаёт из этого структурированный ProductBrief (название, описание, гео, цель, цену).
Дальше человек проверяет и правит в панели.
"""
from __future__ import annotations

import re

import requests

from config.settings import get_settings
from services.llm import complete_json
from services.logger import get_logger
from services.state import ProductBrief

log = get_logger("brief_builder")

SYSTEM = """Ты — маркетолог, который быстро упаковывает продукт в бриф для таргетированной
рекламы. По тексту лендинга и/или заметке о продукте заполни бриф.

Верни СТРОГО валидный JSON без markdown:
{
  "name": "короткое название продукта/услуги",
  "description": "2-3 предложения: что это, для кого, ключевая ценность",
  "landing_url": "URL посадочной, если известен, иначе пустая строка",
  "geo": ["коды стран ISO-2, напр. KZ, RU. Если явно не ясно — [\\"KZ\\"]"],
  "price": "цена строкой, если есть, иначе null",
  "goal": "одно из: TRAFFIC | LEAD_GENERATION | AWARENESS | SALES",
  "extra": "полезные детали для аналитика (УТП, акции), иначе null"
}
Пиши на языке исходных данных. Не выдумывай фактов, которых нет в источнике —
для отсутствующего ставь разумные значения по умолчанию или null."""

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANGLE_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def fetch_landing_text(url: str, max_chars: int = 4000) -> str:
    """Скачивает лендинг и вытаскивает видимый текст (грубо, без тяжёлых парсеров)."""
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (AI-targetolog)"})
    if resp.status_code >= 400:
        raise RuntimeError(f"Лендинг вернул {resp.status_code}")
    html = resp.text
    html = _TAG_RE.sub(" ", html)      # выкидываем script/style
    text = _ANGLE_RE.sub(" ", html)    # снимаем теги
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]


def autofill_brief(note: str = "", url: str = "") -> ProductBrief:
    """Собирает ProductBrief из заметки и/или лендинга.

    Нужен хотя бы один источник: непустая заметка или URL.
    """
    settings = get_settings()
    note = (note or "").strip()
    url = (url or "").strip()
    if not note and not url:
        raise ValueError("Дай ссылку на лендинг или пару слов о продукте.")

    parts = []
    if url:
        try:
            parts.append(f"Текст лендинга ({url}):\n{fetch_landing_text(url)}")
        except Exception as exc:  # noqa: BLE001 — лендинг мог не открыться, работаем по заметке
            log.warning("Не удалось прочитать лендинг %s: %s", url, exc)
            parts.append(f"URL лендинга: {url} (текст недоступен)")
    if note:
        parts.append(f"Заметка о продукте: {note}")

    log.info("Автозаполнение брифа (url=%s, заметка=%d симв.)", bool(url), len(note))
    data = complete_json(SYSTEM, "\n\n".join(parts), model=settings.llm_model)

    geo = data.get("geo") or ["KZ"]
    if isinstance(geo, str):
        geo = [g.strip().upper() for g in geo.split(",") if g.strip()]
    goal = (data.get("goal") or "TRAFFIC").upper()
    if goal not in {"TRAFFIC", "LEAD_GENERATION", "AWARENESS", "SALES"}:
        goal = "TRAFFIC"

    return ProductBrief(
        name=(data.get("name") or "Без названия").strip(),
        description=(data.get("description") or note or "").strip(),
        landing_url=(data.get("landing_url") or url or "").strip(),
        geo=[g.upper() for g in geo],
        price=(data.get("price") or None),
        goal=goal,
        extra=(data.get("extra") or None),
    )
