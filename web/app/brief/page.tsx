"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { PageHeader, Card, Btn, Field, Area, Err } from "@/components/ui";

const GOALS = ["TRAFFIC", "LEAD_GENERATION", "AWARENESS", "SALES"];

export default function BriefPage() {
  const { brief, set } = useStore();
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [b, setB] = useState<any>(
    brief ?? { name: "", description: "", landing_url: "", geo: ["KZ"], price: "", goal: "TRAFFIC" }
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const autofill = async () => {
    setBusy(true);
    setErr(null);
    try {
      const filled = await api.autofillBrief(url, note);
      setB(filled);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    set({ brief: { ...b, geo: Array.isArray(b.geo) ? b.geo : String(b.geo).split(",").map((x: string) => x.trim()) }, research: null, creatives: [] });
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Бриф продукта" subtitle="Заполни вручную или дай ИИ ссылку на лендинг." />

      <Card className="mb-5">
        <div className="mb-2 text-sm font-semibold text-white">✨ Автозаполнение ИИ</div>
        <div className="space-y-3">
          <Field label="Ссылка на лендинг" value={url} onChange={setUrl} placeholder="https://..." />
          <Area label="Пара слов о продукте (необязательно)" value={note} onChange={setNote} rows={2} />
          <Btn onClick={autofill} loading={busy} disabled={!url && !note}>
            ✨ Заполнить с помощью ИИ
          </Btn>
        </div>
        <Err msg={err} />
      </Card>

      <Card>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Название" value={b.name ?? ""} onChange={(v) => setB({ ...b, name: v })} />
          <Field label="Посадочная (URL)" value={b.landing_url ?? ""} onChange={(v) => setB({ ...b, landing_url: v })} />
        </div>
        <div className="mt-3">
          <Area label="Описание" value={b.description ?? ""} onChange={(v) => setB({ ...b, description: v })} />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <Field label="Гео (через запятую)" value={Array.isArray(b.geo) ? b.geo.join(",") : b.geo ?? ""} onChange={(v) => setB({ ...b, geo: v.split(",").map((x) => x.trim()) })} />
          <Field label="Цена" value={b.price ?? ""} onChange={(v) => setB({ ...b, price: v })} />
          <label className="block">
            <span className="mb-1 block text-xs uppercase tracking-wide text-zinc-400">Цель</span>
            <select
              value={b.goal}
              onChange={(e) => setB({ ...b, goal: e.target.value })}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
            >
              {GOALS.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Btn onClick={save} disabled={!b.name || !b.description || !b.landing_url}>Сохранить бриф</Btn>
          {brief && <span className="text-sm text-accent">✓ бриф сохранён</span>}
        </div>
      </Card>
    </div>
  );
}
