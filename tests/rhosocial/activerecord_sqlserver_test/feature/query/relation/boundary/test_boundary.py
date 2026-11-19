# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/boundary/test_boundary.py
"""
Bridge file for relation boundary tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.boundary.test_boundary import *  # noqa: F403
except ImportError:
    pytest.skip("relation boundary tests testsuite not available", allow_module_level=True)
