# tests/providers/query.py
"""
Concrete implementations of `IQuerySyncProvider` and `IQueryAsyncProvider`
for the SQL Server backend.
"""

import os
import sys
import logging
from typing import Type, List, Tuple

from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord

logger = logging.getLogger(__name__)

from rhosocial.activerecord.testsuite.utils import select_fixture  # noqa: E402

from rhosocial.activerecord.testsuite.feature.query.fixtures.models import (  # noqa: E402
    User as UserBase,
    JsonUser as JsonUserBase,
    Order as OrderBase,
    OrderItem as OrderItemBase,
    Post as PostBase,
    Comment as CommentBase,
    MappedUser as MappedUserBase,
    MappedPost as MappedPostBase,
    MappedComment as MappedCommentBase,
)
from rhosocial.activerecord.testsuite.feature.query.fixtures.cte_models import Node  # noqa: E402
from rhosocial.activerecord.testsuite.feature.query.fixtures.extended_models import (  # noqa: E402
    ExtendedOrder,
    ExtendedOrderItem,
)

User310 = JsonUser310 = Order310 = OrderItem310 = Post310 = Comment310 = None
MappedUser310 = MappedPost310 = MappedComment310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models_py310 import (
            User as User310,
            JsonUser as JsonUser310,
            Order as Order310,
            OrderItem as OrderItem310,
            Post as Post310,
            Comment as Comment310,
            MappedUser as MappedUser310,
            MappedPost as MappedPost310,
            MappedComment as MappedComment310,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.10+ fixtures: {e}")

User311 = JsonUser311 = Order311 = OrderItem311 = Post311 = Comment311 = None
MappedUser311 = MappedPost311 = MappedComment311 = None

if sys.version_info >= (3, 11):
    try:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models_py311 import (
            User as User311,
            JsonUser as JsonUser311,
            Order as Order311,
            OrderItem as OrderItem311,
            Post as Post311,
            Comment as Comment311,
            MappedUser as MappedUser311,
            MappedPost as MappedPost311,
            MappedComment as MappedComment311,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.11+ fixtures: {e}")

User312 = JsonUser312 = Order312 = OrderItem312 = Post312 = Comment312 = None
MappedUser312 = MappedPost312 = MappedComment312 = None

if sys.version_info >= (3, 12):
    try:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models_py312 import (
            User as User312,
            JsonUser as JsonUser312,
            Order as Order312,
            OrderItem as OrderItem312,
            Post as Post312,
            Comment as Comment312,
            MappedUser as MappedUser312,
            MappedPost as MappedPost312,
            MappedComment as MappedComment312,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.12+ fixtures: {e}")


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, model_name: str) -> Type:
    """Select the most appropriate model class for the current Python version."""
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
MappedComment = _select_model_class(
    MappedCommentBase, MappedComment312, MappedComment311, MappedComment310, "MappedComment"
)

from rhosocial.activerecord.testsuite.feature.query.interfaces import IQuerySyncProvider, IQueryAsyncProvider  # noqa: E402
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol  # noqa: E402

from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (  # noqa: E402
    OrderItem as CompositeOrderItemBase,
    AsyncOrderItem as AsyncCompositeOrderItemBase,
)

from .scenarios import get_enabled_scenarios, get_scenario  # noqa: E402

from providers.fixtures._common import (
    safe_drop_table, safe_drop_table_async,
    disable_fk_checks, enable_fk_checks,
    disable_fk_checks_async, enable_fk_checks_async,
)

class QueryProviderBase:
    def __init__(self):
        self._scenario_db_files = {}
        self._schema_fixtures_provisioned = False

    @staticmethod
    def _ddl_options():
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        return ExecutionOptions(stmt_type=StatementType.DDL)

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _cross_schema_statements(self) -> List[str]:
        """Provision SCHEMA_A / SCHEMA_B with their tables (T-SQL)."""
        return [
            "IF OBJECT_ID('ar_crm.customers', 'U') IS NOT NULL DROP TABLE ar_crm.customers",
            "IF SCHEMA_ID('ar_crm') IS NOT NULL DROP SCHEMA ar_crm",
            "CREATE SCHEMA ar_crm",
            "IF OBJECT_ID('ar_shop.orders', 'U') IS NOT NULL DROP TABLE ar_shop.orders",
            "IF SCHEMA_ID('ar_shop') IS NOT NULL DROP SCHEMA ar_shop",
            "CREATE SCHEMA ar_shop",
            "CREATE TABLE ar_crm.customers ("
            "id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(100) NOT NULL)",
            "CREATE TABLE ar_shop.orders ("
            "id INT IDENTITY(1,1) PRIMARY KEY, customer_id INT NOT NULL, amount INT NOT NULL)",
        ]

    def _drop_cross_schema_schemas_sync(self, backend_instance) -> None:
        for sql in (
            "IF OBJECT_ID('ar_crm.customers', 'U') IS NOT NULL DROP TABLE ar_crm.customers",
            "IF OBJECT_ID('ar_shop.orders', 'U') IS NOT NULL DROP TABLE ar_shop.orders",
            "IF SCHEMA_ID('ar_crm') IS NOT NULL DROP SCHEMA ar_crm",
            "IF SCHEMA_ID('ar_shop') IS NOT NULL DROP SCHEMA ar_shop",
        ):
            try:
                backend_instance.execute(sql, options=self._ddl_options())
            except Exception:
                pass
        self._schema_fixtures_provisioned = False

    async def _drop_cross_schema_schemas_async(self, backend_instance) -> None:
        for sql in (
            "IF OBJECT_ID('ar_crm.customers', 'U') IS NOT NULL DROP TABLE ar_crm.customers",
            "IF OBJECT_ID('ar_shop.orders', 'U') IS NOT NULL DROP TABLE ar_shop.orders",
            "IF SCHEMA_ID('ar_crm') IS NOT NULL DROP SCHEMA ar_crm",
            "IF SCHEMA_ID('ar_shop') IS NOT NULL DROP SCHEMA ar_shop",
        ):
            try:
                await backend_instance.execute(sql, options=self._ddl_options())
            except Exception:
                pass
        self._schema_fixtures_provisioned = False

    def _provision_cross_schema_sync(self, backend_instance) -> None:
        options = self._ddl_options()
        for sql in self._cross_schema_statements():
            backend_instance.execute(sql, options=options)
        self._schema_fixtures_provisioned = True

    async def _provision_cross_schema_async(self, backend_instance) -> None:
        options = self._ddl_options()
        for sql in self._cross_schema_statements():
            await backend_instance.execute(sql, options=options)
        self._schema_fixtures_provisioned = True

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "query", "schema"
        )
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, "r", encoding="utf-8") as f:
            return f.read()

    _load_mysql_schema = _load_sqlserver_schema


