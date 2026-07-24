"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { PageHeader, Card, Btn, Err } from "@/components/ui";

export default function ResearchPage() {
  const { brief, research, set } = useStore();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.research(brief);
      set({ research: res, creatives: [] });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!brief) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title="Аналитик" />
        <Card>Сначала сохрани бриф на вкладке «Бриф».</Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Аналитик — портреты ЦА и идеи" subtitle={`Продукт: ${brief.name}`} />
      <Btn onClick={run} loading={busy}>🔍 Запустить аналитика</Btn>
      <Err msg={err} />

      {research && (
        <div className="mt-5 space-y-4">
          <div className="text-sm font-semibold text-white">Сегменты ЦА</div>
          <div className="grid gap-3 md:grid-cols-2">
            {research.personas?.map((p: any, i: number) => (
              <Card key={i}>
                <div className="font-semibold text-white">{p.name}</div>
                <div className="mt-1 text-sm text-zinc-400">Боли: {p.pains?.join(", ")}</div>
                <div className="text-sm text-zinc-400">Возражения: {p.objections?.join(", ")}</div>
                <div className="text-sm text-zinc-400">Триггеры: {p.triggers?.join(", ")}</div>
              </Card>
            ))}
          </div>
          <div className="text-sm font-semibold text-white">Идеи объявлений</div>
          <div className="grid gap-3 md:grid-cols-2">
            {research.ideas?.map((idea: any, i: number) => (
              <Card key={i}>
                <div className="text-xs uppercase text-accent">{idea.persona}</div>
                <div className="mt-1 font-medium text-white">{idea.angle}</div>
                <div className="mt-1 text-sm text-zinc-400">{idea.offer}</div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
