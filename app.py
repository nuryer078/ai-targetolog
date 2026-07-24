"""Визуальная панель управления AI-таргетологом (Streamlit).

Сквозной human-in-the-loop пульт с дашбордом:
  Дашборд · Бриф → Аналитик → Креативы → Аудитории → Запуск → Оптимизатор.

Запуск:  streamlit run app.py
Ничего не откручивается, пока в .env DRY_RUN=true — всё создаётся в статусе PAUSED.
"""
from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from services.state import AdIdea, Creative, ProductBrief

st.set_page_config(page_title="AI-таргетолог", page_icon="🎯", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; max-width: 1200px;}
      .stel-card {border:1px solid rgba(128,128,128,.22); border-radius:16px;
                  padding:1rem 1.2rem; margin-bottom:1rem; background:rgba(140,140,140,.06);}
      .stel-badge {display:inline-block; padding:.2rem .7rem; border-radius:999px;
                   font-size:.8rem; font-weight:700; letter-spacing:.02em;}
      .stel-dry {background:#1f6f3c33; color:#39d98a; border:1px solid #39d98a55;}
      .stel-live {background:#7a1f1f33; color:#ff6b6b; border:1px solid #ff6b6b55;}
      /* KPI-плитки */
      .kpi {border:1px solid rgba(128,128,128,.22); border-radius:16px; padding:1rem 1.1rem;
            background:linear-gradient(180deg, rgba(57,217,138,.08), rgba(140,140,140,.03));}
      .kpi .lbl {font-size:.78rem; opacity:.7; text-transform:uppercase; letter-spacing:.04em;}
      .kpi .val {font-size:1.7rem; font-weight:800; line-height:1.2; margin-top:.2rem;}
      /* степпер */
      .step-row {display:flex; gap:.4rem; flex-wrap:wrap; margin:.2rem 0 1rem;}
      .step {flex:1; min-width:120px; text-align:center; padding:.5rem .3rem; border-radius:12px;
             font-size:.82rem; border:1px solid rgba(128,128,128,.2); background:rgba(140,140,140,.05);}
      .step.done {border-color:#39d98a66; background:#1f6f3c22; color:#39d98a;}
      .step.next {border-color:#5b8cff66; background:#22346322; color:#8fb0ff;}
    </style>
    """,
    unsafe_allow_html=True,
)


def ss():
    return st.session_state


for key in ("brief", "research", "creatives", "campaign"):
    ss().setdefault(key, None)
ss().setdefault("metrics", [])
ss().setdefault("decisions", [])
ss().setdefault("interests", [])
ss().setdefault("_int_results", [])
ss().setdefault("audiences_cache", [])
ss().setdefault("target_auds", [])
ss().setdefault("exclude_auds", [])


# ============================================================
#  Боковая панель
# ============================================================
def render_sidebar():
    s = get_settings()
    with st.sidebar:
        st.header("🎯 AI-таргетолог")
        badge = (
            '<span class="stel-badge stel-dry">DRY-RUN · безопасно</span>'
            if s.dry_run
            else '<span class="stel-badge stel-live">БОЕВОЙ РЕЖИМ</span>'
        )
        st.markdown(badge, unsafe_allow_html=True)
        if not s.dry_run:
            st.warning("DRY_RUN выключен — кампании тратят реальные деньги.")

        st.divider()
        st.caption("Предохранители (.env)")
        st.write(f"Лимит бюджета/день: **{s.max_daily_budget} {s.currency}**")
        st.write(f"Норма CPL: **{s.target_cpl} {s.currency}**")

        st.divider()
        st.caption("Подключения")
        st.write(_conn("Claude", s.anthropic_api_key))
        st.write(_conn("Meta Ads", s.meta_access_token and s.meta_ad_account_id))
        st.write(_conn("Пиксель (конверсии)", s.meta_pixel_id))
        st.write(_conn("Replicate", s.replicate_api_token))
        st.write(_conn("Telegram", s.telegram_bot_token and s.telegram_chat_id))

        st.divider()
        if st.button("🛑 Аварийный стоп (паузить всё)", use_container_width=True):
            _emergency_stop()


def _conn(name: str, ok) -> str:
    return f"{'🟢' if ok else '⚪'} {name}"


def _emergency_stop():
    try:
        from tools.facebook_api import FacebookAdsClient

        ids = FacebookAdsClient().kill_all_active()
        st.sidebar.success(f"Поставлено на паузу кампаний: {len(ids)}")
    except Exception as exc:  # noqa: BLE001
        st.sidebar.error(f"Не удалось: {exc}")


# ============================================================
#  Дашборд
# ============================================================
def _kpi(col, label: str, value: str):
    col.markdown(
        f'<div class="kpi"><div class="lbl">{label}</div><div class="val">{value}</div></div>',
        unsafe_allow_html=True,
    )


def step_dashboard():
    s = get_settings()
    # Степпер прогресса
    steps = [
        ("Бриф", bool(ss().brief)),
        ("Аналитик", bool(ss().research)),
        ("Креативы", bool(ss().creatives)),
        ("Запуск", bool(ss().campaign)),
        ("Оптимизация", bool(ss().metrics)),
    ]
    active_idx = next((i for i, (_, done) in enumerate(steps) if not done), len(steps) - 1)
    chips = ""
    for i, (name, done) in enumerate(steps):
        cls = "done" if done else ("next" if i == active_idx else "")
        mark = "✓ " if done else ""
        chips += f'<div class="step {cls}">{mark}{name}</div>'
    st.markdown(f'<div class="step-row">{chips}</div>', unsafe_allow_html=True)

    # KPI из последнего прогона оптимизатора
    metrics = ss().metrics
    total_spend = sum(m.spend for m in metrics)
    total_leads = sum(m.leads for m in metrics)
    total_rev = sum(m.revenue for m in metrics)
    avg_ctr = (sum(m.ctr for m in metrics) / len(metrics)) if metrics else 0.0
    avg_cpl = (total_spend / total_leads) if total_leads else None
    roas = (total_rev / total_spend) if total_spend else None

    c1, c2, c3, c4, c5 = st.columns(5)
    _kpi(c1, f"Расход ({s.currency})", f"{total_spend:.2f}")
    _kpi(c2, "Лиды", str(total_leads))
    _kpi(c3, f"CPL ({s.currency})", f"{avg_cpl:.2f}" if avg_cpl else "—")
    _kpi(c4, "CTR ср.", f"{avg_ctr:.2f}%")
    _kpi(c5, "ROAS", f"{roas:.2f}" if roas else "—")

    st.write("")
    if metrics:
        st.caption("Расход по объявлениям")
        st.bar_chart({m.ad_id[-6:]: m.spend for m in metrics})
    else:
        st.info(
            "Данных пока нет. Пройди шаги: **Бриф → Аналитик → Креативы → Запуск**, "
            "затем сними метрики во вкладке **Оптимизатор** — здесь появятся KPI и график."
        )


# ============================================================
#  Шаг 1. Бриф (с автозаполнением ИИ)
# ============================================================
def step_brief():
    st.subheader("Бриф продукта")

    with st.expander("✨ Автозаполнить бриф (ИИ)", expanded=not ss().brief):
        st.caption("Дай ссылку на лендинг и/или пару слов — Claude заполнит бриф, ты проверишь.")
        af_url = st.text_input("Ссылка на лендинг", key="af_url")
        af_note = st.text_area("Пара слов о продукте (необязательно)", key="af_note", height=68)
        if st.button("✨ Заполнить с помощью ИИ", disabled=not (af_url or af_note)):
            with st.spinner("ИИ читает и заполняет бриф..."):
                try:
                    from agents.brief_builder import autofill_brief

                    ss().brief = autofill_brief(note=af_note, url=af_url)
                    ss().research = ss().creatives = ss().campaign = None
                    st.success("Бриф заполнен — проверь и поправь ниже.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Не вышло: {exc}")

    _goals = ["TRAFFIC", "LEAD_GENERATION", "AWARENESS", "SALES"]
    _goal_idx = _goals.index(_bv("goal")) if _bv("goal") in _goals else 0

    with st.form("brief_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Название продукта/услуги", value=_bv("name") or "")
        url = c2.text_input("Посадочная страница (URL)", value=_bv("landing_url") or "")
        desc = st.text_area("Описание (что это, для кого, чем ценно)", value=_bv("description") or "", height=100)
        c3, c4, c5 = st.columns(3)
        geo = c3.text_input("Гео (коды стран через запятую)", value=",".join(_bv("geo") or ["KZ"]))
        price = c4.text_input("Цена (необязательно)", value=_bv("price") or "")
        goal = c5.selectbox("Цель", _goals, index=_goal_idx)
        extra = st.text_area("Доп. вводные для аналитика (необязательно)", value=_bv("extra") or "", height=68)
        submitted = st.form_submit_button("Сохранить бриф", type="primary")

    if submitted:
        if not (name and desc and url):
            st.error("Заполни минимум: название, описание и посадочную.")
            return
        ss().brief = ProductBrief(
            name=name.strip(), description=desc.strip(), landing_url=url.strip(),
            geo=[g.strip().upper() for g in geo.split(",") if g.strip()],
            price=price.strip() or None, goal=goal, extra=extra.strip() or None,
        )
        ss().research = ss().creatives = ss().campaign = None
        st.success("Бриф сохранён.")


def _bv(field: str):
    return getattr(ss().brief, field, None) if ss().brief else None


# ============================================================
#  Шаг 2. Аналитик
# ============================================================
def step_research():
    st.subheader("Аналитик — портреты ЦА и идеи")
    if not ss().brief:
        st.info("Сначала сохрани бриф.")
        return
    if st.button("🔍 Запустить аналитика", type="primary"):
        with st.spinner("Аналитик думает..."):
            try:
                from agents.research import run_research

                ss().research = run_research(ss().brief)
                ss().creatives = None
            except Exception as exc:  # noqa: BLE001
                st.error(f"Аналитик упал: {exc}")

    res = ss().research
    if not res:
        return
    st.markdown("**Сегменты ЦА**")
    for p in res.personas:
        st.markdown(
            f'<div class="stel-card"><b>{p.name}</b><br>'
            f'Боли: {", ".join(p.pains)}<br>Возражения: {", ".join(p.objections)}<br>'
            f'Триггеры: {", ".join(p.triggers)}</div>', unsafe_allow_html=True)

    st.markdown("**Идеи объявлений** (правь перед креативами)")
    edited: list[AdIdea] = []
    for i, idea in enumerate(res.ideas):
        with st.expander(f"Идея {i + 1}: {idea.angle}"):
            persona = st.text_input("Сегмент", value=idea.persona, key=f"idea_persona_{i}")
            offer = st.text_input("Оффер", value=idea.offer, key=f"idea_offer_{i}")
            angle = st.text_input("Угол", value=idea.angle, key=f"idea_angle_{i}")
            kw = st.text_input("Интересы (через запятую)", value=",".join(idea.keywords), key=f"idea_kw_{i}")
            edited.append(AdIdea(
                persona=persona, offer=offer, angle=angle,
                keywords=[k.strip() for k in kw.split(",") if k.strip()],
            ))
    res.ideas = edited


# ============================================================
#  Шаг 3. Креативы
# ============================================================
def step_creatives():
    st.subheader("Креативы — тексты и баннеры")
    if not ss().research:
        st.info("Сначала запусти аналитика.")
        return
    c1, c2 = st.columns(2)
    framework = c1.selectbox("Фреймворк текста", ["AIDA", "PAS"], index=0)
    aspect = c2.selectbox("Формат баннера", ["1:1", "4:5", "9:16"], index=0)

    if st.button("✍️ Сгенерировать креативы (тексты)", type="primary"):
        with st.spinner("Копирайтер пишет..."):
            try:
                from agents.creative import generate_creatives

                ss().creatives = generate_creatives(ss().brief, ss().research.ideas, framework=framework)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Копирайтер упал: {exc}")

    creatives: list[Creative] = ss().creatives or []
    if not creatives:
        return
    st.caption("Отметь галочкой, что пойдёт в запуск. Тексты редактируются здесь.")
    for i, cr in enumerate(creatives):
        st.markdown('<div class="stel-card">', unsafe_allow_html=True)
        left, right = st.columns([2, 1])
        with left:
            cr.headline = st.text_input("Заголовок", value=cr.headline, key=f"cr_h_{i}")
            cr.primary_text = st.text_area("Основной текст", value=cr.primary_text, height=140, key=f"cr_t_{i}")
            cr.description = st.text_input("Описание", value=cr.description, key=f"cr_d_{i}")
            cr.image_prompt = st.text_area("Промпт баннера (EN)", value=cr.image_prompt, height=80, key=f"cr_p_{i}")
            cr.selected = st.checkbox("✅ В запуск", value=getattr(cr, "selected", True), key=f"cr_sel_{i}")
        with right:
            if cr.image_url:
                st.image(cr.image_url, use_container_width=True)
            else:
                st.caption("Баннер ещё не сгенерирован")
            if st.button("🎨 Сгенерировать баннер", key=f"cr_img_{i}"):
                with st.spinner("Рисую баннер..."):
                    try:
                        from agents.creative import attach_image

                        attach_image(cr, aspect_ratio=aspect)
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Не вышло: {exc}")
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
#  Аудитории (ретаргетинг + lookalike)
# ============================================================
def step_audiences():
    st.subheader("Аудитории — ретаргетинг и lookalike")
    st.caption("Тёплый трафик и похожие аудитории — обычно самый дешёвый источник конверсий.")

    if st.button("🔄 Обновить список аудиторий"):
        try:
            from agents.audiences import list_audiences

            ss().audiences_cache = list_audiences()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Не удалось получить: {exc}")

    if ss().audiences_cache:
        st.dataframe(
            [{"ID": a["id"], "Название": a["name"], "Тип": a["subtype"], "Размер": a.get("count", "—")}
             for a in ss().audiences_cache],
            use_container_width=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**➕ Ретаргетинг (посетители сайта)**")
        rt_name = st.text_input("Название", value="Ретаргетинг — сайт 180д", key="rt_name")
        rt_days = st.slider("Окно, дней", 1, 180, 180, key="rt_days")
        if st.button("Создать ретаргетинг"):
            try:
                from agents.audiences import create_retargeting

                res = create_retargeting(rt_name, retention_days=rt_days)
                st.success(f"Создано: {res.get('id')}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Не вышло: {exc}")

    with col2:
        st.markdown("**➕ Lookalike (похожие)**")
        sources = {f"{a['name']} ({a['id']})": a["id"] for a in ss().audiences_cache}
        ll_name = st.text_input("Название", value="LAL 1% — KZ", key="ll_name")
        ll_src = st.selectbox("Источник", list(sources.keys()) or ["— сначала обнови список —"], key="ll_src")
        cc1, cc2 = st.columns(2)
        ll_country = cc1.text_input("Страна (ISO-2)", value="KZ", key="ll_country")
        ll_ratio = cc2.selectbox("Ширина", [0.01, 0.02, 0.05, 0.10], index=0, key="ll_ratio")
        if st.button("Создать lookalike", disabled=not sources):
            try:
                from agents.audiences import create_lookalike

                res = create_lookalike(ll_name, sources[ll_src], ll_country, ratio=ll_ratio)
                st.success(f"Создано: {res.get('id')}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Не вышло: {exc}")


# ============================================================
#  Шаг 4. Запуск
# ============================================================
def step_launch():
    st.subheader("Запуск кампании")
    s = get_settings()
    creatives: list[Creative] = ss().creatives or []
    chosen = [c for c in creatives if getattr(c, "selected", True)]
    ready = [c for c in chosen if c.image_url]
    if not creatives:
        st.info("Сначала сделай креативы.")
        return

    st.write(f"Выбрано креативов: **{len(chosen)}**, из них с баннером: **{len(ready)}**")
    if len(ready) < len(chosen):
        st.warning("У части выбранных креативов нет баннера — они не попадут в запуск.")

    from agents.media_buyer import resolve_campaign_config

    obj, optgoal, promoted = resolve_campaign_config(ss().brief.goal, s.meta_pixel_id)
    if promoted:
        st.success(f"🎯 Оптимизация на **КОНВЕРСИИ**: {obj} · событие {promoted['custom_event_type']}")
    else:
        st.info(f"Оптимизация на **клики**: {obj} · {optgoal}. Для лидов добавь `META_PIXEL_ID`.")

    # Аудитории для таргета
    with st.expander("👥 Аудитории в таргет (ретаргетинг/LAL) и исключения"):
        auds = {f"{a['name']} ({a['subtype']})": a["id"] for a in ss().audiences_cache}
        if not auds:
            st.caption("Список пуст — обнови его во вкладке «Аудитории».")
        tgt = st.multiselect("Таргетировать на аудитории", list(auds.keys()), key="lp_target")
        exc = st.multiselect("Исключить аудитории", list(auds.keys()), key="lp_exclude")
        ss().target_auds = [auds[k] for k in tgt]
        ss().exclude_auds = [auds[k] for k in exc]

    # Интересы
    with st.expander("🎯 Таргетинг по интересам"):
        q = st.text_input("Найти интерес в Meta", key="int_query")
        if st.button("🔎 Искать", disabled=not q):
            try:
                from tools.facebook_api import FacebookAdsClient

                ss()._int_results = FacebookAdsClient().search_interests(q)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Поиск не удался: {exc}")
        labels = {f"{r['name']} (~{r.get('audience', '?')})": r for r in ss()._int_results if r.get("id")}
        if labels:
            for lbl in st.multiselect("Результаты", list(labels.keys())):
                r = labels[lbl]
                if all(x["id"] != r["id"] for x in ss().interests):
                    ss().interests.append(r)
        if ss().interests:
            st.caption("Добавлены: " + ", ".join(i["name"] for i in ss().interests))
            if st.button("Очистить интересы"):
                ss().interests = []
                st.rerun()

    c1, c2, c3 = st.columns(3)
    cbo = c1.checkbox("CBO (бюджет кампании)", value=False, help="Advantage+: Meta сама распределяет бюджет.")
    budget = c2.number_input(
        f"Дневной бюджет, {s.currency}", min_value=1.0, max_value=float(s.max_daily_budget),
        value=min(5.0, float(s.max_daily_budget)), step=1.0,
    )
    activate = c3.checkbox("Просить ACTIVE", value=False, help="В DRY_RUN всё равно PAUSED.")

    try:
        from services.guardrails import preflight

        chk_budget, chk_status = preflight(budget, "ACTIVE" if activate else "PAUSED")
        st.success(
            f"Предохранители OK: бюджет {chk_budget} {s.currency} "
            f"({'на кампанию (CBO)' if cbo else 'на группу'}), статус → {chk_status}"
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Предохранитель блокирует: {exc}")
        return

    if st.button("🚀 Запустить кампанию", type="primary", disabled=not ready):
        with st.spinner("Разворачиваю кампанию в Meta..."):
            try:
                from agents.media_buyer import launch
                from tools import telegram

                camp = launch(
                    ss().brief, ready, daily_budget=budget, activate=activate,
                    interests=ss().interests,
                    custom_audiences=ss().target_auds or None,
                    excluded_audiences=ss().exclude_auds or None,
                    campaign_budget=budget if cbo else None,
                )
                ss().campaign = camp
                telegram.send_message(telegram.format_launch_report(camp, ss().brief))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Запуск не удался: {exc}")

    camp = ss().campaign
    if camp:
        st.markdown(
            f'<div class="stel-card"><b>Кампания создана</b><br>'
            f'ID: <code>{camp.campaign_id}</code><br>'
            f'Групп: {len(camp.adset_ids)} · Объявлений: {len(camp.ad_ids)}<br>'
            f'Статус: <b>{camp.status}</b> (dry_run={camp.dry_run})<br>{camp.note}</div>',
            unsafe_allow_html=True,
        )


# ============================================================
#  Шаг 5. Оптимизатор
# ============================================================
def step_optimizer():
    st.subheader("Оптимизатор — метрики, авто-пауза и масштабирование")
    s = get_settings()
    default_ads = ",".join(ss().campaign.ad_ids) if ss().campaign else ""
    ads_raw = st.text_input("ID объявлений (через запятую)", value=default_ads)
    ad_ids = [a.strip() for a in ads_raw.split(",") if a.strip()]

    c1, c2 = st.columns(2)
    execute = c1.checkbox("Исполнять паузы", value=False, help="Иначе только показать решения.")
    if c2.button("📊 Снять метрики и решить", type="primary", disabled=not ad_ids):
        with st.spinner("Забираю статистику из Meta..."):
            try:
                from agents.optimizer import run_optimizer

                metrics, decisions = run_optimizer(ad_ids, execute=execute)
                ss().metrics, ss().decisions = metrics, decisions
            except Exception as exc:  # noqa: BLE001
                st.error(f"Оптимизатор упал: {exc}")

    if ss().metrics:
        dmap = {d.ad_id: d for d in ss().decisions}
        rows = []
        for m in ss().metrics:
            d = dmap.get(m.ad_id)
            rows.append({
                "Ad ID": m.ad_id, "Расход": round(m.spend, 2), "Клики": m.clicks,
                "CTR": m.ctr, "Частота": round(m.frequency, 1), "Лиды": m.leads,
                "CPL": m.cpl if m.cpl is not None else "—",
                "ROAS": m.roas if m.roas is not None else "—",
                "Решение": "⏸ PAUSE" if d and d.action == "PAUSE" else "▶ KEEP",
                "Причина": d.reason if d else "",
            })
        st.dataframe(rows, use_container_width=True)

    st.divider()
    st.markdown("**⬆️ Масштабирование победителей** (уровень групп)")
    default_sets = ",".join(ss().campaign.adset_ids) if ss().campaign else ""
    sets_raw = st.text_input("ID групп (adset, через запятую)", value=default_sets)
    adset_ids = [a.strip() for a in sets_raw.split(",") if a.strip()]
    cc1, cc2 = st.columns(2)
    step = cc1.slider("Множитель бюджета", 1.1, 2.0, 1.3, 0.1)
    if cc2.button("⬆️ Оценить/масштабировать", disabled=not adset_ids):
        with st.spinner("Считаю победителей..."):
            try:
                from agents.optimizer import run_scaling

                _, decs = run_scaling(adset_ids, step=step, execute=True)
                scaled = [d for d in decs if d.action == "SCALE"]
                if not scaled:
                    st.info("Кандидатов на масштабирование нет (нужен CPL заметно ниже нормы и объём).")
                for d in scaled:
                    st.success(f"↑ {d.ad_id}: {d.reason}")
                if s.dry_run and scaled:
                    st.warning("DRY_RUN включён — бюджет не изменён, показана только рекомендация.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Не вышло: {exc}")


# ============================================================
#  Компоновка
# ============================================================
render_sidebar()
st.title("Пульт AI-таргетолога")
st.caption("Полный цикл под контролем человека: смотришь, правишь, одобряешь, запускаешь.")

tabs = st.tabs([
    "📊 Дашборд", "1 · Бриф", "2 · Аналитик", "3 · Креативы",
    "👥 Аудитории", "4 · Запуск", "5 · Оптимизатор",
])
with tabs[0]:
    step_dashboard()
with tabs[1]:
    step_brief()
with tabs[2]:
    step_research()
with tabs[3]:
    step_creatives()
with tabs[4]:
    step_audiences()
with tabs[5]:
    step_launch()
with tabs[6]:
    step_optimizer()
