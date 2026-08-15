# tests/rhosocial/activerecord_sqlserver_test/feature/basic/test_fields.py
"""
This is a "bridge" file that connects the generic tests defined in the
`python-activerecord-testsuite` package with the concrete backend
implementation of this project.

IMPORTANT:
- DO NOT add any test logic to this file.
- Its only purpose is to import the generic tests and the fixtures required
  to run them against this specific backend.
"""

# 1. Import the fixtures from the testsuite's conftest.
#    This makes the fixtures defined in the testsuite available to the tests
#    when they are run in the context of this backend project.

# 2. Import all test classes and functions from the generic test file.
#    This pulls in the actual test logic that will be executed.
from rhosocial.activerecord.testsuite.feature.basic.fields.test_fields import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.basic.fields.test_fields_async import *  # noqa: F403

