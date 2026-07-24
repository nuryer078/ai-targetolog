"""Статистика A/B-тестов: определение победителя и его значимости.

Профессиональный подход: не выбираем «победителя» на глаз по первому лиду, а проверяем
разницу конверсий двухвыборочным z-тестом. Победитель объявляется только при
статистической значимости и достаточном объёме данных.
"""
from __future__ import annotations

import math
from typing import Optional

from services.state import AdMetrics, OptimizationDecision


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def two_proportion_pvalue(x1: int, n1: int, x2: int, n2: int) -> float:
    """Двусторонний p-value различия двух долей (z-тест пропорций)."""
    if n1 <= 0 or n2 <= 0:
        return 1.0
    x1, x2 = min(x1, n1), min(x2, n2)
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    denom = p * (1 - p) * (1 / n1 + 1 / n2)
    if denom <= 0:
        return 1.0
    z = (p1 - p2) / math.sqrt(denom)
    return 2 * (1 - _normal_cdf(abs(z)))


def _successes_trials(m: AdMetrics, metric: str) -> tuple[int, int]:
    """Успехи/испытания под выбранную метрику конверсии."""
    if metric == "lead_per_click":
        return min(m.leads, m.clicks), m.clicks
    # ctr: клики на показы
    return min(m.clicks, m.impressions), m.impressions


def _pick_metric(metrics: list[AdMetrics]) -> str:
    """Если везде есть клики и хоть где-то лиды — меряем конверсию в лид, иначе CTR."""
    if all(m.clicks > 0 for m in metrics) and any(m.leads > 0 for m in metrics):
        return "lead_per_click"
    return "ctr"


def evaluate_ab(
    metrics: list[AdMetrics],
    *,
    alpha: float = 0.05,
    min_trials: int = 100,
    metric: str = "auto",
) -> dict:
    """Оценивает A/B: лучший вариант, p-value против остальных, значимость.

    Возвращает словарь с вариантами, победителем (или None), p_value, significant, reason.
    """
    if len(metrics) < 2:
        return {
            "metric": None, "variants": [], "winner": None, "p_value": 1.0,
            "significant": False, "enough_data": False,
            "reason": "Для A/B нужно минимум 2 варианта.",
        }
    if metric == "auto":
        metric = _pick_metric(metrics)

    variants = []
    for m in metrics:
        s, t = _successes_trials(m, metric)
        variants.append({
            "ad_id": m.ad_id, "successes": s, "trials": t,
            "rate": (s / t) if t > 0 else 0.0,
        })

    best = max(variants, key=lambda v: v["rate"])
    others_s = sum(v["successes"] for v in variants if v is not best)
    others_t = sum(v["trials"] for v in variants if v is not best)

    p_value = two_proportion_pvalue(best["successes"], best["trials"], others_s, others_t)
    enough = best["trials"] >= min_trials and others_t >= min_trials
    significant = bool(enough and p_value < alpha and best["rate"] > 0)

    if significant:
        reason = f"Победитель {best['ad_id']} значим (p={p_value:.3f} < {alpha})."
    elif not enough:
        reason = f"Мало данных (нужно ≥{min_trials} испытаний на группу). Дай тесту открутиться."
    else:
        reason = f"Разница пока не значима (p={p_value:.3f} ≥ {alpha})."

    return {
        "metric": metric, "variants": variants,
        "winner": best["ad_id"] if significant else None,
        "p_value": p_value, "significant": significant, "enough_data": enough,
        "reason": reason,
    }


def auto_select_winner(
    metrics: list[AdMetrics],
    *,
    alpha: float = 0.05,
    min_trials: int = 100,
    execute: bool = True,
    client=None,
) -> tuple[dict, list[OptimizationDecision]]:
    """Если победитель значим — паузит проигравшие варианты, оставляет победителя.

    Пауза — снижение риска, поэтому выполняется даже в DRY_RUN (там объявления и так PAUSED).
    """
    res = evaluate_ab(metrics, alpha=alpha, min_trials=min_trials)
    decisions: list[OptimizationDecision] = []
    if res["significant"]:
        winner = res["winner"]
        for m in metrics:
            if m.ad_id == winner:
                decisions.append(OptimizationDecision(
                    ad_id=m.ad_id, action="KEEP", reason="🏆 Победитель A/B",
                ))
            else:
                decisions.append(OptimizationDecision(
                    ad_id=m.ad_id, action="PAUSE",
                    reason=f"Проиграл A/B (p={res['p_value']:.3f})",
                ))
    else:
        for m in metrics:
            decisions.append(OptimizationDecision(
                ad_id=m.ad_id, action="KEEP", reason=res["reason"],
            ))

    if execute:
        from agents.optimizer import apply_decisions

        apply_decisions(decisions, client=client)
    return res, decisions
