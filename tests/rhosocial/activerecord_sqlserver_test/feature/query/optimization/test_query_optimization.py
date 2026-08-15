# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_query_optimization.py
"""
Bridge file for query optimization tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.optimization.test_query_optimization import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.optimization.test_query_optimization_async import *  # noqa: F403

