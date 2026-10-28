"""Example dashboard 'Slack Dashboard': round trip, chart copies and dashboard copy (see checks.py)."""
from .checks import ExampleDashboardChecks


class TestSlackDashboard(ExampleDashboardChecks):
    TITLE = 'Slack Dashboard'
