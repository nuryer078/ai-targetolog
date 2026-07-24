"""Media Buyer Agent (Технический таргетолог).

Принимает готовые креативы и разворачивает в Meta структуру:
    Campaign -> AdSet (таргетинг, гео, бюджет) -> Ads (тексты + баннеры).

СОЗНАТЕЛЬНО детерминированный, а не «свободный» LLM-агент: когда на кону реальные
деньги, порядок и границы действий должны быть жёстко зашиты в код и проходить через
предохранители, а не зависеть от формулировки промпта. LLM отвечает за креативы;
за трату бюджета отвечает предсказуемый код.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config.settings import get_settings
from services.logger import get_logger
from services.state import Creative, LaunchedCampaign, ProductBrief
from tools.facebook_api import FacebookAdsClient

log = get_logger("media_buyer")


def _slug(text: str) -> str:
    """Простой slug для UTM: латиница/цифры, остальное в дефис."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "campaign"


def append_utm(url: str, campaign: str) -> str:
    """Добавляет UTM-метки к ссылке (не перетирая уже существующие).

    Без меток сквозная аналитика слепая — таргетолог всегда размечает трафик.
    """
    if not url:
        return url
    parts = urlparse(url if "://" in url else f"https://{url}")
    query = dict(parse_qsl(parts.query))
    for key, val in {
        "utm_source": "facebook",
        "utm_medium": "paid_social",
        "utm_campaign": _slug(campaign),
    }.items():
        query.setdefault(key, val)
    return urlunparse(parts._replace(query=urlencode(query)))

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
    custom_audiences: Optional[list[str]] = None,
    excluded_audiences: Optional[list[str]] = None,
    age_min: int = 18,
    age_max: int = 65,
) -> dict:
    """Строит таргетинг из брифа: гео + возраст + интересы + аудитории.

    interests — [{id, name}] из search_interests (в flexible_spec).
    custom_audiences — id аудиторий для таргета (ретаргетинг/LAL).
    excluded_audiences — id аудиторий для исключения (напр. уже купившие).
    """
    targeting: dict = {
        "geo_locations": {"countries": [c.upper() for c in brief.geo]},
        "age_min": age_min,
        "age_max": age_max,
    }
    clean = [{"id": i["id"], "name": i.get("name")} for i in (interests or []) if i.get("id")]
    if clean:
        targeting["flexible_spec"] = [{"interests": clean}]
    if custom_audiences:
        targeting["custom_audiences"] = [{"id": a} for a in custom_audiences]
    if excluded_audiences:
        targeting["excluded_custom_audiences"] = [{"id": a} for a in excluded_audiences]
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
    custom_audiences: Optional[list[str]] = None,
    excluded_audiences: Optional[list[str]] = None,
    campaign_budget: Optional[float] = None,
    client: Optional[FacebookAdsClient] = None,
) -> LaunchedCampaign:
    """Разворачивает кампанию в Meta и возвращает её структуру.

    activate=True просит статус ACTIVE, но в режиме DRY_RUN предохранитель всё равно
    оставит PAUSED. Бюджет сверяется с жёстким лимитом внутри клиента.
    interests / custom_audiences / excluded_audiences — таргетинг.
    campaign_budget — если задан, включается CBO (бюджет на кампании); тогда daily_budget
    группы не используется.
    """
    settings = get_settings()
    fb = client or FacebookAdsClient(settings)

    if not creatives:
        raise ValueError("Нет ни одного креатива для запуска.")

    obj_r, optgoal_r, promoted = resolve_campaign_config(brief.goal, settings.meta_pixel_id)
    objective = objective or obj_r
    optimization_goal = optimization_goal or optgoal_r
    targeting = targeting or build_targeting(
        brief, interests=interests,
        custom_audiences=custom_audiences, excluded_audiences=excluded_audiences,
    )
    want_status = "ACTIVE" if activate else "PAUSED"
    cbo = campaign_budget is not None
    link = append_utm(brief.landing_url, brief.name)

    log.info(
        "Запуск: «%s», %s, креативов=%d, activate=%s",
        brief.name,
        f"CBO-бюджет/день={campaign_budget}" if cbo else f"бюджет группы/день={daily_budget}",
        len(creatives), activate,
    )

    # 1) Кампания (при CBO бюджет живёт здесь)
    campaign = fb.create_campaign(
        name=f"[AI] {brief.name}",
        objective=objective,
        status=want_status,
        daily_budget=campaign_budget if cbo else None,
    )
    campaign_id = campaign["id"]

    # 2) Группа объявлений (при CBO — без своего бюджета)
    adset = fb.create_adset(
        name=f"[AI] {brief.name} — {'/'.join(brief.geo)}",
        campaign_id=campaign_id,
        daily_budget=None if cbo else daily_budget,
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
            link=link,
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
