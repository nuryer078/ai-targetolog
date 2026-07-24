"""Генерация рекламных баннеров через Replicate (Flux.1).

Возвращает URL готовой картинки. Если токен не задан или SDK нет — кидает понятную
ошибку, чтобы панель показала «картинки недоступны», а не падала молча.
"""
from __future__ import annotations

from config.settings import get_settings
from services.logger import get_logger

log = get_logger("image_gen")


class ImageGenError(RuntimeError):
    pass


def generate_image(prompt: str, aspect_ratio: str = "1:1") -> str:
    """Генерирует картинку по промпту, возвращает URL.

    aspect_ratio: "1:1" (лента), "4:5" (моб. лента), "9:16" (сторис).
    """
    settings = get_settings()
    if not settings.replicate_api_token:
        raise ImageGenError(
            "REPLICATE_API_TOKEN не задан — генерация картинок недоступна. Заполни .env."
        )
    try:
        import replicate
    except ImportError as exc:  # pragma: no cover
        raise ImageGenError("Пакет replicate не установлен: pip install replicate") from exc

    client = replicate.Client(api_token=settings.replicate_api_token)
    log.info("Генерирую картинку (%s): %.80s...", aspect_ratio, prompt)
    output = client.run(
        settings.image_model,
        input={
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpg",
            "safety_tolerance": 2,
        },
    )
    url = _first_url(output)
    if not url:
        raise ImageGenError(f"Replicate не вернул URL картинки: {output!r}")
    log.info("Картинка готова: %s", url)
    return url


def _first_url(output) -> str | None:
    """Replicate возвращает либо строку-URL, либо список, либо file-объект."""
    if output is None:
        return None
    if isinstance(output, str):
        return output
    if isinstance(output, (list, tuple)):
        return _first_url(output[0]) if output else None
    # FileOutput объект новых версий SDK
    url = getattr(output, "url", None)
    return url if isinstance(url, str) else (str(output) if output else None)
