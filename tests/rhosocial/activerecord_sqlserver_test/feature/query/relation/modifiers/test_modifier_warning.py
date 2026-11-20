# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/modifiers/test_modifier_warning.py
"""
Bridge file for relation modifier warning tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.modifiers.test_modifier_warning import *  # noqa: F403
except ImportError:
    pytest.skip("relation modifier warning tests testsuite not available", allow_module_level=True)
