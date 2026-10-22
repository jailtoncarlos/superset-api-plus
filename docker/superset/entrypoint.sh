#!/bin/bash
# Inicializa o Superset da stack de testes e sobe o servidor (gunicorn de /usr/bin/run-server.sh).
set -euo pipefail

: "${SUPERSET_ADMIN_USERNAME:?defina SUPERSET_ADMIN_USERNAME}"
: "${SUPERSET_ADMIN_PASSWORD:?defina SUPERSET_ADMIN_PASSWORD}"

superset db upgrade
superset fab create-admin \
  --username "${SUPERSET_ADMIN_USERNAME}" \
  --password "${SUPERSET_ADMIN_PASSWORD}" \
  --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Admin}" \
  --lastname "${SUPERSET_ADMIN_LASTNAME:-Testes}" \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@example.com}" || true  # já existe em reinícios
superset init

if [ "${SUPERSET_LOAD_EXAMPLES:-0}" = "1" ]; then
  superset load_examples
fi

exec /usr/bin/run-server.sh
