"""Единая точка чтения конфигурации из .env.

Всё приложение берёт настройки только отсюда. Секреты в код не хардкодятся.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- LLM ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-opus-4-8", alias="LLM_MODEL")
    llm_model_cheap: str = Field(default="claude-sonnet-5", alias="LLM_MODEL_CHEAP")

    # --- Meta Ads ---
    meta_app_id: str = Field(default="", alias="META_APP_ID")
    meta_app_secret: str = Field(default="", alias="META_APP_SECRET")
    meta_access_token: str = Field(default="", alias="META_ACCESS_TOKEN")
    meta_ad_account_id: str = Field(default="", alias="META_AD_ACCOUNT_ID")
    meta_page_id: str = Field(default="", alias="META_PAGE_ID")
    meta_pixel_id: str = Field(default="", alias="META_PIXEL_ID")
    meta_api_version: str = Field(default="v21.0", alias="META_API_VERSION")

    # --- Картинки / Видео ---
    replicate_api_token: str = Field(default="", alias="REPLICATE_API_TOKEN")
    image_model: str = Field(default="black-forest-labs/flux-1.1-pro", alias="IMAGE_MODEL")
    video_model: str = Field(default="minimax/video-01", alias="VIDEO_MODEL")

    # --- История ---
    db_path: str = Field(default="targetolog.db", alias="DB_PATH")
    # Если задан Postgres-URL (Neon) — история пишется туда (постоянно), иначе SQLite.
    database_url: str = Field(default="", alias="DATABASE_URL")

    # --- Telegram ---
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # --- API / доступ ---
    # Токен для FastAPI-бэкенда. Если задан — все запросы к API требуют заголовок
    # X-API-Token. Пусто = без авторизации (локальная разработка).
    api_token: str = Field(default="", alias="API_TOKEN")

    # --- Предохранители ---
    dry_run: bool = Field(default=True, alias="DRY_RUN")
    max_daily_budget: float = Field(default=10.0, alias="MAX_DAILY_BUDGET")
    target_cpl: float = Field(default=5.0, alias="TARGET_CPL")
    currency: str = Field(default="USD", alias="CURRENCY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def ad_account_path(self) -> str:
        """act_<id> — так Meta ожидает рекламный кабинет в путях API."""
        acc = self.meta_ad_account_id
        return acc if acc.startswith("act_") else f"act_{acc}"


@lru_cache
def get_settings() -> Settings:
    """Кешированный синглтон настроек."""
    return Settings()
