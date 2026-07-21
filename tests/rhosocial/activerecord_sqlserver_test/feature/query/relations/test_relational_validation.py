# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_relational_validation.py
"""
Bridge file for relational validation tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.relations.test_relational_validation import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.relations.test_relational_validation_async import *  # noqa: F403

