# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_window_functions.py
"""
Bridge file for window functions tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.window_functions.test_window_functions import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.window_functions.test_window_functions_async import *  # noqa: F403

