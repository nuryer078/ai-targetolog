"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Card, Btn, Field, Err } from "@/components/ui";

export default function AudiencesPage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const search = async () => {
    setBusy(true);
    setErr(null);
    try {
      setRes(await api.interests(q));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Аудитории" subtitle="Поиск интересов Meta для точного таргетинга." />
      <Card>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <Field label="Интерес" value={q} onChange={setQ} placeholder="напр. фитнес, маркетинг…" />
          </div>
          <Btn onClick={search} loading={busy} disabled={!q}>🔎 Искать</Btn>
        </div>
        <Err msg={err} />
        {res.length > 0 && (
          <div className="mt-4 space-y-2">
            {res.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-xl border border-white/10 px-3 py-2 text-sm">
                <span className="text-white">{r.name}</span>
                <span className="text-zinc-500">~{r.audience ?? "?"}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
      <p className="mt-4 text-xs text-zinc-500">
        Ретаргетинг и lookalike-аудитории — в панели Streamlit; здесь пока поиск интересов.
      </p>
    </div>
  );
}
