const BASE = "/api";

async function json(url, options) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      detail = body.detail || body.message || detail;
    } catch {
      // non-JSON error body; keep the HTTP status text
    }
    throw new Error(detail);
  }
  return resp.json();
}

export function fetchProviders() {
  return json(`${BASE}/providers`);
}

export function startAudit(payload) {
  return json(`${BASE}/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchJob(jobId) {
  return json(`${BASE}/audit/${jobId}`);
}

export function fetchMarkdown(jobId) {
  return json(`${BASE}/audit/${jobId}/markdown`);
}

export function downloadMarkdown(markdown, brand, url) {
  const host = url.replace(/^https?:\/\//, "").replace(/\W+/g, "-").slice(0, 40);
  const blob = new Blob([markdown], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `geo-report-${host}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
}
