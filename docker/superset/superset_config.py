"""Configuração do Superset da stack de testes (docker-compose.yml). Valores vêm do ambiente."""
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Metadados em SQLite dentro do container: a stack é descartável.
SQLALCHEMY_DATABASE_URI = os.environ.get("SUPERSET_METADATA_URI", "sqlite:////app/superset_home/superset.db")

# CSRF ligado como em produção, para exercitar o fluxo real (login por sessão + X-CSRFToken).
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False
