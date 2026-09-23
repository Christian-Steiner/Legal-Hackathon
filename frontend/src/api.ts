import type {
  Alert, AuditLogEntry, Company, CompanyIn, Draft, DraftDetail, DraftEdit, EmailPreview, Match, Meta,
  PipelineResult, RegulatoryUpdate, RegulatoryUpdateListItem,
} from "./types";
import { getSession } from "./session";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const s = getSession();
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Role": s.role,
      "X-Actor": s.role === "lawyer" ? s.lawyerName : `company-${s.companyId ?? "new"}`,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch { /* not json */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

const qs = (p: Record<string, string | number | boolean | undefined>) => {
  const e = Object.entries(p).filter(([, v]) => v !== undefined) as [string, string][];
  return e.length ? "?" + new URLSearchParams(e.map(([k, v]) => [k, String(v)])).toString() : "";
};

export const api = {
  meta: () => req<Meta>("GET", "/meta"),

  companies: () => req<Company[]>("GET", "/companies"),
  company: (id: number) => req<Company>("GET", `/companies/${id}`),
  createCompany: (c: CompanyIn) => req<Company>("POST", "/companies", c),
  updateCompany: (id: number, c: CompanyIn) => req<Company>("PUT", `/companies/${id}`, c),
  companyAlerts: (id: number) => req<Alert[]>("GET", `/companies/${id}/alerts`),
  companyMatches: (id: number) => req<Match[]>("GET", `/companies/${id}/matches`),

  updates: (p: { update_type?: string; simulated?: boolean } = {}) =>
    req<RegulatoryUpdateListItem[]>("GET", `/updates${qs(p)}`),
  update: (id: string) => req<RegulatoryUpdate>("GET", `/updates/${id}`),
  updateMatches: (id: string) => req<Match[]>("GET", `/updates/${id}/matches`),

  drafts: (p: { status?: string; company_id?: number } = {}) => req<Draft[]>("GET", `/drafts${qs(p)}`),
  draft: (id: number) => req<DraftDetail>("GET", `/drafts/${id}`),
  editDraft: (id: number, e: DraftEdit) => req<Draft>("PUT", `/drafts/${id}`, e),
  approve: (id: number, comment = "") => req<Alert>("POST", `/drafts/${id}/approve`, { comment }),
  reject: (id: number, comment: string) => req<Draft>("POST", `/drafts/${id}/reject`, { comment }),
  requestRevision: (id: number, comment: string) => req<Draft>("POST", `/drafts/${id}/request-revision`, { comment }),
  emailPreview: (alertId: number) => req<EmailPreview>("GET", `/alerts/${alertId}/email-preview`),

  runStep: (step: "ingest/fedlex" | "ingest/dataset" | "classify" | "match" | "draft", p: { live?: boolean; force?: boolean } = {}) =>
    req<PipelineResult>("POST", `/pipeline/${step}${qs(p)}`),
  runAll: (live: boolean = false) => req<PipelineResult[]>("POST", `/pipeline/run-all${qs({ live })}`),
  audit: (p: { object_type?: string; object_id?: string; limit?: number } = {}) =>
    req<AuditLogEntry[]>("GET", `/audit${qs(p)}`),
};
