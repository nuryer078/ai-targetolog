"""Обёртка над Anthropic Claude API с поддержкой tool calling (agentic loop).

Любой агент = системный промпт + набор инструментов (tools). Класс сам крутит
цикл «модель просит вызвать инструмент -> мы вызываем -> отдаём результат обратно»,
пока модель не выдаст финальный ответ.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from config.settings import get_settings
from services.logger import get_logger

log = get_logger("llm")


@dataclass
class Tool:
    """Инструмент, который агент может вызвать.

    name/description/input_schema — то, что видит модель.
    fn — реальная Python-функция, принимает kwargs, возвращает JSON-сериализуемое.
    """
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., Any]

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ClaudeAgent:
    """Агент на базе Claude: системный промпт + инструменты + цикл tool use."""

    def __init__(
        self,
        system: str,
        tools: list[Tool] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        max_turns: int = 12,
    ) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY не задан. Заполни .env (см. config/.env.example)."
            )
        # Импортируем здесь, чтобы модуль грузился даже без установленного SDK (для тестов).
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.system = system
        self.tools = tools or []
        self._by_name = {t.name: t for t in self.tools}
        self.model = model or settings.llm_model
        self.max_tokens = max_tokens
        self.max_turns = max_turns

    def run(self, user_message: str) -> str:
        """Прогоняет диалог до финального текстового ответа модели.

        Возвращает итоговый текст (агенты обычно просят вернуть JSON-строку).
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        tool_defs = [t.to_anthropic() for t in self.tools]

        for turn in range(self.max_turns):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": self.system,
                "messages": messages,
            }
            if tool_defs:
                kwargs["tools"] = tool_defs

            resp = self._client.messages.create(**kwargs)
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                # Финальный ответ — собираем текст из блоков.
                return _extract_text(resp.content)

            # Модель попросила вызвать инструменты — исполняем каждый.
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                result = self._execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(
            f"Агент не сошёлся за {self.max_turns} ходов — возможно, зациклился на инструментах."
        )

    def _execute_tool(self, name: str, args: dict[str, Any]) -> Any:
        tool = self._by_name.get(name)
        if tool is None:
            log.error("Модель запросила неизвестный инструмент: %s", name)
            return {"error": f"Неизвестный инструмент: {name}"}
        try:
            log.info("Вызов инструмента %s(%s)", name, args)
            return tool.fn(**args)
        except Exception as exc:  # noqa: BLE001 — ошибку отдаём модели, пусть решает
            log.exception("Инструмент %s упал: %s", name, exc)
            return {"error": str(exc)}


def _extract_text(content: list[Any]) -> str:
    parts = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def complete_json(system: str, user_message: str, model: str | None = None) -> dict[str, Any]:
    """Разовый вызов без инструментов, который обязан вернуть JSON-объект.

    Удобно для Research/Creative, где нужен структурированный ответ, а не диалог.
    Терпимо парсит ответ, даже если модель обернула JSON в ```-блок.
    """
    agent = ClaudeAgent(system=system, tools=[], model=model)
    raw = agent.run(user_message)
    return _parse_json_lenient(raw)


def _parse_json_lenient(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        # срезаем ```json ... ```
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)
