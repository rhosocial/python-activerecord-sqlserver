# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/eager_loading/test_with_method_async.py
"""
Bridge file for async with_() method tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.eager_loading.test_with_method_async import *  # noqa: F403
except ImportError:
    pytest.skip("async with_() method tests testsuite not available", allow_module_level=True)
