#!/usr/bin/env bash
# GEO Auditor — dev/test script.
# Usage: ./script.sh [command]
#
#   setup          create backend venv + install deps + npm install
#   dev            run backend (8000) + frontend (5173) together
#   backend        run only the FastAPI backend (port 8000, reload)
#   frontend       run only the Vite frontend (port 5173)
#   test           run backend unit tests (pytest)
#   lint           ruff on backend + eslint on frontend
#   audit <url>    CLI audit: runs the full pipeline and writes reports/<domain>.md + .json
#   reports        regenerate the 3 sample reports (re-runs audits)
#   env-check      show which LLM providers are configured
#   reset          kill servers, clear caches
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_DIR="$PWD/backend"
FRONTEND_DIR="$PWD/frontend"
VENV="$BACKEND_DIR/.venv"
PY="$VENV/bin/python"
PID_DIR="$PWD/.pids"
mkdir -p "$PID_DIR"

log()  { printf '\033[1;34m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m⚠\033[0m %s\n' "$*"; }

cmd_setup() {
  log "Creating python venv + installing backend deps..."
  [ -d "$VENV" ] || python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
  log "Installing frontend deps..."
  (cd "$FRONTEND_DIR" && npm install --no-fund --no-audit)
  log "Done. Copy backend/.env.example -> backend/.env and add a key if you have one."
  log "Note: OPENCODE keys are auto-discovered from ~/.local/share/opencode/auth.json"
}

stop_server() { # $1 = name, $2 = pidfile
  if [ -f "$2" ]; then
    kill "$(cat "$2")" 2>/dev/null && log "Stopped $1" || true
    rm -f "$2"
  fi
}

start_backend() {
  if [ -f "$PID_DIR/backend.pid" ] && kill -0 "$(cat "$PID_DIR/backend.pid")" 2>/dev/null; then
    log "Backend already running (pid $(cat "$PID_DIR/backend.pid"))"
    return
  fi
  log "Starting backend on http://127.0.0.1:8000"
  (cd "$BACKEND_DIR" && setsid nohup "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 > "$PID_DIR/backend.log" 2>&1 & echo $! > "$PID_DIR/backend.pid")
  sleep 2
  curl -sf http://127.0.0.1:8000/api/health >/dev/null || { warn "Backend failed to start - see $PID_DIR/backend.log"; exit 1; }
}

start_frontend() {
  if [ -f "$PID_DIR/frontend.pid" ] && kill -0 "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null; then
    log "Frontend already running (pid $(cat "$PID_DIR/frontend.pid"))"
    return
  fi
  log "Starting frontend on http://localhost:5173"
  (cd "$FRONTEND_DIR" && setsid nohup npm run dev > "$PID_DIR/frontend.log" 2>&1 & echo $! > "$PID_DIR/frontend.pid")
}

cmd_dev() {
  start_backend
  start_frontend
  log "Open http://localhost:5173 — backend API at http://127.0.0.1:8000/api"
  log "Logs: $PID_DIR/backend.log, $PID_DIR/frontend.log  |  Ctrl-C won't stop servers; use ./script.sh stop"
}

cmd_backend()  { start_backend; log "Backend running (reload disabled). Logs: $PID_DIR/backend.log"; }
cmd_frontend() { start_frontend; log "Frontend running at http://localhost:5173"; }
cmd_stop()     { stop_server backend "$PID_DIR/backend.pid"; stop_server frontend "$PID_DIR/frontend.pid"; }

cmd_test() {
  log "Running backend tests (pytest)..."
  (cd "$BACKEND_DIR" && "$VENV/bin/python" -m pytest tests -q)
}

cmd_lint() {
  log "Ruff (backend)..."
  (cd "$BACKEND_DIR" && "$VENV/bin/python" -m ruff check app tests || true)
  log "ESLint (frontend)..."
  (cd "$FRONTEND_DIR" && npx eslint src --max-warnings=0 || true)
}

cmd_env_check() {
  "$PY" -c "
import sys; sys.path.insert(0, '$BACKEND_DIR')
from app.config import settings
from app.llm.registry import Registry
import asyncio

async def main():
    reg = Registry(settings)
    for s in await reg.statuses():
        state = 'CONFIGURED' if s.configured else 'offline/missing'
        print(f'  {s.name:12} {s.model:34} {state:16} web_search: {s.supports_web_search}')

asyncio.run(main())
"
  log "Tip: OPENCODE_API_KEY is auto-discovered from opencode's auth.json; set OPENROUTER_API_KEY / GROQ_API_KEY / OPENAI_API_KEY in backend/.env for more."
}

cmd_audit() {
  URL="${1:-}"
  [ -z "$URL" ] && { echo "usage: ./script.sh audit <url> [provider]" >&2; exit 1; }
  PROVIDER="${2:-}"
  mkdir -p reports
  DOMAIN="$(echo "$URL" | sed -E 's#https?://##; s#/.*##' | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-')"
  log "Auditing $URL (provider: ${PROVIDER:-auto})..."
  "$PY" - "$URL" "$PROVIDER" "$BACKEND_DIR" <<'PYEOF'
import asyncio, json, sys
sys.path.insert(0, sys.argv[3])
from pathlib import Path
from app.config import settings
from app.llm.registry import Registry
from app.audit.orchestrator import AuditRunner, store

async def main():
    url, provider = sys.argv[1], sys.argv[2] or None
    reg = Registry(settings)
    job = await store.create(url, provider, None, None, None)
    await AuditRunner(reg).run(job.id)
    j = await store.get(job.id)
    if j.status != "done":
        print("AUDIT FAILED:", j.error)
        sys.exit(1)
    domain = url.replace("https://", "").replace("http://", "").split("/")[0]
    Path("reports").mkdir(exist_ok=True)
    Path(f"reports/{domain}.json").write_text(json.dumps(j.result, indent=2))
    Path(f"reports/{domain}.md").write_text(j.markdown)
    print(f"SCORE: {j.result['score']['overall']}/100 ({j.result['score']['grade']}) -> reports/{domain}.md")

asyncio.run(main())
PYEOF
}

cmd_reports() {
  log "Regenerating the three sample reports (this re-runs 3 audits, ~10 min)..."
  cmd_audit "https://www.barackobama.com"
  cmd_audit "https://en.wikipedia.org/wiki/Generative_engine_optimization"
  cmd_audit "https://www.openai.com"
  log "Reports written to reports/"
}

cmd_reset() {
  cmd_stop || true
  rm -rf "$PID_DIR" "$BACKEND_DIR/data" backend/.venv frontend/node_modules
  log "Cleaned. Run ./script.sh setup to rebuild."
}

case "${1:-dev}" in
  setup)     cmd_setup ;;
  dev)       cmd_dev ;;
  backend)   cmd_backend ;;
  frontend)  cmd_frontend ;;
  stop)      cmd_stop ;;
  test)      cmd_test ;;
  lint)      cmd_lint ;;
  env-check) cmd_env_check ;;
  audit)     cmd_audit "${2:-}" "${3:-}" ;;
  reports)   cmd_reports ;;
  reset)     cmd_reset ;;
  *) echo "usage: ./script.sh [setup|dev|backend|frontend|stop|test|lint|env-check|audit <url>|reports|reset]" >&2; exit 1 ;;
esac
