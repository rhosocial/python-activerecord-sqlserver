# tests/rhosocial/activerecord_sqlserver_test/feature/query/relation/derived/test_relation_derived_field_json_async.py
"""
Bridge file for async relation derived-field JSON tests from the testsuite.
"""
import pytest
try:
    from rhosocial.activerecord.testsuite.feature.query.relation.derived.test_relation_derived_field_json_async import *  # noqa: F403
except ImportError:
    pytest.skip("async relation derived-field JSON tests testsuite not available", allow_module_level=True)
