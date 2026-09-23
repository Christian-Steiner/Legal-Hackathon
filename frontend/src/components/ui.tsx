import { useCallback, useEffect, useState, type ReactNode } from "react";
import type { Urgency } from "../types";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    fn()
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(reload, [reload]);
  return { data, error, loading, reload, setData };
}

export function UrgencyBadge({ u }: { u: Urgency }) {
  return <span className={`badge urg-${u}`}>{u}</span>;
}

export function StatusBadge({ s }: { s: string }) {
  return <span className={`badge st-${s}`}>{s.replace("_", " ")}</span>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge tone-${tone}`}>{children}</span>;
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error">{error}</div> : null;
}

export function Loading({ on }: { on: boolean }) {
  return on ? <div className="muted">Loading…</div> : null;
}

export function Disclaimer({ text }: { text: string }) {
  return <p className="disclaimer">⚖️ {text}</p>;
}

export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleDateString("de-CH") : "–");
export const fmtDateTime = (s?: string | null) => (s ? new Date(s).toLocaleString("de-CH") : "–");

export const UPDATE_TYPE_LABEL: Record<string, string> = {
  as_publication: "AS publication",
  entry_into_force: "Upcoming entry into force",
  consultation: "Consultation",
  simulated: "Simulated (organisers' dataset)",
};

export const SCOPE_LABEL: Record<string, string> = {
  all_legal_entities: "all companies",
  employers: "all employers",
};
