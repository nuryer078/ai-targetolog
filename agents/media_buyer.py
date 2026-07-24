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

def resolve_campaign_config(goal: str, pixel_id: str) -> tuple[str, str, Optional[dict]]:
    """По цели брифа и наличию пикселя выбирает objective/optimization_goal/promoted_object.

    Профессиональная логика: если есть пиксель — оптимизируем на РЕАЛЬНЫЕ конверсии
    (лиды/покупки), а не на клики. Без пикселя честно откатываемся на клики и пишем
    предупреждение, чтобы не сжигать бюджет на непонятную оптимизацию.
    """
    g = goal.upper()
    if g == "AWARENESS":
        return "OUTCOME_AWARENESS", "REACH", None
    if g in ("LEAD_GENERATION", "SALES"):
        if pixel_id:
            if g == "LEAD_GENERATION":
                return "OUTCOME_LEADS", "OFFSITE_CONVERSIONS", {
                    "pixel_id": pixel_id, "custom_event_type": "LEAD",
                }
            return "OUTCOME_SALES", "OFFSITE_CONVERSIONS", {
                "pixel_id": pixel_id, "custom_event_type": "PURCHASE",
            }
        log.warning(
            "META_PIXEL_ID не задан — цель %s оптимизируем на КЛИКИ, а не на конверсии. "
            "Добавь пиксель в .env для оптимизации на лиды/покупки.", g,
        )
        return "OUTCOME_TRAFFIC", "LINK_CLICKS", None
    return "OUTCOME_TRAFFIC", "LINK_CLICKS", None


def build_targeting(
    brief: ProductBrief,
    interests: Optional[list[dict]] = None,
    age_min: int = 18,
    age_max: int = 65,
) -> dict:
    """Строит таргетинг из брифа: гео + возраст + (опц.) интересы.

    interests — список {id, name} из FacebookAdsClient.search_interests. Кладём в
    flexible_spec (текущий рекомендованный способ Meta для интересов).
    """
    targeting: dict = {
        "geo_locations": {"countries": [c.upper() for c in brief.geo]},
        "age_min": age_min,
        "age_max": age_max,
    }
    clean = [{"id": i["id"], "name": i.get("name")} for i in (interests or []) if i.get("id")]
    if clean:
        targeting["flexible_spec"] = [{"interests": clean}]
    return targeting


def resolve_interests(
    keywords: list[str],
    client: FacebookAdsClient,
    max_interests: int = 5,
) -> list[dict]:
    """Превращает ключевые слова в реальные интересы Meta (топ-1 совпадение на слово)."""
    found: list[dict] = []
    seen: set[str] = set()
    for kw in keywords:
        try:
            matches = client.search_interests(kw, limit=1)
        except Exception as exc:  # noqa: BLE001 — один неудачный поиск не рушит запуск
            log.warning("Поиск интереса «%s» не удался: %s", kw, exc)
            continue
        if matches and matches[0]["id"] not in seen:
            seen.add(matches[0]["id"])
            found.append(matches[0])
        if len(found) >= max_interests:
            break
    return found


def launch(
    brief: ProductBrief,
    creatives: list[Creative],
    daily_budget: float,
    *,
    activate: bool = False,
    objective: Optional[str] = None,
    optimization_goal: Optional[str] = None,
    targeting: Optional[dict] = None,
    interests: Optional[list[dict]] = None,
    client: Optional[FacebookAdsClient] = None,
) -> LaunchedCampaign:
    """Разворачивает кампанию в Meta и возвращает её структуру.

    activate=True просит статус ACTIVE, но в режиме DRY_RUN предохранитель всё равно
    оставит PAUSED. daily_budget сверяется с жёстким лимитом внутри клиента.
    interests — список интересов {id, name} для сужения аудитории (опц.).
    """
    settings = get_settings()
    fb = client or FacebookAdsClient(settings)

    if not creatives:
        raise ValueError("Нет ни одного креатива для запуска.")

    obj_r, optgoal_r, promoted = resolve_campaign_config(brief.goal, settings.meta_pixel_id)
    objective = objective or obj_r
    optimization_goal = optimization_goal or optgoal_r
    targeting = targeting or build_targeting(brief, interests=interests)
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
        promoted_object=promoted,
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
