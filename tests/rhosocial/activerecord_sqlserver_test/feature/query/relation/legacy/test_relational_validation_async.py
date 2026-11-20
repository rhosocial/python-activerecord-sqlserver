# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/legacy/test_relational_validation_async.py
"""
Bridge file for async legacy relational validation tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.legacy.test_relational_validation_async import *  # noqa: F403
except ImportError:
    pytest.skip("async legacy relational validation tests testsuite not available", allow_module_level=True)
