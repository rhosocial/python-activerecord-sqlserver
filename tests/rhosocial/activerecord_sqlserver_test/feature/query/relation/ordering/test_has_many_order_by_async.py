# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/ordering/test_has_many_order_by_async.py
"""
Bridge file for async HasMany order_by tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.ordering.test_has_many_order_by_async import *  # noqa: F403
except ImportError:
    pytest.skip("async HasMany order_by tests testsuite not available", allow_module_level=True)
