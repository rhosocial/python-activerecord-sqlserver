# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_active_query_aggregate.py
"""
Bridge file for ActiveQuery aggregate tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.aggregate.test_active_query_aggregate import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.aggregate.test_active_query_aggregate_async import *  # noqa: F403

