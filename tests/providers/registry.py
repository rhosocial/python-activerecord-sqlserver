# tests/providers/registry.py
"""
Test Provider Registry

This module registers concrete implementations of test suite interfaces.
The registry system allows the test suite to be decoupled from specific
backend implementations, enabling the same tests to run against different
database backends.
"""

from rhosocial.activerecord.testsuite.core.registry import ProviderRegistry
from .basic import BasicSyncProvider, BasicAsyncProvider
from .events import EventsSyncProvider, EventsAsyncProvider
from .mixins import MixinsSyncProvider, MixinsAsyncProvider
from .query import QuerySyncProvider, QueryAsyncProvider
from .relation import RelationSyncProvider, RelationAsyncProvider
from .basic_connection import BasicConnectionProvider
from .query_connection import QueryConnectionProvider

# Importing the pooling module registers the SQL Server-specific pool reset
# handler (a side effect of the import), mirroring MySQL's tests/providers/pooling.py.
from . import pooling  # noqa: F401

provider_registry = ProviderRegistry()

provider_registry.register("feature.basic.IBasicProvider", BasicSyncProvider)
provider_registry.register("feature.basic.IBasicSyncProvider", BasicSyncProvider)
provider_registry.register("feature.basic.IBasicAsyncProvider", BasicAsyncProvider)

provider_registry.register("feature.events.IEventsProvider", EventsSyncProvider)
provider_registry.register("feature.events.IEventsSyncProvider", EventsSyncProvider)
provider_registry.register("feature.events.IEventsAsyncProvider", EventsAsyncProvider)

provider_registry.register("feature.mixins.IMixinsProvider", MixinsSyncProvider)
provider_registry.register("feature.mixins.IMixinsSyncProvider", MixinsSyncProvider)
provider_registry.register("feature.mixins.IMixinsAsyncProvider", MixinsAsyncProvider)

provider_registry.register("feature.query.IQueryProvider", QuerySyncProvider)
provider_registry.register("feature.query.IQuerySyncProvider", QuerySyncProvider)
provider_registry.register("feature.query.IQueryAsyncProvider", QueryAsyncProvider)

provider_registry.register("feature.relation.IRelationProvider", RelationSyncProvider)
provider_registry.register("feature.relation.IRelationSyncProvider", RelationSyncProvider)
provider_registry.register("feature.relation.IRelationAsyncProvider", RelationAsyncProvider)

provider_registry.register(
    "feature.basic.connection.IBasicConnectionProvider", BasicConnectionProvider
)
provider_registry.register(
    "feature.query.connection.IQueryConnectionProvider", QueryConnectionProvider
)
