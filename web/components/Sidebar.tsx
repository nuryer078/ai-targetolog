"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Дашборд", icon: "📊" },
  { href: "/brief", label: "Бриф", icon: "📝" },
  { href: "/research", label: "Аналитик", icon: "🔍" },
  { href: "/creatives", label: "Креативы", icon: "🎨" },
  { href: "/audiences", label: "Аудитории", icon: "👥" },
  { href: "/launch", label: "Запуск", icon: "🚀" },
  { href: "/optimizer", label: "Оптимизатор", icon: "📈" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 flex w-64 flex-col gap-6 border-r border-white/10 bg-black/30 p-5 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft text-lg ring-1 ring-accent/30">
          🎯
        </span>
        <div className="text-sm font-bold leading-tight text-white">
          AI-таргетолог
          <div className="text-[.7rem] font-normal text-zinc-500">performance на автопилоте</div>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map((n) => {
          const active = path === n.href;
          return (
            <Link key={n.href} href={n.href} className={`nav-link ${active ? "nav-link-active" : ""}`}>
              <span>{n.icon}</span>
              {n.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto text-[.7rem] leading-relaxed text-zinc-600">
        Полный цикл под контролем человека:
        <br />
        смотришь · правишь · одобряешь · запускаешь
      </div>
    </aside>
  );
}
