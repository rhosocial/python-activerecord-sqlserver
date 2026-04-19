# tests/conftest.py
"""Root conftest for SQL Server backend tests."""
import pytest


def pytest_configure(config):
    """Configure custom markers for SQL Server tests."""
    config.addinivalue_line(
        "markers", "requires_sqlserver: mark test as requiring SQL Server connection"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
