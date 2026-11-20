# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/derived/test_relation_derived_field.py
"""
Bridge file for relation derived-field tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.derived.test_relation_derived_field import *  # noqa: F403
except ImportError:
    pytest.skip("relation derived-field tests testsuite not available", allow_module_level=True)
