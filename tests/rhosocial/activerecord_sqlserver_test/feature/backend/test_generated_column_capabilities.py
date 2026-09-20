# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_generated_column_capabilities.py
"""Explicit SQL Server generated/computed-column capability assertions."""

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


def test_generated_columns_supported():
    dialect = SQLServerDialect()
    assert dialect.supports_generated_column() is True
    assert dialect.supports_generated_columns() is True


def test_stored_and_virtual_generated_columns_supported():
    dialect = SQLServerDialect()
    assert dialect.supports_stored_generated_columns() is True
    assert dialect.supports_virtual_generated_columns() is True
