# 🚀 Деплой витрины Next.js (тёмный премиум)

Два сервиса:
1. **FastAPI-бэкенд** (`api.py`) → Railway (или Render). Держит агентов, ключи, предохранители.
2. **Next.js-фронт** (`web/`) → Vercel.

> ⚠️ Бэкенд тратит деньги. На проде:
> - **`DRY_RUN=true`** — кампании не откручиваются;
> - **`API_TOKEN`** — API закрыт токеном (фронт присылает `X-API-Token`);
> - секреты только в дашборде хостинга, не в git.

---

## Шаг 1 — FastAPI на Railway

1. **railway.app** → New Project → **Deploy from GitHub repo** → `nuryer078/ai-targetolog`.
2. Railway прочитает `railway.json` и соберёт образ из **`Dockerfile.api`** (uvicorn).
3. **Variables** → добавь (свои значения):
   ```
   API_TOKEN = придумай-длинный-случайный-токен
   DRY_RUN = true
   ANTHROPIC_API_KEY = sk-ant-...
   REPLICATE_API_TOKEN = r8_...
   MAX_DAILY_BUDGET = 10
   TARGET_CPL = 5
   CURRENCY = USD
   # Meta/Telegram/Pixel/DATABASE_URL — по мере готовности
   ```
4. Deploy → Railway выдаст публичный URL, напр. `https://ai-targetolog-api.up.railway.app`.
5. Проверь: открой `<URL>/health` — должен вернуть JSON (если стоит `API_TOKEN`, health тоже
   потребует токен; можно временно убрать токен для проверки, потом вернуть).

*(Render — аналогично: New → Web Service → Docker → путь `Dockerfile.api`, те же переменные.)*

---

## Шаг 2 — Next.js на Vercel

1. **vercel.com** → **Add New → Project** → импортируй `nuryer078/ai-targetolog`.
2. **ВАЖНО:** в настройках проекта **Root Directory** укажи **`web`** (не корень репо).
   Framework Vercel определит сам (Next.js).
3. **Environment Variables**:
   ```
   NEXT_PUBLIC_API_URL = https://твой-railway-url.up.railway.app
   NEXT_PUBLIC_API_TOKEN = тот-же-токен-что-в-API_TOKEN
   ```
4. **Deploy**. Получишь адрес вида `https://ai-targetolog.vercel.app`.

CORS уже настроен: API разрешает запросы с `localhost:3000` и любого `*.vercel.app`.

---

## Порядок и проверка
1. Сначала подними **API** (Шаг 1), скопируй его URL.
2. Потом деплой **фронт** (Шаг 2), вставив этот URL в `NEXT_PUBLIC_API_URL`.
3. Открой Vercel-адрес → на дашборде кружки подключений подтянутся из `/health`.
4. Пройди Бриф → Аналитик → Креативы — если Claude/Replicate заданы на API, всё отработает.

## Чего я не могу за тебя
- Войти в твои Railway/Vercel и нажать Deploy;
- Ввести реальные ключи.
Это финальные шаги — они за тобой. Код и конфиги готовы.

## Безопасность (важно)
- `NEXT_PUBLIC_API_TOKEN` попадает в браузер — это защита от **случайного/ботового** доступа,
  а не абсолютная. Главная защита от траты денег — **`DRY_RUN=true`** на API.
- Реально «боевой» режим включай только осознанно и, в идеале, за нормальной авторизацией
  (логин) — это следующий шаг усиления.
