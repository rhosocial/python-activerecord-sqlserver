# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_active_query_set_operation.py
"""
Bridge file for ActiveQuery set operation tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.set_operations.test_active_query_set_operation import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.set_operations.test_active_query_set_operation_async import *  # noqa: F403

