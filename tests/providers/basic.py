import os
import sys
import logging
from typing import Type, List, Tuple, Optional

logger = logging.getLogger(__name__)

from rhosocial.activerecord.backend.type_adapter import BaseSQLTypeAdapter
from rhosocial.activerecord.model import ActiveRecord

from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    User as UserBase, TypeCase as TypeCaseBase, ValidatedFieldUser as ValidatedFieldUserBase,
    TypeTestModel as TypeTestModelBase, ValidatedUser as ValidatedUserBase,
    TypeAdapterTest as TypeAdapterTestBase, YesOrNoBooleanAdapter,
    MappedUser as MappedUserBase, MappedPost as MappedPostBase, MappedComment as MappedCommentBase,
    ColumnMappingModel as ColumnMappingModelBase, MixedAnnotationModel as MixedAnnotationModelBase,
    PydanticValidatedModel as PydanticValidatedModelBase,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    AsyncUser as AsyncUserBase, AsyncTypeCase as AsyncTypeCaseBase,
    AsyncValidatedUser as AsyncValidatedUserBase, AsyncValidatedFieldUser as AsyncValidatedFieldUserBase,
    AsyncTypeTestModel as AsyncTypeTestModelBase, AsyncTypeAdapterTest as AsyncTypeAdapterTestBase,
    AsyncMappedUser as AsyncMappedUserBase, AsyncMappedPost as AsyncMappedPostBase,
    AsyncMappedComment as AsyncMappedCommentBase,
    AsyncColumnMappingModel as AsyncColumnMappingModelBase, AsyncMixedAnnotationModel as AsyncMixedAnnotationModelBase,
    AsyncPydanticValidatedModel as AsyncPydanticValidatedModelBase,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    BulkUser as BulkUserBase, AsyncBulkUser as AsyncBulkUserBase
)

