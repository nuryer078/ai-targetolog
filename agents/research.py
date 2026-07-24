"""Research Agent (Аналитик).

Из брифа продукта выдаёт структурированный JSON: портреты ЦА (боли, возражения,
триггеры) и идеи объявлений (оффер + рекламный угол). Никаких сторонних инструментов —
только рассуждение LLM, поэтому используем разовый JSON-вызов.
"""
from __future__ import annotations

from config.settings import get_settings
from services.llm import complete_json
from services.logger import get_logger
from services.state import AdIdea, AudiencePersona, ProductBrief, ResearchResult

log = get_logger("research")

SYSTEM = """Ты — сильный маркетинговый аналитик performance-агентства.
Твоя задача: по вводным о продукте определить сегменты целевой аудитории и идеи
для рекламных объявлений в Meta Ads (Facebook/Instagram).

Верни СТРОГО валидный JSON без markdown-обёрток, по схеме:
{
  "personas": [
    {
      "name": "краткое имя сегмента, напр. 'Молодые мамы 25-34'",
      "pains": ["боль 1", "боль 2"],
      "objections": ["возражение 1", "возражение 2"],
      "triggers": ["что мотивирует купить 1", "триггер 2"]
    }
  ],
  "ideas": [
    {
      "persona": "имя сегмента из personas",
      "offer": "конкретный оффер под этот сегмент",
      "angle": "рекламный угол / главный посыл",
      "keywords": ["ключевое слово/интерес для таргетинга"]
    }
  ]
}
Правила: 2-4 сегмента, 3-6 идей. Пиши на языке брифа. Будь конкретным и продающим,
без воды. Интересы в keywords — реальные, пригодные для таргетинга Meta."""


def run_research(brief: ProductBrief, model: str | None = None) -> ResearchResult:
    """Запускает аналитика и возвращает валидированный результат."""
    settings = get_settings()
    user = _build_prompt(brief)
    log.info("Аналитик работает над продуктом «%s»", brief.name)
    data = complete_json(SYSTEM, user, model=model or settings.llm_model)

    personas = [AudiencePersona(**p) for p in data.get("personas", [])]
    ideas = [AdIdea(**i) for i in data.get("ideas", [])]
    if not ideas:
        raise ValueError("Аналитик не вернул ни одной идеи объявления.")
    log.info("Аналитик выдал %d сегментов и %d идей", len(personas), len(ideas))
    return ResearchResult(personas=personas, ideas=ideas)


def _build_prompt(brief: ProductBrief) -> str:
    parts = [
        f"Продукт/услуга: {brief.name}",
        f"Описание: {brief.description}",
        f"Гео: {', '.join(brief.geo)}",
        f"Цель рекламы: {brief.goal}",
        f"Посадочная: {brief.landing_url}",
    ]
    if brief.price:
        parts.append(f"Цена: {brief.price}")
    if brief.extra:
        parts.append(f"Доп. вводные: {brief.extra}")
    return "\n".join(parts)
