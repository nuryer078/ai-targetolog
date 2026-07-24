"""Модели данных, которые ходят между агентами по графу LangGraph.

Каждый агент обогащает общее состояние: продукт -> идеи -> креативы -> кампания -> метрики.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# --- Вход ---
class ProductBrief(BaseModel):
    """Вводные по продукту/услуге — то, с чего стартует весь пайплайн."""
    name: str
    description: str
    price: Optional[str] = None
    landing_url: str
    geo: list[str] = Field(default_factory=lambda: ["KZ"])
    goal: str = "LEAD_GENERATION"  # что оптимизируем: лиды, трафик, продажи
    extra: Optional[str] = None    # любые доп. заметки для аналитика


# --- Research Agent ---
class AudiencePersona(BaseModel):
    name: str                      # «Молодая мама 25-34»
    pains: list[str]
    objections: list[str]
    triggers: list[str]            # что цепляет / мотивирует


class AdIdea(BaseModel):
    persona: str
    offer: str                     # оффер под эту ЦА
    angle: str                     # рекламный угол / посыл
    keywords: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    personas: list[AudiencePersona]
    ideas: list[AdIdea]


# --- Creative Agent ---
class Creative(BaseModel):
    idea_angle: str
    framework: str                 # AIDA | PAS
    primary_text: str              # основной текст объявления
    headline: str
    description: str
    image_prompt: str              # промпт для генерации баннера
    image_url: Optional[str] = None  # заполняется после генерации
    selected: bool = True          # отмечен ли креатив к запуску (правится в панели)


# --- Media Buyer Agent ---
class LaunchedCampaign(BaseModel):
    campaign_id: str
    adset_ids: list[str] = Field(default_factory=list)
    ad_ids: list[str] = Field(default_factory=list)
    status: str                    # PAUSED | ACTIVE
    dry_run: bool
    note: str = ""


# --- Optimizer Agent ---
class AdMetrics(BaseModel):
    ad_id: str
    adset_id: Optional[str] = None
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    leads: int = 0
    cpl: Optional[float] = None     # None = лидов ещё нет


class OptimizationDecision(BaseModel):
    ad_id: str
    action: str                    # KEEP | PAUSE
    reason: str


# --- Общее состояние графа ---
class PipelineState(BaseModel):
    brief: ProductBrief
    research: Optional[ResearchResult] = None
    creatives: list[Creative] = Field(default_factory=list)
    campaign: Optional[LaunchedCampaign] = None
    metrics: list[AdMetrics] = Field(default_factory=list)
    decisions: list[OptimizationDecision] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
