"""Media Buyer Agent (Технический таргетолог).

Принимает готовые креативы и разворачивает в Meta структуру:
    Campaign -> AdSet (таргетинг, гео, бюджет) -> Ads (тексты + баннеры).

СОЗНАТЕЛЬНО детерминированный, а не «свободный» LLM-агент: когда на кону реальные
деньги, порядок и границы действий должны быть жёстко зашиты в код и проходить через
предохранители, а не зависеть от формулировки промпта. LLM отвечает за креативы;
за трату бюджета отвечает предсказуемый код.
"""
from __future__ import annotations

from typing import Optional

from config.settings import get_settings
from services.logger import get_logger
from services.state import Creative, LaunchedCampaign, ProductBrief
from tools.facebook_api import FacebookAdsClient

log = get_logger("media_buyer")

# Соответствие бизнес-цели брифа и настроек Meta.
_GOAL_MAP = {
    "TRAFFIC": ("OUTCOME_TRAFFIC", "LINK_CLICKS"),
    "LEAD_GENERATION": ("OUTCOME_TRAFFIC", "LINK_CLICKS"),  # без пикселя оптимизируем на клики
    "SALES": ("OUTCOME_TRAFFIC", "LINK_CLICKS"),
    "AWARENESS": ("OUTCOME_AWARENESS", "REACH"),
}


def build_targeting(brief: ProductBrief, age_min: int = 18, age_max: int = 65) -> dict:
    """Строит валидный таргетинг из брифа: гео + возраст.

    Держим широко и безопасно (гео+возраст всегда валидны). Интересы можно добавить
    вручную в панели — они требуют точных ID из Meta.
    """
    return {
        "geo_locations": {"countries": [c.upper() for c in brief.geo]},
        "age_min": age_min,
        "age_max": age_max,
    }


def launch(
    brief: ProductBrief,
    creatives: list[Creative],
    daily_budget: float,
    *,
    activate: bool = False,
    objective: Optional[str] = None,
    optimization_goal: Optional[str] = None,
    targeting: Optional[dict] = None,
    client: Optional[FacebookAdsClient] = None,
) -> LaunchedCampaign:
    """Разворачивает кампанию в Meta и возвращает её структуру.

    activate=True просит статус ACTIVE, но в режиме DRY_RUN предохранитель всё равно
    оставит PAUSED. daily_budget сверяется с жёстким лимитом внутри клиента.
    """
    settings = get_settings()
    fb = client or FacebookAdsClient(settings)

    if not creatives:
        raise ValueError("Нет ни одного креатива для запуска.")

    obj_default, optgoal_default = _GOAL_MAP.get(brief.goal.upper(), _GOAL_MAP["TRAFFIC"])
    objective = objective or obj_default
    optimization_goal = optimization_goal or optgoal_default
    targeting = targeting or build_targeting(brief)
    want_status = "ACTIVE" if activate else "PAUSED"

    log.info(
        "Запуск: продукт «%s», бюджет/день=%.2f %s, креативов=%d, activate=%s",
        brief.name, daily_budget, settings.currency, len(creatives), activate,
    )

    # 1) Кампания
    campaign = fb.create_campaign(
        name=f"[AI] {brief.name}",
        objective=objective,
        status=want_status,
    )
    campaign_id = campaign["id"]

    # 2) Группа объявлений (один AdSet, внутри — несколько объявлений на тест креативов)
    adset = fb.create_adset(
        name=f"[AI] {brief.name} — {'/'.join(brief.geo)}",
        campaign_id=campaign_id,
        daily_budget=daily_budget,
        targeting=targeting,
        optimization_goal=optimization_goal,
        status=want_status,
    )
    adset_id = adset["id"]

    # 3) Объявления
    ad_ids: list[str] = []
    for i, cr in enumerate(creatives, start=1):
        if not cr.image_url:
            log.warning("Креатив «%s» без картинки — пропускаю.", cr.idea_angle)
            continue
        image_hash = fb.upload_image_from_url(cr.image_url)
        creative_obj = fb.create_ad_creative(
            name=f"[AI] creative {i} — {brief.name}",
            message=cr.primary_text,
            headline=cr.headline,
            description=cr.description,
            link=brief.landing_url,
            image_hash=image_hash,
        )
        ad = fb.create_ad(
            name=f"[AI] ad {i} — {cr.idea_angle}",
            adset_id=adset_id,
            creative_id=creative_obj["id"],
            status=want_status,
        )
        ad_ids.append(ad["id"])

    if not ad_ids:
        raise ValueError(
            "Ни одно объявление не создано — у выбранных креативов нет картинок. "
            "Сгенерируй баннеры перед запуском."
        )

    final_status = "PAUSED" if settings.dry_run else want_status
    note = (
        "🧪 Режим DRY_RUN: всё создано в PAUSED, бюджет НЕ откручивается. "
        "Чтобы запустить реально — выключи DRY_RUN и активируй кампанию."
        if settings.dry_run
        else "🔴 Боевой режим."
    )
    result = LaunchedCampaign(
        campaign_id=campaign_id,
        adset_ids=[adset_id],
        ad_ids=ad_ids,
        status=final_status,
        dry_run=settings.dry_run,
        note=note,
    )
    log.info("Готово: кампания %s, объявлений %d, статус %s", campaign_id, len(ad_ids), final_status)
    return result
