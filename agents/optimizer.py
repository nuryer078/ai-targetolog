"""Optimization Agent (Оптимизатор) 2.0.

По расписанию снимает метрики через Meta API и применяет детерминированную бизнес-логику
(деньги — не место для галлюцинаций LLM):
  * PAUSE — дорогой лид, слитый бюджет без лидов, усталость креатива (высокая частота);
  * SCALE — поднять бюджет прибыльной группе (opt-in, с жёстким потолком, не в DRY_RUN).

Пауза — снижение риска, выполняется всегда. Масштабирование тратит БОЛЬШЕ денег,
поэтому только вне DRY_RUN и не выше MAX_DAILY_BUDGET.
"""
from __future__ import annotations

from typing import Optional

from config.settings import get_settings
from services.logger import get_logger
from services.state import AdMetrics, OptimizationDecision
from tools.facebook_api import (
    FacebookAdsClient,
    extract_leads,
    extract_purchases,
    extract_revenue,
)

log = get_logger("optimizer")

FATIGUE_FREQUENCY = 4.0  # частота показов, с которой креатив считается «выгоревшим»


def _metrics_from_insights(object_id: str, raw: dict, adset_id: Optional[str] = None) -> AdMetrics:
    spend = float(raw.get("spend", 0) or 0)
    leads = extract_leads(raw)
    purchases = extract_purchases(raw)
    revenue = extract_revenue(raw)
    return AdMetrics(
        ad_id=object_id,
        adset_id=adset_id,
        spend=spend,
        impressions=int(float(raw.get("impressions", 0) or 0)),
        clicks=int(float(raw.get("clicks", 0) or 0)),
        ctr=float(raw.get("ctr", 0) or 0),
        cpc=float(raw.get("cpc", 0) or 0),
        frequency=float(raw.get("frequency", 0) or 0),
        leads=leads,
        cpl=round(spend / leads, 2) if leads > 0 else None,
        purchases=purchases,
        revenue=revenue,
        roas=round(revenue / spend, 2) if spend > 0 and revenue > 0 else None,
    )


def collect_metrics(
    ad_ids: list[str],
    *,
    date_preset: str = "today",
    client: Optional[FacebookAdsClient] = None,
) -> list[AdMetrics]:
    """Снимает статистику по списку объявлений."""
    fb = client or FacebookAdsClient()
    return [
        _metrics_from_insights(ad_id, fb.get_insights(ad_id, date_preset=date_preset))
        for ad_id in ad_ids
    ]


def decide(
    metrics: list[AdMetrics],
    target_cpl: Optional[float] = None,
    *,
    fatigue_frequency: float = FATIGUE_FREQUENCY,
) -> list[OptimizationDecision]:
    """Правила паузы (чистая функция).

      1) Усталость: частота >= порога И лид дорогой/нет -> PAUSE (не трогаем победителей).
      2) Есть лиды и CPL выше нормы -> PAUSE.
      3) Лидов нет, но потрачено >= 3x нормы CPL -> PAUSE.
      4) Иначе -> KEEP.
    """
    settings = get_settings()
    norm = target_cpl if target_cpl is not None else settings.target_cpl
    cur = settings.currency
    decisions: list[OptimizationDecision] = []
    for m in metrics:
        poor = m.cpl is None or m.cpl > norm
        if m.frequency >= fatigue_frequency and m.impressions > 1000 and poor:
            decisions.append(OptimizationDecision(
                ad_id=m.ad_id, action="PAUSE",
                reason=f"Усталость креатива: частота {m.frequency:.1f} без отдачи",
            ))
        elif m.cpl is not None and m.cpl > norm:
            decisions.append(OptimizationDecision(
                ad_id=m.ad_id, action="PAUSE",
                reason=f"CPL {m.cpl:.2f} > нормы {norm:.2f} {cur}",
            ))
        elif m.leads == 0 and m.spend >= norm * 3:
            decisions.append(OptimizationDecision(
                ad_id=m.ad_id, action="PAUSE",
                reason=f"Потрачено {m.spend:.2f} {cur}, 0 лидов",
            ))
        else:
            decisions.append(OptimizationDecision(
                ad_id=m.ad_id, action="KEEP", reason="В пределах нормы",
            ))
    return decisions


