# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_logging_data_summarization.py
"""
Bridge file for logging data summarization tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""
from rhosocial.activerecord.testsuite.feature.query.test_logging_data_summarization import *
from rhosocial.activerecord.testsuite.feature.query.test_logging_data_summarization_async import *  # noqa: F403

