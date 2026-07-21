# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_queries.py
"""
Bridge file for sync queries tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.basic.test_queries import *  # noqa: F403
