# tests/providers/basic.py
"""
This file provides concrete implementations of the `IBasicSyncProvider` and
`IBasicAsyncProvider` interfaces defined in the `rhosocial-activerecord-testsuite`
package for the SQL Server backend.

Its main responsibilities are:
1.  Reporting which test scenarios (database configurations) are available.
2.  Setting up the database environment for a given test. This includes:
    -   Getting the correct database configuration for the scenario.
    -   Configuring the ActiveRecord model with a database connection.
    -   Dropping any old tables and creating the necessary table schema.
3.  Cleaning up any resources after a test runs.
"""

import os
import sys
import logging
from typing import Type, List, Tuple, Optional, Set

logger = logging.getLogger(__name__)

from rhosocial.activerecord.backend.type_adapter import BaseSQLTypeAdapter  # noqa: E402
from rhosocial.activerecord.model import ActiveRecord  # noqa: E402

from rhosocial.activerecord.testsuite.utils import select_fixture  # noqa: E402

from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (  # noqa: E402
    User as UserBase,
    TypeCase as TypeCaseBase,
    ValidatedFieldUser as ValidatedFieldUserBase,
    TypeTestModel as TypeTestModelBase,
    ValidatedUser as ValidatedUserBase,
    TypeAdapterTest as TypeAdapterTestBase,
    YesOrNoBooleanAdapter,
    PydanticValidatedModel as PydanticValidatedModelBase,
    MappedUser as MappedUserBase,
    MappedPost as MappedPostBase,
    MappedComment as MappedCommentBase,
    ColumnMappingModel as ColumnMappingModelBase,
    MixedAnnotationModel as MixedAnnotationModelBase,
    BulkUser as BulkUserBase,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (  # noqa: E402
    AsyncBulkUser as AsyncBulkUserBase,
)

from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (  # noqa: E402
    AsyncUser as AsyncUserBase,
    AsyncTypeCase as AsyncTypeCaseBase,
    AsyncValidatedUser as AsyncValidatedUserBase,
    AsyncValidatedFieldUser as AsyncValidatedFieldUserBase,
    AsyncTypeTestModel as AsyncTypeTestModelBase,
    AsyncTypeAdapterTest as AsyncTypeAdapterTestBase,
    AsyncPydanticValidatedModel as AsyncPydanticValidatedModelBase,
    AsyncMappedUser as AsyncMappedUserBase,
    AsyncMappedPost as AsyncMappedPostBase,
    AsyncMappedComment as AsyncMappedCommentBase,
    AsyncColumnMappingModel as AsyncColumnMappingModelBase,
    AsyncMixedAnnotationModel as AsyncMixedAnnotationModelBase,
)

User310 = TypeCase310 = ValidatedFieldUser310 = TypeTestModel310 = ValidatedUser310 = None
TypeAdapterTest310 = PydanticValidatedModel310 = MappedUser310 = MappedPost310 = MappedComment310 = None
ColumnMappingModel310 = MixedAnnotationModel310 = BulkUser310 = None
AsyncUser310 = AsyncTypeCase310 = AsyncValidatedFieldUser310 = AsyncTypeTestModel310 = None
AsyncValidatedUser310 = AsyncTypeAdapterTest310 = AsyncPydanticValidatedModel310 = AsyncMappedUser310 = (
    AsyncMappedPost310
) = None
AsyncMappedComment310 = AsyncColumnMappingModel310 = AsyncMixedAnnotationModel310 = AsyncBulkUser310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py310 import (
            User as User310,
            TypeCase as TypeCase310,
            ValidatedFieldUser as ValidatedFieldUser310,
            TypeTestModel as TypeTestModel310,
            ValidatedUser as ValidatedUser310,
            TypeAdapterTest as TypeAdapterTest310,
            PydanticValidatedModel as PydanticValidatedModel310,
            MappedUser as MappedUser310,
            MappedPost as MappedPost310,
            MappedComment as MappedComment310,
            ColumnMappingModel as ColumnMappingModel310,
            MixedAnnotationModel as MixedAnnotationModel310,
            BulkUser as BulkUser310,
        )
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py310 import (
            AsyncUser as AsyncUser310,
            AsyncTypeCase as AsyncTypeCase310,
            AsyncValidatedUser as AsyncValidatedUser310,
            AsyncValidatedFieldUser as AsyncValidatedFieldUser310,
            AsyncTypeTestModel as AsyncTypeTestModel310,
            AsyncTypeAdapterTest as AsyncTypeAdapterTest310,
            AsyncPydanticValidatedModel as AsyncPydanticValidatedModel310,
            AsyncMappedUser as AsyncMappedUser310,
            AsyncMappedPost as AsyncMappedPost310,
            AsyncMappedComment as AsyncMappedComment310,
            AsyncColumnMappingModel as AsyncColumnMappingModel310,
            AsyncMixedAnnotationModel as AsyncMixedAnnotationModel310,
            AsyncBulkUser as AsyncBulkUser310,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.10+ fixtures: {e}")

User311 = TypeCase311 = ValidatedFieldUser311 = TypeTestModel311 = ValidatedUser311 = None
TypeAdapterTest311 = PydanticValidatedModel311 = MappedUser311 = MappedPost311 = MappedComment311 = None
ColumnMappingModel311 = MixedAnnotationModel311 = BulkUser311 = None
AsyncUser311 = AsyncTypeCase311 = AsyncValidatedFieldUser311 = AsyncTypeTestModel311 = None
AsyncValidatedUser311 = AsyncTypeAdapterTest311 = AsyncPydanticValidatedModel311 = AsyncMappedUser311 = (
    AsyncMappedPost311
) = None
AsyncMappedComment311 = AsyncColumnMappingModel311 = AsyncMixedAnnotationModel311 = AsyncBulkUser311 = None

if sys.version_info >= (3, 11):
    try:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py311 import (
            User as User311,
            TypeCase as TypeCase311,
            ValidatedFieldUser as ValidatedFieldUser311,
            TypeTestModel as TypeTestModel311,
            ValidatedUser as ValidatedUser311,
            TypeAdapterTest as TypeAdapterTest311,
            PydanticValidatedModel as PydanticValidatedModel311,
            MappedUser as MappedUser311,
            MappedPost as MappedPost311,
            MappedComment as MappedComment311,
            ColumnMappingModel as ColumnMappingModel311,
            MixedAnnotationModel as MixedAnnotationModel311,
            BulkUser as BulkUser311,
        )
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py311 import (
            AsyncUser as AsyncUser311,
            AsyncTypeCase as AsyncTypeCase311,
            AsyncValidatedUser as AsyncValidatedUser311,
            AsyncValidatedFieldUser as AsyncValidatedFieldUser311,
            AsyncTypeTestModel as AsyncTypeTestModel311,
            AsyncTypeAdapterTest as AsyncTypeAdapterTest311,
            AsyncPydanticValidatedModel as AsyncPydanticValidatedModel311,
            AsyncMappedUser as AsyncMappedUser311,
            AsyncMappedPost as AsyncMappedPost311,
            AsyncMappedComment as AsyncMappedComment311,
            AsyncColumnMappingModel as AsyncColumnMappingModel311,
            AsyncMixedAnnotationModel as AsyncMixedAnnotationModel311,
            AsyncBulkUser as AsyncBulkUser311,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.11+ fixtures: {e}")

User312 = TypeCase312 = ValidatedFieldUser312 = TypeTestModel312 = ValidatedUser312 = None
TypeAdapterTest312 = PydanticValidatedModel312 = MappedUser312 = MappedPost312 = MappedComment312 = None
ColumnMappingModel312 = MixedAnnotationModel312 = BulkUser312 = None
AsyncUser312 = AsyncTypeCase312 = AsyncValidatedFieldUser312 = AsyncTypeTestModel312 = None
AsyncValidatedUser312 = AsyncTypeAdapterTest312 = AsyncPydanticValidatedModel312 = AsyncMappedUser312 = (
    AsyncMappedPost312
) = None
AsyncMappedComment312 = AsyncColumnMappingModel312 = AsyncMixedAnnotationModel312 = AsyncBulkUser312 = None

if sys.version_info >= (3, 12):
    try:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py312 import (
            User as User312,
            TypeCase as TypeCase312,
            ValidatedFieldUser as ValidatedFieldUser312,
            TypeTestModel as TypeTestModel312,
            ValidatedUser as ValidatedUser312,
            TypeAdapterTest as TypeAdapterTest312,
            PydanticValidatedModel as PydanticValidatedModel312,
            MappedUser as MappedUser312,
            MappedPost as MappedPost312,
            MappedComment as MappedComment312,
            ColumnMappingModel as ColumnMappingModel312,
            MixedAnnotationModel as MixedAnnotationModel312,
            BulkUser as BulkUser312,
        )
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py312 import (
            AsyncUser as AsyncUser312,
            AsyncTypeCase as AsyncTypeCase312,
            AsyncValidatedUser as AsyncValidatedUser312,
            AsyncValidatedFieldUser as AsyncValidatedFieldUser312,
            AsyncTypeTestModel as AsyncTypeTestModel312,
            AsyncTypeAdapterTest as AsyncTypeAdapterTest312,
            AsyncPydanticValidatedModel as AsyncPydanticValidatedModel312,
            AsyncMappedUser as AsyncMappedUser312,
            AsyncMappedPost as AsyncMappedPost312,
            AsyncMappedComment as AsyncMappedComment312,
            AsyncColumnMappingModel as AsyncColumnMappingModel312,
            AsyncMixedAnnotationModel as AsyncMixedAnnotationModel312,
            AsyncBulkUser as AsyncBulkUser312,
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
TypeCase = _select_model_class(TypeCaseBase, TypeCase312, TypeCase311, TypeCase310, "TypeCase")
ValidatedFieldUser = _select_model_class(
    ValidatedFieldUserBase, ValidatedFieldUser312, ValidatedFieldUser311, ValidatedFieldUser310, "ValidatedFieldUser"
)
TypeTestModel = _select_model_class(
    TypeTestModelBase, TypeTestModel312, TypeTestModel311, TypeTestModel310, "TypeTestModel"
)
ValidatedUser = _select_model_class(
    ValidatedUserBase, ValidatedUser312, ValidatedUser311, ValidatedUser310, "ValidatedUser"
)
TypeAdapterTest = _select_model_class(
    TypeAdapterTestBase, TypeAdapterTest312, TypeAdapterTest311, TypeAdapterTest310, "TypeAdapterTest"
)
PydanticValidatedModel = _select_model_class(
    PydanticValidatedModelBase,
    PydanticValidatedModel312,
    PydanticValidatedModel311,
    PydanticValidatedModel310,
    "PydanticValidatedModel",
)
MappedUser = _select_model_class(MappedUserBase, MappedUser312, MappedUser311, MappedUser310, "MappedUser")
MappedPost = _select_model_class(MappedPostBase, MappedPost312, MappedPost311, MappedPost310, "MappedPost")
MappedComment = _select_model_class(
    MappedCommentBase, MappedComment312, MappedComment311, MappedComment310, "MappedComment"
)
ColumnMappingModel = _select_model_class(
    ColumnMappingModelBase, ColumnMappingModel312, ColumnMappingModel311, ColumnMappingModel310, "ColumnMappingModel"
)
MixedAnnotationModel = _select_model_class(
    MixedAnnotationModelBase,
    MixedAnnotationModel312,
    MixedAnnotationModel311,
    MixedAnnotationModel310,
    "MixedAnnotationModel",
)
BulkUser = _select_model_class(BulkUserBase, BulkUser312, BulkUser311, BulkUser310, "BulkUser")

AsyncUser = _select_model_class(AsyncUserBase, AsyncUser312, AsyncUser311, AsyncUser310, "AsyncUser")
AsyncTypeCase = _select_model_class(
    AsyncTypeCaseBase, AsyncTypeCase312, AsyncTypeCase311, AsyncTypeCase310, "AsyncTypeCase"
)
AsyncValidatedFieldUser = _select_model_class(
    AsyncValidatedFieldUserBase,
    AsyncValidatedFieldUser312,
    AsyncValidatedFieldUser311,
    AsyncValidatedFieldUser310,
    "AsyncValidatedFieldUser",
)
AsyncTypeTestModel = _select_model_class(
    AsyncTypeTestModelBase, AsyncTypeTestModel312, AsyncTypeTestModel311, AsyncTypeTestModel310, "AsyncTypeTestModel"
)
AsyncValidatedUser = _select_model_class(
    AsyncValidatedUserBase, AsyncValidatedUser312, AsyncValidatedUser311, AsyncValidatedUser310, "AsyncValidatedUser"
)
AsyncTypeAdapterTest = _select_model_class(
    AsyncTypeAdapterTestBase,
    AsyncTypeAdapterTest312,
    AsyncTypeAdapterTest311,
    AsyncTypeAdapterTest310,
    "AsyncTypeAdapterTest",
)
AsyncPydanticValidatedModel = _select_model_class(
    AsyncPydanticValidatedModelBase,
    AsyncPydanticValidatedModel312,
    AsyncPydanticValidatedModel311,
    AsyncPydanticValidatedModel310,
    "AsyncPydanticValidatedModel",
)
AsyncMappedUser = _select_model_class(
    AsyncMappedUserBase, AsyncMappedUser312, AsyncMappedUser311, AsyncMappedUser310, "AsyncMappedUser"
)
AsyncMappedPost = _select_model_class(
    AsyncMappedPostBase, AsyncMappedPost312, AsyncMappedPost311, AsyncMappedPost310, "AsyncMappedPost"
)
AsyncMappedComment = _select_model_class(
    AsyncMappedCommentBase, AsyncMappedComment312, AsyncMappedComment311, AsyncMappedComment310, "AsyncMappedComment"
)
AsyncColumnMappingModel = _select_model_class(
    AsyncColumnMappingModelBase,
    AsyncColumnMappingModel312,
    AsyncColumnMappingModel311,
    AsyncColumnMappingModel310,
    "AsyncColumnMappingModel",
)
AsyncMixedAnnotationModel = _select_model_class(
    AsyncMixedAnnotationModelBase,
    AsyncMixedAnnotationModel312,
    AsyncMixedAnnotationModel311,
    AsyncMixedAnnotationModel310,
    "AsyncMixedAnnotationModel",
)
AsyncBulkUser = _select_model_class(
    AsyncBulkUserBase, AsyncBulkUser312, AsyncBulkUser311, AsyncBulkUser310, "AsyncBulkUser"
)

from rhosocial.activerecord.testsuite.feature.basic.interfaces import (  # noqa: E402
    IBasicSyncProvider,
    IBasicAsyncProvider,
)
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol  # noqa: E402

from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (  # noqa: E402
    OrderItem as CompositeOrderItem,
    AsyncOrderItem as AsyncCompositeOrderItem,
    StoreInventory as StoreInventoryModel,
    AsyncStoreInventory as AsyncStoreInventoryModel,
    Order as OrderModel,
    AsyncOrder as AsyncOrderModel,
    MappedOrderItem as MappedOrderItemModel,
    AsyncMappedOrderItem as AsyncMappedOrderItemModel,
    Product as ProductModel,
    AsyncProduct as AsyncProductModel,
    ProductFormA as ProductFormAModel,
    AsyncProductFormA as AsyncProductFormAModel,
    ProductWithProxy as ProductWithProxyModel,
    AsyncProductWithProxy as AsyncProductWithProxyModel,
    ProductWithColumnAndAdapter as ProductWithColumnAndAdapterModel,
    AsyncProductWithColumnAndAdapter as AsyncProductWithColumnAndAdapterModel,
)

from .scenarios import get_enabled_scenarios, get_scenario  # noqa: E402

from providers.fixtures._common import (
    safe_drop_table, safe_drop_table_async,
    disable_fk_checks, enable_fk_checks,
    disable_fk_checks_async, enable_fk_checks_async,
)

class BasicProviderBase:
    def __init__(self):
        self._scenario_db_files = {}
        self._created_tables: Set[str] = set()

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def get_yes_no_adapter(self) -> "BaseSQLTypeAdapter":
        return YesOrNoBooleanAdapter()

    def get_dialect(self, scenario_name: str = "default"):
        """Return a bare, fully-constructed SQL Server dialect instance.

        Used by the ``feature/basic/ddl`` subtopic (expression/dialect
        contract). ``(16, 0, 0)`` advertises support for the ``IF
        [NOT] EXISTS`` ``DROP`` modifiers (available since 2016).
        """
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        return SQLServerDialect(version=(16, 0, 0))

    def _track_backend(self, backend_instance, collection: List) -> None:
        if backend_instance not in collection:
            collection.append(backend_instance)

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "basic", "schema"
        )
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, "r", encoding="utf-8") as f:
            return f.read()

    _load_mysql_schema = _load_sqlserver_schema


class BasicSyncProvider(BasicProviderBase, IBasicSyncProvider, WorkerTestProtocol):
    def __init__(self):
        super().__init__()
        self._active_backends = []

    def _setup_model(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend_instance = model_class.__backend__
        self._track_backend(backend_instance, self._active_backends)
        self._reset_table_sync(model_class, table_name)
        self._created_tables.add(table_name)
        return model_class

    def _reset_table_sync(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.basic import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        options = ExecutionOptions(stmt_type=StatementType.DDL)
        backend = model_class.__backend__
        safe_drop_table(backend, backend.dialect, table_name)
        if fn := TABLE_EXPRESSIONS.get(table_name):
            create_expr = fn(backend.dialect, table_name)
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            backend.execute(create_sql, params, options=options)
        else:
            schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
            backend.execute(schema_sql, options=options)

    def _initialize_model_schema(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        self._reset_table_sync(model_class, table_name)

    def _setup_multiple_models(
        self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str
    ) -> Tuple[Type[ActiveRecord], ...]:
        if not model_classes:
            return tuple()
        first_model_class, first_table_name = model_classes[0]
        first_model = self._setup_model(first_model_class, scenario_name, first_table_name)
        shared_backend = first_model.__backend__
        result = [first_model]
        for model_class, table_name in model_classes[1:]:
            model_class.__connection_config__ = first_model.__connection_config__
            model_class.__backend_class__ = first_model.__backend_class__
            model_class.__backend__ = shared_backend
            self._track_backend(shared_backend, self._active_backends)
            self._initialize_model_schema(model_class, table_name)
            self._created_tables.add(table_name)
            result.append(model_class)
        return tuple(result)

    def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(User, scenario_name, "users")

    def setup_type_case_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TypeCase, scenario_name, "type_cases")

    def setup_type_test_model(self, scenario_name: str) -> Type[ActiveRecord]:
        import pytest
        backend_class, config = get_scenario(scenario_name)
        temp_backend = backend_class(connection_config=config)
        temp_backend.connect()
        actual_version = temp_backend.get_server_version()
        temp_backend.disconnect()
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        temp_dialect = SQLServerDialect(actual_version)
        if not temp_dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by SQLServer version {actual_version}")
        model = self._setup_model(TypeTestModel, scenario_name, "type_tests")
        return model

    def setup_validated_field_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ValidatedFieldUser, scenario_name, "validated_field_users")

    def setup_validated_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ValidatedUser, scenario_name, "validated_users")

    def setup_pydantic_validated_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(PydanticValidatedModel, scenario_name, "pydantic_validated_models")

    def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models(
            [(MappedUser, "users"), (MappedPost, "posts"), (MappedComment, "comments")], scenario_name
        )

    def setup_mixed_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        return self._setup_multiple_models(
            [(ColumnMappingModel, "column_mapping_items"), (MixedAnnotationModel, "mixed_annotation_items")],
            scenario_name,
        )

    def setup_type_adapter_model_and_schema(self, scenario_name: Optional[str] = None) -> Type[ActiveRecord]:
        if scenario_name is None:
            scenario_name = self.get_test_scenarios()[0] if self.get_test_scenarios() else "default"
        return self._setup_model(TypeAdapterTest, scenario_name, "type_adapter_tests")

    def setup_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(BulkUser, scenario_name, "bulk_users")

    def setup_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(CompositeOrderItem, scenario_name, "order_items")

    def setup_order_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(OrderModel, scenario_name, "orders")

    def setup_mapped_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(MappedOrderItemModel, scenario_name, "order_items")

    def setup_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductModel, scenario_name, "product")

    def setup_product_form_a_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductFormAModel, scenario_name, "product")

    def setup_product_with_proxy_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductWithProxyModel, scenario_name, "product")

    def setup_product_with_column_and_adapter_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductWithColumnAndAdapterModel, scenario_name, "product")

    def get_worker_connection_params(self, scenario_name: str, fixture_type: str = None) -> dict:
        from .scenarios import SCENARIO_MAP
        is_async = fixture_type and fixture_type.startswith("async_")
        backend_class_name = "AsyncSQLServerBackend" if is_async else "SQLServerBackend"
        table_name = "users"
        if fixture_type:
            base_type = fixture_type.replace("async_", "")
            table_map = {
                "user": "users",
                "type_case": "type_cases",
                "type_test": "type_tests",
                "validated_field_user": "validated_field_users",
                "validated_user": "validated_users",
                "pydantic_validated_model": "pydantic_validated_models",
                "type_adapter_test": "type_adapter_tests",
            }
            table_name = table_map.get(base_type, "users")
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
            "schema_sql": self.get_worker_schema_sql(scenario_name, table_name),
        }

    def get_worker_schema_sql(self, scenario_name: str, table_name: str) -> str:
        from providers.fixtures.basic import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        if fn := TABLE_EXPRESSIONS.get(table_name):
            dialect = SQLServerDialect()
            sql, _ = to_sqlserver_ddl_sql(fn(dialect, table_name))
            return sql
        return self._load_sqlserver_schema(f"{table_name}.sql")

    def cleanup_after_test(self, scenario_name: str):
        for backend_instance in self._active_backends:
            for table_name in list(self._created_tables):
                try:
                    safe_drop_table(backend_instance, backend_instance.dialect, table_name)
                except Exception:
                    pass
            try:
                backend_instance.disconnect()
            except Exception:
                pass
        self._active_backends.clear()
        self._created_tables.clear()


