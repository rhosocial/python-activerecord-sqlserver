# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/descriptors/test_descriptors.py
"""
Bridge file for relation descriptor tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.descriptors.test_descriptors import *  # noqa: F403
except ImportError:
    pytest.skip("relation descriptor tests testsuite not available", allow_module_level=True)
