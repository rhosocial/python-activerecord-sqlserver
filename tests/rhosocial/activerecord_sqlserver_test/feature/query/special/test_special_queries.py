# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_special_queries.py
"""
Bridge file for special queries tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.special.test_special_queries import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.special.test_special_queries_async import *  # noqa: F403