class QuerySyncProvider(QueryProviderBase, IQuerySyncProvider, WorkerTestProtocol):
    def __init__(self):
        super().__init__()
        self._active_backends = []

    def _setup_model(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.query import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend_instance = model_class.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)
        options = ExecutionOptions(stmt_type=StatementType.DDL)
        safe_drop_table(backend_instance, backend_instance.dialect, table_name)
        if fn := TABLE_EXPRESSIONS.get(table_name):
            create_expr = fn(backend_instance.dialect, table_name)
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            backend_instance.execute(create_sql, params, options=options)
        else:
            schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
            backend_instance.execute(schema_sql, options=options)
        return model_class

    def _setup_multiple_models(
        self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str
    ) -> Tuple[Type[ActiveRecord], ...]:
        result = []
        shared_backend = None
        for i, (model_class, table_name) in enumerate(model_classes):
            if i == 0:
                configured_model = self._setup_model(model_class, scenario_name, table_name)
                shared_backend = configured_model.__backend__
            else:
                backend_class, config = get_scenario(scenario_name)
                model_class.__connection_config__ = config
                model_class.__backend_class__ = backend_class
                model_class.__backend__ = shared_backend
                self._reset_schema(shared_backend, table_name)
                configured_model = model_class
            result.append(configured_model)
        return tuple(result)

    def _reset_schema(self, backend_instance, table_name: str) -> None:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.query import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        options = ExecutionOptions(stmt_type=StatementType.DDL)
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)
        safe_drop_table(backend_instance, backend_instance.dialect, table_name)
        if fn := TABLE_EXPRESSIONS.get(table_name):
            create_expr = fn(backend_instance.dialect, table_name)
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            backend_instance.execute(create_sql, params, options=options)
        else:
            schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
            backend_instance.execute(schema_sql, options=options)

    def setup_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models(
            [(User, "users"), (Order, "orders"), (OrderItem, "order_items")], scenario_name
        )

    def setup_blog_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([(User, "users"), (Post, "posts"), (Comment, "comments")], scenario_name)

    def setup_json_user_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        import pytest
        backend_class, config = get_scenario(scenario_name)
        JsonUser.configure(config, backend_class)
        backend_instance = JsonUser.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)
        if not backend_instance.dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by SQLServer version {backend_instance.get_server_version()}")
        json_user_model = self._setup_model(JsonUser, scenario_name, "json_users")
        return (json_user_model,)

    def setup_tree_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        node_model = self._setup_model(Node, scenario_name, "nodes")
        return (node_model,)

    def setup_extended_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models(
            [(User, "users"), (ExtendedOrder, "extended_orders"), (ExtendedOrderItem, "extended_order_items")],
            scenario_name,
        )

    def setup_combined_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models(
            [(User, "users"), (Order, "orders"), (OrderItem, "order_items"), (Post, "posts"), (Comment, "comments")],
            scenario_name,
        )

    def setup_annotated_query_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.annotated_adapter_models import SearchableItem
        return self._setup_multiple_models(
            [(SearchableItem, "searchable_items")],
            scenario_name,
        )

    def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models(
            [(MappedUser, "users"), (MappedPost, "posts"), (MappedComment, "comments")], scenario_name
        )

    def setup_profile_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord]]:
        Profile = User.get_relation('profile').get_related_model(User)
        return self._setup_multiple_models([(User, "users"), (Profile, "profiles")], scenario_name)

    def setup_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.basic import TABLE_EXPRESSIONS as BASIC_EXPRS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        backend_class, config = get_scenario(scenario_name)
        CompositeOrderItemBase.configure(config, backend_class)
        backend_instance = CompositeOrderItemBase.__backend__
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)
        options = ExecutionOptions(stmt_type=StatementType.DDL)
        safe_drop_table(backend_instance, backend_instance.dialect, "order_items")
        if fn := BASIC_EXPRS.get("order_items"):
            create_expr = fn(backend_instance.dialect, "order_items")
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            backend_instance.execute(create_sql, params, options=options)
        return CompositeOrderItemBase

    def setup_schema_fixtures(self, scenario_name: str):
        """Two models in two distinct schemas (see testsuite schema_models)."""
        from rhosocial.activerecord.testsuite.feature.query.fixtures.schema_models import (
            SchemaCustomer,
            SchemaOrder,
        )

        backend_class, config = get_scenario(scenario_name)
        SchemaCustomer.configure(config, backend_class)
        SchemaOrder.configure(config, backend_class)
        shared_backend = SchemaCustomer.__backend__
        if shared_backend not in self._active_backends:
            self._active_backends.append(shared_backend)
        self._provision_cross_schema_sync(shared_backend)
        return SchemaCustomer, SchemaOrder

    def cleanup_after_test(self, scenario_name: str):
        for backend_instance in self._active_backends:
            for table_name in [
                "users",
                "orders",
                "order_items",
                "posts",
                "comments",
                "json_users",
                "nodes",
                "extended_orders",
                "extended_order_items",
                "searchable_items",
                "profiles",
            ]:
                try:
                    safe_drop_table(backend_instance, backend_instance.dialect, table_name)
                except Exception:
                    pass
            if self._schema_fixtures_provisioned:
                try:
                    self._drop_cross_schema_schemas_sync(backend_instance)
                except Exception:
                    pass
            try:
                backend_instance.disconnect()
            except Exception:
                pass
        self._active_backends.clear()

    def get_worker_connection_params(self, scenario_name: str, fixture_type: str = "order") -> dict:
        from .scenarios import SCENARIO_MAP
        is_async = fixture_type and fixture_type.startswith("async_")
        backend_class_name = "AsyncSQLServerBackend" if is_async else "SQLServerBackend"
        base_fixture_type = fixture_type.replace("async_", "") if fixture_type else "order"
        schema_sql = self._get_schema_sql_for_fixture_type(base_fixture_type)
        if scenario_name not in SCENARIO_MAP:
            if SCENARIO_MAP:
                scenario_name = next(iter(SCENARIO_MAP))
            else:
                raise ValueError("No scenarios registered")
        config_dict = SCENARIO_MAP[scenario_name]
        from providers.pooling import resolve_database_name
        pooled_db = resolve_database_name(scenario_name)
        if pooled_db:
            config_dict = {**config_dict, "database": pooled_db}
        return {
            "backend_module": "rhosocial.activerecord.backend.impl.sqlserver",
            "backend_class_name": backend_class_name,
            "config_class_module": "rhosocial.activerecord.backend.impl.sqlserver.config",
            "config_class_name": "SQLServerConnectionConfig",
            "config_kwargs": config_dict,
            "schema_sql": schema_sql,
        }

    def get_worker_schema_sql(self, scenario_name: str, table_name: str) -> str:
        from providers.fixtures.query import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        if fn := TABLE_EXPRESSIONS.get(table_name):
            dialect = SQLServerDialect()
            sql, _ = to_sqlserver_ddl_sql(fn(dialect, table_name))
            return sql
        return self._load_sqlserver_schema(f"{table_name}.sql")

    def _get_schema_sql_for_fixture_type(self, fixture_type: str) -> dict:
        from providers.fixtures.query import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        if fixture_type == "order":
            tables = ["users", "orders", "order_items"]
        elif fixture_type == "blog":
            tables = ["users", "posts", "comments"]
        elif fixture_type == "user":
            tables = ["users"]
        elif fixture_type == "combined":
            tables = ["users", "orders", "order_items", "posts", "comments"]
        else:
            tables = ["users"]
        schemas = {}
        dialect = SQLServerDialect()
        for table in tables:
            if fn := TABLE_EXPRESSIONS.get(table):
                sql, _ = to_sqlserver_ddl_sql(fn(dialect, table))
                schemas[table] = sql
            else:
                schemas[table] = self._load_sqlserver_schema(f"{table}.sql")
        return schemas


