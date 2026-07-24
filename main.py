"""CLI-вход в AI-таргетолог.

Панель управления запускается отдельно:  streamlit run app.py
CLI нужен для автономного прогона, оптимизатора (крон) и аварийного стопа.

Примеры:
    python main.py run --name "Курс по SMM" --desc "..." --url https://... --geo KZ --budget 5
    python main.py optimize --ads 123 456          # цикл оптимизатора
    python main.py kill                             # аварийно паузит все ACTIVE-кампании
"""
from __future__ import annotations

import argparse
import sys

from config.settings import get_settings
from services.logger import get_logger
from services.state import ProductBrief

log = get_logger("cli")


def cmd_run(args: argparse.Namespace) -> int:
    from agents.pipeline import run_autonomous

    brief = ProductBrief(
        name=args.name,
        description=args.desc,
        landing_url=args.url,
        geo=args.geo,
        price=args.price,
        goal=args.goal,
        extra=args.extra,
    )
    campaign = run_autonomous(
        brief, daily_budget=args.budget, framework=args.framework, activate=args.activate
    )
    print(f"\nКампания: {campaign.campaign_id}")
    print(f"Статус:   {campaign.status}  (dry_run={campaign.dry_run})")
    print(f"Объявлений: {len(campaign.ad_ids)}")
    print(campaign.note)
    return 0


def cmd_optimize(args: argparse.Namespace) -> int:
    from agents.optimizer import run_optimizer
    from tools import telegram

    settings = get_settings()
    metrics, decisions = run_optimizer(args.ads, execute=not args.dry)
    for m in metrics:
        cpl = f"{m.cpl:.2f}" if m.cpl is not None else "—"
        print(f"{m.ad_id}: spend={m.spend:.2f} clicks={m.clicks} leads={m.leads} CPL={cpl}")
    report = telegram.format_optimization_report(decisions, metrics, settings.currency)
    telegram.send_message(report)
    paused = sum(1 for d in decisions if d.action == "PAUSE")
    print(f"\nНа паузу: {paused} из {len(decisions)}")
    return 0


def cmd_scale(args: argparse.Namespace) -> int:
    from agents.optimizer import run_scaling

    settings = get_settings()
    metrics, decisions = run_scaling(args.adsets, step=args.step, execute=not args.dry)
    scaled = [d for d in decisions if d.action == "SCALE"]
    for d in scaled:
        print(f"↑ {d.ad_id}: {d.reason}")
    if settings.dry_run:
        print("DRY_RUN включён — масштабирование не исполнено (только показано).")
    print(f"\nК масштабированию: {len(scaled)} из {len(args.adsets)} групп")
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    from tools.facebook_api import FacebookAdsClient

    ids = FacebookAdsClient().kill_all_active()
    print(f"Аварийно поставлено на паузу кампаний: {len(ids)}")
    for i in ids:
        print(f"  ⏸ {i}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AI-таргетолог — мультиагентная система Meta Ads")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="Автономный проход: аналитика -> креативы -> запуск")
    r.add_argument("--name", required=True)
    r.add_argument("--desc", required=True)
    r.add_argument("--url", required=True, help="Посадочная страница")
    r.add_argument("--geo", nargs="+", default=["KZ"])
    r.add_argument("--budget", type=float, required=True, help="Дневной бюджет группы")
    r.add_argument("--price", default=None)
    r.add_argument("--goal", default="TRAFFIC")
    r.add_argument("--framework", default="AIDA", choices=["AIDA", "PAS"])
    r.add_argument("--extra", default=None)
    r.add_argument(
        "--activate", action="store_true",
        help="Просить ACTIVE (в DRY_RUN всё равно останется PAUSED)",
    )
    r.set_defaults(func=cmd_run)

    o = sub.add_parser("optimize", help="Цикл оптимизатора по списку объявлений")
    o.add_argument("--ads", nargs="+", required=True, help="ID объявлений")
    o.add_argument("--dry", action="store_true", help="Не паузить, только показать")
    o.set_defaults(func=cmd_optimize)

    sc = sub.add_parser("scale", help="Масштабировать бюджет групп-победителей (с потолком)")
    sc.add_argument("--adsets", nargs="+", required=True, help="ID групп объявлений")
    sc.add_argument("--step", type=float, default=1.3, help="Множитель бюджета (по умолч. 1.3)")
    sc.add_argument("--dry", action="store_true", help="Только показать, не менять")
    sc.set_defaults(func=cmd_scale)

    k = sub.add_parser("kill", help="Аварийно поставить на паузу все ACTIVE-кампании")
    k.set_defaults(func=cmd_kill)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        log.exception("Команда упала: %s", exc)
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
