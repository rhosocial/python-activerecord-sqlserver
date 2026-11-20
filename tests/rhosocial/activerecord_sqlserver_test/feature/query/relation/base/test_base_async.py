# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/base/test_base_async.py
"""
Bridge file for async relation base tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.base.test_base_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation base tests testsuite not available", allow_module_level=True)
