import { Fragment, useState } from "react";
import { api } from "../api";
import { Badge, ErrorBox, Loading, SCOPE_LABEL, UPDATE_TYPE_LABEL, UrgencyBadge, fmtDate, useAsync } from "../components/ui";

export default function Updates() {
  const [type, setType] = useState("");
  const updates = useAsync(() => api.updates({ update_type: type || undefined }), [type]);
  const [open, setOpen] = useState<string | null>(null);
  const matches = useAsync(() => (open ? api.updateMatches(open) : Promise.resolve([])), [open]);
  const companies = useAsync(api.companies);
  const cname = (id: number) => companies.data?.find((c) => c.id === id)?.name ?? id;

  return (
    <div>
      <h1>Regulatory updates</h1>
      <div className="row filters">
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {Object.entries(UPDATE_TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <span className="muted">{updates.data?.length ?? 0} updates</span>
      </div>
      <ErrorBox error={updates.error} />
      <Loading on={updates.loading} />
      <table>
        <thead><tr><th>Type</th><th>Title</th><th>Dates</th><th>Classification</th><th>Sources</th></tr></thead>
        <tbody>
          {updates.data?.map((u) => (
            <Fragment key={u.id}>
              <tr className="clickable" onClick={() => setOpen(open === u.id ? null : u.id)}>
                <td className="small">{UPDATE_TYPE_LABEL[u.update_type]}{u.is_simulated && <> <Badge tone="bad">simulated</Badge></>}</td>
                <td>{u.title}{u.eli_uri && <> <a className="small" href={u.eli_uri} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>ELI↗</a></>}</td>
                <td className="small nowrap">
                  pub {fmtDate(u.publication_date)}
                  {u.entry_into_force_date && <><br />in force {fmtDate(u.entry_into_force_date)}</>}
                  {u.consultation_deadline && <><br />until {fmtDate(u.consultation_deadline)}</>}
                </td>
                <td className="small">
                  {u.classification ? <><UrgencyBadge u={u.classification.urgency} /> {u.classification.topics.join(", ")}<br /><span className="muted">{u.classification.functional_teams.join(" + ")}</span>
                    {u.classification.applies_to?.map((a) => <Fragment key={a}> <Badge>applies to {SCOPE_LABEL[a] ?? a}</Badge></Fragment>)}</> : <span className="muted">not classified</span>}
                </td>
                <td className="small">{u.sources.length > 1 ? <Badge tone="good">{u.sources.length} merged</Badge> : u.sources[0]?.source}</td>
              </tr>
              {open === u.id && (
                <tr>
                  <td colSpan={5} className="expanded small">
                    <b>Match decisions for every client (non-matches are stored with their reason):</b>
                    {matches.data?.map((m) => (
                      <div key={m.id}>{m.matched ? "✅" : "—"} <b>{cname(m.company_id)}</b> ({m.relevance_score.toFixed(2)}, {m.model_version}): {m.llm_reason}</div>
                    ))}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
