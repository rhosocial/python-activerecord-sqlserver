# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/integration/test_integration_async.py
"""
Bridge file for async relation integration tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.integration.test_integration_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation integration tests testsuite not available", allow_module_level=True)
