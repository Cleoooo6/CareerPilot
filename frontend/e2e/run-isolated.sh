#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
HOST_PY="$ROOT/backend/.venv/Scripts/python.exe"

if [ ! -f .env ]; then
  echo "BLOCKED: .env is required" >&2
  exit 1
fi
set -a
. ./.env
set +a

: "${TEST_DATABASE_URL:?TEST_DATABASE_URL is required in .env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in .env}"
POSTGRES_USER="${POSTGRES_USER:-careerpilot}"

DB_INFO="$("$HOST_PY" - <<'PY'
from dotenv import dotenv_values
from urllib.parse import urlparse
values = dotenv_values('.env')
for key in ('DATABASE_URL', 'TEST_DATABASE_URL'):
    parsed = urlparse(values.get(key, ''))
    print(f"{key}={parsed.path.lstrip('/')}")
PY
)"
DEV_DB="$(printf '%s\n' "$DB_INFO" | sed -n 's/^DATABASE_URL=//p')"
TEST_DB="$(printf '%s\n' "$DB_INFO" | sed -n 's/^TEST_DATABASE_URL=//p')"
echo "DEV_DB=$DEV_DB"
echo "TEST_DB=$TEST_DB"
if [ "$TEST_DB" != "careerpilot_test" ]; then
  echo "BLOCKED: TEST_DATABASE_URL does not target careerpilot_test" >&2
  exit 1
fi
if [ "$TEST_DB" = "$DEV_DB" ]; then
  echo "BLOCKED: TEST_DATABASE_URL and DATABASE_URL are the same database" >&2
  exit 1
fi

INTERNAL_TEST_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${TEST_DB}"
WORKERS="${E2E_WORKERS:-1}"
RUN_ID="${E2E_RUN_ID:-$(date +%Y%m%d%H%M%S)}"
case "$RUN_ID" in
  *[!A-Za-z0-9_.-]*) echo "BLOCKED: invalid E2E_RUN_ID" >&2; exit 1;;
esac
NET="careerpilot-e2e-${RUN_ID}"
API="careerpilot-e2e-api-${RUN_ID}"
WEB="careerpilot-e2e-web-${RUN_ID}"
E2E_IMAGE="careerpilot-e2e-isolated"
WEB_IMAGE="${E2E_WEB_IMAGE:-careerpilot-web:latest}"

demo_snapshot() {
  "$HOST_PY" - <<'PY'
import json
import psycopg
from dotenv import dotenv_values

url = dotenv_values('.env')['DATABASE_URL']
with psycopg.connect(url, options='-c default_transaction_read_only=on') as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM app_user WHERE external_id='demo-user'")
        row = cur.fetchone()
        uid = row[0] if row else None
        counts = {}
        if uid is None:
            for name in ('profile', 'profile_revisions', 'roadmaps', 'conversations', 'messages'):
                counts[name] = 0
        else:
            for name, sql in (
                ('profile', 'SELECT count(*) FROM career_profile WHERE user_id=%s'),
                ('profile_revisions', 'SELECT count(*) FROM profile_revision WHERE user_id=%s'),
                ('roadmaps', 'SELECT count(*) FROM career_roadmap WHERE user_id=%s'),
                ('conversations', 'SELECT count(*) FROM conversation WHERE user_id=%s'),
                ('messages', 'SELECT count(*) FROM message m JOIN conversation c ON c.id=m.conversation_id WHERE c.user_id=%s'),
            ):
                cur.execute(sql, (uid,))
                counts[name] = cur.fetchone()[0]
        for name, sql in (
            ('market_jobs', 'SELECT count(*) FROM market_job'),
            ('market_sources', 'SELECT count(*) FROM market_source'),
        ):
            cur.execute(sql)
            counts[name] = cur.fetchone()[0]
        print(json.dumps(counts, sort_keys=True))
PY
}

reset_test_db() {
  MSYS_NO_PATHCONV=1 docker exec -i -e E2E_DB_GUARD="$TEST_DB" "$API" python - < "$ROOT/backend/tests/e2e_reset.py"
}

snapshot_test_db() {
  MSYS_NO_PATHCONV=1 docker exec -i -e E2E_DB_GUARD="$TEST_DB" "$API" python - < "$ROOT/backend/tests/e2e_reset.py" --snapshot
}

