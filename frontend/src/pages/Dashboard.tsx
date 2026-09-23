import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, useAsync } from "../components/ui";
import type { PipelineResult } from "../types";

const STEPS = [
  { key: "ingest/fedlex", label: "1. Ingest Fedlex", hint: "AS publications, upcoming entry into force, open consultations" },
  { key: "ingest/dataset", label: "1b. Import organisers' dataset", hint: "8 simulated updates (marked as simulated)" },
  { key: "classify", label: "2. Classify updates", hint: "Topics, functional teams, urgency (company-independent)" },
  { key: "match", label: "3. Match to client profiles", hint: "Rules first, then LLM with a written reason" },
  { key: "draft", label: "4. Draft client alerts", hint: "Summary, departments, next steps, citations" },
] as const;

export default function Dashboard() {
  const [log, setLog] = useState<PipelineResult[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = useAsync(() => api.drafts({ status: "pending" }));
  const companies = useAsync(api.companies);
  const updates = useAsync(() => api.updates());

  const run = async (key: string, fn: () => Promise<PipelineResult | PipelineResult[]>) => {
    setBusy(key);
    setError(null);
    try {
      const r = await fn();
      setLog((l) => [...(Array.isArray(r) ? r : [r]), ...l]);
      pending.reload();
      updates.reload();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <h1>Pipeline</h1>
      <div className="stats">
        <div className="stat"><b>{updates.data?.length ?? "–"}</b><span>regulatory updates</span></div>
        <div className="stat"><b>{companies.data?.length ?? "–"}</b><span>client profiles</span></div>
        <div className="stat"><b>{pending.data?.length ?? "–"}</b><span>drafts awaiting review</span></div>
      </div>
      <ErrorBox error={error} />
      <div className="card">
        <div className="row between">
          <h2>Run steps</h2>
          <button className="primary" disabled={!!busy} onClick={() => run("all", api.runAll)}>
            {busy === "all" ? "Running…" : "Run all steps"}
          </button>
        </div>
        {STEPS.map((s) => (
          <div key={s.key} className="row step">
            <button disabled={!!busy} onClick={() => run(s.key, () => api.runStep(s.key))}>
              {busy === s.key ? "Running…" : s.label}
            </button>
            <span className="muted small">{s.hint}</span>
          </div>
        ))}
        <div className="row step">
          <button disabled={!!busy} onClick={() => run("live", () => api.runStep("ingest/fedlex", { live: true }))}>
            Ingest live from Fedlex SPARQL
          </button>
          <span className="muted small">Bypasses the demo cache (needs internet, ~20 s)</span>
        </div>
        <p className="small muted">
          Nothing reaches a client from here. Drafts go to the <Link to="/lawyer/review">review queue</Link>; only
          approved drafts become alerts.
        </p>
      </div>
      {log.length > 0 && (
        <div className="card">
          <h2>Run log</h2>
          <table>
            <thead><tr><th>Step</th><th>Created</th><th>Updated</th><th>Skipped</th><th>Info / errors</th></tr></thead>
            <tbody>
              {log.map((r, i) => (
                <tr key={i}>
                  <td>{r.step}</td><td>{r.created}</td><td>{r.updated}</td><td>{r.skipped}</td>
                  <td className="small">{JSON.stringify(r.info)} {r.errors.length > 0 && <span className="err">{r.errors.length} errors: {r.errors.slice(0, 3).join("; ")}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
