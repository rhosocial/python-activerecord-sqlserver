# tests/rhosocial/activerecord_sqlserver_test/feature/basic/ddl/conftest.py
"""
Pytest configuration for the basic/ddl ALTER TABLE tests.

This file imports fixtures from the corresponding testsuite subtopic, making
them (and the ``requires_protocol`` protocol-check autouse fixture) available
to the tests in this directory.
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.conftest import *  # noqa: F403
