# tests/providers/mixins.py
"""
Concrete implementations of `IMixinsSyncProvider` and `IMixinsAsyncProvider`
for the SQL Server backend.
"""

import os
import sys
import logging
from typing import Type, List

from rhosocial.activerecord.model import ActiveRecord

logger = logging.getLogger(__name__)

from rhosocial.activerecord.testsuite.utils import select_fixture  # noqa: E402

from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import (  # noqa: E402
    TimestampedPost as TimestampedPostBase,
    VersionedProduct as VersionedProductBase,
    Task as TaskBase,
    CombinedArticle as CombinedArticleBase,
    AsyncTimestampedPost as AsyncTimestampedPostBase,
    AsyncVersionedProduct as AsyncVersionedProductBase,
    AsyncTask as AsyncTaskBase,
    AsyncCombinedArticle as AsyncCombinedArticleBase,
)

TimestampedPost310 = VersionedProduct310 = Task310 = CombinedArticle310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models_py310 import (
            TimestampedPost as TimestampedPost310,
            VersionedProduct as VersionedProduct310,
            Task as Task310,
            CombinedArticle as CombinedArticle310,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.10+ fixtures: {e}")

TimestampedPost311 = VersionedProduct311 = Task311 = CombinedArticle311 = None

if sys.version_info >= (3, 11):
    try:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models_py311 import (
            TimestampedPost as TimestampedPost311,
            VersionedProduct as VersionedProduct311,
            Task as Task311,
            CombinedArticle as CombinedArticle311,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.11+ fixtures: {e}")

TimestampedPost312 = VersionedProduct312 = Task312 = CombinedArticle312 = None

if sys.version_info >= (3, 12):
    try:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models_py312 import (
            TimestampedPost as TimestampedPost312,
            VersionedProduct as VersionedProduct312,
            Task as Task312,
            CombinedArticle as CombinedArticle312,
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.12+ fixtures: {e}")


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, model_name: str) -> Type:
    """Select the most appropriate model class for the current Python version."""
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    selected = select_fixture(*candidates)
    logger.info(f"Selected {model_name}: {selected.__name__} from {selected.__module__}")
    return selected


TimestampedPost = _select_model_class(
    TimestampedPostBase, TimestampedPost312, TimestampedPost311, TimestampedPost310, "TimestampedPost"
)
VersionedProduct = _select_model_class(
    VersionedProductBase, VersionedProduct312, VersionedProduct311, VersionedProduct310, "VersionedProduct"
)
Task = _select_model_class(TaskBase, Task312, Task311, Task310, "Task")
CombinedArticle = _select_model_class(
    CombinedArticleBase, CombinedArticle312, CombinedArticle311, CombinedArticle310, "CombinedArticle"
)

AsyncTimestampedPost = AsyncTimestampedPostBase
AsyncVersionedProduct = AsyncVersionedProductBase
AsyncTask = AsyncTaskBase
AsyncCombinedArticle = AsyncCombinedArticleBase

from rhosocial.activerecord.testsuite.feature.mixins.interfaces import (  # noqa: E402
    IMixinsSyncProvider,
    IMixinsAsyncProvider,
)

from .scenarios import get_enabled_scenarios, get_scenario  # noqa: E402

from providers.fixtures._common import (
    safe_drop_table, safe_drop_table_async,
    disable_fk_checks, enable_fk_checks,
    disable_fk_checks_async, enable_fk_checks_async,
)

class MixinsProviderBase:
    def __init__(self):
        self._scenario_db_files = {}

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "mixins", "schema"
        )
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, "r", encoding="utf-8") as f:
            return f.read()

    _load_mysql_schema = _load_sqlserver_schema


class MixinsSyncProvider(MixinsProviderBase, IMixinsSyncProvider):
    def __init__(self):
        super().__init__()
        self._active_backends = []

    def _setup_model(self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.mixins import TABLE_EXPRESSIONS
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

    def setup_timestamped_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TimestampedPost, scenario_name, "timestamped_posts")

    def setup_versioned_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(VersionedProduct, scenario_name, "versioned_products")

    def setup_task_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(Task, scenario_name, "tasks")

    def setup_combined_article_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(CombinedArticle, scenario_name, "combined_articles")

    def cleanup_after_test(self, scenario_name: str):
        for backend_instance in self._active_backends:
            for table_name in ["timestamped_posts", "versioned_products", "tasks", "combined_articles"]:
                try:
                    safe_drop_table(backend_instance, backend_instance.dialect, table_name)
                except Exception:
                    pass
            try:
                backend_instance.disconnect()
            except Exception:
                pass
        self._active_backends.clear()


class MixinsAsyncProvider(MixinsProviderBase, IMixinsAsyncProvider):
    def __init__(self):
        super().__init__()
        self._active_async_backends = []

    async def _setup_async_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str
    ) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType
        from rhosocial.activerecord.backend.expression import DropTableExpression, TableExpression
        from providers.fixtures.mixins import TABLE_EXPRESSIONS
        from providers.fixtures._common import to_sqlserver_ddl_sql

        _, config = get_scenario(scenario_name)
        await model_class.configure(config, AsyncSQLServerBackend)
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

    async def setup_timestamped_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncTimestampedPost, scenario_name, "timestamped_posts")

    async def setup_versioned_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncVersionedProduct, scenario_name, "versioned_products")

    async def setup_task_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncTask, scenario_name, "tasks")

    async def setup_combined_article_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return await self._setup_async_model(AsyncCombinedArticle, scenario_name, "combined_articles")

    async def cleanup_after_test(self, scenario_name: str):
        for backend_instance in self._active_async_backends:
            for table_name in ["timestamped_posts", "versioned_products", "tasks", "combined_articles"]:
                try:
                    await safe_drop_table_async(backend_instance, backend_instance.dialect, table_name)
                except Exception:
                    pass
            try:
                await backend_instance.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()
