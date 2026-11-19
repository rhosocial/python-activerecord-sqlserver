# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/base/test_interfaces.py
"""
Bridge file for relation interface tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.base.test_interfaces import *  # noqa: F403
except ImportError:
    pytest.skip("relation interface tests testsuite not available", allow_module_level=True)
