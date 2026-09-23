// Client self-service onboarding + profile edit (same form).
// TODO(ws3): split into a multi-step wizard (Company → Activities → Legal situation → Departments);
//            suggest department functions from the name; privacy note on what we store.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, useAsync } from "../components/ui";
import { setSession, useSession } from "../session";
import type { CompanyIn, DepartmentIn } from "../types";

const EMPTY: CompanyIn = {
  name: "", industry: "", description: "", size_band: "11-50", hq_canton: "ZH", jurisdictions: ["CH"], flags: {},
  legal_context: "", key_challenges: "", topics: [], preferred_language: "EN",
  departments: [{ name: "Legal", contact_email: "", functions: ["Legal", "Compliance"], responsibilities: "" }],
};

export default function Onboarding({ edit = false }: { edit?: boolean }) {
  const s = useSession();
  const nav = useNavigate();
  const meta = useAsync(api.meta);
  const [form, setForm] = useState<CompanyIn>(EMPTY);
  const [topicsText, setTopicsText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (edit && s.companyId) {
      api.company(s.companyId).then((c) => {
        const { id, created_at, updated_at, ...rest } = c;
        setForm({ ...rest, departments: c.departments.map(({ id: _id, ...d }) => d) });
        setTopicsText(c.topics.join(", "));
      });
    } else {
      setForm(EMPTY);
      setTopicsText("");
    }
  }, [edit, s.companyId]);

  const set = <K extends keyof CompanyIn>(k: K, v: CompanyIn[K]) => setForm({ ...form, [k]: v });
  const setDep = (i: number, patch: Partial<DepartmentIn>) =>
    set("departments", form.departments.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  const submit = async () => {
    setError(null);
    const body = { ...form, topics: topicsText.split(",").map((t) => t.trim()).filter(Boolean) };
    try {
      if (edit && s.companyId) {
        await api.updateCompany(s.companyId, body);
        setSaved(true);
      } else {
        const c = await api.createCompany(body);
        setSession({ role: "client", companyId: c.id });
        nav("/client/inbox");
      }
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  if (!meta.data) return null;
  const m = meta.data;

  return (
    <div className="narrow">
      <h1>{edit ? "Company profile" : "Onboarding: tell LEXR about your company"}</h1>
      <p className="muted">
        We only store company-level information and department contact addresses - no other personal data. The profile
        decides which regulatory changes are flagged for you, and which department receives them.
      </p>

      <div className="card">
        <h2>Company</h2>
        <div className="grid2">
          <div><label>Company name</label><input value={form.name} onChange={(e) => set("name", e.target.value)} /></div>
          <div><label>Industry</label><input value={form.industry} onChange={(e) => set("industry", e.target.value)} placeholder="e.g. Fintech / Payments" /></div>
          <div><label>Size</label><select value={form.size_band} onChange={(e) => set("size_band", e.target.value)}>{m.size_bands.map((x) => <option key={x}>{x}</option>)}</select></div>
          <div><label>Headquarters canton</label><select value={form.hq_canton} onChange={(e) => set("hq_canton", e.target.value)}>{m.cantons.map((x) => <option key={x}>{x}</option>)}</select></div>
          <div><label>Preferred language</label><select value={form.preferred_language} onChange={(e) => set("preferred_language", e.target.value as CompanyIn["preferred_language"])}>{["DE", "FR", "EN"].map((x) => <option key={x}>{x}</option>)}</select></div>
          <div>
            <label>Active in</label>
            <div className="row">{["CH", "EU", "other"].map((j) => (
              <label key={j} className="check"><input type="checkbox" checked={form.jurisdictions.includes(j)}
                onChange={(e) => set("jurisdictions", e.target.checked ? [...form.jurisdictions, j] : form.jurisdictions.filter((x) => x !== j))} /> {j}</label>
            ))}</div>
          </div>
        </div>
        <label>What does your company do?</label>
        <textarea rows={2} value={form.description} onChange={(e) => set("description", e.target.value)} />
      </div>

      <div className="card">
        <h2>Activities</h2>
        <div className="grid2">
          {Object.entries(m.activity_flags).map(([k, label]) => (
            <label key={k} className="check"><input type="checkbox" checked={!!form.flags[k]} onChange={(e) => set("flags", { ...form.flags, [k]: e.target.checked })} /> {label}</label>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Legal situation</h2>
        <label>Current legal situation (licences, supervisors, laws you know apply)</label>
        <textarea rows={3} value={form.legal_context} onChange={(e) => set("legal_context", e.target.value)} />
        <label>Key legal challenges right now</label>
        <textarea rows={3} value={form.key_challenges} onChange={(e) => set("key_challenges", e.target.value)} />
        <label>Topics of interest (comma separated)</label>
        <input value={topicsText} onChange={(e) => setTopicsText(e.target.value)} placeholder="data protection, AI governance, tax" />
      </div>

      <div className="card">
        <h2>Departments</h2>
        <p className="muted small">Alerts are routed to departments by the functions they cover.</p>
        {form.departments.map((d, i) => (
          <div key={i} className="dep">
            <div className="grid2">
              <div><label>Name</label><input value={d.name} onChange={(e) => setDep(i, { name: e.target.value })} /></div>
              <div><label>Contact email (team address)</label><input value={d.contact_email} onChange={(e) => setDep(i, { contact_email: e.target.value })} /></div>
            </div>
            <label>Functions covered</label>
            <div className="chips">
              {m.functional_teams.map((t) => (
                <button key={t} type="button" className={`chip ${d.functions.includes(t) ? "on" : ""}`}
                  onClick={() => setDep(i, { functions: d.functions.includes(t) ? d.functions.filter((x) => x !== t) : [...d.functions, t] })}>{t}</button>
              ))}
            </div>
            <button className="link" onClick={() => set("departments", form.departments.filter((_, j) => j !== i))}>remove department</button>
          </div>
        ))}
        <button onClick={() => set("departments", [...form.departments, { name: "", contact_email: "", functions: [], responsibilities: "" }])}>+ Add department</button>
      </div>

      <ErrorBox error={error} />
      <button className="primary" onClick={submit} disabled={!form.name || !form.industry}>{edit ? "Save profile" : "Complete onboarding"}</button>
      {saved && <span className="muted"> Saved. New updates will be matched against the new profile.</span>}
    </div>
  );
}
