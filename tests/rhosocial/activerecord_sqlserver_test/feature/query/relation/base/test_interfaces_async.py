# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/base/test_interfaces_async.py
"""
Bridge file for async relation interface tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.base.test_interfaces_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation interface tests testsuite not available", allow_module_level=True)
