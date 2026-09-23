// Funnel back to LEXR: the client asks the lawyer who approved an alert for advice.
// Frontend only - opens the client's own email app with a pre-filled message; nothing is sent or stored here.
import { useState } from "react";
import type { Alert } from "../types";
import { fmtDate } from "./ui";

// TODO(ws3): replace with LEXR's real domain / a lawyer directory before a public demo.
export const LEXR_EMAIL_DOMAIN = "lexr.example";

export function lawyerName(reviewedBy: string) {
  return reviewedBy.replace(/^lawyer:/, "").trim() || "your LEXR lawyer";
}

// "lawyer:Dr. Anna Keller" -> "anna.keller@<domain>" (academic titles dropped, accents stripped).
export function lawyerEmail(reviewedBy: string) {
  const local = lawyerName(reviewedBy)
    .split(/\s+/)
    .filter((w) => !w.endsWith("."))
    .join(".")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/ß/g, "ss")
    .replace(/[^a-z.-]/g, "");
  return `${local || "contact"}@${LEXR_EMAIL_DOMAIN}`;
}

function message(a: Alert, question: string, companyName: string) {
  const name = lawyerName(a.reviewed_by);
  const sources = a.citations
    .map((c, i) => `  [${i + 1}] ${c.article ?? ""} ${c.eli ?? c.source_url ?? ""}`.trimEnd())
    .join("\n");
  const subject = `Question on LEXR alert: ${a.title.length > 80 ? a.title.slice(0, 77) + "…" : a.title}`;
  const body =
    `Dear ${name},\n\n${question.trim()}\n\n` +
    `This concerns the regulatory alert you reviewed:\n${a.title}\n` +
    `Delivered ${fmtDate(a.delivered_at)} · urgency ${a.urgency} · alert #${a.id}\n` +
    (sources ? `Sources:\n${sources}\n` : "") +
    `\nKind regards,\n${companyName}`;
  return { subject, body };
}

export function ContactLawyerModal({ alert, companyName, onClose }: { alert: Alert; companyName: string; onClose: () => void }) {
  const [question, setQuestion] = useState("");
  const [copied, setCopied] = useState(false);
  const name = lawyerName(alert.reviewed_by);
  const to = lawyerEmail(alert.reviewed_by);
  const { subject, body } = message(alert, question, companyName);
  const mailto = `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  const copy = () =>
    navigator.clipboard
      .writeText(`To: ${to}\nSubject: ${subject}\n\n${body}`)
      .then(() => setCopied(true))
      .catch(() => setCopied(false));

  return (
    <div className="modal" onClick={onClose}>
      <div className="card" onClick={(e) => e.stopPropagation()}>
        <h3 className="tight">Ask {name} about this alert</h3>
        <p className="muted small">{alert.title}</p>
        <p className="small">
          {name} reviewed and approved this alert. Ask how it applies to your company and they will reply directly by email.
        </p>
        <label htmlFor="contact-question">Your question</label>
        <textarea id="contact-question" rows={5} autoFocus value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Does this apply to our Swiss subsidiary, and what should we prioritise before the entry into force?" />
        <p className="small"><b>To:</b> {to}</p>
        <div className="row wrap">
          <a className={`button primary${question.trim() ? "" : " disabled"}`} href={question.trim() ? mailto : undefined}
            aria-disabled={!question.trim()}>
            Open in email app
          </a>
          <button onClick={copy} disabled={!question.trim()}>{copied ? "Copied ✓" : "Copy message"}</button>
          <button onClick={onClose}>Close</button>
        </div>
        <p className="muted small">
          This opens your own email app with the alert details filled in. Nothing is sent from this prototype, and the
          alert itself is not legal advice.
        </p>
      </div>
    </div>
  );
}
