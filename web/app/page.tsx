"use client";

import { useEffect, useState } from "react";
import { api, type Health } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { useStore } from "@/lib/store";

const STEPS = ["Бриф", "Аналитик", "Креативы", "Запуск", "Оптимизация"];

const CONN_LABELS: Record<string, string> = {
  claude: "Claude",
  meta: "Meta Ads",
  pixel: "Пиксель",
  replicate: "Replicate",
  telegram: "Telegram",
};

export default function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { metrics } = useStore();

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const spend = metrics.reduce((a, m) => a + (m.spend ?? 0), 0);
  const leads = metrics.reduce((a, m) => a + (m.leads ?? 0), 0);
  const revenue = metrics.reduce((a, m) => a + (m.revenue ?? 0), 0);
  const ctr = metrics.length ? metrics.reduce((a, m) => a + (m.ctr ?? 0), 0) / metrics.length : 0;
  const cpl = leads ? spend / leads : null;
  const roas = spend ? revenue / spend : null;

  return (
    <div className="mx-auto max-w-6xl">
      {/* Шапка */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-white">Пульт AI-таргетолога</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Полный цикл под контролем человека: смотришь, правишь, одобряешь, запускаешь.
          </p>
        </div>
        {health && (
          <span
            className={`chip ${
              health.dry_run
                ? "border-accent/40 bg-accent-soft text-accent"
                : "border-danger/40 bg-danger/10 text-danger"
            }`}
          >
            {health.dry_run ? "DRY-RUN · безопасно" : "БОЕВОЙ РЕЖИМ"}
          </span>
        )}
      </div>

      {error && (
        <div className="glass mb-6 border-danger/30 p-4 text-sm text-danger">
          API недоступен: {error}. Запусти бэкенд: <code>uvicorn api:app --port 8000</code>
        </div>
      )}

      {/* Степпер */}
      <div className="mb-6 flex gap-2">
        {STEPS.map((s) => (
          <div
            key={s}
            className="glass flex-1 py-2 text-center text-sm text-zinc-400"
          >
            {s}
          </div>
        ))}
      </div>

      {/* KPI */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <KpiCard label={`Расход (${health?.currency ?? "USD"})`} value={spend.toFixed(2)} />
        <KpiCard label="Лиды" value={String(leads)} />
        <KpiCard label={`CPL (${health?.currency ?? "USD"})`} value={cpl ? cpl.toFixed(2) : "—"} />
        <KpiCard label="CTR ср." value={`${ctr.toFixed(2)}%`} />
        <KpiCard label="ROAS" value={roas ? roas.toFixed(2) : "—"} />
      </div>

      {/* Подключения + предохранители */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="glass p-5">
          <div className="mb-3 text-sm font-semibold text-white">Подключения</div>
          <div className="flex flex-wrap gap-2">
            {health &&
              Object.entries(health.connections).map(([k, ok]) => (
                <span
                  key={k}
                  className={`chip ${
                    ok ? "border-accent/40 text-accent" : "border-white/10 text-zinc-500"
                  }`}
                >
                  {ok ? "🟢" : "⚪"} {CONN_LABELS[k] ?? k}
                </span>
              ))}
          </div>
        </div>
        <div className="glass p-5">
          <div className="mb-3 text-sm font-semibold text-white">Предохранители</div>
          <div className="space-y-1 text-sm text-zinc-400">
            <div>
              Лимит бюджета/день:{" "}
              <b className="text-white">
                {health?.max_daily_budget ?? "—"} {health?.currency}
              </b>
            </div>
            <div>
              Норма CPL:{" "}
              <b className="text-white">
                {health?.target_cpl ?? "—"} {health?.currency}
              </b>
            </div>
          </div>
        </div>
      </div>

      <p className="mt-8 text-center text-xs text-zinc-600">
        Витрина Next.js (тёмный премиум) · milestone 1 · остальные экраны — в разработке
      </p>
    </div>
  );
}
