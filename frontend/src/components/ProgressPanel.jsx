import { useEffect, useRef, useState } from "react";
import { fetchJob } from "../api.js";

const STAGE_LABELS = {
  provider: "Connecting to AI provider",
  crawl: "Crawling your website",
  plan: "Planning the questions customers ask AI",
  presence: "Testing AI answers for your brand",
  score: "Scoring & prioritizing fixes",
  done: "Done",
  error: "Failed",
};

export default function ProgressPanel({ jobId, url, onDone, onError }) {
  const [job, setJob] = useState(null);
  const seen = useRef(new Set());

  useEffect(() => {
    let stop = false;
    const onDoneRef = { current: onDone };
    const onErrorRef = { current: onError };
    const poll = async () => {
      try {
        const j = await fetchJob(jobId);
        if (stop) return;
        setJob(j);
        (j.stage_log || []).forEach((l) => seen.current.add(JSON.stringify(l)));
        if (j.status === "done" && j.result) onDoneRef.current(j.result);
        else if (j.status === "failed") onErrorRef.current(j.error || "Audit failed");
        else setTimeout(poll, 1500);
      } catch {
        if (!stop) setTimeout(poll, 2000);
      }
    };
    poll();
    return () => {
      stop = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- poll loop uses refs; jobId only
  }, [jobId]);

  if (!job) {
    return <div className="card">Starting audit…</div>;
  }

  const stage = job.stage || "provider";
  const log = (job.stage_log || []).slice(-40);

  return (
    <div className="card progress-card">
      <h2>Auditing {url}</h2>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.round(job.progress * 100)}%` }} />
      </div>
      <p className="progress-pct">{Math.round(job.progress * 100)}% — {STAGE_LABELS[stage] || stage}</p>
      <div className="stage-log">
        {log.map((l, i) => (
          <div key={i} className="log-line">
            <span className="log-stage">{l.stage}</span>
            <span className="log-msg">{l.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
