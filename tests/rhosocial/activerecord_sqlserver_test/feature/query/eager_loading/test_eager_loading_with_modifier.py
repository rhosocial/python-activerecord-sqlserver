# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_eager_loading_with_modifier.py
"""
Bridge file for eager loading with_modifier tests from the testsuite.

Includes:
- Basic modifier tests (filter, order, noop)
- Backward-compatibility tests (eager == lazy)
- for_update + with_ tests (SQLServer supports LockingSupport)
"""
from rhosocial.activerecord.testsuite.feature.query.eager_loading.test_eager_loading_with_modifier import *  # noqa: F401, F403
from rhosocial.activerecord.testsuite.feature.query.eager_loading.test_eager_loading_with_modifier_async import *  # noqa: F403

