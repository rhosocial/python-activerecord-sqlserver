# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/integration/test_integration.py
"""
Bridge file for relation integration tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.integration.test_integration import *  # noqa: F403
except ImportError:
    pytest.skip("relation integration tests testsuite not available", allow_module_level=True)
