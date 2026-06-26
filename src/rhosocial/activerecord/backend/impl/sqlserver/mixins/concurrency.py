# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/concurrency.py
"""SQL Server concurrency hint mixin."""

import logging
from typing import Optional

from rhosocial.activerecord.backend.protocols import ConcurrencyHint


class SQLServerConcurrencyMixin:
    _concurrency_hint: Optional[ConcurrencyHint] = None

    def connect(self):
        super().connect()
        self._fetch_concurrency_hint()

    def _fetch_concurrency_hint(self) -> None:
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT value_in_use FROM sys.configurations WHERE name = 'max worker threads'"
            )
            row = cursor.fetchone()
            cursor.close()

            if row:
                max_threads = int(row[0])
                pool_size = getattr(self.config, "pool_size", 5) or 5
                limit = min(max_threads, pool_size)
                self._concurrency_hint = ConcurrencyHint(
                    max_concurrency=limit,
                    reason=f"min(max_worker_threads={max_threads}, pool_size={pool_size})",
                )
                self.log(logging.DEBUG, f"Concurrency hint: max_concurrency={limit}")
        except Exception as e:
            self.log(logging.WARNING, f"Failed to fetch concurrency hint: {e}")
            self._concurrency_hint = None

    def get_concurrency_hint(self) -> Optional[ConcurrencyHint]:
        return self._concurrency_hint