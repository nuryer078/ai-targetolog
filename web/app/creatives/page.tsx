"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { PageHeader, Card, Btn, Area, Field, Err } from "@/components/ui";

export default function CreativesPage() {
  const { brief, research, creatives, set } = useStore();
  const [framework, setFramework] = useState("AIDA");
  const [busy, setBusy] = useState(false);
  const [imgBusy, setImgBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const gen = async () => {
    setBusy(true);
    setErr(null);
    try {
      const list = await api.creatives(brief, research.ideas, framework);
      set({ creatives: list.map((c: any) => ({ ...c, selected: true })) });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const update = (i: number, patch: any) => {
    const next = creatives.map((c, idx) => (idx === i ? { ...c, ...patch } : c));
    set({ creatives: next });
  };

  const makeImage = async (i: number) => {
    setImgBusy(i);
    setErr(null);
    try {
      const updated = await api.creativeImage(creatives[i]);
      update(i, { image_url: updated.image_url });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setImgBusy(null);
    }
  };

  if (!research) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title="Креативы" />
        <Card>Сначала запусти аналитика.</Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Креативы — тексты и баннеры" />
      <div className="mb-4 flex items-center gap-3">
        <select
          value={framework}
          onChange={(e) => setFramework(e.target.value)}
          className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
        >
          <option>AIDA</option>
          <option>PAS</option>
        </select>
        <Btn onClick={gen} loading={busy}>✍️ Сгенерировать креативы</Btn>
      </div>
      <Err msg={err} />

      <div className="mt-4 space-y-4">
        {creatives.map((c, i) => (
          <Card key={i}>
            <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
              <div className="space-y-2">
                <Field label="Заголовок" value={c.headline ?? ""} onChange={(v) => update(i, { headline: v })} />
                <Area label="Текст" value={c.primary_text ?? ""} onChange={(v) => update(i, { primary_text: v })} rows={4} />
                <Field label="Описание" value={c.description ?? ""} onChange={(v) => update(i, { description: v })} />
                <label className="flex items-center gap-2 text-sm text-zinc-300">
                  <input type="checkbox" checked={c.selected ?? true} onChange={(e) => update(i, { selected: e.target.checked })} />
                  В запуск
                </label>
              </div>
              <div>
                {c.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.image_url} alt="" className="w-full rounded-xl border border-white/10" />
                ) : (
                  <div className="grid h-40 place-items-center rounded-xl border border-dashed border-white/10 text-xs text-zinc-500">
                    баннер не сгенерирован
                  </div>
                )}
                <div className="mt-2">
                  <Btn variant="ghost" onClick={() => makeImage(i)} loading={imgBusy === i}>🎨 Баннер</Btn>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
