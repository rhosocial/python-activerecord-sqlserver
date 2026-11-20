# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/validation/test_path_validation.py
"""
Bridge file for relation path validation tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.validation.test_path_validation import *  # noqa: F403
except ImportError:
    pytest.skip("relation path validation tests testsuite not available", allow_module_level=True)
