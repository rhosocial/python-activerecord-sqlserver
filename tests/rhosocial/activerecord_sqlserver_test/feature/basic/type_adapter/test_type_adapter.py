# tests/rhosocial/activerecord_sqlserver_test/feature/basic/test_type_adapter.py
"""
This is a "bridge" file for the basic features test group, specifically for
type adapter tests.

Its purpose is to import the generic tests from the `rhosocial-activerecord-testsuite`
package and make them discoverable by `pytest` within this project's test run.
"""

# Import the fixture that provides the configured model and backend for type adapter tests.

# Import all tests from the generic testsuite file.
from rhosocial.activerecord.testsuite.feature.basic.type_adapter.test_type_adapter import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.basic.type_adapter.test_type_adapter_async import *  # noqa: F403

