# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/descriptors/test_descriptors_async.py
"""
Bridge file for async relation descriptor tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.descriptors.test_descriptors_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation descriptor tests testsuite not available", allow_module_level=True)
