import os
import sys
import logging
from typing import Type, List, Tuple

from rhosocial.activerecord.model import ActiveRecord

logger = logging.getLogger(__name__)

from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.query.fixtures.models import (
    User as UserBase, JsonUser as JsonUserBase,
    Order as OrderBase, OrderItem as OrderItemBase,
    Post as PostBase, Comment as CommentBase,
    MappedUser as MappedUserBase, MappedPost as MappedPostBase, MappedComment as MappedCommentBase
)
from rhosocial.activerecord.testsuite.feature.query.fixtures.cte_models import Node
from rhosocial.activerecord.testsuite.feature.query.fixtures.extended_models import ExtendedOrder, ExtendedOrderItem

User310 = JsonUser310 = Order310 = OrderItem310 = Post310 = Comment310 = None
MappedUser310 = MappedPost310 = MappedComment310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models_py310 import (
            User as User310, JsonUser as JsonUser310,
            Order as Order310, OrderItem as OrderItem310,
            Post as Post310, Comment as Comment310,
            MappedUser as MappedUser310, MappedPost as MappedPost310, MappedComment as MappedComment310
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.10+ fixtures: {e}")

User311 = JsonUser311 = Order311 = OrderItem311 = Post311 = Comment311 = None
MappedUser311 = MappedPost311 = MappedComment311 = None

if sys.version_info >= (3, 11):
    try:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models_py311 import (
            User as User311, JsonUser as JsonUser311,
            Order as Order311, OrderItem as OrderItem311,
            Post as Post311, Comment as Comment311,
            MappedUser as MappedUser311, MappedPost as MappedPost311, MappedComment as MappedComment311
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.11+ fixtures: {e}")

User312 = JsonUser312 = Order312 = OrderItem312 = Post312 = Comment312 = None
MappedUser312 = MappedPost312 = MappedComment312 = None

if sys.version_info >= (3, 12):
    try:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models_py312 import (
            User as User312, JsonUser as JsonUser312,
            Order as Order312, OrderItem as OrderItem312,
            Post as Post312, Comment as Comment312,
            MappedUser as MappedUser312, MappedPost as MappedPost312, MappedComment as MappedComment312
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.12+ fixtures: {e}")


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, model_name: str) -> Type:
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    selected = select_fixture(*candidates)
    logger.info(f"Selected {model_name}: {selected.__name__} from {selected.__module__}")
    return selected


User = _select_model_class(UserBase, User312, User311, User310, "User")
JsonUser = _select_model_class(JsonUserBase, JsonUser312, JsonUser311, JsonUser310, "JsonUser")
Order = _select_model_class(OrderBase, Order312, Order311, Order310, "Order")
OrderItem = _select_model_class(OrderItemBase, OrderItem312, OrderItem311, OrderItem310, "OrderItem")
Post = _select_model_class(PostBase, Post312, Post311, Post310, "Post")
Comment = _select_model_class(CommentBase, Comment312, Comment311, Comment310, "Comment")
MappedUser = _select_model_class(MappedUserBase, MappedUser312, MappedUser311, MappedUser310, "MappedUser")
MappedPost = _select_model_class(MappedPostBase, MappedPost312, MappedPost311, MappedPost310, "MappedPost")
MappedComment = _select_model_class(MappedCommentBase, MappedComment312, MappedComment311, MappedComment310, "MappedComment")

from rhosocial.activerecord.testsuite.feature.query.interfaces import IQueryProvider
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol
from .scenarios import get_enabled_scenarios, get_scenario


class QueryProvider(IQueryProvider, WorkerTestProtocol):

    def __init__(self):
        self._active_backends = []

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _setup_model(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)

        backend_instance = model_class.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)

        try:
            expr = DropTableExpression(backend_instance.dialect, table_name, if_exists=True)
            model_class.__backend__.execute(*expr.to_sql())
        except Exception:
            pass

        schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
        model_class.__backend__.execute(schema_sql)

        return model_class

    def _setup_multiple_models(self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        result = []
        for model_class, table_name in model_classes:
            configured_model = self._setup_model(model_class, scenario_name, table_name)
            result.append(configured_model)
        return tuple(result)

    async def _setup_model_async(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression

        _, config = get_scenario(scenario_name)
        await model_class.configure(config, AsyncSQLServerBackend)

        backend_instance = model_class.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)

        try:
            expr = DropTableExpression(backend_instance.dialect, table_name, if_exists=True)
            await model_class.__backend__.execute(*expr.to_sql())
        except Exception:
            pass

        schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
        await model_class.__backend__.execute(schema_sql)

        return model_class

    async def _setup_multiple_models_async(self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        result = []
        for i, (model_class, table_name) in enumerate(model_classes):
            if i == 0:
                configured_model = await self._setup_model_async(model_class, scenario_name, table_name)
            else:
                model_class.__connection_config__ = configured_model.__connection_config__
                model_class.__backend_class__ = type(configured_model.__backend__)
                model_class.__backend__ = configured_model.__backend__
                configured_model = await self._setup_model_async(model_class, scenario_name, table_name)
            result.append(configured_model)
        return tuple(result)

    def setup_order_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (User, "users"),
            (Order, "orders"),
            (OrderItem, "order_items")
        ], scenario_name)

    def setup_blog_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (User, "users"),
            (Post, "posts"),
            (Comment, "comments")
        ], scenario_name)

    def setup_json_user_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        import pytest
        backend_class, config = get_scenario(scenario_name)
        JsonUser.configure(config, backend_class)
        backend_instance = JsonUser.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)
        if not backend_instance.dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by SQL Server version {backend_instance.get_server_version()}")
        json_user_model = self._setup_model(JsonUser, scenario_name, "json_users")
        return (json_user_model,)

    def setup_tree_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        node_model = self._setup_model(Node, scenario_name, "nodes")
        return (node_model,)

    def setup_extended_order_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (User, "users"),
            (ExtendedOrder, "extended_orders"),
            (ExtendedOrderItem, "extended_order_items")
        ], scenario_name)

    def setup_combined_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (User, "users"),
            (Order, "orders"),
            (OrderItem, "order_items"),
            (Post, "posts"),
            (Comment, "comments")
        ], scenario_name)

    def setup_annotated_query_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.annotated_adapter_models import SearchableItem
        return self._setup_multiple_models([
            (SearchableItem, "searchable_items"),
        ], scenario_name)

    def setup_mapped_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (MappedUser, "users"),
            (MappedPost, "posts"),
            (MappedComment, "comments")
        ], scenario_name)

    async def setup_async_order_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import AsyncUser, AsyncOrder, AsyncOrderItem
        return await self._setup_multiple_models_async([
            (AsyncUser, "users"),
            (AsyncOrder, "orders"),
            (AsyncOrderItem, "order_items")
        ], scenario_name)

    async def setup_async_blog_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_blog_models import AsyncUser, AsyncPost, AsyncComment
        return await self._setup_multiple_models_async([
            (AsyncUser, "users"),
            (AsyncPost, "posts"),
            (AsyncComment, "comments")
        ], scenario_name)

    async def setup_async_json_user_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        import pytest
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_json_models import AsyncJsonUser
        backend_class, config = get_scenario(scenario_name)
        await AsyncJsonUser.configure(config, backend_class)
        backend_instance = AsyncJsonUser.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)
        if not backend_instance.dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by SQL Server version {backend_instance.get_server_version()}")
        json_user_model = await self._setup_model_async(AsyncJsonUser, scenario_name, "json_users")
        return (json_user_model,)

    async def setup_async_tree_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_cte_models import AsyncNode
        node_model = await self._setup_model_async(AsyncNode, scenario_name, "nodes")
        return (node_model,)

    async def setup_async_extended_order_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_extended_models import AsyncUser, AsyncExtendedOrder, AsyncExtendedOrderItem
        return await self._setup_multiple_models_async([
            (AsyncUser, "users"),
            (AsyncExtendedOrder, "extended_orders"),
            (AsyncExtendedOrderItem, "extended_order_items")
        ], scenario_name)

    async def setup_async_combined_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import AsyncUser, AsyncOrder, AsyncOrderItem
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_blog_models import AsyncPost, AsyncComment
        return await self._setup_multiple_models_async([
            (AsyncUser, "users"),
            (AsyncOrder, "orders"),
            (AsyncOrderItem, "order_items"),
            (AsyncPost, "posts"),
            (AsyncComment, "comments")
        ], scenario_name)

    async def setup_async_annotated_query_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_annotated_adapter_models import AsyncSearchableItem
        return await self._setup_multiple_models_async([
            (AsyncSearchableItem, "searchable_items"),
        ], scenario_name)

    async def setup_async_mapped_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_mapped_models import AsyncMappedUser, AsyncMappedPost, AsyncMappedComment
        return await self._setup_multiple_models_async([
            (AsyncMappedUser, "users"),
            (AsyncMappedPost, "posts"),
            (AsyncMappedComment, "comments")
        ], scenario_name)

    async def cleanup_after_test_async(self, scenario_name: str) -> None:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression

        for backend_instance in self._active_backends:
            is_async = isinstance(backend_instance, AsyncSQLServerBackend)
            if not is_async:
                continue
            try:
                for table_name in ['comments', 'order_items', 'posts', 'orders', 'users', 'json_users', 'nodes', 'extended_order_items', 'extended_orders', 'searchable_items']:
                    try:
                        expr = DropTableExpression(backend_instance.dialect, table_name, if_exists=True)
                        await backend_instance.execute(*expr.to_sql())
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                try:
                    await backend_instance.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "query", "schema")
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, 'r', encoding='utf-8') as f:
            return f.read()

    def cleanup_after_test(self, scenario_name: str):
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        for backend_instance in self._active_backends:
            try:
                for table_name in ['comments', 'order_items', 'posts', 'orders', 'users', 'json_users', 'nodes', 'extended_order_items', 'extended_orders', 'searchable_items']:
                    try:
                        expr = DropTableExpression(backend_instance.dialect, table_name, if_exists=True)
                        backend_instance.execute(*expr.to_sql())
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                try:
                    backend_instance.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()

    def get_worker_connection_params(self, scenario_name: str, fixture_type: str = 'order') -> dict:
        from .scenarios import SCENARIO_MAP

        is_async = fixture_type and fixture_type.startswith('async_')
        backend_class_name = 'AsyncSQLServerBackend' if is_async else 'SQLServerBackend'

        base_fixture_type = fixture_type.replace('async_', '') if fixture_type else 'order'

        schema_sql = self._get_schema_sql_for_fixture_type(base_fixture_type)

        if scenario_name not in SCENARIO_MAP:
            if SCENARIO_MAP:
                scenario_name = next(iter(SCENARIO_MAP))
            else:
                raise ValueError("No scenarios registered")

        config_dict = SCENARIO_MAP[scenario_name]

        return {
            'backend_module': 'rhosocial.activerecord.backend.impl.sqlserver',
            'backend_class_name': backend_class_name,
            'config_class_module': 'rhosocial.activerecord.backend.impl.sqlserver.config',
            'config_class_name': 'SQLServerConnectionConfig',
            'config_kwargs': config_dict,
            'schema_sql': schema_sql,
        }

    def get_worker_schema_sql(self, scenario_name: str, table_name: str) -> str:
        return self._load_sqlserver_schema(f'{table_name}.sql')

    def _get_schema_sql_for_fixture_type(self, fixture_type: str) -> dict:
        schemas = {}
        if fixture_type == 'order':
            tables = ['users', 'orders', 'order_items']
        elif fixture_type == 'blog':
            tables = ['users', 'posts', 'comments']
        elif fixture_type == 'user':
            tables = ['users']
        elif fixture_type == 'combined':
            tables = ['users', 'orders', 'order_items', 'posts', 'comments']
        else:
            tables = ['users']
        for table in tables:
            schemas[table] = self._load_sqlserver_schema(f'{table}.sql')
        return schemas
