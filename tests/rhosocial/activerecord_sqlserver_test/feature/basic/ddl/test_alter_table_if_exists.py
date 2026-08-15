# tests/rhosocial/activerecord_sqlserver_test/feature/basic/ddl/test_alter_table_if_exists.py
"""
ALTER TABLE IF [NOT] EXISTS tests (sync) for the SQL Server backend.

Thin bridge that runs the shared testsuite contract against the SQL Server
dialect, which supports ``DROP COLUMN IF EXISTS`` / ``DROP CONSTRAINT
IF EXISTS`` (2016+) but not ``ADD COLUMN IF NOT EXISTS``.
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.test_alter_table_if_exists import *  # noqa: F403
