# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_cross_database_compatibility.py
"""
Bridge file for cross-database compatibility tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.cross_database.test_cross_database_compatibility import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.cross_database.test_cross_database_compatibility_async import *  # noqa: F403

