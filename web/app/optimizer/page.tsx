"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { PageHeader, Card, Btn, Err } from "@/components/ui";

export default function OptimizerPage() {
  const { campaign, metrics, set } = useStore();
  const [ids, setIds] = useState<string>((campaign?.ad_ids ?? []).join(","));
  const [execute, setExecute] = useState(false);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const adIds = ids.split(",").map((s: string) => s.trim()).filter(Boolean);
      const r = await api.optimize(adIds, execute);
      set({ metrics: r.metrics });
      setDecisions(r.decisions);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const dmap = Object.fromEntries(decisions.map((d) => [d.ad_id, d]));

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Оптимизатор — метрики и авто-пауза" />
      <Card>
        <label className="block">
          <span className="mb-1 block text-xs uppercase text-zinc-400">ID объявлений (через запятую)</span>
          <input
            value={ids}
            onChange={(e) => setIds(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
          />
        </label>
        <div className="mt-3 flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={execute} onChange={(e) => setExecute(e.target.checked)} /> Исполнять паузы
          </label>
          <Btn onClick={run} loading={busy} disabled={!ids.trim()}>📊 Снять метрики</Btn>
        </div>
        <Err msg={err} />
      </Card>

      {metrics.length > 0 && (
        <Card className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-zinc-400">
              <tr>
                <th className="py-2">Ad</th><th>Расход</th><th>Клики</th><th>Лиды</th>
                <th>CPL</th><th>ROAS</th><th>Решение</th>
              </tr>
            </thead>
            <tbody className="text-zinc-200">
              {metrics.map((m) => (
                <tr key={m.ad_id} className="border-t border-white/5">
                  <td className="py-2">{m.ad_id}</td>
                  <td>{m.spend?.toFixed?.(2)}</td>
                  <td>{m.clicks}</td>
                  <td>{m.leads}</td>
                  <td>{m.cpl ?? "—"}</td>
                  <td>{m.roas ?? "—"}</td>
                  <td className={dmap[m.ad_id]?.action === "PAUSE" ? "text-danger" : "text-accent"}>
                    {dmap[m.ad_id]?.action === "PAUSE" ? "⏸ PAUSE" : "▶ KEEP"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
