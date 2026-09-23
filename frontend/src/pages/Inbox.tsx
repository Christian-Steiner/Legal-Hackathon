// Client inbox: approved alerts only, grouped by department.
// TODO(ws3): mark as read; filter by urgency; nicer email preview.
import { useState } from "react";
import { api } from "../api";
import { Badge, Disclaimer, ErrorBox, UrgencyBadge, fmtDate, useAsync } from "../components/ui";
import { useSession } from "../session";
import type { Alert, EmailPreview } from "../types";

export default function Inbox() {
  const s = useSession();
  const alerts = useAsync(() => (s.companyId ? api.companyAlerts(s.companyId) : Promise.resolve([])), [s.companyId]);
  const company = useAsync(() => (s.companyId ? api.company(s.companyId) : Promise.resolve(null)), [s.companyId]);
  const [preview, setPreview] = useState<EmailPreview | null>(null);

  if (!s.companyId) return <p>Select a client in the top right, or complete onboarding.</p>;

  const groups = new Map<string, Alert[]>();
  for (const a of alerts.data ?? []) {
    for (const d of a.departments.length ? a.departments : [{ name: "General", department_id: null, why: "" }]) {
      groups.set(d.name, [...(groups.get(d.name) ?? []), a]);
    }
  }

  return (
    <div>
      <h1>{company.data?.name}: regulatory alerts</h1>
      <p className="muted">Only alerts reviewed and approved by a LEXR lawyer appear here.</p>
      <ErrorBox error={alerts.error} />
      {alerts.data?.length === 0 && <div className="card muted">No approved alerts yet.</div>}
      {[...groups.entries()].map(([dep, list]) => (
        <section key={dep}>
          <h2>{dep}</h2>
          {list.map((a) => (
            <div key={a.id} className="card alert">
              <div className="row between">
                <h3 className="tight">{a.title}</h3>
                <UrgencyBadge u={a.urgency} />
              </div>
              {a.is_simulated && <Badge tone="bad">Simulated source (organisers' dataset)</Badge>}
              <p>{a.summary}</p>
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
              <p className="reviewed">✔ Reviewed by LEXR ({a.reviewed_by.replace("lawyer:", "")}) on {fmtDate(a.delivered_at)}</p>
              <Disclaimer text={a.disclaimer} />
              <button className="link" onClick={() => api.emailPreview(a.id).then(setPreview)}>Show email preview</button>
            </div>
          ))}
        </section>
      ))}
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
