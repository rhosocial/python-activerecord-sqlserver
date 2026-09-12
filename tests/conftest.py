# tests/conftest.py
"""Root conftest for SQL Server backend tests."""
import os
import time

import pytest
import yaml

os.environ.setdefault(
    'TESTSUITE_PROVIDER_REGISTRY',
    'providers.registry:provider_registry'
)


def _load_scenario_map():
    """Load scenario configs from the environment or the default file."""
    config_path = os.getenv("SQLSERVER_SCENARIOS_CONFIG_PATH")
    if config_path and not os.path.exists(config_path):
        print(f"Warning: scenario file not found: {config_path}")
        return {}
    if not config_path:
        config_path = os.path.join(os.path.dirname(__file__), "config", "sqlserver_scenarios.yaml")
        if not os.path.exists(config_path):
            return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception:
        return {}
    return data.get("scenarios", {}) or {}


@pytest.fixture(scope="session", autouse=True)
def _prepare_read_committed_snapshot():
    """Verify READ_COMMITTED_SNAPSHOT is enabled on every scenario database.

    The actual ALTER DATABASE is performed by the CI workflow step
    'Enable READ_COMMITTED_SNAPSHOT' *before* pytest runs, so there is
    no risk of xdist workers deadlocking on the exclusive database lock.

    This fixture only checks and warns if the option is not yet on
    (e.g. when running locally without the workflow).
    """
    from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
    from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

    scenarios = _load_scenario_map()
    if not scenarios:
        return

    for _scenario_name, config in scenarios.items():
        if not config:
            continue
        db_name = config.get("database")
        if not db_name:
            continue
        try:
            backend = SQLServerBackend(connection_config=SQLServerConnectionConfig(**config))
            backend.connect()
        except Exception:
            continue
        try:
            cursor = backend._connection.cursor()
            cursor.execute(
                "SELECT is_read_committed_snapshot_on FROM sys.databases WHERE name = ?",
                (db_name,),
            )
            row = cursor.fetchone()
            is_on = row[0] if row and isinstance(row, (list, tuple)) else (
                getattr(row, "is_read_committed_snapshot_on", False) if row else False
            )
            cursor.close()
            if not is_on:
                # Not yet enabled — try to enable (single-process / local run).
                # With xdist, only the first worker to acquire the lock succeeds;
                # others will get a timeout and we silently continue.
                for _attempt in range(2):
                    try:
                        backend.execute("SET LOCK_TIMEOUT 3000")
                        backend.execute(
                            f"ALTER DATABASE [{db_name}] SET READ_COMMITTED_SNAPSHOT ON"
                        )
                        break
                    except Exception:
                        time.sleep(0.5)
        except Exception:
            pass
        finally:
            try:
                backend.disconnect()
            except Exception:
                pass


def pytest_configure(config):
    """Configure custom markers for SQL Server tests."""
    config.addinivalue_line(
        "markers", "requires_sqlserver: mark test as requiring SQL Server connection"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_protocol: Mark tests that require specific database protocol support"
    )
    config.addinivalue_line(
        "markers", "requires_functions: Mark tests that require specific database functions"
    )
    config.addinivalue_line(
        "markers", "requires_inner_join: Mark test as requiring INNER JOIN support"
    )