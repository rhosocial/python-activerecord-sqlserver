# src/rhosocial/activerecord/backend/impl/sqlserver/examples/connection/quickstart.py
"""SQL Server connection quickstart examples.

This module demonstrates various ways to connect to SQL Server
using the rhosocial-activerecord backend.
"""

import os
import yaml
from pathlib import Path

from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)


def get_test_config(scenario: str = "sqlserver_2022"):
    """Load test configuration from yaml file.
    
    Args:
        scenario: Configuration scenario name
    
    Returns:
        Dict with connection parameters
    """
    config_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / "tests" / "config" / "sqlserver_scenarios.yaml"
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            return config_data.get('scenarios', {}).get(scenario, {})
    
    return {}


def example_sql_authentication():
    """Example: Connect using SQL Server Authentication.
    
    This is the most common authentication method for SQL Server,
    using username and password.
    """
    config = get_test_config("sqlserver_2022")
    
    backend = SQLServerBackend(
        connection_config=SQLServerConnectionConfig(
            host=config.get('host', 'localhost'),
            port=config.get('port', 1433),
            database=config.get('database', 'test_db'),
            username=config.get('username', 'sa'),
            password=config.get('password', ''),
            driver=config.get('driver', 'ODBC Driver 17 for SQL Server'),
            encrypt=config.get('encrypt', False),
            trust_server_certificate=config.get('trust_server_certificate', True),
        )
    )
    
    backend.connect()
    print(f"Connected: {backend.ping()}")
    print(f"Version: {backend.get_server_version()}")
    backend.disconnect()
    
    return backend


def example_windows_authentication():
    """Example: Connect using Windows Authentication.
    
    Windows Authentication uses the current Windows credentials
    and doesn't require a username/password.
    """
    backend = SQLServerBackend(
        connection_config=SQLServerConnectionConfig(
            host="localhost",
            port=1433,
            database="test_db",
            trusted_connection=True,
        )
    )
    
    backend.connect()
    print(f"Connected: {backend.ping()}")
    backend.disconnect()
    
    return backend


def example_azure_sql():
    """Example: Connect to Azure SQL Database.
    
    Azure SQL Database requires encryption and proper authentication.
    """
    backend = SQLServerBackend(
        connection_config=SQLServerConnectionConfig(
            host="myserver.database.windows.net",
            port=1433,
            database="mydb",
            username="admin@myserver",
            password="password",
            encrypt=True,
            trust_server_certificate=False,
        )
    )
    
    return backend


def example_simple_connection():
    """Example: Simple connection with minimal configuration.
    
    Uses default values for most parameters.
    """
    config = get_test_config("sqlserver_2022")
    
    backend = SQLServerBackend(
        host=config.get('host', 'localhost'),
        port=config.get('port', 1433),
        database=config.get('database', 'test_db'),
        username=config.get('username', 'sa'),
        password=config.get('password', ''),
    )
    
    backend.connect()
    
    result = backend.execute("SELECT @@VERSION AS version")
    if result.data:
        print(f"Server version: {result.data[0]['version']}")
    
    backend.disconnect()
    
    return backend


def example_connection_with_options():
    """Example: Connection with additional ODBC options.
    
    Demonstrates how to pass additional connection options.
    """
    config = get_test_config("sqlserver_2022")
    
    backend = SQLServerBackend(
        connection_config=SQLServerConnectionConfig(
            host=config.get('host', 'localhost'),
            port=config.get('port', 1433),
            database=config.get('database', 'test_db'),
            username=config.get('username', 'sa'),
            password=config.get('password', ''),
            timeout=30,
            autocommit=True,
            options={
                'MARS_Connection': 'yes',
                'APP': 'MyApp',
            }
        )
    )
    
    return backend


def main():
    """Run all connection examples."""
    print("=" * 60)
    print("SQL Server Connection Examples")
    print("=" * 60)
    
    print("\n1. SQL Server Authentication:")
    try:
        example_sql_authentication()
        print("   Success!")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Simple Connection:")
    try:
        example_simple_connection()
        print("   Success!")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\nConnection examples completed.")


if __name__ == "__main__":
    main()
