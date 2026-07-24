# AI-таргетолог — контекст проекта

## Что это
Мультиагентная система для Meta Ads (Facebook/Instagram): 4 AI-агента создают,
генерируют креативы, запускают и оптимизируют рекламные кампании. Управление —
через визуальную панель (human-in-the-loop) и CLI/крон.

## Стек
Python 3.11+, Claude (Anthropic API) с tool calling, LangGraph (оркестрация),
Meta Graph API (прямые HTTP-вызовы), Replicate/Flux.1 (баннеры), Streamlit (панель),
Telegram (отчёты). Тесты — pytest.

## Устройство
- `agents/` — research, creative, media_buyer, optimizer + pipeline (LangGraph-граф).
- `tools/` — facebook_api (Meta), image_gen (Replicate), telegram.
- `services/` — llm (Claude+tool calling), guardrails (предохранители), state (pydantic-модели), logger.
- `config/settings.py` — единственная точка чтения .env.
- `app.py` — веб-панель. `main.py` — CLI (run/optimize/kill).

## Запуск
```
streamlit run app.py                 # визуальная панель
python main.py run --name ... --budget 5   # автономный проход
python main.py optimize --ads ID...  # цикл оптимизатора (для крона)
python main.py kill                  # аварийно паузить все ACTIVE
pytest                               # тесты
```

## ГЛАВНОЕ ПРО ДЕНЬГИ (не ломать)
- **Предохранители живут в `services/guardrails.py`**, а не в агентах/промптах.
- `DRY_RUN=true` (по умолчанию) — всё создаётся в статусе PAUSED, бюджет не тратится.
- `MAX_DAILY_BUDGET` — жёсткий потолок; media_buyer/facebook_api не создадут adset дороже.
- Файл `.KILL_SWITCH` в корне блокирует любой запуск.
- Optimizer только **паузит**, никогда не повышает бюджет сам.
- Решения о трате бюджета — детерминированный код, не «свободный» LLM.

## Секреты
Только в `.env` (в git не попадает). Шаблон — `config/.env.example`.
Реальные токены в код и в чат не вставлять.
