import os
import sys
import logging
from typing import Type, List

from rhosocial.activerecord.model import ActiveRecord

logger = logging.getLogger(__name__)

from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import (
    TimestampedPost as TimestampedPostBase,
    VersionedProduct as VersionedProductBase,
    Task as TaskBase,
    CombinedArticle as CombinedArticleBase
)

TimestampedPost310 = VersionedProduct310 = Task310 = CombinedArticle310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models_py310 import (
            TimestampedPost as TimestampedPost310,
            VersionedProduct as VersionedProduct310,
            Task as Task310,
            CombinedArticle as CombinedArticle310
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
            CombinedArticle as CombinedArticle311
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
            CombinedArticle as CombinedArticle312
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.12+ fixtures: {e}")


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, model_name: str) -> Type:
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    selected = select_fixture(*candidates)
    logger.info(f"Selected {model_name}: {selected.__name__} from {selected.__module__}")
    return selected


TimestampedPost = _select_model_class(TimestampedPostBase, TimestampedPost312, TimestampedPost311, TimestampedPost310, "TimestampedPost")
VersionedProduct = _select_model_class(VersionedProductBase, VersionedProduct312, VersionedProduct311, VersionedProduct310, "VersionedProduct")
Task = _select_model_class(TaskBase, Task312, Task311, Task310, "Task")
CombinedArticle = _select_model_class(CombinedArticleBase, CombinedArticle312, CombinedArticle311, CombinedArticle310, "CombinedArticle")

from rhosocial.activerecord.testsuite.feature.mixins.interfaces import IMixinsProvider
from .scenarios import get_enabled_scenarios, get_scenario


class MixinsProvider(IMixinsProvider):

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

    def setup_timestamped_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TimestampedPost, scenario_name, "timestamped_posts")

    def setup_versioned_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(VersionedProduct, scenario_name, "versioned_products")

    def setup_task_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(Task, scenario_name, "tasks")

    def setup_combined_article_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(CombinedArticle, scenario_name, "combined_articles")

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "mixins", "schema")
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, 'r', encoding='utf-8') as f:
            return f.read()

    def cleanup_after_test(self, scenario_name: str):
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        for backend_instance in self._active_backends:
            try:
                for table_name in ['combined_articles', 'tasks', 'versioned_products', 'timestamped_posts']:
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
