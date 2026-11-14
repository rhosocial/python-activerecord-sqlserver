# tests/rhosocial/activerecord_sqlserver_test/feature/logging/conftest.py
"""No database is used here.

The execution-logging cases drive the backend through fake connections and
cursors, so this directory declares no ``prepare`` / ``teardown`` contract: it
needs neither a database nor the per-directory pinning that comes with one.
"""