class BasicAsyncProvider(BasicProviderBase, IBasicAsyncProvider):
    def __init__(self):
        super().__init__()
        self._active_async_backends = []

    async def get_dialect(self, scenario_name: str = "default"):
        """Async mirror of ``BasicProviderBase.get_dialect``."""
        return super().get_dialect(scenario_name)

    async def _setup_async_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str
    ) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        _, config = get_scenario(scenario_name)
        await model_class.configure(config, AsyncSQLServerBackend)
        backend_instance = model_class.__backend__
        self._track_backend(backend_instance, self._active_async_backends)
        await self._reset_table_async(model_class, table_name)
        self._created_tables.add(table_name)
        return model_class

    async def _reset_table_async(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.basic import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        options = ExecutionOptions(stmt_type=StatementType.DDL)
        backend = model_class.__backend__
        await safe_drop_table_async(backend, backend.dialect, table_name)
        if fn := TABLE_EXPRESSIONS.get(table_name):
            create_expr = fn(backend.dialect, table_name)
            create_sql, params = to_sqlserver_ddl_sql(create_expr)
            await backend.execute(create_sql, params, options=options)
        else:
            schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
            await backend.execute(schema_sql, options=options)

    async def _initialize_async_model_schema(self, model_class: Type[ActiveRecord], table_name: str):
        await self._reset_table_async(model_class, table_name)

    async def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncUser, scenario_name, "users")

    async def setup_type_case_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncTypeCase, scenario_name, "type_cases")

    async def setup_type_test_model(self, scenario_name: str) -> Type[ActiveRecord]:
        import pytest
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        _, config = get_scenario(scenario_name)
        temp_backend = AsyncSQLServerBackend(connection_config=config)
        await temp_backend.connect()
        actual_version = await temp_backend.get_server_version()
        await temp_backend.disconnect()
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        temp_dialect = SQLServerDialect(actual_version)
        if not temp_dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by SQLServer version {actual_version}")
        model = await self._setup_async_model(AsyncTypeTestModel, scenario_name, "type_tests")
        return model

    async def setup_validated_field_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncValidatedFieldUser, scenario_name, "validated_field_users")

    async def setup_validated_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncValidatedUser, scenario_name, "validated_users")

    async def setup_pydantic_validated_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncPydanticValidatedModel, scenario_name, "pydantic_validated_models")

    async def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        user = await self._setup_async_model(AsyncMappedUser, scenario_name, "users")
        shared_backend = user.__backend__
        post_model_class = AsyncMappedPost
        post_model_class.__connection_config__ = user.__connection_config__
        post_model_class.__backend_class__ = user.__backend_class__
        post_model_class.__backend__ = shared_backend
        await self._initialize_async_model_schema(post_model_class, "posts")
        self._created_tables.add("posts")
        comment_model_class = AsyncMappedComment
        comment_model_class.__connection_config__ = user.__connection_config__
        comment_model_class.__backend_class__ = user.__backend_class__
        comment_model_class.__backend__ = shared_backend
        await self._initialize_async_model_schema(comment_model_class, "comments")
        self._created_tables.add("comments")
        return user, post_model_class, comment_model_class

    async def setup_mixed_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        column_mapping_model = await self._setup_async_model(
            AsyncColumnMappingModel, scenario_name, "column_mapping_items"
        )
        shared_backend = column_mapping_model.__backend__
        mixed_annotation_model_class = AsyncMixedAnnotationModel
        mixed_annotation_model_class.__connection_config__ = column_mapping_model.__connection_config__
        mixed_annotation_model_class.__backend_class__ = column_mapping_model.__backend_class__
        mixed_annotation_model_class.__backend__ = shared_backend
        await self._initialize_async_model_schema(mixed_annotation_model_class, "mixed_annotation_items")
        self._created_tables.add("mixed_annotation_items")
        return column_mapping_model, mixed_annotation_model_class

    async def setup_type_adapter_model_and_schema(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncTypeAdapterTest, scenario_name, "type_adapter_tests")

    async def setup_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncBulkUser, scenario_name, "bulk_users")

    async def setup_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncCompositeOrderItem, scenario_name, "order_items")

    async def setup_order_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncOrderModel, scenario_name, "orders")

    async def setup_mapped_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncMappedOrderItemModel, scenario_name, "order_items")

    async def setup_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncProductModel, scenario_name, "product")

    async def setup_product_form_a_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncProductFormAModel, scenario_name, "product")

    async def setup_product_with_proxy_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncProductWithProxyModel, scenario_name, "product")

    async def setup_product_with_column_and_adapter_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncProductWithColumnAndAdapterModel, scenario_name, "product")

    async def cleanup_after_test(self, scenario_name: str):
        for backend_instance in self._active_async_backends:
            for table_name in list(self._created_tables):
                try:
                    await safe_drop_table_async(backend_instance, backend_instance.dialect, table_name)
                except Exception:
                    pass
            try:
                await backend_instance.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()
        self._created_tables.clear()