User310 = TypeCase310 = ValidatedFieldUser310 = TypeTestModel310 = ValidatedUser310 = None
TypeAdapterTest310 = MappedUser310 = MappedPost310 = MappedComment310 = None
ColumnMappingModel310 = MixedAnnotationModel310 = None
AsyncUser310 = AsyncTypeCase310 = AsyncValidatedFieldUser310 = AsyncTypeTestModel310 = None
AsyncValidatedUser310 = AsyncTypeAdapterTest310 = AsyncMappedUser310 = AsyncMappedPost310 = None
AsyncMappedComment310 = AsyncColumnMappingModel310 = AsyncMixedAnnotationModel310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py310 import (
            User as User310, TypeCase as TypeCase310, ValidatedFieldUser as ValidatedFieldUser310,
            TypeTestModel as TypeTestModel310, ValidatedUser as ValidatedUser310,
            TypeAdapterTest as TypeAdapterTest310,
            MappedUser as MappedUser310, MappedPost as MappedPost310, MappedComment as MappedComment310,
            ColumnMappingModel as ColumnMappingModel310, MixedAnnotationModel as MixedAnnotationModel310
        )
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py310 import (
            AsyncUser as AsyncUser310, AsyncTypeCase as AsyncTypeCase310,
            AsyncValidatedUser as AsyncValidatedUser310, AsyncValidatedFieldUser as AsyncValidatedFieldUser310,
            AsyncTypeTestModel as AsyncTypeTestModel310, AsyncTypeAdapterTest as AsyncTypeAdapterTest310,
            AsyncMappedUser as AsyncMappedUser310, AsyncMappedPost as AsyncMappedPost310,
            AsyncMappedComment as AsyncMappedComment310,
            AsyncColumnMappingModel as AsyncColumnMappingModel310, AsyncMixedAnnotationModel as AsyncMixedAnnotationModel310
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.10+ fixtures: {e}")

User311 = TypeCase311 = ValidatedFieldUser311 = TypeTestModel311 = ValidatedUser311 = None
TypeAdapterTest311 = MappedUser311 = MappedPost311 = MappedComment311 = None
ColumnMappingModel311 = MixedAnnotationModel311 = None
AsyncUser311 = AsyncTypeCase311 = AsyncValidatedFieldUser311 = AsyncTypeTestModel311 = None
AsyncValidatedUser311 = AsyncTypeAdapterTest311 = AsyncMappedUser311 = AsyncMappedPost311 = None
AsyncMappedComment311 = AsyncColumnMappingModel311 = AsyncMixedAnnotationModel311 = None

if sys.version_info >= (3, 11):
    try:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py311 import (
            User as User311, TypeCase as TypeCase311, ValidatedFieldUser as ValidatedFieldUser311,
            TypeTestModel as TypeTestModel311, ValidatedUser as ValidatedUser311,
            TypeAdapterTest as TypeAdapterTest311,
            MappedUser as MappedUser311, MappedPost as MappedPost311, MappedComment as MappedComment311,
            ColumnMappingModel as ColumnMappingModel311, MixedAnnotationModel as MixedAnnotationModel311
        )
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py311 import (
            AsyncUser as AsyncUser311, AsyncTypeCase as AsyncTypeCase311,
            AsyncValidatedUser as AsyncValidatedUser311, AsyncValidatedFieldUser as AsyncValidatedFieldUser311,
            AsyncTypeTestModel as AsyncTypeTestModel311, AsyncTypeAdapterTest as AsyncTypeAdapterTest311,
            AsyncMappedUser as AsyncMappedUser311, AsyncMappedPost as AsyncMappedPost311,
            AsyncMappedComment as AsyncMappedComment311,
            AsyncColumnMappingModel as AsyncColumnMappingModel311, AsyncMixedAnnotationModel as AsyncMixedAnnotationModel311
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.11+ fixtures: {e}")

User312 = TypeCase312 = ValidatedFieldUser312 = TypeTestModel312 = ValidatedUser312 = None
TypeAdapterTest312 = MappedUser312 = MappedPost312 = MappedComment312 = None
ColumnMappingModel312 = MixedAnnotationModel312 = None
AsyncUser312 = AsyncTypeCase312 = AsyncValidatedFieldUser312 = AsyncTypeTestModel312 = None
AsyncValidatedUser312 = AsyncTypeAdapterTest312 = AsyncMappedUser312 = AsyncMappedPost312 = None
AsyncMappedComment312 = AsyncColumnMappingModel312 = AsyncMixedAnnotationModel312 = None

if sys.version_info >= (3, 12):
    try:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py312 import (
            User as User312, TypeCase as TypeCase312, ValidatedFieldUser as ValidatedFieldUser312,
            TypeTestModel as TypeTestModel312, ValidatedUser as ValidatedUser312,
            TypeAdapterTest as TypeAdapterTest312,
            MappedUser as MappedUser312, MappedPost as MappedPost312, MappedComment as MappedComment312,
            ColumnMappingModel as ColumnMappingModel312, MixedAnnotationModel as MixedAnnotationModel312
        )
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models_py312 import (
            AsyncUser as AsyncUser312, AsyncTypeCase as AsyncTypeCase312,
            AsyncValidatedUser as AsyncValidatedUser312, AsyncValidatedFieldUser as AsyncValidatedFieldUser312,
            AsyncTypeTestModel as AsyncTypeTestModel312, AsyncTypeAdapterTest as AsyncTypeAdapterTest312,
            AsyncMappedUser as AsyncMappedUser312, AsyncMappedPost as AsyncMappedPost312,
            AsyncMappedComment as AsyncMappedComment312,
            AsyncColumnMappingModel as AsyncColumnMappingModel312, AsyncMixedAnnotationModel as AsyncMixedAnnotationModel312
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.12+ fixtures: {e}")


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, model_name: str) -> Type:
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    selected = select_fixture(*candidates)
    logger.info(f"Selected {model_name}: {selected.__name__} from {selected.__module__}")
    return selected


User = _select_model_class(UserBase, User312, User311, User310, "User")
TypeCase = _select_model_class(TypeCaseBase, TypeCase312, TypeCase311, TypeCase310, "TypeCase")
ValidatedFieldUser = _select_model_class(ValidatedFieldUserBase, ValidatedFieldUser312, ValidatedFieldUser311, ValidatedFieldUser310, "ValidatedFieldUser")
TypeTestModel = _select_model_class(TypeTestModelBase, TypeTestModel312, TypeTestModel311, TypeTestModel310, "TypeTestModel")
ValidatedUser = _select_model_class(ValidatedUserBase, ValidatedUser312, ValidatedUser311, ValidatedUser310, "ValidatedUser")
TypeAdapterTest = _select_model_class(TypeAdapterTestBase, TypeAdapterTest312, TypeAdapterTest311, TypeAdapterTest310, "TypeAdapterTest")
MappedUser = _select_model_class(MappedUserBase, MappedUser312, MappedUser311, MappedUser310, "MappedUser")
MappedPost = _select_model_class(MappedPostBase, MappedPost312, MappedPost311, MappedPost310, "MappedPost")
MappedComment = _select_model_class(MappedCommentBase, MappedComment312, MappedComment311, MappedComment310, "MappedComment")
ColumnMappingModel = _select_model_class(ColumnMappingModelBase, ColumnMappingModel312, ColumnMappingModel311, ColumnMappingModel310, "ColumnMappingModel")
MixedAnnotationModel = _select_model_class(MixedAnnotationModelBase, MixedAnnotationModel312, MixedAnnotationModel311, MixedAnnotationModel310, "MixedAnnotationModel")

AsyncUser = _select_model_class(AsyncUserBase, AsyncUser312, AsyncUser311, AsyncUser310, "AsyncUser")
AsyncTypeCase = _select_model_class(AsyncTypeCaseBase, AsyncTypeCase312, AsyncTypeCase311, AsyncTypeCase310, "AsyncTypeCase")
AsyncValidatedFieldUser = _select_model_class(AsyncValidatedFieldUserBase, AsyncValidatedFieldUser312, AsyncValidatedFieldUser311, AsyncValidatedFieldUser310, "AsyncValidatedFieldUser")
AsyncTypeTestModel = _select_model_class(AsyncTypeTestModelBase, AsyncTypeTestModel312, AsyncTypeTestModel311, AsyncTypeTestModel310, "AsyncTypeTestModel")
AsyncValidatedUser = _select_model_class(AsyncValidatedUserBase, AsyncValidatedUser312, AsyncValidatedUser311, AsyncValidatedUser310, "AsyncValidatedUser")
AsyncTypeAdapterTest = _select_model_class(AsyncTypeAdapterTestBase, AsyncTypeAdapterTest312, AsyncTypeAdapterTest311, AsyncTypeAdapterTest310, "AsyncTypeAdapterTest")
AsyncMappedUser = _select_model_class(AsyncMappedUserBase, AsyncMappedUser312, AsyncMappedUser311, AsyncMappedUser310, "AsyncMappedUser")
AsyncMappedPost = _select_model_class(AsyncMappedPostBase, AsyncMappedPost312, AsyncMappedPost311, AsyncMappedPost310, "AsyncMappedPost")
AsyncMappedComment = _select_model_class(AsyncMappedCommentBase, AsyncMappedComment312, AsyncMappedComment311, AsyncMappedComment310, "AsyncMappedComment")
AsyncColumnMappingModel = _select_model_class(AsyncColumnMappingModelBase, AsyncColumnMappingModel312, AsyncColumnMappingModel311, AsyncColumnMappingModel310, "AsyncColumnMappingModel")
AsyncMixedAnnotationModel = _select_model_class(AsyncMixedAnnotationModelBase, AsyncMixedAnnotationModel312, AsyncMixedAnnotationModel311, AsyncMixedAnnotationModel310, "AsyncMixedAnnotationModel")
BulkUser = BulkUserBase
AsyncBulkUser = AsyncBulkUserBase
PydanticValidatedModel = PydanticValidatedModelBase
AsyncPydanticValidatedModel = AsyncPydanticValidatedModelBase

from rhosocial.activerecord.testsuite.feature.basic.interfaces import IBasicProvider
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol
from .scenarios import get_enabled_scenarios, get_scenario


class BasicProvider(IBasicProvider, WorkerTestProtocol):

    def __init__(self):
        self._active_backends = []
        self._active_async_backends = []

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _track_backend(self, backend_instance, collection: List) -> None:
        if backend_instance not in collection:
            collection.append(backend_instance)

    def _setup_model(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)

        backend_instance = model_class.__backend__
        self._track_backend(backend_instance, self._active_backends)

        self._reset_table_sync(model_class, table_name)
        return model_class

    async def _setup_async_model(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend

        _, config = get_scenario(scenario_name)
        await model_class.configure(config, AsyncSQLServerBackend)

        backend_instance = model_class.__backend__
        self._track_backend(backend_instance, self._active_async_backends)

        await self._reset_table_async(model_class, table_name)
        return model_class

    # Tables that must be dropped before a given table (due to FK references)
    _FK_DEPENDENCY_MAP = {
        'users': ['comments', 'posts', 'validated_users', 'validated_field_users'],
        'posts': ['comments'],
    }

    def _drop_table_safely(self, backend, table_name: str) -> None:
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        for child in self._FK_DEPENDENCY_MAP.get(table_name, []):
            try:
                expr = DropTableExpression(backend.dialect, child, if_exists=True)
                backend.execute(*expr.to_sql())
            except Exception:
                pass
        try:
            expr = DropTableExpression(backend.dialect, table_name, if_exists=True)
            backend.execute(*expr.to_sql())
        except Exception:
            pass

    def _reset_table_sync(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        self._drop_table_safely(model_class.__backend__, table_name)
        schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
        model_class.__backend__.execute(schema_sql)

    async def _reset_table_async(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        expr = DropTableExpression(model_class.__backend__.dialect, table_name, if_exists=True)
        await model_class.__backend__.execute(*expr.to_sql())
        schema_sql = self._load_sqlserver_schema(f"{table_name}.sql")
        await model_class.__backend__.execute(schema_sql)

    def _initialize_model_schema(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        self._reset_table_sync(model_class, table_name)

    async def _initialize_async_model_schema(self, model_class: Type[ActiveRecord], table_name: str):
        await self._reset_table_async(model_class, table_name)

    def _setup_multiple_models(self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        if not model_classes:
            return tuple()

        first_model_class, first_table_name = model_classes[0]
        backend_class, config = get_scenario(scenario_name)
        temp_backend = backend_class(connection_config=config)
        temp_backend.connect()
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        for _, table_name in reversed(model_classes):
            try:
                expr = DropTableExpression(temp_backend.dialect, table_name, if_exists=True)
                temp_backend.execute(*expr.to_sql())
            except Exception:
                pass
        temp_backend.disconnect()

        first_model = self._setup_model(first_model_class, scenario_name, first_table_name)
        shared_backend = first_model.__backend__

        result = [first_model]

        for model_class, table_name in model_classes[1:]:
            model_class.__connection_config__ = first_model.__connection_config__
            model_class.__backend_class__ = first_model.__backend_class__
            model_class.__backend__ = shared_backend
            self._track_backend(shared_backend, self._active_backends)
            self._initialize_model_schema(model_class, table_name)
            result.append(model_class)

        return tuple(result)

    def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(User, scenario_name, "users")

    async def setup_async_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncUser, scenario_name, "users")

    def setup_type_case_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TypeCase, scenario_name, "type_cases")

    async def setup_async_type_case_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncTypeCase, scenario_name, "type_cases")

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
            pytest.skip(f"JSON type not supported by SQL Server version {actual_version}")
        model = self._setup_model(TypeTestModel, scenario_name, "type_tests")
        return model

    async def setup_async_type_test_model(self, scenario_name: str) -> Type[ActiveRecord]:
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
            pytest.skip(f"JSON type not supported by SQL Server version {actual_version}")
        model = await self._setup_async_model(AsyncTypeTestModel, scenario_name, "type_tests")
        return model

    def setup_validated_field_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ValidatedFieldUser, scenario_name, "validated_field_users")

    async def setup_async_validated_field_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncValidatedFieldUser, scenario_name, "validated_field_users")

    def setup_validated_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ValidatedUser, scenario_name, "validated_users")

    async def setup_async_validated_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncValidatedUser, scenario_name, "validated_users")

    def setup_mapped_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (MappedUser, "users"),
            (MappedPost, "posts"),
            (MappedComment, "comments")
        ], scenario_name)

    async def setup_async_mapped_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        user = await self._setup_async_model(AsyncMappedUser, scenario_name, "users")
        shared_backend = user.__backend__

        post_model_class = AsyncMappedPost
        post_model_class.__connection_config__ = user.__connection_config__
        post_model_class.__backend_class__ = user.__backend_class__
        post_model_class.__backend__ = shared_backend
        await self._initialize_async_model_schema(post_model_class, "posts")

        comment_model_class = AsyncMappedComment
        comment_model_class.__connection_config__ = user.__connection_config__
        comment_model_class.__backend_class__ = user.__backend_class__
        comment_model_class.__backend__ = shared_backend
        await self._initialize_async_model_schema(comment_model_class, "comments")

        return user, post_model_class, comment_model_class

    def setup_mixed_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        return self._setup_multiple_models([
            (ColumnMappingModel, "column_mapping_items"),
            (MixedAnnotationModel, "mixed_annotation_items")
        ], scenario_name)

    async def setup_async_mixed_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        column_mapping_model = await self._setup_async_model(AsyncColumnMappingModel, scenario_name, "column_mapping_items")
        shared_backend = column_mapping_model.__backend__

        mixed_annotation_model_class = AsyncMixedAnnotationModel
        mixed_annotation_model_class.__connection_config__ = column_mapping_model.__connection_config__
        mixed_annotation_model_class.__backend_class__ = column_mapping_model.__backend_class__
        mixed_annotation_model_class.__backend__ = shared_backend
        await self._initialize_async_model_schema(mixed_annotation_model_class, "mixed_annotation_items")

        return column_mapping_model, mixed_annotation_model_class

    def setup_type_adapter_model_and_schema(self, scenario_name: Optional[str] = None) -> Type[ActiveRecord]:
        if scenario_name is None:
            scenario_name = self.get_test_scenarios()[0] if self.get_test_scenarios() else "default"
        return self._setup_model(TypeAdapterTest, scenario_name, "type_adapter_tests")

    async def setup_async_type_adapter_model_and_schema(self, scenario_name: Optional[str] = None) -> Type[ActiveRecord]:
        if scenario_name is None:
            scenario_name = self.get_test_scenarios()[0] if self.get_test_scenarios() else "default"
        return await self._setup_async_model(AsyncTypeAdapterTest, scenario_name, "type_adapter_tests")

    def setup_pydantic_validated_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(PydanticValidatedModel, scenario_name, "pydantic_validated_models")

    async def setup_async_pydantic_validated_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncPydanticValidatedModel, scenario_name, "pydantic_validated_models")

    def setup_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        """Sets up the database for the `BulkUser` model tests."""
        return self._setup_model(BulkUser, scenario_name, "bulk_users")

    async def setup_async_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        """Sets up the database for the `AsyncBulkUser` model tests."""
        return await self._setup_async_model(AsyncBulkUser, scenario_name, "bulk_users")

    def get_yes_no_adapter(self) -> 'BaseSQLTypeAdapter':
        return YesOrNoBooleanAdapter()

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "basic", "schema")
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, 'r', encoding='utf-8') as f:
            return f.read()

    def cleanup_after_test(self, scenario_name: str):
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        tables_to_drop = [
            'comments', 'posts', 'users', 'type_cases', 'type_tests',
            'validated_field_users', 'validated_users', 'type_adapter_tests',
            'column_mapping_items', 'mixed_annotation_items', 'bulk_users',
            'pydantic_validated_models'
        ]
        for backend_instance in self._active_backends:
            try:
                for table_name in tables_to_drop:
                    try:
                        expr = DropTableExpression(backend_instance.dialect, table_name, if_exists=True)
                        backend_instance.execute(*expr.to_sql())
                    except Exception:
                        pass
            finally:
                try:
                    backend_instance.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()

    async def cleanup_after_test_async(self, scenario_name: str):
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        tables_to_drop = [
            'comments', 'posts', 'users', 'type_cases', 'type_tests',
            'validated_field_users', 'validated_users', 'type_adapter_tests',
            'column_mapping_items', 'mixed_annotation_items', 'bulk_users',
            'pydantic_validated_models'
        ]
        for backend_instance in self._active_async_backends:
            try:
                for table_name in tables_to_drop:
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
        self._active_async_backends.clear()

    def get_worker_connection_params(self, scenario_name: str, fixture_type: str = None) -> dict:
        from .scenarios import SCENARIO_MAP

        is_async = fixture_type and fixture_type.startswith('async_')
        backend_class_name = 'AsyncSQLServerBackend' if is_async else 'SQLServerBackend'

        table_name = 'users'
        if fixture_type:
            base_type = fixture_type.replace('async_', '')
            table_map = {
                'user': 'users',
                'type_case': 'type_cases',
                'type_test': 'type_tests',
                'validated_field_user': 'validated_field_users',
                'validated_user': 'validated_users',
                'type_adapter_test': 'type_adapter_tests',
            }
            table_name = table_map.get(base_type, 'users')

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
            'schema_sql': self._load_sqlserver_schema(f'{table_name}.sql'),
        }

    def get_worker_schema_sql(self, scenario_name: str, table_name: str) -> str:
        return self._load_sqlserver_schema(f'{table_name}.sql')
