"""Superset configuration for the test stack (docker-compose.yml). Values come from the environment."""
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Metadata in SQLite inside the container: the stack is disposable.
SQLALCHEMY_DATABASE_URI = os.environ.get("SUPERSET_METADATA_URI", "sqlite:////app/superset_home/superset.db")

# CSRF enabled as in production, to exercise the real flow (session login + X-CSRFToken).
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False

# A database login form for service accounts at /service-login/login/, besides the instance's own login (the
# README's "Instances with OAuth login"): exercises enable_session_mode(login_path=...).
from flask_appbuilder.security.views import AuthDBView  # noqa: E402 (after the settings above, as Superset reads them)
from superset.security import SupersetSecurityManager  # noqa: E402


class ServiceLoginView(AuthDBView):
    route_base = "/service-login"


class TestStackSecurityManager(SupersetSecurityManager):
    def register_views(self) -> None:
        super().register_views()
        self.appbuilder.add_view_no_menu(ServiceLoginView())


CUSTOM_SECURITY_MANAGER = TestStackSecurityManager

# SUPERSET_TEST_AUTH_TYPE=oauth: people log in through OAuth (the provider is a placeholder no test contacts); the
# suite then logs in through the service route (SUPERSET_LOGIN_PATH=/service-login/login/).
if os.environ.get("SUPERSET_TEST_AUTH_TYPE", "db") == "oauth":
    from flask_appbuilder.security.manager import AUTH_OAUTH  # noqa: E402

    AUTH_TYPE = AUTH_OAUTH
    OAUTH_PROVIDERS = [{
        "name": "placeholder", "icon": "fa-key", "token_key": "access_token",
        "remote_app": {"client_id": "superset", "client_secret": "placeholder",
                       "api_base_url": "http://oauth.invalid/", "access_token_url": "http://oauth.invalid/token",
                       "authorize_url": "http://oauth.invalid/authorize"},
    }]

# Superset 7.0: dashboard and chart viewers (Subjects) are behind ENABLE_VIEWERS, off by default; the library models
# them (T-05), so the test stack turns it on. SOFT_DELETE stays at its default (on), as on a real instance.
FEATURE_FLAGS = {"ENABLE_VIEWERS": True}
