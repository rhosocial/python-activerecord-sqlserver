# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/validation/test_validator.py
"""
Bridge file for relation validator tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.validation.test_validator import *  # noqa: F403
except ImportError:
    pytest.skip("relation validator tests testsuite not available", allow_module_level=True)
