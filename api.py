"""FastAPI-бэкенд для Next.js-витрины.

Тонкий REST-слой поверх готовых Python-агентов: вся доменная логика и предохранители
остаются в agents/ и services/. Фронт (web/) общается только с этим API.

Запуск:  uvicorn api:app --reload --port 8000
Docs:    http://localhost:8000/docs
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from services.state import AdIdea, Creative, ProductBrief


def require_token(request: Request, x_api_token: str | None = Header(default=None)) -> None:
    """Если задан API_TOKEN — требуем заголовок X-API-Token. Иначе доступ открыт (dev).

    /health всегда открыт: это нужно для health-check хостинга и статуса подключений на фронте.
    """
    if request.url.path == "/health":
        return
    token = get_settings().api_token
    if token and x_api_token != token:
        raise HTTPException(status_code=401, detail="Неверный или отсутствующий API-токен.")


app = FastAPI(title="AI-таргетолог API", version="1.0", dependencies=[Depends(require_token)])

# Next.js dev-сервер и продовый домен фронта.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- модели запросов ----------
class AutofillReq(BaseModel):
    url: str = ""
    note: str = ""


class ResearchReq(BaseModel):
    brief: ProductBrief


class CreativesReq(BaseModel):
    brief: ProductBrief
    ideas: list[AdIdea]
    framework: str = "AIDA"


class ImageReq(BaseModel):
    creative: Creative
    aspect_ratio: str = "1:1"


class LaunchReq(BaseModel):
    brief: ProductBrief
    creatives: list[Creative]
    daily_budget: float
    ab_test: bool = False
    campaign_budget: Optional[float] = None
    interests: Optional[list[dict]] = None


class OptimizeReq(BaseModel):
    ad_ids: list[str]
    execute: bool = False


# ---------- служебное ----------
@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "dry_run": s.dry_run,
        "currency": s.currency,
        "max_daily_budget": s.max_daily_budget,
        "target_cpl": s.target_cpl,
        "connections": {
            "claude": bool(s.anthropic_api_key),
            "meta": bool(s.meta_access_token and s.meta_ad_account_id),
            "pixel": bool(s.meta_pixel_id),
            "replicate": bool(s.replicate_api_token),
            "telegram": bool(s.telegram_bot_token and s.telegram_chat_id),
        },
    }


def _guard(fn):
    """Оборачивает доменную ошибку в 400, чтобы фронт показал понятный текст."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------- эндпоинты агентов ----------
@app.post("/brief/autofill", response_model=ProductBrief)
def brief_autofill(req: AutofillReq) -> ProductBrief:
    from agents.brief_builder import autofill_brief

    return _guard(lambda: autofill_brief(note=req.note, url=req.url))


@app.post("/research")
def research(req: ResearchReq) -> dict:
    from agents.research import run_research

    return _guard(lambda: run_research(req.brief).model_dump())


@app.post("/creatives")
def creatives(req: CreativesReq) -> list[dict]:
    from agents.creative import generate_creatives

    return _guard(lambda: [c.model_dump() for c in
                           generate_creatives(req.brief, req.ideas, framework=req.framework)])


@app.post("/creatives/image", response_model=Creative)
def creative_image(req: ImageReq) -> Creative:
    from agents.creative import attach_image

    return _guard(lambda: attach_image(req.creative, aspect_ratio=req.aspect_ratio))


@app.get("/audiences/interests")
def interests(q: str) -> list[dict]:
    from tools.facebook_api import FacebookAdsClient

    return _guard(lambda: FacebookAdsClient().search_interests(q))


@app.post("/launch")
def launch(req: LaunchReq) -> dict:
    from agents.media_buyer import launch as do_launch
    from services import store
    from tools import telegram

    def _run():
        camp = do_launch(
            req.brief, req.creatives, daily_budget=req.daily_budget,
            ab_test=req.ab_test, interests=req.interests,
            campaign_budget=req.campaign_budget,
        )
        telegram.send_message(telegram.format_launch_report(camp, req.brief))
        try:
            store.save_run(req.brief, camp)
        except Exception:  # noqa: BLE001
            pass
        return camp.model_dump()

    return _guard(_run)


@app.post("/optimize")
def optimize(req: OptimizeReq) -> dict:
    from agents.optimizer import run_optimizer

    def _run():
        metrics, decisions = run_optimizer(req.ad_ids, execute=req.execute)
        return {
            "metrics": [m.model_dump() for m in metrics],
            "decisions": [d.model_dump() for d in decisions],
        }

    return _guard(_run)


@app.get("/history")
def history(limit: int = 50) -> list[dict]:
    from services import store

    return _guard(lambda: store.list_runs(limit))
