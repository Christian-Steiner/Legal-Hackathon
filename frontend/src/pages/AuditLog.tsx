import { useState } from "react";
import { api } from "../api";
import { ErrorBox, fmtDateTime, useAsync } from "../components/ui";

export default function AuditLog() {
  const [type, setType] = useState("");
  const log = useAsync(() => api.audit({ object_type: type || undefined, limit: 500 }), [type]);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      <h1>Audit log</h1>
      <p className="muted">Every ingest, classification, match, draft, edit and decision - with actor, model and prompt version.</p>
      <div className="row filters">
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All objects</option>
          {["update", "match", "draft", "alert", "company"].map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>
      <ErrorBox error={log.error} />
      <table>
        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Details</th></tr></thead>
        <tbody>
          {log.data?.map((e) => (
            <tr key={e.id} className="clickable" onClick={() => setOpen(open === e.id ? null : e.id)}>
              <td className="small nowrap">{fmtDateTime(e.timestamp)}</td>
              <td className="small">{e.actor}</td>
              <td>{e.action}</td>
              <td className="small">{e.object_type} {e.object_id}</td>
              <td className="small">{open === e.id ? <pre>{JSON.stringify(e.details, null, 2)}</pre> : <span className="muted">{JSON.stringify(e.details).slice(0, 90)}…</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
