# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_active_query_join.py
"""
Bridge file for ActiveQuery join tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.joins.test_active_query_join import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.joins.test_active_query_join_async import *  # noqa: F403

