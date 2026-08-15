# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_cte_query_active_query.py
"""
Bridge file for CTE query active query tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.cte.test_cte_query_active_query import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.cte.test_cte_query_active_query_async import *  # noqa: F403

