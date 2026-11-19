# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/base/test_base.py
"""
Bridge file for relation base tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.base.test_base import *  # noqa: F403
except ImportError:
    pytest.skip("relation base tests testsuite not available", allow_module_level=True)
