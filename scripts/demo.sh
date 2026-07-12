#!/usr/bin/env bash
#
# Set up and run the demo site: Django/Channels backend + React frontend.
#
#   scripts/demo.sh                 setup, then run both processes
#   scripts/demo.sh --setup-only    setup, then exit
#   scripts/demo.sh --no-setup      skip setup, just run
#   scripts/demo.sh --backend-only  setup, then run only the backend
#   scripts/demo.sh --frontend-only setup, then run only the frontend
#
# Ports are overridable: BACKEND_PORT (8000), FRONTEND_PORT (3000). The
# frontend talks websockets to ws://localhost:$BACKEND_PORT, so if you move
# the backend the frontend is told about it via REACT_APP_RX_WEBSOCKET_URL.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/examples/backend"
FRONTEND="$ROOT/examples/frontend"
REACT_PACKAGE="$ROOT/packages/react"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

run_setup=true
run_backend=true
run_frontend=true

for arg in "$@"; do
  case "$arg" in
    --setup-only)    run_backend=false; run_frontend=false ;;
    --no-setup)      run_setup=false ;;
    --backend-only)  run_frontend=false ;;
    --frontend-only) run_backend=false ;;
    -h|--help)       sed -n '3,13p' "${BASH_SOURCE[0]}" | cut -c3-; exit 0 ;;
    *) echo "demo.sh: unknown option '$arg' (try --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but not on PATH. $2"
}

# The channel layer is channels_redis with no in-memory fallback, so a
# reachable Redis is a hard requirement for the reactive write path.
ensure_redis() {
  local host port
  host="$(printf '%s' "$REDIS_URL" | sed -E 's#^redis://([^:/]+).*#\1#')"
  port="$(printf '%s' "$REDIS_URL" | sed -E 's#^redis://[^:]+:([0-9]+).*#\1#')"
  [ "$port" = "$REDIS_URL" ] && port=6379

  if (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null; then
    say "Redis is up at $host:$port"
    return
  fi

  if [ "$host" = "127.0.0.1" ] || [ "$host" = "localhost" ]; then
    if command -v redis-server >/dev/null 2>&1; then
      say "Starting redis-server on port $port"
      redis-server --port "$port" --daemonize yes
      sleep 1
      (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null && return
    fi
  fi

  die "no Redis at $host:$port. Start one, e.g.:
    redis-server --daemonize yes
    docker run -d -p 6379:6379 redis:7-alpine
  Or point REDIS_URL at an existing instance."
}

setup() {
  require uv "See https://docs.astral.sh/uv/getting-started/installation/"
  require npm "Install Node.js (>=18)."

  say "Syncing the Python workspace"
  (cd "$ROOT" && uv sync)

  # examples/frontend depends on @rxdjango/react via a file: path, so the
  # package has to be built before the frontend can resolve it.
  say "Building @rxdjango/react"
  [ -x "$REACT_PACKAGE/node_modules/.bin/tsup" ] || npm --prefix "$REACT_PACKAGE" install
  npm --prefix "$REACT_PACKAGE" run build

  if [ ! -d "$FRONTEND/node_modules" ]; then
    say "Installing frontend dependencies"
    npm --prefix "$FRONTEND" install
  fi

  say "Generating frontend channel types (makefrontend)"
  (cd "$BACKEND" && uv run ./manage.py makefrontend)

  # The demo's seed data (sample users, tasks, projects) ships as data
  # migrations, so migrate is all it takes to get a populated database.
  say "Applying migrations"
  (cd "$BACKEND" && DEBUG=True REDIS_URL="$REDIS_URL" uv run ./manage.py migrate)
}

start_backend() {
  say "Backend  → http://localhost:$BACKEND_PORT (admin at /admin)"
  cd "$BACKEND"
  DEBUG=True REDIS_URL="$REDIS_URL" \
    uv run ./manage.py runserver "$BACKEND_PORT"
}

start_frontend() {
  say "Frontend → http://localhost:$FRONTEND_PORT"
  PORT="$FRONTEND_PORT" \
  REACT_APP_RX_WEBSOCKET_URL="ws://localhost:$BACKEND_PORT" \
    npm --prefix "$FRONTEND" start
}

ensure_redis

if $run_setup; then
  setup
fi

if ! $run_backend && ! $run_frontend; then
  say "Setup complete."
  exit 0
fi

trap 'kill 0' INT TERM EXIT

if $run_backend; then
  start_backend &
fi

if $run_frontend; then
  start_frontend &
fi

wait
