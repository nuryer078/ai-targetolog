"""Общие фикстуры тестов.

Настройки читаются через кешированный get_settings(); чтобы тесты были изолированы,
перед каждым сбрасываем кеш и задаём предсказуемые переменные окружения.
"""
from __future__ import annotations

import os

import pytest

from config.settings import get_settings

_BASE_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "META_ACCESS_TOKEN": "test-token",
    "META_AD_ACCOUNT_ID": "1234567890",
    "META_PAGE_ID": "111",
    "META_API_VERSION": "v21.0",
    "DRY_RUN": "true",
    "MAX_DAILY_BUDGET": "10.0",
    "TARGET_CPL": "5.0",
    "CURRENCY": "USD",
}


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    """Задаёт базовое окружение и сбрасывает кеш настроек до и после теста.

    Переменные окружения приоритетнее .env в pydantic-settings, поэтому реальный
    .env проекта на эти значения не влияет.
    """
    for k, v in _BASE_ENV.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def set_env(monkeypatch):
    """Позволяет тесту переопределить отдельные переменные и сбросить кеш."""
    def _set(**kwargs):
        for k, v in kwargs.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()
        return get_settings()

    return _set


@pytest.fixture(autouse=True)
def no_kill_switch():
    """Гарантирует отсутствие файла аварийного стопа в тестах."""
    from services.guardrails import KILL_SWITCH_FILE

    if os.path.exists(KILL_SWITCH_FILE):
        os.remove(KILL_SWITCH_FILE)
    yield
    if os.path.exists(KILL_SWITCH_FILE):
        os.remove(KILL_SWITCH_FILE)
