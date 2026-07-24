"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

// Общее состояние витрины между экранами (аналог st.session_state в Streamlit).
type State = {
  brief: any | null;
  research: any | null;
  creatives: any[];
  campaign: any | null;
  metrics: any[];
};

const EMPTY: State = { brief: null, research: null, creatives: [], campaign: null, metrics: [] };

type Ctx = State & {
  set: (patch: Partial<State>) => void;
  reset: () => void;
};

const StoreContext = createContext<Ctx | null>(null);
const KEY = "targetolog-state";

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(EMPTY);

  // загрузка из localStorage
  useEffect(() => {
    try {
      const raw = typeof window !== "undefined" && localStorage.getItem(KEY);
      if (raw) setState({ ...EMPTY, ...JSON.parse(raw) });
    } catch {}
  }, []);

  // сохранение
  useEffect(() => {
    try {
      if (typeof window !== "undefined") localStorage.setItem(KEY, JSON.stringify(state));
    } catch {}
  }, [state]);

  const set = (patch: Partial<State>) => setState((s) => ({ ...s, ...patch }));
  const reset = () => setState(EMPTY);

  return <StoreContext.Provider value={{ ...state, set, reset }}>{children}</StoreContext.Provider>;
}

export function useStore(): Ctx {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore вне StoreProvider");
  return ctx;
}
