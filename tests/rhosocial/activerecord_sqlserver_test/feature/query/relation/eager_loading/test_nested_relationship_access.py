# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/eager_loading/test_nested_relationship_access.py
"""
Bridge file for nested relationship access tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.eager_loading.test_nested_relationship_access import *  # noqa: F403
except ImportError:
    pytest.skip("nested relationship access tests testsuite not available", allow_module_level=True)
