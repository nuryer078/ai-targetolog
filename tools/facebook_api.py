"""Клиент Meta Ads (Facebook Graph API).

Единственное место, где мы реально трогаем рекламный кабинет. Все создающие
методы проходят через предохранители (services.guardrails):
  * KILL_SWITCH — аварийный стоп;
  * жёсткий лимит дневного бюджета;
  * DRY_RUN принудительно делает статус PAUSED (ничего не откручивается).

Работаем прямыми HTTP-вызовами (requests), а не через тяжёлый SDK — так прозрачнее
и полностью тестируемо на моках.
"""
from __future__ import annotations

from typing import Any, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from services import guardrails
from services.logger import get_logger

log = get_logger("facebook_api")

# Валюты без дробной части: сумма в API указывается 1:1, а не в «центах».
_ZERO_DECIMAL = {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "TWD"}


class MetaApiError(RuntimeError):
    """Ошибка от Graph API (с телом ответа для диагностики)."""


class FacebookAdsClient:
    def __init__(self, settings=None) -> None:
        self.s = settings or get_settings()
        self.base = f"https://graph.facebook.com/{self.s.meta_api_version}"
        self._session = requests.Session()

    # ---------- низкоуровневые запросы ----------

    @retry(
        retry=retry_if_exception_type(requests.exceptions.ConnectionError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        path: str,
        *,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        files: Optional[dict] = None,
    ) -> dict[str, Any]:
        url = f"{self.base}/{path.lstrip('/')}"
        payload = dict(data or {})
        query = dict(params or {})
        # Токен всегда в query, чтобы не светить в теле логов.
        query["access_token"] = self.s.meta_access_token

        resp = self._session.request(
            method, url, data=payload or None, params=query, files=files, timeout=60
        )
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}

        if resp.status_code >= 400 or (isinstance(body, dict) and "error" in body):
            err = body.get("error", body) if isinstance(body, dict) else body
            log.error("Meta API %s %s -> %s: %s", method, path, resp.status_code, err)
            raise MetaApiError(f"{method} {path}: {err}")
        return body

    # ---------- деньги ----------

    def _to_minor_units(self, amount: float) -> int:
        """Перевод суммы в минимальные единицы валюты кабинета для API."""
        if self.s.currency.upper() in _ZERO_DECIMAL:
            return int(round(amount))
        return int(round(amount * 100))

    def _from_minor_units(self, amount: float) -> float:
        """Обратный перевод из минимальных единиц в валюту (для чтения бюджета)."""
        if self.s.currency.upper() in _ZERO_DECIMAL:
            return float(amount)
        return round(float(amount) / 100, 2)

    # ---------- кампания ----------

    def create_campaign(
        self,
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        status: str = "PAUSED",
        special_ad_categories: Optional[list[str]] = None,
        *,
        daily_budget: Optional[float] = None,
        bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
    ) -> dict[str, Any]:
        """Создаёт рекламную кампанию (верхний уровень).

        objective — цель ODAX: OUTCOME_TRAFFIC / OUTCOME_LEADS / OUTCOME_SALES и т.д.
        daily_budget — если задан, включается CBO (Advantage+ бюджет кампании): Meta
        сама распределяет бюджет между группами. Проходит через тот же предохранитель.
        """
        guardrails.check_kill_switch()
        safe_status = guardrails.effective_status(status)
        data: dict[str, Any] = {
            "name": name,
            "objective": objective,
            "status": safe_status,
            "special_ad_categories": str(special_ad_categories or []).replace("'", '"'),
        }
        if daily_budget is not None:
            budget = guardrails.validate_daily_budget(daily_budget)
            data["daily_budget"] = self._to_minor_units(budget)
            data["bid_strategy"] = bid_strategy
        body = self._request("POST", f"{self.s.ad_account_path}/campaigns", data=data)
        log.info(
            "Кампания создана: %s (%s)%s",
            body.get("id"), safe_status,
            f", CBO-бюджет/день={daily_budget}" if daily_budget else "",
        )
        return body

    # ---------- группа объявлений ----------

    def create_adset(
        self,
        name: str,
        campaign_id: str,
        daily_budget: Optional[float],
        targeting: dict[str, Any],
        *,
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
        status: str = "PAUSED",
        promoted_object: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Создаёт группу объявлений (таргетинг + бюджет).

        daily_budget — В ВАЛЮТЕ кабинета (не в центах): предохранитель сверит с лимитом.
        Если None — бюджет живёт на кампании (CBO), у группы своего бюджета нет.
        """
        data: dict[str, Any] = {
            "name": name,
            "campaign_id": campaign_id,
            "optimization_goal": optimization_goal,
            "billing_event": billing_event,
            "targeting": _json(targeting),
        }
        if daily_budget is None:
            # CBO: бюджет на кампании. Предохранитель бюджета уже отработал там.
            guardrails.check_kill_switch()
            data["status"] = guardrails.effective_status(status)
        else:
            budget, safe_status = guardrails.preflight(daily_budget, status)
            data["daily_budget"] = self._to_minor_units(budget)
            data["bid_strategy"] = bid_strategy
            data["status"] = safe_status
        if promoted_object:
            data["promoted_object"] = _json(promoted_object)
        body = self._request("POST", f"{self.s.ad_account_path}/adsets", data=data)
        log.info(
            "Группа создана: %s, бюджет/день=%s",
            body.get("id"), f"{daily_budget:.2f} {self.s.currency}" if daily_budget else "CBO",
        )
        return body

    def update_adset_budget(self, adset_id: str, new_daily_budget: float) -> dict[str, Any]:
        """Меняет дневной бюджет группы (для масштабирования). Сверяется с потолком.

        Повышение бюджета — единственное действие, которое тратит БОЛЬШЕ денег, поэтому
        оно жёстко ограничено предохранителем MAX_DAILY_BUDGET.
        """
        budget = guardrails.validate_daily_budget(new_daily_budget)
        log.info("Меняю бюджет группы %s -> %.2f %s", adset_id, budget, self.s.currency)
        return self._request(
            "POST", adset_id, data={"daily_budget": self._to_minor_units(budget)}
        )

    # ---------- картинка ----------

    def upload_image_from_url(self, image_url: str) -> str:
        """Скачивает картинку по URL и грузит в кабинет. Возвращает image_hash."""
        img = requests.get(image_url, timeout=60)
        if img.status_code >= 400:
            raise MetaApiError(f"Не удалось скачать картинку {image_url}: {img.status_code}")
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/adimages",
            files={"filename": ("creative.jpg", img.content, "image/jpeg")},
        )
        images = body.get("images", {})
        first = next(iter(images.values()), None)
        if not first or "hash" not in first:
            raise MetaApiError(f"Meta не вернула image_hash: {body}")
        log.info("Картинка загружена, hash=%s", first["hash"])
        return first["hash"]

    # ---------- креатив ----------

    def create_ad_creative(
        self,
        name: str,
        message: str,
        headline: str,
        description: str,
        link: str,
        image_hash: str,
        *,
        call_to_action: str = "LEARN_MORE",
    ) -> dict[str, Any]:
        """Создаёт рекламный креатив (текст + картинка + ссылка)."""
        object_story_spec = {
            "page_id": self.s.meta_page_id,
            "link_data": {
                "message": message,
                "link": link,
                "name": headline,
                "description": description,
                "image_hash": image_hash,
                "call_to_action": {"type": call_to_action, "value": {"link": link}},
            },
        }
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/adcreatives",
            data={"name": name, "object_story_spec": _json(object_story_spec)},
        )
        log.info("Креатив создан: %s", body.get("id"))
        return body

    # ---------- видео (Reels/лента) ----------

    def upload_video_from_url(self, video_url: str) -> str:
        """Загружает видео в кабинет по URL. Возвращает video_id."""
        guardrails.check_kill_switch()
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/advideos",
            data={"file_url": video_url, "name": "[AI] video"},
        )
        vid = body.get("id")
        if not vid:
            raise MetaApiError(f"Meta не вернула video_id: {body}")
        log.info("Видео загружено: %s", vid)
        return vid

    def create_ad_creative_video(
        self,
        name: str,
        message: str,
        headline: str,
        description: str,
        link: str,
        video_id: str,
        thumbnail_url: str,
        *,
        call_to_action: str = "LEARN_MORE",
    ) -> dict[str, Any]:
        """Создаёт видео-креатив (видео + обложка + текст + ссылка)."""
        object_story_spec = {
            "page_id": self.s.meta_page_id,
            "video_data": {
                "video_id": video_id,
                "message": message,
                "title": headline,
                "link_description": description,
                "image_url": thumbnail_url,
                "call_to_action": {"type": call_to_action, "value": {"link": link}},
            },
        }
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/adcreatives",
            data={"name": name, "object_story_spec": _json(object_story_spec)},
        )
        log.info("Видео-креатив создан: %s", body.get("id"))
        return body

    # ---------- объявление ----------

    def create_ad(
        self,
        name: str,
        adset_id: str,
        creative_id: str,
        status: str = "PAUSED",
    ) -> dict[str, Any]:
        """Создаёт объявление (связка группа + креатив)."""
        guardrails.check_kill_switch()
        safe_status = guardrails.effective_status(status)
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/ads",
            data={
                "name": name,
                "adset_id": adset_id,
                "creative": _json({"creative_id": creative_id}),
                "status": safe_status,
            },
        )
        log.info("Объявление создано: %s (%s)", body.get("id"), safe_status)
        return body

    # ---------- поиск интересов для таргетинга ----------

    def search_interests(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Ищет интересы Meta по ключевому слову. Возвращает [{id, name, audience}].

        Это то, чем таргетолог сужает аудиторию: точные интересы вместо «всех подряд».
        """
        body = self._request(
            "GET",
            "search",
            params={
                "type": "adinterest",
                "q": query,
                "limit": limit,
                "locale": "ru_RU",
            },
        )
        out = []
        for item in body.get("data", []):
            out.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "audience": item.get("audience_size_lower_bound")
                    or item.get("audience_size"),
                    "topic": item.get("topic"),
                }
            )
        return out

    # ---------- аудитории: ретаргетинг и lookalike ----------

    def create_custom_audience_website(
        self,
        name: str,
        pixel_id: str,
        retention_days: int = 180,
    ) -> dict[str, Any]:
        """Создаёт аудиторию ретаргетинга: все, кто заходил на сайт (по пикселю).

        Тёплый трафик — обычно самый дешёвый источник конверсий.
        """
        guardrails.check_kill_switch()
        rule = {
            "inclusions": {
                "operator": "or",
                "rules": [{
                    "event_sources": [{"type": "pixel", "id": pixel_id}],
                    "retention_seconds": retention_days * 86400,
                    "filter": {"operator": "and", "filters": [
                        {"field": "event", "operator": "eq", "value": "PageView"}
                    ]},
                }],
            }
        }
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/customaudiences",
            data={"name": name, "subtype": "WEBSITE", "rule": _json(rule),
                  "prefill": "true", "retention_days": retention_days},
        )
        log.info("Аудитория ретаргетинга создана: %s", body.get("id"))
        return body

    def create_lookalike_audience(
        self,
        name: str,
        source_audience_id: str,
        country: str,
        ratio: float = 0.01,
    ) -> dict[str, Any]:
        """Создаёт lookalike-аудиторию (похожие на источник) для страны.

        ratio — «ширина» LAL: 0.01 = топ-1% похожих (уже/точнее), 0.10 = 10% (шире).
        """
        guardrails.check_kill_switch()
        spec = {"type": "similarity", "country": country.upper(), "ratio": ratio}
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/customaudiences",
            data={
                "name": name,
                "subtype": "LOOKALIKE",
                "origin_audience_id": source_audience_id,
                "lookalike_spec": _json(spec),
            },
        )
        log.info("Lookalike-аудитория создана: %s (ratio=%.2f, %s)", body.get("id"), ratio, country)
        return body

    def list_custom_audiences(self) -> list[dict[str, Any]]:
        """Список аудиторий кабинета: id, name, subtype, размер."""
        body = self._request(
            "GET",
            f"{self.s.ad_account_path}/customaudiences",
            params={"fields": "id,name,subtype,approximate_count_lower_bound", "limit": 100},
        )
        return [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "subtype": a.get("subtype"),
                "count": a.get("approximate_count_lower_bound"),
            }
            for a in body.get("data", [])
        ]

    # ---------- метрики ----------

    def get_insights(self, object_id: str, date_preset: str = "today") -> dict[str, Any]:
        """Снимает статистику по объекту (ad/adset/campaign).

        frequency нужен для детекта усталости креатива, action_values — для ROAS.
        """
        body = self._request(
            "GET",
            f"{object_id}/insights",
            params={
                "fields": "spend,impressions,clicks,ctr,cpc,frequency,actions,action_values",
                "date_preset": date_preset,
            },
        )
        rows = body.get("data", [])
        return rows[0] if rows else {}

    def get_adset(self, adset_id: str) -> dict[str, Any]:
        """Читает группу: id, name, дневной бюджет (в валюте), статус."""
        body = self._request(
            "GET", adset_id, params={"fields": "id,name,daily_budget,status"}
        )
        db = body.get("daily_budget")
        return {
            "id": body.get("id"),
            "name": body.get("name"),
            "daily_budget": self._from_minor_units(db) if db else None,
            "status": body.get("status"),
        }

    # ---------- пауза (предохранитель Optimizer'а) ----------

    def pause_ad(self, ad_id: str) -> dict[str, Any]:
        """Ставит объявление на паузу. Всегда разрешено (это снижение риска)."""
        log.warning("Ставлю на паузу объявление %s", ad_id)
        return self._request("POST", ad_id, data={"status": "PAUSED"})

    def pause_adset(self, adset_id: str) -> dict[str, Any]:
        """Ставит группу объявлений на паузу."""
        log.warning("Ставлю на паузу группу %s", adset_id)
        return self._request("POST", adset_id, data={"status": "PAUSED"})

    def kill_all_active(self) -> list[str]:
        """Аварийно паузит все ACTIVE-кампании кабинета. Возвращает их id."""
        body = self._request(
            "GET",
            f"{self.s.ad_account_path}/campaigns",
            params={"fields": "id,status", "effective_status": '["ACTIVE"]'},
        )
        paused = []
        for camp in body.get("data", []):
            self._request("POST", camp["id"], data={"status": "PAUSED"})
            paused.append(camp["id"])
        log.warning("Аварийно поставлено на паузу кампаний: %d", len(paused))
        return paused


def _json(obj: Any) -> str:
    """Meta ждёт вложенные структуры JSON-строкой в теле формы."""
    import json

    return json.dumps(obj, ensure_ascii=False)


def extract_leads(insights: dict[str, Any]) -> int:
    """Достаёт число лидов из поля actions статистики Meta."""
    lead_types = {"lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead"}
    total = 0
    for action in insights.get("actions", []) or []:
        if action.get("action_type") in lead_types:
            total += int(float(action.get("value", 0)))
    return total


_PURCHASE_TYPES = {"purchase", "offsite_conversion.fb_pixel_purchase", "omni_purchase"}


def extract_purchases(insights: dict[str, Any]) -> int:
    """Число покупок из actions."""
    total = 0
    for action in insights.get("actions", []) or []:
        if action.get("action_type") in _PURCHASE_TYPES:
            total += int(float(action.get("value", 0)))
    return total


def extract_revenue(insights: dict[str, Any]) -> float:
    """Выручка из action_values (ценность покупок) — для расчёта ROAS."""
    total = 0.0
    for av in insights.get("action_values", []) or []:
        if av.get("action_type") in _PURCHASE_TYPES:
            total += float(av.get("value", 0) or 0)
    return total
