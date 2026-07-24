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

    # ---------- кампания ----------

    def create_campaign(
        self,
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        status: str = "PAUSED",
        special_ad_categories: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Создаёт рекламную кампанию (верхний уровень).

        objective — цель ODAX: OUTCOME_TRAFFIC / OUTCOME_LEADS / OUTCOME_SALES и т.д.
        """
        guardrails.check_kill_switch()
        safe_status = guardrails.effective_status(status)
        body = self._request(
            "POST",
            f"{self.s.ad_account_path}/campaigns",
            data={
                "name": name,
                "objective": objective,
                "status": safe_status,
                "special_ad_categories": str(special_ad_categories or []).replace("'", '"'),
            },
        )
        log.info("Кампания создана: %s (%s)", body.get("id"), safe_status)
        return body

    # ---------- группа объявлений ----------

    def create_adset(
        self,
        name: str,
        campaign_id: str,
        daily_budget: float,
        targeting: dict[str, Any],
        *,
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
        status: str = "PAUSED",
        promoted_object: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Создаёт группу объявлений (таргетинг + бюджет).

        daily_budget — В ВАЛЮТЕ кабинета (не в центах): предохранитель сверит с лимитом,
        а перевод в минимальные единицы делает клиент.
        """
        budget, safe_status = guardrails.preflight(daily_budget, status)
        data: dict[str, Any] = {
            "name": name,
            "campaign_id": campaign_id,
            "daily_budget": self._to_minor_units(budget),
            "billing_event": billing_event,
            "optimization_goal": optimization_goal,
            "bid_strategy": bid_strategy,
            "targeting": _json(targeting),
            "status": safe_status,
        }
        if promoted_object:
            data["promoted_object"] = _json(promoted_object)
        body = self._request("POST", f"{self.s.ad_account_path}/adsets", data=data)
        log.info("Группа создана: %s, бюджет/день=%.2f %s", body.get("id"), budget, self.s.currency)
        return body

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

    # ---------- метрики ----------

    def get_insights(self, object_id: str, date_preset: str = "today") -> dict[str, Any]:
        """Снимает статистику по объекту (ad/adset/campaign)."""
        body = self._request(
            "GET",
            f"{object_id}/insights",
            params={
                "fields": "spend,impressions,clicks,ctr,cpc,actions",
                "date_preset": date_preset,
            },
        )
        rows = body.get("data", [])
        return rows[0] if rows else {}

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
