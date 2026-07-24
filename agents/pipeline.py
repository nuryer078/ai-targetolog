"""Оркестрация агентов через LangGraph.

Собирает полный автономный проход: Аналитик -> Копирайтер -> Баннеры -> Media Buyer
-> отчёт в Telegram. Используется CLI и кроном. Для ручного режима «посмотрел-поправил»
панель дёргает тех же агентов по шагам (см. app.py).

Импорт langgraph ленивый — модуль не требуется тестам на агентах/предохранителях.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from agents import creative as creative_agent
from agents import media_buyer
from agents import research as research_agent
from config.settings import get_settings
from services.logger import get_logger
from services.state import (
    Creative,
    LaunchedCampaign,
    ProductBrief,
    ResearchResult,
)
from tools import telegram

log = get_logger("pipeline")


class GraphState(TypedDict, total=False):
    brief: ProductBrief
    framework: str
    daily_budget: float
    activate: bool
    research: ResearchResult
    creatives: list[Creative]
    campaign: LaunchedCampaign
    errors: list[str]


def _node_research(state: GraphState) -> GraphState:
    state["research"] = research_agent.run_research(state["brief"])
    return state


def _node_creative(state: GraphState) -> GraphState:
    ideas = state["research"].ideas
    creatives = creative_agent.generate_creatives(
        state["brief"], ideas, framework=state.get("framework", "AIDA")
    )
    state["creatives"] = creatives
    return state


def _node_images(state: GraphState) -> GraphState:
    for cr in state["creatives"]:
        try:
            creative_agent.attach_image(cr)
        except Exception as exc:  # noqa: BLE001
            log.error("Картинка не сгенерирована для «%s»: %s", cr.idea_angle, exc)
            state.setdefault("errors", []).append(f"image: {exc}")
    return state


def _node_media_buyer(state: GraphState) -> GraphState:
    with_images = [c for c in state["creatives"] if c.image_url]
    state["campaign"] = media_buyer.launch(
        state["brief"],
        with_images,
        daily_budget=state["daily_budget"],
        activate=state.get("activate", False),
    )
    return state


def _node_report(state: GraphState) -> GraphState:
    camp = state.get("campaign")
    if camp:
        telegram.send_message(telegram.format_launch_report(camp, state["brief"]))
    return state


def build_graph():
    """Собирает и компилирует граф LangGraph."""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(GraphState)
    g.add_node("research", _node_research)
    g.add_node("creative", _node_creative)
    g.add_node("images", _node_images)
    g.add_node("media_buyer", _node_media_buyer)
    g.add_node("report", _node_report)

    g.add_edge(START, "research")
    g.add_edge("research", "creative")
    g.add_edge("creative", "images")
    g.add_edge("images", "media_buyer")
    g.add_edge("media_buyer", "report")
    g.add_edge("report", END)
    return g.compile()


def run_autonomous(
    brief: ProductBrief,
    daily_budget: float,
    *,
    framework: str = "AIDA",
    activate: bool = False,
) -> LaunchedCampaign:
    """Полный автономный проход. В DRY_RUN всё создаётся в PAUSED — безопасно."""
    settings = get_settings()
    log.info("Автономный проход. DRY_RUN=%s", settings.dry_run)
    graph = build_graph()
    result: GraphState = graph.invoke(
        {
            "brief": brief,
            "framework": framework,
            "daily_budget": daily_budget,
            "activate": activate,
        }
    )
    campaign = result.get("campaign")
    if not campaign:
        raise RuntimeError("Пайплайн завершился без созданной кампании. Смотри логи.")
    return campaign
