# Superset for the superset-api-plus integration test stack.
ARG SUPERSET_IMAGE=apachesuperset.docker.scarf.sh/apache/superset
ARG SUPERSET_VERSION=6.1.0
FROM ${SUPERSET_IMAGE}:${SUPERSET_VERSION}

# The official 6.x image ships no database drivers; the tests register a Postgres database.
ARG PSYCOPG2_VERSION=2.9.13
USER root
RUN uv pip install --no-cache --python /app/.venv/bin/python "psycopg2-binary==${PSYCOPG2_VERSION}"

COPY --chown=superset:superset docker/superset/superset_config.py /app/pythonpath/superset_config.py
COPY --chown=superset:superset --chmod=755 docker/superset/entrypoint.sh /app/docker/test-entrypoint.sh
USER superset

ENTRYPOINT ["/app/docker/test-entrypoint.sh"]
