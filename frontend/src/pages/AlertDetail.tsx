// One approved alert in full: summary, next steps, sources, disclaimer, contact the reviewing lawyer.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ContactLawyerModal, lawyerName } from "../components/ContactLawyer";
import { Badge, Disclaimer, ErrorBox, Loading, UrgencyBadge, fmtDate, useAsync } from "../components/ui";
import { useSession } from "../session";
import type { EmailPreview } from "../types";

export default function AlertDetail() {
  const { id } = useParams();
  const s = useSession();
  // No single-alert endpoint; the company's list is small, so pick the alert from it.
  const alerts = useAsync(() => (s.companyId ? api.companyAlerts(s.companyId) : Promise.resolve([])), [s.companyId]);
  const company = useAsync(() => (s.companyId ? api.company(s.companyId) : Promise.resolve(null)), [s.companyId]);
  const [preview, setPreview] = useState<EmailPreview | null>(null);
  const [contact, setContact] = useState(false);

  if (!s.companyId) return <p>Select a client in the top right, or complete onboarding.</p>;
  const a = alerts.data?.find((x) => x.id === Number(id));

  return (
    <div className="narrow">
      <Link to="/client/inbox" className="small">← All alerts</Link>
      <ErrorBox error={alerts.error} />
      <Loading on={alerts.loading && !alerts.data} />
      {alerts.data && !a && <div className="card muted">This alert was not found for {company.data?.name ?? "this client"}.</div>}
      {a && (
        <div className="card alert">
          <div className="row between">
            <h1 className="tight">{a.title}</h1>
            <UrgencyBadge u={a.urgency} />
          </div>
          <p className="muted small">
            {a.departments.length ? a.departments.map((d) => d.name).join(" · ") : "General"} · delivered {fmtDate(a.delivered_at)}
          </p>
          {a.is_simulated && <Badge tone="bad">Simulated source (organisers' dataset)</Badge>}
          <p>{a.summary}</p>
          {a.departments.some((d) => d.why) && (
            <>
              <b>Why this concerns you</b>
              <ul>{a.departments.filter((d) => d.why).map((d, i) => <li key={i}><b>{d.name}:</b> {d.why}</li>)}</ul>
            </>
          )}
          {a.next_steps.length > 0 && (
            <>
              <b>Suggested next steps</b>
              <ul>{a.next_steps.map((n, i) => <li key={i}>{n.action}{n.due && <span className="muted"> · by {fmtDate(n.due)}</span>}</li>)}</ul>
            </>
          )}
          <div className="small">
            Sources: {a.citations.map((c, i) => (
              <span key={i}>[{i + 1}] {c.article} {c.eli && <a href={c.eli} target="_blank" rel="noreferrer">official text↗</a>} </span>
            ))}
          </div>
          <p className="reviewed">✔ Reviewed by LEXR ({lawyerName(a.reviewed_by)}) on {fmtDate(a.delivered_at)}</p>
          <Disclaimer text={a.disclaimer} />
          <div className="row wrap between contact">
            <button className="primary" onClick={() => setContact(true)}>Ask {lawyerName(a.reviewed_by)} about this</button>
            <button className="link" onClick={() => api.emailPreview(a.id).then(setPreview)}>Show email preview</button>
          </div>
        </div>
      )}
      {a && contact && <ContactLawyerModal alert={a} companyName={company.data?.name ?? ""} onClose={() => setContact(false)} />}
      {preview && (
        <div className="modal" onClick={() => setPreview(null)}>
          <div className="card" onClick={(e) => e.stopPropagation()}>
            <p className="small"><b>To:</b> {preview.to.join(", ")}<br /><b>Subject:</b> {preview.subject}</p>
            <pre>{preview.body_text}</pre>
            <p className="muted small">Preview only - no email is sent in this prototype.</p>
            <button onClick={() => setPreview(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
