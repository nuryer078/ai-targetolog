// Клиент FastAPI-бэкенда. Базовый URL берём из окружения (по умолчанию localhost:8000).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Health = {
  ok: boolean;
  dry_run: boolean;
  currency: string;
  max_daily_budget: number;
  target_cpl: number;
  connections: Record<string, boolean>;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `Ошибка API ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<Health>("/health"),
  history: () => req<any[]>("/history"),
  autofillBrief: (url: string, note: string) =>
    req<any>("/brief/autofill", { method: "POST", body: JSON.stringify({ url, note }) }),
  research: (brief: any) =>
    req<any>("/research", { method: "POST", body: JSON.stringify({ brief }) }),
};
