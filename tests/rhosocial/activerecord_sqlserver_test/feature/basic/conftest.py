# tests/rhosocial/activerecord_sqlserver_test/feature/basic/conftest.py
"""Fixtures shared by the ``basic`` subtopics.

The testsuite defines one fixture per model here, and every ``basic``
subdirectory imports its own minimal test set from below.  This file only re
exports the model fixtures, so the subdirectories can request them by name.
"""

from rhosocial.activerecord.testsuite.feature.basic.conftest import *  # noqa: F401,F403
