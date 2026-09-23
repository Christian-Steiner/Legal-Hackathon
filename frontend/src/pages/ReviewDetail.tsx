// THE SHOWCASE: draft next to the cited source, reasons, approve / edit / reject / request revision.
// TODO(ws3): highlight the cited article in the source panel when a citation is clicked;
//            show a machine translation next to the original (Supertext, TODO ws2);
//            diff view between revision_history versions.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Badge, ErrorBox, Loading, StatusBadge, UPDATE_TYPE_LABEL, UrgencyBadge, fmtDate, fmtDateTime, useAsync } from "../components/ui";
import type { AffectedDepartment, Citation, DraftDetail, NextStep, Urgency } from "../types";

export default function ReviewDetail() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const { data: d, error, loading, reload } = useAsync(() => api.draft(id), [id]);
  const audit = useAsync(() => api.audit({ object_type: "draft", object_id: String(id) }), [id, d?.version, d?.status]);
  const [form, setForm] = useState<Editable | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeRef, setActiveRef] = useState<string | null>(null);

  useEffect(() => { if (d) setForm(toEditable(d)); }, [d]);

  if (loading && !d) return <Loading on />;
  if (error || !d || !form) return <ErrorBox error={error} />;

  const locked = d.status === "approved" || d.status === "rejected";
  const dirty = JSON.stringify(form) !== JSON.stringify(toEditable(d));

  const act = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      setComment("");
      after ? after() : reload();
    } catch (e) {
      setActionError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const u = d.update;
  const set = <K extends keyof Editable>(k: K, v: Editable[K]) => setForm({ ...form, [k]: v });

  return (
    <div>
      <p><Link to="/lawyer/review">← Review queue</Link></p>
      <div className="row between">
        <h1 className="tight">{u.title}</h1>
        <div className="row"><StatusBadge s={d.status} /> <span className="muted small">v{d.version}</span></div>
      </div>
      <p className="muted">
        For <b>{d.company.name}</b> ({d.company.industry}, {d.company.hq_canton}) · client language {d.company.preferred_language}
        {d.language && d.language !== d.company.preferred_language && <> · <Badge tone="bad">draft written in {d.language}</Badge></>}
      </p>

      {d.warnings.length > 0 && (
        <div className="warnings">{d.warnings.map((w) => <div key={w}>⚠ {w}</div>)}</div>
      )}

      <div className="split">
        {/* ---------------- LEFT: the draft ---------------- */}
        <section className="card">
          <h2>AI draft <span className="muted small">({d.model_version} · {d.prompt_version}{d.edited_by_lawyer ? " · edited by lawyer" : ""})</span></h2>

          <label>Title shown to the client{d.language ? ` (${d.language})` : ""}</label>
          <input value={form.title} disabled={locked} placeholder={u.title} onChange={(e) => set("title", e.target.value)} />

          <label>Summary</label>
          <textarea rows={7} value={form.summary} disabled={locked} onChange={(e) => set("summary", e.target.value)} />

          <label>Urgency</label>
          <select value={form.urgency} disabled={locked} onChange={(e) => set("urgency", e.target.value as Urgency)}>
            <option value="high">high</option><option value="medium">medium</option><option value="low">low</option>
          </select>

          <label>Affected departments</label>
          {form.affected_departments.map((a, i) => (
            <div key={i} className="row item">
              <b>{a.name}</b>
              <input value={a.why} disabled={locked} onChange={(e) => set("affected_departments", form.affected_departments.map((x, j) => j === i ? { ...x, why: e.target.value } : x))} />
              {!locked && <button className="link" onClick={() => set("affected_departments", form.affected_departments.filter((_, j) => j !== i))}>remove</button>}
            </div>
          ))}
          {!locked && (
            <select value="" onChange={(e) => {
              const dep = d.company.departments.find((x) => x.id === Number(e.target.value));
              if (dep) set("affected_departments", [...form.affected_departments, { department_id: dep.id, name: dep.name, why: "Added by reviewer." }]);
            }}>
              <option value="">+ add department…</option>
              {d.company.departments.filter((x) => !form.affected_departments.some((a) => a.department_id === x.id))
                .map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          )}

          <label>Next steps</label>
          {form.next_steps.map((s, i) => (
            <div key={i} className="row item">
              <input value={s.action} disabled={locked} onChange={(e) => set("next_steps", form.next_steps.map((x, j) => j === i ? { ...x, action: e.target.value } : x))} />
              <span className="small muted nowrap">{s.department ?? ""} {s.due ? `· due ${s.due}` : ""}</span>
              {!locked && <button className="link" onClick={() => set("next_steps", form.next_steps.filter((_, j) => j !== i))}>remove</button>}
            </div>
          ))}
          {!locked && <button className="link" onClick={() => set("next_steps", [...form.next_steps, { action: "", department: null, due: null }])}>+ add step</button>}

          <label>Citations {form.citations.length === 0 && <Badge tone="bad">missing</Badge>}</label>
          {form.citations.map((c, i) => (
            <div key={i} className={`citation ${activeRef === c.article ? "active" : ""}`} onClick={() => setActiveRef(c.article ?? null)}>
              <div className="small"><b>[{i + 1}]</b> {c.claim}</div>
              <div className="small muted">
                {c.article ?? <Badge tone="bad">no article</Badge>} ·{" "}
                {c.eli ? <a href={c.eli} target="_blank" rel="noreferrer">{c.eli.replace("https://fedlex.data.admin.ch/eli/", "ELI ")}</a> : <Badge tone="bad">no ELI</Badge>}
              </div>
              {c.quote && <blockquote>{c.quote}</blockquote>}
            </div>
          ))}

          {!locked && (
            <div className="actions">
              <button disabled={!dirty || busy} onClick={() => act(() => api.editDraft(id, form))}>Save edits</button>
              <textarea rows={2} placeholder="Comment (required for reject / revision; sent to the model on revision)" value={comment} onChange={(e) => setComment(e.target.value)} />
              <div className="row">
                <button className="primary" disabled={busy || dirty || d.status !== "pending"} title={dirty ? "Save edits first" : ""}
                  onClick={() => act(() => api.approve(id, comment), () => nav("/lawyer/review"))}>
                  ✓ Approve & send to client
                </button>
                <button disabled={busy || !comment.trim()} onClick={() => act(() => api.requestRevision(id, comment))}>↻ Request revision</button>
                <button className="danger" disabled={busy || !comment.trim()} onClick={() => act(() => api.reject(id, comment))}>✕ Reject</button>
              </div>
              {busy && <span className="muted small">Working…</span>}
              <ErrorBox error={actionError} />
            </div>
          )}
          {locked && <p className="muted">Reviewed by {d.reviewed_by} on {fmtDateTime(d.reviewed_at)}. Locked.</p>}
        </section>

        {/* ---------------- RIGHT: source & reasoning ---------------- */}
        <section className="card">
          <h2>Why this client? <span className="muted small">({d.match.model_version} · {d.match.prompt_version})</span></h2>
          <p>{d.match.llm_reason}</p>
          <div className="small">
            Relevance score {d.match.relevance_score.toFixed(2)} · rule hits:
            <ul>{d.match.rule_hits.map((h, i) => <li key={i}><code>{h.rule}</code> ({h.weight > 0 ? "+" : ""}{h.weight}) {h.detail}</li>)}</ul>
          </div>

          <h2>Official source</h2>
          <div className="row wrap small">
            <Badge>{UPDATE_TYPE_LABEL[u.update_type]}</Badge>
            {u.is_simulated && <Badge tone="bad">SIMULATED - not an official publication</Badge>}
            <Badge>{u.jurisdiction}</Badge>
            <Badge>original language: {u.source_language}</Badge>
          </div>
          <table className="kv small">
            <tbody>
              <tr><td>ELI</td><td>{u.eli_uri ? <a href={u.eli_uri} target="_blank" rel="noreferrer">{u.eli_uri}</a> : "–"}</td></tr>
              <tr><td>Published</td><td>{fmtDate(u.publication_date)}</td></tr>
              <tr><td>Entry into force</td><td>{fmtDate(u.entry_into_force_date)}</td></tr>
              <tr><td>Consultation until</td><td>{fmtDate(u.consultation_deadline)}</td></tr>
              <tr><td>Fedlex version</td><td>{u.source_version ?? "–"}</td></tr>
              <tr><td>Reported by</td><td>{u.sources.map((s) => `${s.source} (${s.kind ?? ""})`).join(", ")}</td></tr>
            </tbody>
          </table>
          <div className="source-text">
            {u.source_articles.length > 0
              ? u.source_articles.map((a, i) => (
                  <div key={i} className={`article ${activeRef && a.ref === activeRef ? "active" : ""}`}>
                    <b>{a.ref}</b> <span>{a.text}</span>
                  </div>
                ))
              : <pre>{u.source_text ?? "No text available - open the ELI link."}</pre>}
          </div>
        </section>
      </div>

      <div className="split">
        <section className="card">
          <h2>Reviewer comments</h2>
          {d.reviewer_comments.length === 0 && <p className="muted small">None yet.</p>}
          {d.reviewer_comments.map((c, i) => <p key={i} className="small"><b>{c.by}</b> · {c.decision} · {fmtDateTime(c.at)}<br />{c.comment}</p>)}
          <h2>Revision history</h2>
          {d.revision_history.map((r) => <div key={r.version} className="small">v{r.version} · {r.change} · {r.by} · {fmtDateTime(r.at)}</div>)}
        </section>
        <section className="card">
          <h2>Audit trail (this draft)</h2>
          {audit.data?.map((e) => <div key={e.id} className="small">{fmtDateTime(e.timestamp)} · <b>{e.actor}</b> · {e.action}</div>)}
        </section>
      </div>
    </div>
  );
}

interface Editable {
  title: string;
  summary: string;
  urgency: Urgency;
  affected_departments: AffectedDepartment[];
  next_steps: NextStep[];
  citations: Citation[];
}
const toEditable = (d: DraftDetail): Editable => ({
  title: d.title ?? "", summary: d.summary, urgency: d.urgency, affected_departments: d.affected_departments,
  next_steps: d.next_steps, citations: d.citations,
});
