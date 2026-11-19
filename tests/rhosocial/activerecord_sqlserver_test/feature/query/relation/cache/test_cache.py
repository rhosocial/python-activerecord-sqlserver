# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/cache/test_cache.py
"""
Bridge file for relation cache tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.cache.test_cache import *  # noqa: F403
except ImportError:
    pytest.skip("relation cache tests testsuite not available", allow_module_level=True)
