"""Example dashboard "World Bank's Data": round trip, chart copies and dashboard copy (see checks.py)."""
from .checks import ExampleDashboardChecks


class TestWorldHealth(ExampleDashboardChecks):
    TITLE = "World Bank's Data"
