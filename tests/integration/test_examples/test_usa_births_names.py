"""Example dashboard 'USA Births Names': round trip, chart copies and dashboard copy (see checks.py)."""
from .checks import ExampleDashboardChecks


class TestUsaBirthsNames(ExampleDashboardChecks):
    TITLE = 'USA Births Names'
