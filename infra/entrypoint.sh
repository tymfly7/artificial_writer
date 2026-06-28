#!/usr/bin/env bash
# Container entrypoint: wait for Postgres, (optionally) apply migrations, then run
# the passed command.
#
# Every service shares this entrypoint, but only ONE should migrate: the `api`
# service runs `alembic upgrade head` on start, while the worker/scheduler set
# AW_RUN_MIGRATIONS=0 and wait for the api to come up healthy first. Running the
# migration from several services at once races on creating alembic_version.
set -euo pipefail

# Derive host:port from AW_DATABASE_URL for the readiness wait. Falls back to the
# compose service name so this works out of the box with the bundled stack.
DB_HOST="$(python - <<'PY'
import os
from urllib.parse import urlparse

url = os.environ.get("AW_DATABASE_URL", "")
# Strip the SQLAlchemy driver suffix (e.g. postgresql+asyncpg) before parsing.
scheme, _, rest = url.partition("://")
parsed = urlparse("scheme://" + rest)
print(parsed.hostname or "postgres")
PY
)"
DB_PORT="$(python - <<'PY'
import os
from urllib.parse import urlparse

url = os.environ.get("AW_DATABASE_URL", "")
scheme, _, rest = url.partition("://")
parsed = urlparse("scheme://" + rest)
print(parsed.port or 5432)
PY
)"

echo "entrypoint: waiting for Postgres at ${DB_HOST}:${DB_PORT} ..."
for _ in $(seq 1 60); do
    if python -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(0 if s.connect_ex(('${DB_HOST}', ${DB_PORT}))==0 else 1)"; then
        echo "entrypoint: Postgres is up."
        break
    fi
    sleep 1
done

if [ "${AW_RUN_MIGRATIONS:-1}" != "0" ]; then
    echo "entrypoint: applying database migrations (alembic upgrade head) ..."
    alembic upgrade head
else
    echo "entrypoint: AW_RUN_MIGRATIONS=0 -> skipping migrations."
fi

echo "entrypoint: starting -> $*"
exec "$@"
