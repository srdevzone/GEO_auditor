import { useState } from "react";
import AuditForm from "./components/AuditForm.jsx";
import ProgressPanel from "./components/ProgressPanel.jsx";
import ReportView from "./components/ReportView.jsx";

export default function App() {
  const [view, setView] = useState("form"); // form | running | report | error
  const [jobId, setJobId] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");

  const onStart = (jobId, url) => {
    setJobId(jobId);
    setUrl(url);
    setView("running");
  };

  const onDone = (result) => {
    setReport(result);
    setView("report");
  };

  const onError = (message) => {
    setError(message);
    setView("error");
  };

  const reset = () => {
    setView("form");
    setJobId(null);
    setReport(null);
    setError("");
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo" onClick={reset}>
          <span className="logo-mark">◈</span>
          <span>
            <strong>GEO Auditor</strong>
            <small>AI visibility audit</small>
          </span>
        </div>
        {view !== "form" && (
          <button className="ghost" onClick={reset}>
            ← New audit
          </button>
        )}
      </header>

      <main className="content">
        {view === "form" && <AuditForm onStart={onStart} />}
        {view === "running" && (
          <ProgressPanel jobId={jobId} url={url} onDone={onDone} onError={onError} />
        )}
        {view === "report" && report && <ReportView report={report} url={url} />}
        {view === "error" && (
          <div className="card error-card">
            <h2>Audit failed</h2>
            <p>{error}</p>
            <button className="primary" onClick={reset}>
              Try again
            </button>
          </div>
        )}
      </main>

      <footer className="footer">
        Evidence is real crawl + search data. Presence checks may use a labelled
        search-engine proxy when the chosen model cannot search the web.
      </footer>
    </div>
  );
}
