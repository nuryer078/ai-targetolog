"""Тесты предохранителей — самый важный слой: он защищает бюджет."""
from __future__ import annotations

import pytest

from services import guardrails
from services.guardrails import BudgetExceeded, KillSwitchActive


def test_budget_within_limit_ok():
    assert guardrails.validate_daily_budget(5.0) == 5.0


def test_budget_over_limit_raises():
    with pytest.raises(BudgetExceeded):
        guardrails.validate_daily_budget(999.0)  # лимит в тестах = 10


def test_budget_zero_or_negative_raises():
    with pytest.raises(BudgetExceeded):
        guardrails.validate_daily_budget(0)
    with pytest.raises(BudgetExceeded):
        guardrails.validate_daily_budget(-3)


def test_dry_run_forces_paused():
    # DRY_RUN=true в тестовом окружении
    assert guardrails.effective_status("ACTIVE") == "PAUSED"
    assert guardrails.effective_status("PAUSED") == "PAUSED"


def test_live_mode_keeps_active(set_env):
    set_env(DRY_RUN="false")
    assert guardrails.effective_status("ACTIVE") == "ACTIVE"
    assert guardrails.effective_status("PAUSED") == "PAUSED"


def test_kill_switch_blocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / guardrails.KILL_SWITCH_FILE).write_text("stop")
    with pytest.raises(KillSwitchActive):
        guardrails.check_kill_switch()


def test_preflight_combines_checks():
    budget, status = guardrails.preflight(4.0, "ACTIVE")
    assert budget == 4.0
    assert status == "PAUSED"  # dry-run

    with pytest.raises(BudgetExceeded):
        guardrails.preflight(50.0, "ACTIVE")
