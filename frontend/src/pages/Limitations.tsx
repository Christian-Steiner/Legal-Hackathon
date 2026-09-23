import { api } from "../api";
import { useAsync } from "../components/ui";

export default function Limitations() {
  const meta = useAsync(api.meta);
  return (
    <div className="narrow">
      <h1>Limitations: what this tool does not do</h1>
      <div className="card">
        <h2>Not legal advice</h2>
        <p>
          This tool notifies clients about regulatory changes. It does not provide a legal assessment. Every alert is
          drafted with AI assistance and approved by a LEXR lawyer before a client sees it. Approval means that a
          lawyer considers the alert relevant and correctly sourced; it is not a full analysis of your situation.
        </p>
      </div>
      <div className="card">
        <h2>Sources covered</h2>
        <ul>
          <li><b>Covered:</b> Swiss federal law via the Fedlex SPARQL endpoint: new publications in the Official Compilation (AS), acts with upcoming entry-into-force dates, and open consultations (Vernehmlassungen).</li>
          <li><b>Simulated:</b> 8 updates from the hackathon organisers' dataset, clearly marked as simulated.</li>
          <li><b>Not covered:</b> soft law (e.g. FINMA circulars, FDPIC guidance), EU law (on the roadmap), cantonal and communal law, court decisions, and industry self-regulation.</li>
          <li>Fedlex data is fetched on demand; in demo mode a cached snapshot is used and may be out of date.</li>
        </ul>
      </div>
      <div className="card">
        <h2>AI can be wrong</h2>
        <ul>
          <li>The model ({meta.data?.llm_model ?? "…"}) can miss relevant changes, flag irrelevant ones, mistranslate, or misstate what a provision says.</li>
          <li>Matching depends on how complete and accurate the client's profile is.</li>
          <li>Source texts are mostly in German, French or Italian; summaries may be in another language. The reviewer sees the original next to the summary.</li>
          <li>Every statement in an alert must cite the official source (ELI + article). Always check the original text.</li>
          <li>Non-matches are stored with a reason, so missed alerts can be investigated.</li>
        </ul>
      </div>
      <div className="card">
        <h2>Data handling</h2>
        <ul>
          <li>Client profiles store company-level information and department contact addresses only.</li>
          <li>Model provider: {meta.data?.llm_provider ?? "…"}. With Apertus (Swisscom), prompts are processed in Switzerland. With OpenAI, profile data leaves Switzerland; use it only with the client's consent.</li>
          <li>Every ingest, match, draft, edit and decision is recorded in an audit log, with the model and prompt version used.</li>
        </ul>
      </div>
    </div>
  );
}
