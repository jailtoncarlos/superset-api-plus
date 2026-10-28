"""Example dashboard 'Sales Dashboard': round trip, chart copies and dashboard copy (see checks.py)."""
from .checks import ExampleDashboardChecks


class TestSalesDashboard(ExampleDashboardChecks):
    TITLE = 'Sales Dashboard'
