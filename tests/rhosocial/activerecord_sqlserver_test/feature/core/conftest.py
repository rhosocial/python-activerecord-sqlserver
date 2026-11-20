# tests/rhosocial/activerecord_sqlserver_test/feature/core/conftest.py
"""Use the stubs declared for the feature area.

The protocol/function decorator smoke tests moved out of ``feature/`` because
that directory also holds every feature subdirectory: a directory carries
either test files or subdirectories, never both.
"""

from rhosocial.activerecord_sqlserver_test.feature.conftest import *  # noqa: F401,F403