seed_industry() {
  MSYS_NO_PATHCONV=1 docker exec -i -e E2E_DB_GUARD="$TEST_DB" "$API" python - < "$ROOT/backend/tests/e2e_industry_seed.py"
}

cleanup() {
  if docker ps -a --format '{{.Names}}' | grep -qx "$API"; then
    MSYS_NO_PATHCONV=1 docker exec -i -e E2E_DB_GUARD="$TEST_DB" "$API" python - < "$ROOT/backend/tests/e2e_reset.py" >/dev/null 2>&1 || true
  fi
  docker rm -f "$WEB" "$API" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Building isolated images..."
if [ "${E2E_SKIP_API_BUILD:-0}" != "1" ]; then
  docker build -t careerpilot-api-e2e ./backend >/dev/null
fi
docker image inspect "$WEB_IMAGE" >/dev/null 2>&1 || docker build -t "$WEB_IMAGE" -f frontend/Dockerfile . >/dev/null
docker build -f - -t "$E2E_IMAGE" . >/dev/null <<'DOCKER'
FROM mcr.microsoft.com/playwright:v1.65.1-noble
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
DOCKER

docker network create "$NET" >/dev/null

docker run -d --name "$API" --network careerpilot_net \
  -e APP_ENV=test \
  -e DATABASE_URL="$INTERNAL_TEST_URL" \
  -e AUTH_COOKIE_SECURE=false \
  -e LLM_MODE=mock \
  -e LLM_API_KEY= \
  careerpilot-api-e2e >/dev/null
docker network connect --alias api "$NET" "$API"

for i in $(seq 1 60); do
  if docker exec "$API" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "BLOCKED: isolated API did not become ready" >&2
    docker logs "$API" >&2 || true
    exit 1
  fi
done

ACTUAL_TEST_DB="$(docker exec "$API" python -c "import os, psycopg; c=psycopg.connect(os.environ['DATABASE_URL']); print(c.info.dbname)")"
ACTUAL_DEV_DB="$(docker exec careerpilot-api-1 python -c "from app.core.config import get_settings; import psycopg; c=psycopg.connect(get_settings().database_url); print(c.info.dbname)")"
echo "ISOLATED_TEST_DB=$ACTUAL_TEST_DB"
echo "FORMAL_DEV_DB=$ACTUAL_DEV_DB"
if [ "$ACTUAL_TEST_DB" != "careerpilot_test" ] || [ "$ACTUAL_TEST_DB" = "$ACTUAL_DEV_DB" ]; then
  echo "BLOCKED: database identity check failed" >&2
  exit 1
fi

docker run -d --name "$WEB" --network "$NET" "$WEB_IMAGE" >/dev/null
for i in $(seq 1 30); do
  if docker exec "$WEB" wget -qO- http://127.0.0.1:8080/ >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "BLOCKED: isolated web did not become ready" >&2
    exit 1
  fi
done

reset_test_db
DEMO_BEFORE="$(demo_snapshot)"
echo "DEMO_BEFORE=$DEMO_BEFORE"
echo "TEST_DB_AFTER_RESET=$(snapshot_test_db)"

for round in 1 2; do
  echo "=== isolated E2E round $round ==="
  reset_test_db
  seed_industry
  docker run --rm --network "$NET" \
    -e E2E_BASE_URL="http://$WEB:8080" \
    -e E2E_TEST_DB_CONFIRMED=true \
    -e E2E_RUN_ID="${RUN_ID}-r${round}" \
    -e E2E_USER_PREFIX=e2e-cp \
    "$E2E_IMAGE" npx playwright test --workers="$WORKERS"
  reset_test_db
  echo "TEST_DB_AFTER_ROUND_${round}=$(snapshot_test_db)"
done

DEMO_AFTER="$(demo_snapshot)"
echo "DEMO_AFTER=$DEMO_AFTER"
if [ "$DEMO_BEFORE" != "$DEMO_AFTER" ]; then
  echo "BLOCKED: demo-user/dev DB changed during isolated E2E" >&2
  exit 1
fi
echo "PASS: isolated E2E completed; demo-user unchanged; test DB cleaned"