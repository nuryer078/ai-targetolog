# 🎯 AI-таргетолог

Автономная мультиагентная система для рекламы в **Meta Ads** (Facebook/Instagram).
Четыре AI-агента на **Claude** проводят полный цикл: анализ ЦА → креативы и баннеры →
запуск кампании → оптимизация по метрикам. Всё под контролем человека через
визуальную панель.

```
Бриф → 🔍 Аналитик → ✍️ Копирайтер+🎨 Дизайнер → 🚀 Media Buyer → 📊 Оптимизатор
```

---

## ⚠️ Про деньги — прочитай первым

Система тратит рекламный бюджет. Поэтому в неё встроены предохранители:

| Предохранитель | Что делает |
|---|---|
| `DRY_RUN=true` (по умолчанию) | Всё создаётся в статусе **PAUSED** — деньги **не** тратятся |
| `MAX_DAILY_BUDGET` | Жёсткий потолок дневного бюджета группы — дороже физически не создать |
| `.KILL_SWITCH` (файл) | Пока лежит в корне — любой запуск заблокирован |
| Кнопка «Аварийный стоп» | Мгновенно паузит все активные кампании |
| Оптимизатор | Только **паузит** слабые объявления, сам бюджет не поднимает |

**Первый боевой запуск делай осознанно:** сначала прогони всё в `DRY_RUN`, проверь
структуру кампании в кабинете Meta, и только потом выключай `DRY_RUN`.

---

## 🚀 Установка

```powershell
# 1. Виртуальное окружение
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Зависимости
pip install -r requirements.txt

# 3. Конфиг: скопируй шаблон и заполни своими токенами
copy config\.env.example .env
notepad .env
```

`.env` в git не попадает (см. `.gitignore`). Токены — только туда.

---

## 🔑 Где взять токены

| Переменная | Где взять |
|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys |
| `META_APP_ID`, `META_APP_SECRET` | https://developers.facebook.com/apps → твоё приложение → Settings → Basic |
| `META_ACCESS_TOKEN` | Graph API Explorer, права `ads_management`, `ads_read`, `pages_read_engagement`; затем обменять на long-lived (см. ниже) |
| `META_AD_ACCOUNT_ID` | Ads Manager → номер кабинета (без префикса `act_`) |
| `META_PAGE_ID` | Страница FB → About → Page ID |
| `META_PIXEL_ID` | Events Manager → Data Sources → пиксель. **Нужен для оптимизации на конверсии** (лиды/покупки); без него — оптимизация по кликам |
| `REPLICATE_API_TOKEN` | https://replicate.com/account/api-tokens |
| `TELEGRAM_BOT_TOKEN` | @BotFather → `/newbot` |
| `TELEGRAM_CHAT_ID` | напиши боту, затем @userinfobot покажет твой chat_id |

**Long-lived токен Meta** (живёт ~60 дней):
```
GET https://graph.facebook.com/v21.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=<META_APP_ID>
  &client_secret=<META_APP_SECRET>
  &fb_exchange_token=<короткий_токен_из_Explorer>
```

> Права `ads_management` требуют, чтобы приложение прошло App Review, либо чтобы ты
> был в ролях разработчика/тестировщика приложения (для своего кабинета этого хватает).

---

## 🖥️ Визуальная панель (основной способ)

```powershell
streamlit run app.py
```

Откроется пульт с вкладками:

1. **Бриф** — вводишь продукт, гео, цель.
2. **Аналитик** — портреты ЦА и идеи (правишь прямо в панели).
3. **Креативы** — тексты по AIDA/PAS + баннеры. Редактируешь текст, перегенерируешь картинку.
4. **Запуск** — выбираешь креативы, ставишь бюджет; панель показывает проверку
   предохранителей; жмёшь «Запустить» (в DRY_RUN → PAUSED).
5. **Оптимизатор** — метрики (Spend/CTR/CPL), решения и авто-пауза.

В боковой панели — статус подключений, лимиты и **аварийный стоп**.

---

## ⌨️ CLI и автоматизация

```powershell
# Полный автономный проход
python main.py run --name "Курс по SMM" --desc "Онлайн-курс для новичков" `
  --url https://lending.kz --geo KZ --budget 5 --framework AIDA

# Оптимизатор (для крона) — снять метрики и поставить на паузу слабых
python main.py optimize --ads 120xxxx 120yyyy

# Аварийно остановить всё
python main.py kill
```

**Оптимизатор по расписанию (Windows Task Scheduler), каждые 6 часов:**
```powershell
schtasks /Create /SC HOURLY /MO 6 /TN "AI-targetolog-optimize" `
  /TR "C:\Users\User\Documents\ai-targetolog\.venv\Scripts\python.exe C:\Users\User\Documents\ai-targetolog\main.py optimize --ads 120xxxx"
```

---

## 🏗️ Архитектура

```
ai-targetolog/
├── agents/         research · creative · media_buyer · optimizer · pipeline (LangGraph)
├── tools/          facebook_api (Meta) · image_gen (Flux) · telegram
├── services/       llm (Claude+tools) · guardrails · state (pydantic) · logger
├── config/         settings.py · .env.example
├── app.py          визуальная панель (Streamlit)
├── main.py         CLI
└── tests/          pytest (предохранители, Meta-клиент, оптимизатор, media buyer)
```

- **Креативы** генерирует LLM. **Трату бюджета** исполняет детерминированный код
  через предохранители — так галлюцинация модели не сможет слить деньги.
- Meta API — прямые HTTP-вызовы (`requests`), полностью покрыты тестами на моках.

---

## ✅ Тесты

```powershell
pytest              # 24 теста: предохранители, бюджет, статусы, оптимизатор, media buyer
```

Ни один тест не ходит в реальную сеть.

---

## 🎯 Профессиональная оптимизация

- **Оптимизация на конверсии.** Если задан `META_PIXEL_ID`, для целей
  `LEAD_GENERATION`/`SALES` система создаёт кампанию с оптимизацией на реальные
  события пикселя (LEAD/PURCHASE), а не на клики. Без пикселя — честный откат на
  клики с предупреждением.
- **Таргетинг по интересам.** Media Buyer ищет реальные интересы Meta по ключевым
  словам (в автономном режиме — из идей аналитика; в панели — вручную через поиск)
  и подмешивает их в `flexible_spec`, сужая аудиторию.

## 🗺️ Дальше (роадмап)

- Хранилище прогонов (БД) и история кампаний в панели.
- Автотест креативов A/B и авто-масштабирование бюджета (с жёсткими лимитами).
- Lookalike-аудитории и ретаргетинг по событиям пикселя.
