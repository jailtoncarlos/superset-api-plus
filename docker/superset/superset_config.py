"""Superset configuration for the test stack (docker-compose.yml). Values come from the environment."""
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Metadata in SQLite inside the container: the stack is disposable.
SQLALCHEMY_DATABASE_URI = os.environ.get("SUPERSET_METADATA_URI", "sqlite:////app/superset_home/superset.db")

# CSRF enabled as in production, to exercise the real flow (session login + X-CSRFToken).
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False
