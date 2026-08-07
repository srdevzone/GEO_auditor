import { useState } from "react";
import { downloadMarkdown, fetchMarkdown } from "../api.js";

const SEVERITY_COLOR = { critical: "var(--danger)", major: "var(--warn)", minor: "var(--accent)", info: "var(--muted)" };
const DIM_LABEL = { presence: "AI presence", answerability: "Answerability", entity: "Entity & foundation", authority: "Authority & trust" };

export default function ReportView({ report, url }) {
  const [downloading, setDownloading] = useState(false);
  const score = report.score;
  const pct = Math.min(score.overall, 100);

  const download = async () => {
    setDownloading(true);
    try {
      const { markdown } = await fetchMarkdown(report.meta?.job_id || "");
      downloadMarkdown(markdown, report.meta?.brand, url);
    } catch (e) {
      console.error("Download failed", e);
    }
    setDownloading(false);
  };

  return (
    <div className="report">
      <section className="report-head card">
        <div className="score-block">
          <div className="gauge" style={{ "--pct": `${pct * 3.6}deg` }}>
            <div className="gauge-inner">
              <span className="gauge-num">{score.overall}</span>
              <span className="gauge-grade">{score.grade}</span>
            </div>
          </div>
          <div className="score-copy">
            <h2>{report.meta?.brand || url}</h2>
            <p className="grade-blurb">{score.grade_blurb}</p>
            <p className="meta-line">
              Crawled {report.meta?.crawled_count} page(s) · LLM: {report.meta?.provider?.name} ·{" "}
              {report.meta?.search_mode}
            </p>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>
          How the score is calculated{" "}
          <button className="mini" onClick={download} disabled={downloading}>
            {downloading ? "…" : "⬇ Download report (.md)"}
          </button>
        </h3>
        <p className="how">{score.how_calculated}</p>
        <table className="dim-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Weight</th>
              <th>Score</th>
              <th>Weighted</th>
              <th>How it was measured</th>
            </tr>
          </thead>
          <tbody>
            {score.dimensions.map((d) => (
              <tr key={d.dimension}>
                <td><strong>{d.label}</strong></td>
                <td>{Math.round(d.weight * 100)}%</td>
                <td>
                  <div className="dim-bar">
                    <div className="dim-fill" style={{ width: `${d.skipped ? 0 : d.score}%` }} />
                    <span>{d.skipped ? "—" : d.score}</span>
                  </div>
                </td>
                <td>{d.skipped ? "—" : d.weighted}</td>
                <td className="dim-measured">
                  {d.measured || d.skip_reason}
                  {d.deductions?.length > 0 && (
                    <details>
                      <summary>deductions</summary>
                      <ul className="deductions">
                        {d.deductions.slice(0, 12).map((dd, i) => (
                          <li key={i}>
                            <span className="sev-dot" style={{ background: dd.severity ? SEVERITY_COLOR[dd.severity] : "var(--accent)" }} />
                            {dd.title} {dd.appeared !== undefined && (dd.appeared ? "✓" : "✗")}
                            {dd.points ? ` (−${dd.points})` : ""}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {report.summary && (
        <section className="card">
          <h3>Plain-language summary</h3>
          <p className="summary">{report.summary}</p>
        </section>
      )}

      <section className="card">
        <h3>Where you show up in AI answers</h3>
        <table className="presence-table">
          <thead>
            <tr><th>Customer question</th><th>Intent</th><th>Surfaced?</th><th>Evidence</th></tr>
          </thead>
          <tbody>
            {report.presence.map((p, i) => (
              <tr key={i}>
                <td>{p.query}</td>
                <td><span className="tag">{p.intent}</span></td>
                <td>
                  {p.appeared === null && <span className="pill err">error</span>}
                  {p.appeared === true && <span className="pill ok">YES</span>}
                  {p.appeared === false && <span className="pill no">no</span>}
                  <div className="tiny">{p.mode}</div>
                </td>
                <td className="pres-evidence">
                  {p.appeared && p.mention_quote && <blockquote>“{p.mention_quote}”</blockquote>}
                  {p.appeared && !p.mention_quote && p.answer_excerpt && <blockquote>“{p.answer_excerpt.slice(0, 220)}…”</blockquote>}
                  {!p.appeared && p.answer_excerpt && <blockquote className="muted">“{p.answer_excerpt.slice(0, 260)}…”</blockquote>}
                  {p.cited_urls?.length > 0 && (
                    <details>
                      <summary>cites ({p.cited_urls.length})</summary>
                      <ul className="top-results">
                        {p.cited_urls.slice(0, 10).map((u, j) => (
                          <li key={j}>
                            <a href={u} target="_blank" rel="noreferrer">{u}</a>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {p.top_results?.length > 0 && (
                    <details>
                      <summary>top results ({p.top_results.length})</summary>
                      <ol className="top-results">
                        {p.top_results.map((r, j) => (
                          <li key={j}>
                            <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
                            <span className="tiny">{r.url}</span>
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                  {p.note && <p className="tiny">{p.note}</p>}
                  {p.error && <p className="tiny err-text">{p.error}</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="tiny">
          {report.meta?.search_mode?.includes("proxy")
            ? "Your model cannot search the web, so this used a labelled search-engine proxy: we checked whether your domain appears in the top organic results the AI engines draw from."
            : "Live probing: the AI searched and answered like ChatGPT, then we checked whether your domain was cited."}
        </p>
      </section>

      <section className="card">
        <h3>What's broken — with proof</h3>
        {["presence", "answerability", "entity", "authority"]
          .filter((dim) => report.findings.some((f) => f.dimension === dim))
          .map((dim) => (
            <div key={dim} className="dim-group">
              <h4>{DIM_LABEL[dim]}</h4>
              {report.findings
                .filter((f) => f.dimension === dim)
                .map((f, i) => (
                  <div key={i} className="finding">
                    <div className="finding-head">
                      <span className="sev-badge" style={{ background: SEVERITY_COLOR[f.severity] }}>
                        {f.severity}
                      </span>
                      <strong>{f.title}</strong>
                    </div>
                    {f.jargon && <p className="jargon">💡 {f.jargon}</p>}
                    <div className="evidence">
                      {f.evidence.page && <div><span className="ev-label">Page</span> <a href={f.evidence.page} target="_blank" rel="noreferrer">{f.evidence.page}</a></div>}
                      {f.evidence.quote && <div><span className="ev-label">Found (quote)</span> <blockquote>“{f.evidence.quote}”</blockquote></div>}
                      {f.evidence.found && <div><span className="ev-label">What exists today</span> <p>{f.evidence.found}</p></div>}
                      {f.evidence.should_be && <div><span className="ev-label">What it should be</span> <p>{f.evidence.should_be}</p></div>}
                    </div>
                  </div>
                ))}
            </div>
          ))}
      </section>

      <section className="card">
        <h3>Fix list — in priority order (impact ÷ effort)</h3>
        {report.fixes.length === 0 && <p className="tiny">No fixes needed — the model found nothing actionable. Double-check with a different provider.</p>}
        <ol className="fix-list">
          {report.fixes.map((fix, i) => (
            <li key={i} className={`fix-item fix-${fix.bucket.replace(/\s+/g, "-").toLowerCase()}`}>
              <div className="fix-rank">#{fix.rank}</div>
              <div className="fix-body">
                <div className="fix-head">
                  <span className="bucket-pill">{fix.bucket}</span>
                  <span className="tiny">
                    impact {fix.impact}/5 · effort {fix.effort}/5 · priority {fix.priority_score}
                  </span>
                </div>
                <p className="fix-title">{fix.title}</p>
                {fix.jargon && <p className="jargon">💡 {fix.jargon}</p>}
                <pre className="fix-code">{fix.fix}</pre>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {report.strengths?.length > 0 && (
        <section className="card">
          <h3>What's already working</h3>
          <ul className="strengths">
            {report.strengths.map((s, i) => (
              <li key={i}><strong>{s.title}</strong> — {s.evidence}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
