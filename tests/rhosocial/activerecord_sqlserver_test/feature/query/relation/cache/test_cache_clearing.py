# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/cache/test_cache_clearing.py
"""
Bridge file for relation cache clearing tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.cache.test_cache_clearing import *  # noqa: F403
except ImportError:
    pytest.skip("relation cache clearing tests testsuite not available", allow_module_level=True)
