// One approved alert in full, for one department (?dept=<id>): only that department's reason and next
// steps, the shared summary and sources, disclaimer, contact the reviewing lawyer. All in the alert's language.
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ContactLawyerModal, lawyerName } from "../components/ContactLawyer";
import { Badge, Disclaimer, ErrorBox, Loading, UrgencyBadge, fmtDate, useAsync } from "../components/ui";
import { strings } from "../i18n";
import { useSession } from "../session";
import type { EmailPreview } from "../types";

export default function AlertDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const s = useSession();
  // No single-alert endpoint; the company's list is small, so pick the alert from it.
  const alerts = useAsync(() => (s.companyId ? api.companyAlerts(s.companyId) : Promise.resolve([])), [s.companyId]);
  const company = useAsync(() => (s.companyId ? api.company(s.companyId) : Promise.resolve(null)), [s.companyId]);
  const [preview, setPreview] = useState<EmailPreview | null>(null);
  const [contact, setContact] = useState(false);

  if (!s.companyId) return <p>Select a client in the top right, or complete onboarding.</p>;
  const a = alerts.data?.find((x) => x.id === Number(id));
  const t = strings(a?.language ?? company.data?.preferred_language);

  // The department this alert was opened for; without one (or an unknown one) show every department.
  const dep = a?.departments.find((d) => d.department_id != null && d.department_id === Number(params.get("dept")));
  const deps = a ? (dep ? [dep] : a.departments) : [];
  const routed = new Set(a?.departments.map((d) => d.name));
  // Steps for this department, plus steps not assigned to any routed department (so none get lost).
  const steps = a?.next_steps.filter((n) => !dep || n.department === dep.name || !routed.has(n.department ?? "")) ?? [];

  return (
    <div className="narrow" lang={a?.language?.toLowerCase()}>
      <Link to="/client/inbox" className="small">{t.allAlerts}</Link>
      <ErrorBox error={alerts.error} />
      <Loading on={alerts.loading && !alerts.data} />
      {alerts.data && !a && <div className="card muted">{t.notFound}</div>}
      {a && (
        <div className="card alert">
          <div className="row between">
            <h1 className="tight">{a.title}</h1>
            <UrgencyBadge u={a.urgency} label={t.urgency[a.urgency]} />
          </div>
          <p className="muted small">
            {t.forDept} {dep ? dep.name : a.departments.map((d) => d.name).join(" · ") || t.general} · {t.delivered} {fmtDate(a.delivered_at)}
          </p>
          {a.is_simulated && <Badge tone="bad">{t.simulatedLong}</Badge>}
          <p>{a.summary}</p>
          {deps.some((d) => d.why) && (
            <>
              <b className="block">{t.why}</b>
              {dep
                ? <p className="tight">{dep.why}</p>
                : <ul>{deps.filter((d) => d.why).map((d, i) => <li key={i}><b>{d.name}:</b> {d.why}</li>)}</ul>}
            </>
          )}
          {steps.length > 0 && (
            <>
              <b className="block">{t.steps}</b>
              <ul>
                {steps.map((n, i) => (
                  <li key={i}>
                    {n.action}
                    {!dep && n.department && <span className="muted"> · {n.department}</span>}
                    {n.due && <span className="muted"> · {t.by} {fmtDate(n.due)}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="small">
            {t.sources}: {a.citations.map((c, i) => (
              <span key={i}>[{i + 1}] {c.article} {c.eli && <a href={c.eli} target="_blank" rel="noreferrer">{t.officialText}↗</a>} </span>
            ))}
          </div>
          <p className="reviewed">{t.reviewedFull(lawyerName(a.reviewed_by), fmtDate(a.delivered_at))}</p>
          <Disclaimer text={a.disclaimer} />
          <div className="row wrap between contact">
            <button className="primary" onClick={() => setContact(true)}>{t.ask(lawyerName(a.reviewed_by))}</button>
            <button className="link" onClick={() => api.emailPreview(a.id, dep?.department_id ?? undefined).then(setPreview)}>{t.emailPreview}</button>
          </div>
        </div>
      )}
      {a && contact && (
        <ContactLawyerModal alert={a} department={dep?.name} companyName={company.data?.name ?? ""} onClose={() => setContact(false)} />
      )}
      {preview && (
        <div className="modal" onClick={() => setPreview(null)}>
          <div className="card" onClick={(e) => e.stopPropagation()}>
            <p className="small"><b>{t.to}:</b> {preview.to.join(", ")}<br /><b>{t.subject}:</b> {preview.subject}</p>
            <pre>{preview.body_text}</pre>
            <p className="muted small">{t.previewOnly}</p>
            <button onClick={() => setPreview(null)}>{t.close}</button>
          </div>
        </div>
      )}
    </div>
  );
}
