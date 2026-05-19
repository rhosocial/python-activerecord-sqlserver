import os
import sys
import logging
from typing import Type, List

from rhosocial.activerecord.model import ActiveRecord

logger = logging.getLogger(__name__)

from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.events.fixtures.models import (
    EventTestModel as EventTestModelBase,
    EventTrackingModel as EventTrackingModelBase
)

EventTestModel310 = EventTrackingModel310 = None

if sys.version_info >= (3, 10):
    try:
        from rhosocial.activerecord.testsuite.feature.events.fixtures.models_py310 import (
            EventTestModel as EventTestModel310,
            EventTrackingModel as EventTrackingModel310
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.10+ fixtures: {e}")

EventTestModel311 = EventTrackingModel311 = None

if sys.version_info >= (3, 11):
    try:
        from rhosocial.activerecord.testsuite.feature.events.fixtures.models_py311 import (
            EventTestModel as EventTestModel311,
            EventTrackingModel as EventTrackingModel311
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.11+ fixtures: {e}")

EventTestModel312 = EventTrackingModel312 = None

if sys.version_info >= (3, 12):
    try:
        from rhosocial.activerecord.testsuite.feature.events.fixtures.models_py312 import (
            EventTestModel as EventTestModel312,
            EventTrackingModel as EventTrackingModel312
        )
    except ImportError as e:
        logger.warning(f"Failed to import Python 3.12+ fixtures: {e}")


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, model_name: str) -> Type:
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    selected = select_fixture(*candidates)
    logger.info(f"Selected {model_name}: {selected.__name__} from {selected.__module__}")
    return selected


EventTestModel = _select_model_class(EventTestModelBase, EventTestModel312, EventTestModel311, EventTestModel310, "EventTestModel")
EventTrackingModel = _select_model_class(EventTrackingModelBase, EventTrackingModel312, EventTrackingModel311, EventTrackingModel310, "EventTrackingModel")

from rhosocial.activerecord.testsuite.feature.events.interfaces import IEventsProvider
from .scenarios import get_enabled_scenarios, get_scenario


class EventsProvider(IEventsProvider):

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

    def setup_event_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(EventTestModel, scenario_name, "event_tests")

    def setup_event_tracking_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(EventTrackingModel, scenario_name, "event_tracking_models")

    def _load_sqlserver_schema(self, filename: str) -> str:
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial", "activerecord_sqlserver_test", "feature", "events", "schema")
        schema_path = os.path.join(schema_dir, filename)
        with open(schema_path, 'r', encoding='utf-8') as f:
            return f.read()

    def cleanup_after_test(self, scenario_name: str):
        from rhosocial.activerecord.backend.expression.statements import DropTableExpression
        for backend_instance in self._active_backends:
            try:
                for table_name in ['event_tracking_models', 'event_tests']:
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
