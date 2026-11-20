# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/modifiers/test_modifier_behavior.py
"""
Bridge file for relation modifier behavior tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.modifiers.test_modifier_behavior import *  # noqa: F403
except ImportError:
    pytest.skip("relation modifier behavior tests testsuite not available", allow_module_level=True)
