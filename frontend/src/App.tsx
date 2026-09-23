import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import { useAsync } from "./components/ui";
import { setSession, useSession } from "./session";
import Dashboard from "./pages/Dashboard";
import ReviewQueue from "./pages/ReviewQueue";
import ReviewDetail from "./pages/ReviewDetail";
import Updates from "./pages/Updates";
import AuditLog from "./pages/AuditLog";
import Onboarding from "./pages/Onboarding";
import Inbox from "./pages/Inbox";
import Limitations from "./pages/Limitations";

export default function App() {
  const s = useSession();
  const nav = useNavigate();
  const companies = useAsync(api.companies, [s.role, s.companyId]);
  const meta = useAsync(api.meta);

  const switchTo = (value: string) => {
    if (value === "lawyer") {
      setSession({ role: "lawyer" });
      nav("/lawyer");
    } else if (value === "new") {
      setSession({ role: "client", companyId: null });
      nav("/onboarding");
    } else {
      setSession({ role: "client", companyId: Number(value) });
      nav("/client/inbox");
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <strong>LEXR</strong> Regulatory Change Monitor
          {meta.data && (
            <span className="muted small">
              {" "}· {meta.data.demo_mode ? "demo mode (cached Fedlex)" : "live Fedlex"} · model {meta.data.llm_model}
            </span>
          )}
        </div>
        <nav>
          {s.role === "lawyer" ? (
            <>
              <NavLink to="/lawyer">Pipeline</NavLink>
              <NavLink to="/lawyer/review">Review queue</NavLink>
              <NavLink to="/lawyer/updates">Updates</NavLink>
              <NavLink to="/lawyer/audit">Audit log</NavLink>
            </>
          ) : (
            <>
              {s.companyId && <NavLink to="/client/inbox">Inbox</NavLink>}
              <NavLink to={s.companyId ? "/client/profile" : "/onboarding"}>Company profile</NavLink>
            </>
          )}
          <NavLink to="/limitations">Limitations</NavLink>
        </nav>
        <div className="role">
          <label className="small muted">Viewing as</label>
          <select value={s.role === "lawyer" ? "lawyer" : String(s.companyId ?? "new")} onChange={(e) => switchTo(e.target.value)}>
            <option value="lawyer">LEXR lawyer</option>
            {companies.data?.map((c) => (
              <option key={c.id} value={c.id}>Client: {c.name}</option>
            ))}
            <option value="new">New client (onboarding)</option>
          </select>
          {s.role === "lawyer" && (
            <input className="small-input" value={s.lawyerName} onChange={(e) => setSession({ lawyerName: e.target.value })}
              title="Reviewer name recorded in the audit log" />
          )}
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to={s.role === "lawyer" ? "/lawyer" : "/client/inbox"} />} />
          <Route path="/lawyer" element={<Dashboard />} />
          <Route path="/lawyer/review" element={<ReviewQueue />} />
          <Route path="/lawyer/review/:id" element={<ReviewDetail />} />
          <Route path="/lawyer/updates" element={<Updates />} />
          <Route path="/lawyer/audit" element={<AuditLog />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/client/profile" element={<Onboarding edit />} />
          <Route path="/client/inbox" element={<Inbox />} />
          <Route path="/limitations" element={<Limitations />} />
          <Route path="*" element={<p>Not found</p>} />
        </Routes>
      </main>
      <footer className="muted small">
        Hackathon prototype · Not legal advice · Every client alert is approved by a LEXR lawyer ·{" "}
        <NavLink to="/limitations">What this tool does not cover</NavLink>
      </footer>
    </div>
  );
}
