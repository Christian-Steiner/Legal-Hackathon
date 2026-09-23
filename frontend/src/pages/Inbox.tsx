// Client inbox: approved alerts only, grouped by department, as compact tiles. Full alert in AlertDetail.
// TODO(ws3): mark as read; filter by urgency.
import { Link } from "react-router-dom";
import { api } from "../api";
import { lawyerName } from "../components/ContactLawyer";
import { Badge, ErrorBox, Loading, UrgencyBadge, fmtDate, useAsync } from "../components/ui";
import { useSession } from "../session";
import type { Alert } from "../types";

export default function Inbox() {
  const s = useSession();
  const alerts = useAsync(() => (s.companyId ? api.companyAlerts(s.companyId) : Promise.resolve([])), [s.companyId]);
  const company = useAsync(() => (s.companyId ? api.company(s.companyId) : Promise.resolve(null)), [s.companyId]);

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
      <p className="muted">
        Only alerts reviewed and approved by a LEXR lawyer appear here. Open an alert for the full summary, next steps,
        sources and to ask your lawyer. Not legal advice.
      </p>
      <ErrorBox error={alerts.error} />
      <Loading on={alerts.loading && !alerts.data} />
      {alerts.data?.length === 0 && <div className="card muted">No approved alerts yet.</div>}
      {[...groups.entries()].map(([dep, list]) => (
        <section key={dep}>
          <h2>{dep}</h2>
          <div className="tiles">
            {list.map((a) => (
              <Link key={a.id} to={`/client/inbox/${a.id}`} className="card tile">
                <div className="row between">
                  <UrgencyBadge u={a.urgency} />
                  <span className="muted small">{fmtDate(a.delivered_at)}</span>
                </div>
                <h3 className="tile-title">{a.title}</h3>
                {a.is_simulated && <Badge tone="bad">Simulated source</Badge>}
                <p className="tile-summary">{a.summary}</p>
                <div className="row between small tile-foot">
                  <span className="muted">✔ Reviewed by {lawyerName(a.reviewed_by)}</span>
                  <span className="tile-open">View →</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
