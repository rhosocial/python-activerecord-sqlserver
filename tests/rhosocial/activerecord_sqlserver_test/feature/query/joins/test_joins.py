# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_joins.py
"""
Bridge file for joins tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.joins.test_joins import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.joins.test_joins_async import *  # noqa: F403

