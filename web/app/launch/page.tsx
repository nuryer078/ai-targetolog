"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { PageHeader, Card, Btn, Err } from "@/components/ui";

export default function LaunchPage() {
  const { brief, creatives, campaign, set } = useStore();
  const [budget, setBudget] = useState(5);
  const [ab, setAb] = useState(false);
  const [cbo, setCbo] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const ready = creatives.filter((c) => (c.selected ?? true) && c.image_url);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const camp = await api.launch({
        brief,
        creatives: ready,
        daily_budget: budget,
        ab_test: ab,
        campaign_budget: cbo ? budget : null,
      });
      set({ campaign: camp });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!creatives.length) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title="Запуск" />
        <Card>Сначала сделай креативы (с баннерами).</Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Запуск кампании" subtitle={`Готовых креативов с баннером: ${ready.length}`} />
      <Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-xs uppercase text-zinc-400">Бюджет/день</span>
            <input
              type="number"
              value={budget}
              min={1}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="mt-6 flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={ab} onChange={(e) => setAb(e.target.checked)} /> A/B-тест
          </label>
          <label className="mt-6 flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={cbo} onChange={(e) => setCbo(e.target.checked)} /> CBO
          </label>
        </div>
        {ab && !cbo && (
          <p className="mt-2 text-xs text-amber-400">
            ⚠️ A/B без CBO: суммарно до {budget * Math.max(ready.length, 1)} /день.
          </p>
        )}
        <div className="mt-4">
          <Btn onClick={run} loading={busy} disabled={!ready.length}>🚀 Запустить кампанию</Btn>
        </div>
        <Err msg={err} />
      </Card>

      {campaign && (
        <Card className="mt-4">
          <div className="font-semibold text-white">Кампания создана</div>
          <div className="mt-1 text-sm text-zinc-400">ID: {campaign.campaign_id}</div>
          <div className="text-sm text-zinc-400">
            Групп: {campaign.adset_ids?.length} · Объявлений: {campaign.ad_ids?.length} · Статус:{" "}
            <b className="text-white">{campaign.status}</b>
          </div>
          <div className="mt-1 text-sm text-accent">{campaign.note}</div>
        </Card>
      )}
    </div>
  );
}
