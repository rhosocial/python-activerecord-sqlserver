# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/modifiers/test_modifier_warning_async.py
"""
Bridge file for async relation modifier warning tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.modifiers.test_modifier_warning_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation modifier warning tests testsuite not available", allow_module_level=True)
