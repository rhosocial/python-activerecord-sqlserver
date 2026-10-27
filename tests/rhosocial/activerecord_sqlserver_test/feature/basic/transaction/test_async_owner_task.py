# tests/rhosocial/activerecord_sqlserver_test/feature/basic/transaction/test_async_owner_task.py
"""
Async contract for AsyncTransactionManager._owner_task (SQL Server backend).

Imports the shared tests: a second asyncio task entering ``transaction()``
while another task owns an active outermost transaction is refused with
``TransactionError``, and ownership is released when the outermost one ends.
"""

from rhosocial.activerecord.testsuite.feature.basic.transaction.test_async_owner_task import *  # noqa: F403
