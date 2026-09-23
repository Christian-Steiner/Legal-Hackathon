import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Loading, StatusBadge, UrgencyBadge, fmtDate, useAsync } from "../components/ui";

const URG_ORDER = { high: 0, medium: 1, low: 2 };

export default function ReviewQueue() {
  const [status, setStatus] = useState("pending");
  const [companyId, setCompanyId] = useState<number | undefined>();
  const drafts = useAsync(() => api.drafts({ status: status || undefined, company_id: companyId }), [status, companyId]);
  const companies = useAsync(api.companies);
  const updates = useAsync(() => api.updates());
  const cname = (id: number) => companies.data?.find((c) => c.id === id)?.name ?? id;
  const utitle = (id: string) => updates.data?.find((u) => u.id === id)?.title ?? id;

  const rows = [...(drafts.data ?? [])].sort((a, b) => URG_ORDER[a.urgency] - URG_ORDER[b.urgency]);

  return (
    <div>
      <h1>Review queue</h1>
      <div className="row filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="pending">Pending</option>
          <option value="revision_requested">Revision requested</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="">All</option>
        </select>
        <select value={companyId ?? ""} onChange={(e) => setCompanyId(e.target.value ? Number(e.target.value) : undefined)}>
          <option value="">All clients</option>
          {companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <span className="muted">{rows.length} drafts</span>
      </div>
      <ErrorBox error={drafts.error} />
      <Loading on={drafts.loading} />
      <table className="clickable">
        <thead>
          <tr><th>Urgency</th><th>Client</th><th>Regulatory update</th><th>Departments</th><th>Warnings</th><th>Status</th><th>Created</th></tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id}>
              <td><UrgencyBadge u={d.urgency} /></td>
              <td>{cname(d.company_id)}</td>
              <td><Link to={`/lawyer/review/${d.id}`}>{utitle(d.update_id)}</Link></td>
              <td className="small">{d.affected_departments.map((x) => x.name).join(", ")}</td>
              <td>{d.warnings.length > 0 && <span className="warn-count" title={d.warnings.join("\n")}>⚠ {d.warnings.length}</span>}</td>
              <td><StatusBadge s={d.status} /></td>
              <td className="small">{fmtDate(d.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
