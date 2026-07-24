"""Предохранители: всё, что защищает рекламный бюджет от бага или галлюцинации LLM.

Правила ЗДЕСЬ, а не в агентах — чтобы их нельзя было случайно обойти в промпте.
"""
from __future__ import annotations

from config.settings import get_settings
from services.logger import get_logger

log = get_logger("guardrails")


class BudgetExceeded(Exception):
    """Попытка создать группу дороже жёсткого лимита."""


class KillSwitchActive(Exception):
    """Активен аварийный стоп — запуск запрещён."""


# Файл-флаг аварийного стопа. Если существует — ничего не запускается.
KILL_SWITCH_FILE = ".KILL_SWITCH"


def check_kill_switch() -> None:
    """Аварийный стоп. Создай файл .KILL_SWITCH в корне — и запуски заблокируются."""
    import os

    if os.path.exists(KILL_SWITCH_FILE):
        log.error("KILL SWITCH активен (файл %s) — запуск заблокирован.", KILL_SWITCH_FILE)
        raise KillSwitchActive(
            f"Активен аварийный стоп: удали файл {KILL_SWITCH_FILE}, чтобы разрешить запуск."
        )


def validate_daily_budget(daily_budget: float) -> float:
    """Проверка дневного бюджета группы против жёсткого потолка из .env.

    Возвращает бюджет, если он в пределах, иначе кидает BudgetExceeded.
    """
    settings = get_settings()
    cap = settings.max_daily_budget
    if daily_budget <= 0:
        raise BudgetExceeded(f"Дневной бюджет должен быть > 0, получено {daily_budget}.")
    if daily_budget > cap:
        raise BudgetExceeded(
            f"Дневной бюджет {daily_budget} {settings.currency} превышает лимит "
            f"MAX_DAILY_BUDGET={cap}. Запуск отклонён предохранителем."
        )
    log.info("Бюджет %.2f %s — в пределах лимита %.2f.", daily_budget, settings.currency, cap)
    return daily_budget


def effective_status(requested: str) -> str:
    """В режиме DRY_RUN любой запрос ACTIVE принудительно превращается в PAUSED.

    Это главный предохранитель: пока DRY_RUN=true, реально ничего не откручивается.
    """
    settings = get_settings()
    if settings.dry_run:
        if requested.upper() == "ACTIVE":
            log.warning("DRY_RUN=true: статус ACTIVE принудительно заменён на PAUSED.")
        return "PAUSED"
    return requested.upper()


def preflight(daily_budget: float, requested_status: str) -> tuple[float, str]:
    """Полная проверка перед созданием кампании. Возвращает (бюджет, безопасный_статус)."""
    check_kill_switch()
    budget = validate_daily_budget(daily_budget)
    status = effective_status(requested_status)
    return budget, status
