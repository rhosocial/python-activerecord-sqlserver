# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/boundary/test_boundary_async.py
"""
Bridge file for async relation boundary tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.boundary.test_boundary_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation boundary tests testsuite not available", allow_module_level=True)
