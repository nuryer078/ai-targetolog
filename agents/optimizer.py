"""Optimization Agent (Оптимизатор).

По расписанию снимает метрики через Meta API и применяет бизнес-логику:
если цена лида (CPL) выше нормы — ставит объявление на паузу. Логика решений
ДЕТЕРМИНИРОВАНА (деньги!), LLM здесь не решает, кого паузить.

Пауза — всегда разрешённое действие (снижение риска), поэтому выполняется даже
без выключения DRY_RUN.
"""
from __future__ import annotations

from typing import Optional

from config.settings import get_settings
from services.logger import get_logger
from services.state import AdMetrics, OptimizationDecision
from tools.facebook_api import FacebookAdsClient, extract_leads

log = get_logger("optimizer")


def collect_metrics(
    ad_ids: list[str],
    *,
    date_preset: str = "today",
    client: Optional[FacebookAdsClient] = None,
) -> list[AdMetrics]:
    """Снимает статистику по списку объявлений."""
    fb = client or FacebookAdsClient()
    metrics: list[AdMetrics] = []
    for ad_id in ad_ids:
        raw = fb.get_insights(ad_id, date_preset=date_preset)
        spend = float(raw.get("spend", 0) or 0)
        leads = extract_leads(raw)
        cpl = round(spend / leads, 2) if leads > 0 else None
        metrics.append(
            AdMetrics(
                ad_id=ad_id,
                spend=spend,
                impressions=int(float(raw.get("impressions", 0) or 0)),
                clicks=int(float(raw.get("clicks", 0) or 0)),
                ctr=float(raw.get("ctr", 0) or 0),
                cpc=float(raw.get("cpc", 0) or 0),
                leads=leads,
                cpl=cpl,
            )
        )
    return metrics


def decide(metrics: list[AdMetrics], target_cpl: Optional[float] = None) -> list[OptimizationDecision]:
    """Бизнес-правила паузы. Чистая функция — легко тестируется.

    Правила:
      1) Есть лиды и CPL выше нормы -> PAUSE.
      2) Лидов нет, но потрачено >= 3x нормы CPL (бюджет уходит впустую) -> PAUSE.
      3) Иначе -> KEEP.
    """
    settings = get_settings()
    norm = target_cpl if target_cpl is not None else settings.target_cpl
    decisions: list[OptimizationDecision] = []
    for m in metrics:
        if m.cpl is not None and m.cpl > norm:
            decisions.append(
                OptimizationDecision(
                    ad_id=m.ad_id,
                    action="PAUSE",
                    reason=f"CPL {m.cpl:.2f} > нормы {norm:.2f} {settings.currency}",
                )
            )
        elif m.leads == 0 and m.spend >= norm * 3:
            decisions.append(
                OptimizationDecision(
                    ad_id=m.ad_id,
                    action="PAUSE",
                    reason=f"Потрачено {m.spend:.2f} {settings.currency}, 0 лидов",
                )
            )
        else:
            decisions.append(
                OptimizationDecision(ad_id=m.ad_id, action="KEEP", reason="В пределах нормы")
            )
    return decisions


def apply_decisions(
    decisions: list[OptimizationDecision],
    *,
    client: Optional[FacebookAdsClient] = None,
) -> list[str]:
    """Исполняет решения PAUSE в Meta. Возвращает id поставленных на паузу."""
    fb = client or FacebookAdsClient()
    paused: list[str] = []
    for d in decisions:
        if d.action == "PAUSE":
            fb.pause_ad(d.ad_id)
            paused.append(d.ad_id)
            log.warning("Пауза %s — %s", d.ad_id, d.reason)
    return paused


def run_optimizer(
    ad_ids: list[str],
    *,
    target_cpl: Optional[float] = None,
    execute: bool = True,
    client: Optional[FacebookAdsClient] = None,
) -> tuple[list[AdMetrics], list[OptimizationDecision]]:
    """Полный цикл: собрать метрики -> решить -> (опц.) исполнить паузы."""
    fb = client or FacebookAdsClient()
    metrics = collect_metrics(ad_ids, client=fb)
    decisions = decide(metrics, target_cpl=target_cpl)
    if execute:
        apply_decisions(decisions, client=fb)
    return metrics, decisions
