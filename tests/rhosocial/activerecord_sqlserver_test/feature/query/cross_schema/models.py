# tests/rhosocial/activerecord_sqlserver_test/feature/query/cross_schema/models.py
"""activerecord_sqlserver local models for cross-schema tests.

Schema qualification is dialect-specific, so these live in this repository
rather than the shared testsuite. Each backend owns its fixtures and cases:
qualification syntax, whether a column reference may carry a namespace at
all, and how a namespace is created all differ between PostgreSQL, SQL
Server, Oracle, MariaDB (schema == database), BigQuery (dataset) and
Snowflake (three-level). A shared contract would assert the lowest common
denominator and stop catching the dialect-specific mistakes.
"""

from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
    AsyncOrder,
)
from rhosocial.activerecord.testsuite.feature.query.fixtures.models import Order

# Non-default namespace provisioned by this repository's provider.
SCHEMA_A = "ar_crm"


class MixedSchemaOrder(Order):
    """The ``orders`` fixture, relocated into a non-default namespace.

    The provider provisions the same table shape in both namespaces, so only
    ``__schema_name__`` differs from the default-schema ``Order``.
    """

    __schema_name__ = SCHEMA_A


class AsyncMixedSchemaOrder(AsyncOrder):
    """Async variant of :class:`MixedSchemaOrder`."""

    __schema_name__ = SCHEMA_A
