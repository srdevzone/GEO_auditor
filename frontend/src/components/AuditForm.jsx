import { useEffect, useState } from "react";
import { fetchProviders, startAudit } from "../api.js";

export default function AuditForm({ onStart }) {
  const [url, setUrl] = useState("");
  const [providers, setProviders] = useState([]);
  const [selected, setSelected] = useState("");
  const [maxPages, setMaxPages] = useState(15);
  const [queries, setQueries] = useState(7);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchProviders()
      .then((d) => {
        setProviders(d.providers || []);
        setSelected(d.default || "");
      })
      .catch(() => setProviders([]));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await startAudit({
        url: url.trim(),
        provider: selected || null,
        max_pages: Number(maxPages) || undefined,
        num_queries: Number(queries) || undefined,
      });
      onStart(res.job_id, url.trim(), selected);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  const configured = providers.filter((p) => p.configured);

  return (
    <div className="form-wrap">
      <h1 className="hero">Is your business visible inside AI answers?</h1>
      <p className="hero-sub">
        ChatGPT, Perplexity and Google AI Overviews now answer your customers' questions —
        and they cite only a handful of sources. Enter your website to find out if you're one
        of them, exactly why not, and what to fix first.
      </p>

      <form className="card audit-form" onSubmit={submit}>
        <label className="field">
          <span>Website URL</span>
          <input
            type="text"
            placeholder="https://yourbusiness.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>LLM provider</span>
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">Auto (best available)</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.configured ? "" : " (not configured)"}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Pages to crawl</span>
            <select value={maxPages} onChange={(e) => setMaxPages(e.target.value)}>
              {[5, 10, 15, 25, 40].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>AI questions to test</span>
            <select value={queries} onChange={(e) => setQueries(e.target.value)}>
              {[3, 5, 7, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="provider-status">
          {configured.length === 0 && (
            <span className="warn">No LLM provider detected — configure one in backend/.env first.</span>
          )}
          {configured.map((p) => (
            <span key={p.id} className="chip" title={p.note || p.name}>
              {p.supports_web_search ? "🔎" : "◇"} {p.name}
              {p.supports_web_search ? " · web search" : " · search proxy"}
            </span>
          ))}
        </div>

        {error && <div className="error-msg">{error}</div>}
        <button className="primary big" type="submit" disabled={submitting}>
          {submitting ? "Starting audit…" : "Audit my AI visibility →"}
        </button>
      </form>

      <div className="how">
        <h3>What you get</h3>
        <ol>
          <li>A score out of 100 with the full math behind it</li>
          <li>Proof of where you appear — or don't — inside AI answers</li>
          <li>Broken things with the exact quote from your site as evidence</li>
          <li>A prioritized fix list, ordered by impact vs. effort, with copy-paste solutions</li>
        </ol>
      </div>
    </div>
  );
}