class QueryAsyncProvider(QueryProviderBase, IQueryAsyncProvider):
    def __init__(self):
        super().__init__()
        self._active_async_backends = []

    async def _setup_model_async(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str, shared_backend=None
    ) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.query import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        _, config = get_scenario(scenario_name)
        if shared_backend is None:
            await model_class.configure(config, AsyncSQLServerBackend)
        else:
            model_class.__connection_config__ = config
            model_class.__backend_class__ = AsyncSQLServerBackend
            model_class.__backend__ = shared_backend
        backend_instance = model_class.__backend__
        if backend_instance not in self._active_async_backends:
            self._active_async_backends.append(backend_instance)
        options = ExecutionOptions(stmt_type=StatementType.DDL)
        await safe_drop_table_async(backend_instance, backend_instance.dialect, table_name)
        if fn := TABLE_EXPRESSIONS.get(table_name):
            create_expr = fn(backend_instance.dialect, table_name)
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            await backend_instance.execute(create_sql, params, options=options)
        else:
            schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
            await backend_instance.execute(schema_sql, options=options)
        return model_class

    async def _setup_multiple_models_async(
        self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str
    ) -> Tuple[Type[ActiveRecord], ...]:
        result = []
        shared_backend = None
        for i, (model_class, table_name) in enumerate(model_classes):
            if i == 0:
                configured_model = await self._setup_model_async(model_class, scenario_name, table_name)
                shared_backend = configured_model.__backend__
            else:
                model_class.__connection_config__ = configured_model.__connection_config__
                model_class.__backend_class__ = type(shared_backend)
                model_class.__backend__ = shared_backend
                configured_model = await self._setup_model_async(model_class, scenario_name, table_name, shared_backend)
            result.append(configured_model)
        return tuple(result)

    async def setup_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
            AsyncUser,
            AsyncOrder,
            AsyncOrderItem,
        )
        return await self._setup_multiple_models_async(
            [(AsyncUser, "users"), (AsyncOrder, "orders"), (AsyncOrderItem, "order_items")], scenario_name
        )

    async def setup_blog_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_blog_models import AsyncPost, AsyncComment
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import AsyncUser
        return await self._setup_multiple_models_async(
            [(AsyncUser, "users"), (AsyncPost, "posts"), (AsyncComment, "comments")], scenario_name
        )

    async def setup_json_user_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        import pytest
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_json_models import AsyncJsonUser
        _, config = get_scenario(scenario_name)
        await AsyncJsonUser.configure(config, AsyncSQLServerBackend)
        backend_instance = AsyncJsonUser.__backend__
        if backend_instance not in self._active_async_backends:
            self._active_async_backends.append(backend_instance)
        if not backend_instance.dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by SQLServer version {backend_instance.get_server_version()}")
        json_user_model = await self._setup_model_async(AsyncJsonUser, scenario_name, "json_users")
        return (json_user_model,)

    async def setup_tree_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_cte_models import AsyncNode
        node_model = await self._setup_model_async(AsyncNode, scenario_name, "nodes")
        return (node_model,)

    async def setup_extended_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_extended_models import (
            AsyncUser,
            AsyncExtendedOrder,
            AsyncExtendedOrderItem,
        )
        return await self._setup_multiple_models_async(
            [
                (AsyncUser, "users"),
                (AsyncExtendedOrder, "extended_orders"),
                (AsyncExtendedOrderItem, "extended_order_items"),
            ],
            scenario_name,
        )

    async def setup_combined_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
            AsyncUser,
            AsyncOrder,
            AsyncOrderItem,
        )
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_blog_models import AsyncPost, AsyncComment
        return await self._setup_multiple_models_async(
            [
                (AsyncUser, "users"),
                (AsyncOrder, "orders"),
                (AsyncOrderItem, "order_items"),
                (AsyncPost, "posts"),
                (AsyncComment, "comments"),
            ],
            scenario_name,
        )

    async def setup_annotated_query_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_annotated_adapter_models import (
            AsyncSearchableItem,
        )
        return await self._setup_multiple_models_async(
            [(AsyncSearchableItem, "searchable_items")],
            scenario_name,
        )

    async def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models import (
            AsyncMappedUser,
            AsyncMappedPost,
            AsyncMappedComment,
        )
        return await self._setup_multiple_models_async(
            [(AsyncMappedUser, "users"), (AsyncMappedPost, "posts"), (AsyncMappedComment, "comments")], scenario_name
        )

    async def setup_profile_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[AsyncActiveRecord], Type[AsyncActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
            AsyncUser,
            AsyncProfile,
        )
        return await self._setup_multiple_models_async(
            [(AsyncUser, "users"), (AsyncProfile, "profiles")], scenario_name
        )

    async def setup_order_item_model(self, scenario_name: str) -> Type[AsyncActiveRecord]:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from providers.fixtures.basic import TABLE_EXPRESSIONS as BASIC_EXPRS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        _, config = get_scenario(scenario_name)
        await AsyncCompositeOrderItemBase.configure(config, AsyncSQLServerBackend)
        backend_instance = AsyncCompositeOrderItemBase.__backend__
        if backend_instance not in self._active_async_backends:
            self._active_async_backends.append(backend_instance)
        options = ExecutionOptions(stmt_type=StatementType.DDL)
        await safe_drop_table_async(backend_instance, backend_instance.dialect, "order_items")
        if fn := BASIC_EXPRS.get("order_items"):
            create_expr = fn(backend_instance.dialect, "order_items")
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            await backend_instance.execute(create_sql, params, options=options)
        return AsyncCompositeOrderItemBase

    async def cleanup_after_test(self, scenario_name: str) -> None:
        for backend_instance in self._active_async_backends:
            for table_name in [
                "users",
                "orders",
                "order_items",
                "posts",
                "comments",
                "json_users",
                "nodes",
                "extended_orders",
                "extended_order_items",
                "searchable_items",
                "profiles",
            ]:
                try:
                    await safe_drop_table_async(backend_instance, backend_instance.dialect, table_name)
                except Exception:
                    pass
            if self._schema_fixtures_provisioned:
                try:
                    await self._drop_cross_schema_schemas_async(backend_instance)
                except Exception:
                    pass
            try:
                await backend_instance.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()

    async def setup_schema_fixtures(self, scenario_name: str):
        """Two async models in two distinct schemas."""
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from rhosocial.activerecord.testsuite.feature.query.fixtures.schema_models import (
            AsyncSchemaCustomer,
            AsyncSchemaOrder,
        )

        _, config = get_scenario(scenario_name)
        await AsyncSchemaCustomer.configure(config, AsyncSQLServerBackend)
        AsyncSchemaOrder.__connection_config__ = config
        AsyncSchemaOrder.__backend_class__ = AsyncSQLServerBackend
        AsyncSchemaOrder.__backend__ = AsyncSchemaCustomer.__backend__
        shared_backend = AsyncSchemaCustomer.__backend__
        if shared_backend not in self._active_async_backends:
            self._active_async_backends.append(shared_backend)
        await self._provision_cross_schema_async(shared_backend)
        return AsyncSchemaCustomer, AsyncSchemaOrder
