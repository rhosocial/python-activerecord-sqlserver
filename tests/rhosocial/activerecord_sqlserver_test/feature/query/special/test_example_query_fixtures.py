# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_example_query_fixtures.py
"""
Bridge file for example query fixtures tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.special.test_example_query_fixtures import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.special.test_example_query_fixtures_async import *  # noqa: F403

