# tests/rhosocial/activerecord_sqlserver_test/feature/backend/conftest.py
import pytest
import pytest_asyncio
import yaml
import os
from typing import Dict, Any, Tuple, Type

from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    AsyncSQLServerBackend,
    SQLServerConnectionConfig,
)

SCENARIO_MAP: Dict[str, Dict[str, Any]] = {}


def register_scenario(name: str, config: Dict[str, Any]):
    SCENARIO_MAP[name] = config


def _load_scenarios_from_config():
    """
    Load scenarios from a configuration file with the following priority:
    1. Environment variable specified path (highest priority)
    2. Default path tests/config/sqlserver_scenarios.yaml (lowest priority)
    If no valid configuration file is found, terminate with an error.
    """
    config_path = None
    env_config_path = os.getenv("SQLSERVER_SCENARIOS_CONFIG_PATH")

    if env_config_path and os.path.exists(env_config_path):
        print(f"Loading SQL Server scenarios from environment-specified path: {env_config_path}")
        config_path = env_config_path
    else:
        default_path = os.path.join(
            os.path.dirname(__file__),
            "../../../../config",
            "sqlserver_scenarios.yaml",
        )
        if os.path.exists(default_path):
            config_path = default_path
        elif env_config_path:
            print(f"Warning: Scenario file specified in SQLSERVER_SCENARIOS_CONFIG_PATH not found: {env_config_path}")
            return

    if not config_path:
        raise FileNotFoundError(
            "No SQL Server scenarios configuration file found. "
            "Either set SQLSERVER_SCENARIOS_CONFIG_PATH to a valid YAML file "
            "or place sqlserver_scenarios.yaml in the tests/config directory."
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        if "scenarios" not in config_data:
            raise ValueError(f"Configuration file {config_path} does not contain 'scenarios' key")

        for scenario_name, config in config_data["scenarios"].items():
            register_scenario(scenario_name, config)

    except ImportError:
        raise ImportError("PyYAML is required to load SQL Server scenario configuration files")


_load_scenarios_from_config()


def get_scenario(name: str) -> Tuple[Type[SQLServerBackend], SQLServerConnectionConfig]:
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered")
    scenario_config = SCENARIO_MAP[name].copy()
    config = SQLServerConnectionConfig(**scenario_config)
    return SQLServerBackend, config


def get_enabled_scenarios() -> Dict[str, Any]:
    return SCENARIO_MAP


class BackendFeatureProvider:
    def __init__(self):
        self._backend = None
        self._async_backend = None

    def setup_backend(self, scenario_name: str):
        if self._backend:
            return self._backend
        backend_class, config = get_scenario(scenario_name)
        self._backend = backend_class(connection_config=config)
        self._backend.connect()
        return self._backend

    async def setup_async_backend(self, scenario_name: str):
        if self._async_backend:
            return self._async_backend
        _, config = get_scenario(scenario_name)
        self._async_backend = AsyncSQLServerBackend(connection_config=config)
        await self._async_backend.connect()
        return self._async_backend

    def cleanup(self):
        if self._backend:
            self._backend.disconnect()
            self._backend = None

    async def async_cleanup(self):
        if self._async_backend:
            await self._async_backend.disconnect()
            self._async_backend = None


def get_scenario_names():
    return list(get_enabled_scenarios().keys())


@pytest.fixture(scope="function", params=get_scenario_names())
def sqlserver_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name)
    yield backend
    provider.cleanup()


@pytest.fixture(scope="function")
def sqlserver_backend_single():
    """Non-parameterized fixture using the first available scenario."""
    scenario_names = get_scenario_names()
    if not scenario_names:
        pytest.skip("No SQL Server scenarios configured")
    scenario_name = scenario_names[0]
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name)
    yield backend
    provider.cleanup()


@pytest_asyncio.fixture(scope="function", params=get_scenario_names())
async def async_sqlserver_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = await provider.setup_async_backend(scenario_name)
    yield backend
    await provider.async_cleanup()


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_backend_single():
    """Non-parameterized async fixture using the first available scenario."""
    scenario_names = get_scenario_names()
    if not scenario_names:
        pytest.skip("No SQL Server scenarios configured")
    scenario_name = scenario_names[0]
    provider = BackendFeatureProvider()
    backend = await provider.setup_async_backend(scenario_name)
    yield backend
    await provider.async_cleanup()


@pytest.fixture(scope="function")
def sqlserver_dialect():
    """Fixture providing SQLServerDialect instance for testing."""
    from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
    return SQLServerDialect()
