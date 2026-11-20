# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/eager_loading/test_nested_relationship_access_async.py  # noqa: E501
"""
Bridge file for async nested relationship access tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.eager_loading.test_nested_relationship_access_async import *  # noqa: F403,E501
except ImportError:
    pytest.skip("async nested relationship access tests testsuite not available", allow_module_level=True)
