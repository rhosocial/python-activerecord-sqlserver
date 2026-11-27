# tests/rhosocial/activerecord_sqlserver_test/feature/rules/backend/__init__.py
"""SQL Server's own formal rule suite.

Every bridge here is driven by the shared testsuite rule library against
``backend/impl/sqlserver`` only, including the import-boundary guard that stops
backends from referring to one another.
"""
