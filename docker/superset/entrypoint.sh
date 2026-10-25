#!/bin/bash
# Initialize the test stack's Superset and start the server (gunicorn from /usr/bin/run-server.sh).
set -euo pipefail

: "${SUPERSET_ADMIN_USERNAME:?set SUPERSET_ADMIN_USERNAME}"
: "${SUPERSET_ADMIN_PASSWORD:?set SUPERSET_ADMIN_PASSWORD}"

superset db upgrade
superset fab create-admin \
  --username "${SUPERSET_ADMIN_USERNAME}" \
  --password "${SUPERSET_ADMIN_PASSWORD}" \
  --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Admin}" \
  --lastname "${SUPERSET_ADMIN_LASTNAME:-Tests}" \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@example.com}" || true  # already exists on restarts
superset init

if [ "${SUPERSET_LOAD_EXAMPLES:-0}" = "1" ]; then
  superset load_examples
fi

exec /usr/bin/run-server.sh
