// Клиент FastAPI-бэкенда. Базовый URL берём из окружения (по умолчанию localhost:8000).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Токен для защищённого API (совпадает с API_TOKEN на бэкенде). Пусто = без токена.
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

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
    headers: {
      "Content-Type": "application/json",
      ...(API_TOKEN ? { "X-API-Token": API_TOKEN } : {}),
    },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `Ошибка API ${res.status}`);
  }
  return res.json() as Promise<T>;
}

const post = (path: string, body: any) =>
  req<any>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => req<Health>("/health"),
  history: () => req<any[]>("/history"),

  autofillBrief: (url: string, note: string) => post("/brief/autofill", { url, note }),
  research: (brief: any) => post("/research", { brief }),
  creatives: (brief: any, ideas: any[], framework: string) =>
    post("/creatives", { brief, ideas, framework }),
  creativeImage: (creative: any, aspect_ratio = "1:1") =>
    post("/creatives/image", { creative, aspect_ratio }),
  interests: (q: string) => req<any[]>(`/audiences/interests?q=${encodeURIComponent(q)}`),
  launch: (payload: {
    brief: any;
    creatives: any[];
    daily_budget: number;
    ab_test?: boolean;
    campaign_budget?: number | null;
    interests?: any[] | null;
  }) => post("/launch", payload),
  optimize: (ad_ids: string[], execute = false) => post("/optimize", { ad_ids, execute }),
};
