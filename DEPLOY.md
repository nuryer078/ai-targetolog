# 🚀 Деплой AI-таргетолога

Панель написана на **Streamlit** — ей нужен постоянно работающий сервер.
**Vercel (serverless) для неё не подходит** — он хостит Next.js, а не Streamlit.
Поэтому ниже — рабочие пути. Vercel появится, когда сделаем отдельный Next.js-фронт.

> ⚠️ Приложение управляет реальным рекламным бюджетом. На проде:
> - держи **`DRY_RUN=true`**, пока не убедишься, что всё верно;
> - обязательно задай **`APP_PASSWORD`** — панель закроется паролем;
> - секреты вводи только в дашборде хостинга, никогда не коммить в git.

---

## Вариант 1 — Streamlit Community Cloud (быстрее всего, бесплатно)

1. Репозиторий уже на GitHub (приватный). Зайди на **share.streamlit.io** под своим GitHub.
2. **New app** → выбери репозиторий, ветку `master`, файл `app.py`.
3. **Advanced settings → Secrets** → вставь содержимое `.streamlit/secrets.toml.example`,
   подставив свои ключи (обязательно `APP_PASSWORD` и `DRY_RUN=true`).
4. **Deploy**. Через ~2 минуты будет живой адрес вида `https://<app>.streamlit.app`.

## Вариант 2 — Railway (Docker, гибче)

1. **railway.app** → New Project → **Deploy from GitHub repo** → выбери репозиторий.
2. Railway подхватит `Dockerfile` автоматически.
3. **Variables** → добавь переменные из `config/.env.example` (свои значения) +
   `APP_PASSWORD`, `DRY_RUN=true`.
4. Deploy → Railway выдаст публичный URL.

## Вариант 3 — Render (Docker, есть Blueprint)

1. **render.com** → New → **Blueprint** → укажи репозиторий (там лежит `render.yaml`).
2. В дашборде заполни секреты (помечены `sync: false`).
3. Deploy.

---

## Что я подготовил в репозитории
- `Dockerfile`, `.dockerignore` — образ для любого Docker-хоста;
- `Procfile` — для Railway/Render/Heroku-подобных;
- `render.yaml` — Blueprint для Render;
- `.streamlit/secrets.toml.example` — шаблон секретов для Streamlit Cloud;
- пароль на вход (`APP_PASSWORD`) и перенос секретов хостинга в конфиг — в `app.py`.

## Чего я не могу сделать за тебя
- Войти в твой аккаунт хостинга и нажать Deploy;
- Ввести твои реальные токены (их нельзя показывать/передавать).
Это финальные 2 шага — они за тобой.

---

## Позже: настоящий Vercel
Когда сделаем **Next.js-фронт** — он задеплоится на Vercel, а Python-API (эти же агенты
через FastAPI) поедет на Railway/Render. Тогда получится «на Vercel» и премиум-дизайн.
