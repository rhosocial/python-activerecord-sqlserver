# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/legacy/test_relational_validation.py
"""
Bridge file for legacy relational validation tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.legacy.test_relational_validation import *  # noqa: F403
except ImportError:
    pytest.skip("legacy relational validation tests testsuite not available", allow_module_level=True)
