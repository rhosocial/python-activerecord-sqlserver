# tests/providers/scenarios.py
"""SQL Server backend test scenario configuration mapping table"""

import os
from dataclasses import replace
from typing import Dict, Any, Tuple, Type
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.testsuite.core.pool import pooled_database_name

SCENARIO_MAP: Dict[str, Dict[str, Any]] = {}


def register_scenario(name: str, config: Dict[str, Any]):
    SCENARIO_MAP[name] = config


def get_scenario_raw(name: str) -> Tuple[Type[SQLServerBackend], SQLServerConnectionConfig]:
    """Return the backend class and connection config for a scenario.

    The config uses the scenario's configured ``database``; no pool override is
    applied. Used by the pool reset handler, which must reach the server
    regardless of whether a pooled database exists yet.
    """
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered")
    config = SQLServerConnectionConfig(**SCENARIO_MAP[name])
    return SQLServerBackend, config


def get_scenario(name: str) -> Tuple[Type[SQLServerBackend], SQLServerConnectionConfig]:
    """
    Retrieves the backend class and a connection configuration object for a given
    scenario name. This is called by the provider to set up the database for a test.

    Under an active database pool the config's ``database`` is replaced by the
    worker's pooled database name (``{database}_{index}``) so concurrent workers
    never share a schema. Serial runs keep the scenario's configured database.
    """
    backend_class, config = get_scenario_raw(name)
    pooled_db = pooled_database_name(name)
    if pooled_db:
        config = replace(config, database=pooled_db)
    return backend_class, config


def get_enabled_scenarios() -> Dict[str, Any]:
    return SCENARIO_MAP


def _load_scenarios_from_config():
    env_config_path = os.getenv("SQLSERVER_SCENARIOS_CONFIG_PATH")
    if env_config_path and os.path.exists(env_config_path):
        print(f"Loading SQL Server scenarios from environment-specified path: {env_config_path}")
        config_path = env_config_path
    else:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "sqlserver_scenarios.yaml")
        if not os.path.exists(config_path):
            print("No SQL Server scenarios configuration file found. Skipping scenario registration.")
            return
        print(f"Loading SQL Server scenarios from default path: {config_path}")

    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if 'scenarios' not in config_data:
            raise ValueError(f"Configuration file {config_path} does not contain 'scenarios' key")

        for scenario_name, config in config_data['scenarios'].items():
            register_scenario(scenario_name, config)

        _apply_scenario_filter()

    except ImportError:
        raise ImportError("PyYAML is required to load SQL Server scenario configuration files")


def _apply_scenario_filter():
    """Filter SCENARIO_MAP based on the active scenarios env var.

    The env var is set either by the --scenarios pytest option in the
    testsuite's root conftest (TESTSUITE_ACTIVE_SCENARIOS) or by a backend
    local override (SQLSERVER_ACTIVE_SCENARIOS). It contains comma-separated
    full scenario names (e.g., "sqlserver_2022,sqlserver_2019").
    """
    filter_str = os.getenv("SQLSERVER_ACTIVE_SCENARIOS") or os.getenv("TESTSUITE_ACTIVE_SCENARIOS")
    if not filter_str:
        return

    allowed = set(s.strip() for s in filter_str.split(',') if s.strip())
    if not allowed:
        return

    to_remove = [name for name in SCENARIO_MAP if name not in allowed]
    for name in to_remove:
        del SCENARIO_MAP[name]

    if to_remove:
        print(f"Filtered scenarios: kept {list(SCENARIO_MAP.keys())}, "
              f"removed {to_remove} (--scenarios={filter_str})")


def _register_default_scenarios():
    _load_scenarios_from_config()


_register_default_scenarios()
