"use client";

import { ReactNode } from "react";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-extrabold text-white">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-zinc-400">{subtitle}</p>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`glass p-5 ${className}`}>{children}</div>;
}

export function Btn({
  children,
  onClick,
  disabled,
  loading,
  variant = "accent",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "accent" | "ghost";
}) {
  const base =
    variant === "accent"
      ? "btn-accent"
      : "rounded-xl border border-white/15 px-4 py-2 font-medium text-zinc-200 transition hover:bg-white/5";
  return (
    <button onClick={onClick} disabled={disabled || loading} className={`${base} disabled:opacity-50`}>
      {loading ? "…" : children}
    </button>
  );
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs uppercase tracking-wide text-zinc-400">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
      />
    </label>
  );
}

export function Area({
  label,
  value,
  onChange,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs uppercase tracking-wide text-zinc-400">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
      />
    </label>
  );
}

export function Err({ msg }: { msg?: string | null }) {
  if (!msg) return null;
  return <div className="glass mt-3 border-danger/30 p-3 text-sm text-danger">{msg}</div>;
}