def decide_scaling(
    metrics: list[AdMetrics],
    current_budgets: dict[str, float],
    *,
    target_cpl: Optional[float] = None,
    step: float = 1.3,
) -> list[OptimizationDecision]:
    """Правило масштабирования (чистая функция).

    Группа-победитель (CPL заметно ниже нормы и есть объём >= 3 лидов) получает +30%
    бюджета, но НЕ выше жёсткого потолка MAX_DAILY_BUDGET.
    """
    settings = get_settings()
    norm = target_cpl if target_cpl is not None else settings.target_cpl
    cap = settings.max_daily_budget
    good = norm * 0.7
    out: list[OptimizationDecision] = []
    for m in metrics:
        aid = m.adset_id or m.ad_id
        cur_budget = current_budgets.get(aid)
        if cur_budget is None:
            continue
        if m.cpl is not None and m.leads >= 3 and m.cpl <= good and cur_budget < cap:
            new_budget = min(round(cur_budget * step, 2), cap)
            if new_budget > cur_budget:
                out.append(OptimizationDecision(
                    ad_id=aid, action="SCALE", new_budget=new_budget,
                    reason=f"CPL {m.cpl:.2f} <= {good:.2f}: бюджет {cur_budget:.2f}→{new_budget:.2f} {settings.currency}",
                ))
    return out


def apply_decisions(
    decisions: list[OptimizationDecision],
    *,
    client: Optional[FacebookAdsClient] = None,
) -> dict[str, list[str]]:
    """Исполняет решения. PAUSE — всегда; SCALE — только вне DRY_RUN (тратит больше).

    Возвращает {'paused': [...], 'scaled': [...]}.
    """
    settings = get_settings()
    fb = client or FacebookAdsClient()
    paused: list[str] = []
    scaled: list[str] = []
    for d in decisions:
        if d.action == "PAUSE":
            fb.pause_ad(d.ad_id)
            paused.append(d.ad_id)
            log.warning("Пауза %s — %s", d.ad_id, d.reason)
        elif d.action == "SCALE" and d.new_budget is not None:
            if settings.dry_run:
                log.info("DRY_RUN: масштабирование %s пропущено (%s)", d.ad_id, d.reason)
                continue
            fb.update_adset_budget(d.ad_id, d.new_budget)
            scaled.append(d.ad_id)
            log.info("Масштабирование %s — %s", d.ad_id, d.reason)
    return {"paused": paused, "scaled": scaled}


def run_optimizer(
    ad_ids: list[str],
    *,
    target_cpl: Optional[float] = None,
    execute: bool = True,
    client: Optional[FacebookAdsClient] = None,
) -> tuple[list[AdMetrics], list[OptimizationDecision]]:
    """Полный цикл пауз по объявлениям: метрики -> решить -> (опц.) исполнить."""
    fb = client or FacebookAdsClient()
    metrics = collect_metrics(ad_ids, client=fb)
    decisions = decide(metrics, target_cpl=target_cpl)
    if execute:
        apply_decisions(decisions, client=fb)
    return metrics, decisions


def run_scaling(
    adset_ids: list[str],
    *,
    target_cpl: Optional[float] = None,
    step: float = 1.3,
    execute: bool = True,
    client: Optional[FacebookAdsClient] = None,
) -> tuple[list[AdMetrics], list[OptimizationDecision]]:
    """Масштабирование групп-победителей: метрики + текущий бюджет -> решить -> исполнить."""
    fb = client or FacebookAdsClient()
    metrics: list[AdMetrics] = []
    budgets: dict[str, float] = {}
    for aid in adset_ids:
        metrics.append(_metrics_from_insights(aid, fb.get_insights(aid), adset_id=aid))
        info = fb.get_adset(aid)
        if info.get("daily_budget") is not None:
            budgets[aid] = info["daily_budget"]
    decisions = decide_scaling(metrics, budgets, target_cpl=target_cpl, step=step)
    if execute:
        apply_decisions(decisions, client=fb)
    return metrics, decisions
