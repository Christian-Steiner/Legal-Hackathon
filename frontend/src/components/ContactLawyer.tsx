// Funnel back to LEXR: the client asks the lawyer who approved an alert for advice.
// Frontend only - opens the client's own email app with a pre-filled message; nothing is sent or stored here.
import { useState } from "react";
import type { Alert } from "../types";
import { strings } from "../i18n";
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

function message(a: Alert, question: string, companyName: string, department?: string) {
  const t = strings(a.language);
  const name = lawyerName(a.reviewed_by);
  const sources = a.citations
    .map((c, i) => `  [${i + 1}] ${c.article ?? ""} ${c.eli ?? c.source_url ?? ""}`.trimEnd())
    .join("\n");
  const subject = t.mailSubject(a.title.length > 80 ? a.title.slice(0, 77) + "…" : a.title);
  const body =
    `${t.mailGreeting(name)}\n\n${question.trim()}\n\n` +
    `${t.mailConcerns}\n${a.title}\n` +
    (department ? `${t.mailDept(department)}\n` : "") +
    `${t.mailMeta(fmtDate(a.delivered_at), t.urgency[a.urgency], a.id)}\n` +
    (sources ? `${t.sources}:\n${sources}\n` : "") +
    `\n${t.mailRegards}\n${companyName}`;
  return { subject, body };
}

export function ContactLawyerModal({ alert, department, companyName, onClose }:
  { alert: Alert; department?: string; companyName: string; onClose: () => void }) {
  const t = strings(alert.language);
  const [question, setQuestion] = useState("");
  const [copied, setCopied] = useState(false);
  const name = lawyerName(alert.reviewed_by);
  const to = lawyerEmail(alert.reviewed_by);
  const { subject, body } = message(alert, question, companyName, department);
  const mailto = `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  const copy = () =>
    navigator.clipboard
      .writeText(`${t.to}: ${to}\n${t.subject}: ${subject}\n\n${body}`)
      .then(() => setCopied(true))
      .catch(() => setCopied(false));

  return (
    <div className="modal" onClick={onClose}>
      <div className="card" onClick={(e) => e.stopPropagation()} lang={alert.language?.toLowerCase()}>
        <h3 className="tight">{t.contactTitle(name)}</h3>
        <p className="muted small">{alert.title}</p>
        <p className="small">{t.contactIntro(name)}</p>
        <label htmlFor="contact-question">{t.yourQuestion}</label>
        <textarea id="contact-question" rows={5} autoFocus value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder={t.questionPlaceholder} />
        <p className="small"><b>{t.to}:</b> {to}</p>
        <div className="row wrap">
          <a className={`button primary${question.trim() ? "" : " disabled"}`} href={question.trim() ? mailto : undefined}
            aria-disabled={!question.trim()}>
            {t.openEmail}
          </a>
          <button onClick={copy} disabled={!question.trim()}>{copied ? t.copied : t.copy}</button>
          <button onClick={onClose}>{t.close}</button>
        </div>
        <p className="muted small">{t.contactNote}</p>
      </div>
    </div>
  );
}
