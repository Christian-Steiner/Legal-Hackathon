// Demo role switching (no real auth - out of scope). Persisted per browser.
import { useEffect, useState } from "react";

export interface Session {
  role: "lawyer" | "client";
  lawyerName: string;
  companyId: number | null;
}

const KEY = "regmonitor.session";
const DEFAULT: Session = { role: "lawyer", lawyerName: "Dr. Anna Keller", companyId: null };

export function getSession(): Session {
  try {
    return { ...DEFAULT, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return DEFAULT;
  }
}

export function setSession(patch: Partial<Session>) {
  const next = { ...getSession(), ...patch };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch { /* private mode */ }
  window.dispatchEvent(new Event("session"));
}

export function useSession(): Session {
  const [s, set] = useState(getSession);
  useEffect(() => {
    const h = () => set(getSession());
    window.addEventListener("session", h);
    return () => window.removeEventListener("session", h);
  }, []);
  return s;
}
