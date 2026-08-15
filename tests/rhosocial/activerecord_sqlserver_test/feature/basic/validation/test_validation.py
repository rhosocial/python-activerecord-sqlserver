# tests/rhosocial/activerecord_sqlserver_test/feature/basic/test_validation.py
"""
This is a "bridge" file for the basic features test group, specifically for data validation mechanism tests.

Its purpose is to import the generic tests from the `rhosocial-activerecord-testsuite`
package and make them discoverable by `pytest` within this project's test run.

This approach allows us to keep the actual test logic separate and reusable across
different backends, while this file acts as the entry point for running those
tests against our specific (SQLite) backend.
"""

# IMPORTANT: These imports are essential for pytest to work correctly.
# Even though they may be flagged as "unused" by some IDEs or linters,
# they must not be removed. They are the mechanism by which pytest discovers
# the fixtures and the tests from the external testsuite package.

# Although the root conftest.py sets up the environment, explicitly importing
# the fixtures here makes the dependency clear and can help with test discovery
# in some IDEs. These fixtures are defined in the testsuite package and are
# parameterized to run against the scenarios defined in `providers/scenarios.py`.

from rhosocial.activerecord.testsuite.feature.basic.validation.test_validation import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.basic.validation.test_validation_async import *  # noqa: F403

