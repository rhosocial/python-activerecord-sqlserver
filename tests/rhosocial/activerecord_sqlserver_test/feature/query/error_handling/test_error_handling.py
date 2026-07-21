# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_error_handling.py
"""
Bridge file for error handling tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.error_handling.test_error_handling import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.error_handling.test_error_handling_async import *  # noqa: F403

