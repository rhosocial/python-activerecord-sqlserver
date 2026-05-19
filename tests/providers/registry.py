from rhosocial.activerecord.testsuite.core.registry import ProviderRegistry
from .basic import BasicProvider
from .events import EventsProvider
from .mixins import MixinsProvider
from .query import QueryProvider
from .basic_connection import BasicConnectionProvider
from .query_connection import QueryConnectionProvider

provider_registry = ProviderRegistry()

provider_registry.register("feature.basic.IBasicProvider", BasicProvider)
provider_registry.register("feature.events.IEventsProvider", EventsProvider)
provider_registry.register("feature.mixins.IMixinsProvider", MixinsProvider)
provider_registry.register("feature.query.IQueryProvider", QueryProvider)
provider_registry.register("feature.basic.connection.IBasicConnectionProvider", BasicConnectionProvider)
provider_registry.register("feature.query.connection.IQueryConnectionProvider", QueryConnectionProvider)
