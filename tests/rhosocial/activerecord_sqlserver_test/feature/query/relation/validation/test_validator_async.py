# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/validation/test_validator_async.py
"""
Bridge file for async relation validator tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.validation.test_validator_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation validator tests testsuite not available", allow_module_level=True)
