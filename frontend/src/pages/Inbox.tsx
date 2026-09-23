// Client inbox: approved alerts only, grouped by department, as compact tiles. Full alert in AlertDetail.
// Each tile opens the alert for that department only; each alert is shown in its own language.
// TODO(ws3): mark as read; filter by urgency.
import { Link } from "react-router-dom";
import { api } from "../api";
import { lawyerName } from "../components/ContactLawyer";
import { Badge, ErrorBox, Loading, UrgencyBadge, fmtDate, useAsync } from "../components/ui";
import { strings } from "../i18n";
import { useSession } from "../session";
import type { Alert } from "../types";

export default function Inbox() {
  const s = useSession();
  const alerts = useAsync(() => (s.companyId ? api.companyAlerts(s.companyId) : Promise.resolve([])), [s.companyId]);
  const company = useAsync(() => (s.companyId ? api.company(s.companyId) : Promise.resolve(null)), [s.companyId]);

  if (!s.companyId) return <p>Select a client in the top right, or complete onboarding.</p>;
  const t = strings(company.data?.preferred_language);

  // department name -> its id (null for the "General" group of alerts without departments) and alerts
  const groups = new Map<string, { id: number | null; list: Alert[] }>();
  for (const a of alerts.data ?? []) {
    for (const d of a.departments.length ? a.departments : [{ name: t.general, department_id: null, why: "" }]) {
      const g = groups.get(d.name) ?? { id: d.department_id, list: [] };
      g.list.push(a);
      groups.set(d.name, g);
    }
  }

  return (
    <div>
      <h1>{t.inboxTitle(company.data?.name ?? "")}</h1>
      <p className="muted">{t.inboxIntro}</p>
      <ErrorBox error={alerts.error} />
      <Loading on={alerts.loading && !alerts.data} />
      {alerts.data?.length === 0 && <div className="card muted">{t.noAlerts}</div>}
      {[...groups.entries()].map(([dep, g]) => (
        <section key={dep}>
          <h2>{dep}</h2>
          <div className="tiles">
            {g.list.map((a) => {
              const at = strings(a.language);
              return (
                <Link key={a.id} to={`/client/inbox/${a.id}${g.id != null ? `?dept=${g.id}` : ""}`} className="card tile" lang={a.language?.toLowerCase()}>
                  <div className="row between">
                    <UrgencyBadge u={a.urgency} label={at.urgency[a.urgency]} />
                    <span className="muted small">{fmtDate(a.delivered_at)}</span>
                  </div>
                  <h3 className="tile-title">{a.title}</h3>
                  {a.is_simulated && <Badge tone="bad">{at.simulatedShort}</Badge>}
                  <p className="tile-summary">{a.summary}</p>
                  <div className="row between small tile-foot">
                    <span className="muted">{at.reviewedBy(lawyerName(a.reviewed_by))}</span>
                    <span className="tile-open">{at.view}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
