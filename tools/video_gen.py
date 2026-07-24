"""Генерация рекламного видео (Reels/лента) через Replicate.

Если есть картинка креатива — делаем image-to-video (видео «оживляет» баннер),
иначе text-to-video по промпту. Возвращает URL готового видео.
"""
from __future__ import annotations

from typing import Optional

from config.settings import get_settings
from services.logger import get_logger

log = get_logger("video_gen")


class VideoGenError(RuntimeError):
    pass


def generate_video(prompt: str, image_url: Optional[str] = None) -> str:
    """Генерирует видео по промпту (+опц. стартовый кадр). Возвращает URL."""
    settings = get_settings()
    if not settings.replicate_api_token:
        raise VideoGenError(
            "REPLICATE_API_TOKEN не задан — генерация видео недоступна. Заполни .env."
        )
    try:
        import replicate
    except ImportError as exc:  # pragma: no cover
        raise VideoGenError("Пакет replicate не установлен: pip install replicate") from exc

    client = replicate.Client(api_token=settings.replicate_api_token)
    payload: dict = {"prompt": prompt}
    if image_url:
        payload["first_frame_image"] = image_url  # image-to-video
    log.info("Генерирую видео (%s): %.70s...", "img2vid" if image_url else "txt2vid", prompt)
    output = client.run(settings.video_model, input=payload)

    from tools.image_gen import _first_url  # тот же разбор форматов вывода Replicate

    url = _first_url(output)
    if not url:
        raise VideoGenError(f"Replicate не вернул URL видео: {output!r}")
    log.info("Видео готово: %s", url)
    return url
