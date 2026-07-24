"""Отправка отчётов и алертов в Telegram.

Тихо-безопасно: если токен не настроен, функция не роняет пайплайн, а пишет в лог.
Отчёт — это уведомление, деньги не трогает, поэтому доп. подтверждения не требует.
"""
from __future__ import annotations

import requests

from config.settings import get_settings
from services.logger import get_logger

log = get_logger("telegram")


def send_message(text: str, *, silent: bool = False) -> bool:
    """Шлёт текст в настроенный чат. Возвращает True при успехе.

    Не бросает исключение при сбое доставки — отчёт не должен ронять запуск кампании.
    """
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        log.warning("Telegram не настроен (нет токена/чата) — отчёт пропущен.")
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_notification": silent,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            log.error("Telegram ответил %s: %s", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as exc:
        log.error("Не удалось отправить в Telegram: %s", exc)
        return False


def format_launch_report(campaign, brief) -> str:
    """Готовит человекочитаемый отчёт о запуске кампании."""
    mode = "🧪 DRY-RUN (PAUSED)" if campaign.dry_run else "🔴 БОЕВОЙ"
    lines = [
        f"<b>Запущена кампания</b> — {mode}",
        f"Продукт: {brief.name}",
        f"Кампания: <code>{campaign.campaign_id}</code>",
        f"Групп: {len(campaign.adset_ids)}, объявлений: {len(campaign.ad_ids)}",
        f"Статус: {campaign.status}",
    ]
    if campaign.note:
        lines.append(campaign.note)
    return "\n".join(lines)


def format_optimization_report(decisions, metrics, currency: str = "USD") -> str:
    """Готовит ежедневную сводку оптимизатора."""
    paused = [d for d in decisions if d.action == "PAUSE"]
    total_spend = sum(m.spend for m in metrics)
    lines = [
        "<b>📊 Сводка оптимизатора</b>",
        f"Объявлений под наблюдением: {len(metrics)}",
        f"Потрачено: {total_spend:.2f} {currency}",
        f"Поставлено на паузу: {len(paused)}",
    ]
    for d in paused:
        lines.append(f"⏸ <code>{d.ad_id}</code> — {d.reason}")
    return "\n".join(lines)
