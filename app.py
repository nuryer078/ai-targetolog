"""Визуальная панель управления AI-таргетологом (Streamlit).

Сквозной human-in-the-loop пульт:
  Бриф -> Аналитик -> Креативы (правка + баннеры) -> Отбор и запуск -> Оптимизатор.

Запуск:  streamlit run app.py

Ничего не откручивается, пока в .env DRY_RUN=true — всё создаётся в статусе PAUSED.
"""
from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from services.state import AdIdea, Creative, ProductBrief

st.set_page_config(page_title="AI-таргетолог", page_icon="🎯", layout="wide")

# --- лёгкий стиль ---
st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem;}
      .stel-card {border:1px solid rgba(128,128,128,.25); border-radius:14px;
                  padding:1rem 1.2rem; margin-bottom:1rem; background:rgba(128,128,128,.05);}
      .stel-badge {display:inline-block; padding:.15rem .6rem; border-radius:999px;
                   font-size:.8rem; font-weight:600;}
      .stel-dry {background:#1f6f3c33; color:#39d98a; border:1px solid #39d98a55;}
      .stel-live {background:#7a1f1f33; color:#ff6b6b; border:1px solid #ff6b6b55;}
    </style>
    """,
    unsafe_allow_html=True,
)


def ss():
    return st.session_state


# --- инициализация состояния ---
for key in ("brief", "research", "creatives", "campaign"):
    ss().setdefault(key, None)
ss().setdefault("metrics", [])
ss().setdefault("decisions", [])


# ============================================================
#  Боковая панель: статус, предохранители, аварийный стоп
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
            st.warning("DRY_RUN выключен — кампании можно активировать за реальные деньги.")

        st.divider()
        st.caption("Предохранители (.env)")
        st.write(f"Лимит бюджета/день: **{s.max_daily_budget} {s.currency}**")
        st.write(f"Норма CPL: **{s.target_cpl} {s.currency}**")

        st.divider()
        st.caption("Подключения")
        st.write(_conn("Claude", s.anthropic_api_key))
        st.write(_conn("Meta Ads", s.meta_access_token and s.meta_ad_account_id))
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
#  Шаг 1. Бриф продукта
# ============================================================
def step_brief():
    st.subheader("1 · Бриф продукта")
    with st.form("brief_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Название продукта/услуги", value=_bv("name"))
        url = c2.text_input("Посадочная страница (URL)", value=_bv("landing_url"))
        desc = st.text_area("Описание (что это, для кого, чем ценно)", value=_bv("description"), height=100)
        c3, c4, c5 = st.columns(3)
        geo = c3.text_input("Гео (коды стран через запятую)", value=",".join(_bv("geo") or ["KZ"]))
        price = c4.text_input("Цена (необязательно)", value=_bv("price") or "")
        goal = c5.selectbox("Цель", ["TRAFFIC", "LEAD_GENERATION", "AWARENESS"], index=0)
        extra = st.text_area("Доп. вводные для аналитика (необязательно)", value=_bv("extra") or "", height=68)
        submitted = st.form_submit_button("Сохранить бриф", type="primary")

    if submitted:
        if not (name and desc and url):
            st.error("Заполни минимум: название, описание и посадочную.")
            return
        ss().brief = ProductBrief(
            name=name.strip(),
            description=desc.strip(),
            landing_url=url.strip(),
            geo=[g.strip().upper() for g in geo.split(",") if g.strip()],
            price=price.strip() or None,
            goal=goal,
            extra=extra.strip() or None,
        )
        # сброс дальнейших шагов
        ss().research = ss().creatives = ss().campaign = None
        st.success("Бриф сохранён.")


def _bv(field: str):
    return getattr(ss().brief, field, None) if ss().brief else None


# ============================================================
#  Шаг 2. Аналитик
# ============================================================
def step_research():
    st.subheader("2 · Аналитик — портреты ЦА и идеи")
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
        with st.container():
            st.markdown(f'<div class="stel-card"><b>{p.name}</b><br>'
                        f'Боли: {", ".join(p.pains)}<br>'
                        f'Возражения: {", ".join(p.objections)}<br>'
                        f'Триггеры: {", ".join(p.triggers)}</div>', unsafe_allow_html=True)

    st.markdown("**Идеи объявлений** (можно править перед креативами)")
    edited: list[AdIdea] = []
    for i, idea in enumerate(res.ideas):
        with st.expander(f"Идея {i + 1}: {idea.angle}", expanded=False):
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
#  Шаг 3. Креативы (текст + баннеры), правка на лету
# ============================================================
def step_creatives():
    st.subheader("3 · Креативы — тексты и баннеры")
    if not ss().research:
        st.info("Сначала запусти аналитика.")
        return

    c1, c2 = st.columns([1, 1])
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

    st.caption("Отметь галочкой, что пойдёт в запуск. Тексты редактируются прямо здесь.")
    for i, cr in enumerate(creatives):
        with st.container():
            st.markdown(f'<div class="stel-card">', unsafe_allow_html=True)
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
#  Шаг 4. Отбор и запуск
# ============================================================
def step_launch():
    st.subheader("4 · Запуск кампании")
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

    c1, c2 = st.columns(2)
    budget = c1.number_input(
        f"Дневной бюджет группы, {s.currency}",
        min_value=1.0, max_value=float(s.max_daily_budget), value=min(5.0, float(s.max_daily_budget)), step=1.0,
    )
    activate = c2.checkbox("Просить ACTIVE после создания", value=False,
                           help="В режиме DRY_RUN всё равно останется PAUSED.")

    # предпросмотр проверки предохранителей
    try:
        from services.guardrails import preflight

        chk_budget, chk_status = preflight(budget, "ACTIVE" if activate else "PAUSED")
        st.success(f"Предохранители OK: бюджет {chk_budget} {s.currency}, статус при создании → {chk_status}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Предохранитель блокирует: {exc}")
        return

    if st.button("🚀 Запустить кампанию", type="primary", disabled=not ready):
        with st.spinner("Разворачиваю кампанию в Meta..."):
            try:
                from agents.media_buyer import launch
                from tools import telegram

                camp = launch(ss().brief, ready, daily_budget=budget, activate=activate)
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
    st.subheader("5 · Оптимизатор — метрики и авто-пауза")
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
        rows = []
        dmap = {d.ad_id: d for d in ss().decisions}
        for m in ss().metrics:
            d = dmap.get(m.ad_id)
            rows.append({
                "Ad ID": m.ad_id, "Spend": m.spend, "Clicks": m.clicks,
                "CTR": m.ctr, "Leads": m.leads,
                "CPL": m.cpl if m.cpl is not None else "—",
                "Решение": f"{'⏸ PAUSE' if d and d.action == 'PAUSE' else '▶ KEEP'}",
                "Причина": d.reason if d else "",
            })
        st.dataframe(rows, use_container_width=True)


# ============================================================
#  Компоновка
# ============================================================
render_sidebar()
st.title("Пульт AI-таргетолога")
st.caption("Полный цикл под контролем человека: смотришь, правишь, одобряешь, запускаешь.")

tabs = st.tabs(["1 · Бриф", "2 · Аналитик", "3 · Креативы", "4 · Запуск", "5 · Оптимизатор"])
with tabs[0]:
    step_brief()
with tabs[1]:
    step_research()
with tabs[2]:
    step_creatives()
with tabs[3]:
    step_launch()
with tabs[4]:
    step_optimizer()
