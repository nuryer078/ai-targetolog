"""Creative & Copy Agent (Копирайтер/Дизайнер).

Из идей аналитика делает готовые креативы: продающий текст по фреймворку (AIDA/PAS),
заголовок, описание и детальный промпт для генерации баннера. Генерацию самой картинки
выносим отдельной функцией — чтобы панель могла показать текст сразу, а картинку
догенерировать/перегенерировать по кнопке.
"""
from __future__ import annotations

from config.settings import get_settings
from services.llm import complete_json
from services.logger import get_logger
from services.state import AdIdea, Creative, ProductBrief
from tools.image_gen import generate_image

log = get_logger("creative")

SYSTEM = """Ты — креативный копирайтер и арт-директор performance-рекламы в Meta Ads.
По идее объявления сделай готовый креатив, используя указанный фреймворк (AIDA или PAS).

Верни СТРОГО валидный JSON без markdown:
{
  "framework": "AIDA" | "PAS",
  "primary_text": "основной текст объявления, 2-4 коротких абзаца, с эмодзи в меру, заканчивается призывом",
  "headline": "заголовок до 40 символов",
  "description": "описание до 30 символов",
  "image_prompt": "детальный промпт НА АНГЛИЙСКОМ для генератора изображений: сцена, стиль, свет, композиция, настроение. Без текста на картинке."
}
Пиши текст на языке идеи/оффера. Заголовок и текст — продающие и конкретные,
без кликбейта и запрещённых Meta обещаний (гарантий дохода, «до/после» по здоровью и т.п.)."""


def run_creative(
    brief: ProductBrief,
    idea: AdIdea,
    framework: str = "AIDA",
    model: str | None = None,
) -> Creative:
    """Генерирует текстовую часть креатива (без картинки)."""
    settings = get_settings()
    user = (
        f"Продукт: {brief.name} — {brief.description}\n"
        f"Сегмент ЦА: {idea.persona}\n"
        f"Оффер: {idea.offer}\n"
        f"Рекламный угол: {idea.angle}\n"
        f"Посадочная: {brief.landing_url}\n"
        f"Используй фреймворк: {framework}"
    )
    log.info("Копирайтер пишет креатив (%s) под угол «%s»", framework, idea.angle)
    data = complete_json(SYSTEM, user, model=model or settings.llm_model_cheap)

    return Creative(
        idea_angle=idea.angle,
        framework=data.get("framework", framework),
        primary_text=data["primary_text"],
        headline=data["headline"],
        description=data["description"],
        image_prompt=data["image_prompt"],
    )


def generate_creatives(
    brief: ProductBrief,
    ideas: list[AdIdea],
    framework: str = "AIDA",
    model: str | None = None,
) -> list[Creative]:
    """Пакетно готовит тексты креативов по списку идей."""
    creatives: list[Creative] = []
    for idea in ideas:
        try:
            creatives.append(run_creative(brief, idea, framework=framework, model=model))
        except Exception as exc:  # noqa: BLE001 — один сбойный креатив не рушит пачку
            log.error("Не удалось сделать креатив под «%s»: %s", idea.angle, exc)
    return creatives


def attach_image(creative: Creative, aspect_ratio: str = "1:1") -> Creative:
    """Генерирует баннер для креатива и проставляет image_url. Возвращает тот же объект."""
    creative.image_url = generate_image(creative.image_prompt, aspect_ratio=aspect_ratio)
    return creative


def attach_video(creative: Creative, use_image_as_first_frame: bool = True) -> Creative:
    """Генерирует видео для креатива (Reels/лента) и проставляет video_url.

    Если есть баннер — «оживляем» его (image-to-video) для визуальной связности.
    Обложкой видео-объявления служит image_url, поэтому баннер желателен.
    """
    from tools.video_gen import generate_video

    prompt = creative.video_prompt or creative.image_prompt
    first_frame = creative.image_url if use_image_as_first_frame else None
    creative.video_url = generate_video(prompt, image_url=first_frame)
    return creative
