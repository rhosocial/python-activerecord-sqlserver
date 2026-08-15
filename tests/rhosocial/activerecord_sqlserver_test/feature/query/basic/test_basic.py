# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_basic.py
"""
Bridge file for basic tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.basic.test_basic import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.basic.test_basic_async import *  # noqa: F403

