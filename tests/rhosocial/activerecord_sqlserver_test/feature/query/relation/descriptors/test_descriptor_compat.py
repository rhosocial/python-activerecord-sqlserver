# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/descriptors/test_descriptor_compat.py
"""
Bridge file for relation descriptor compatibility tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.descriptors.test_descriptor_compat import *  # noqa: F403
except ImportError:
    pytest.skip("relation descriptor compatibility tests testsuite not available", allow_module_level=True)
