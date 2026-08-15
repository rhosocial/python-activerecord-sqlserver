# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_config.py
"""Tests for SQL Server connection configuration."""
import os
import pytest
from unittest.mock import patch
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig


class TestSQLServerConnectionConfig:
    """Test cases for SQL Server connection configuration."""

    def test_basic_config(self):
        """Test basic configuration creation."""
        config = SQLServerConnectionConfig(
            host="localhost",
            port=1433,
            database="test_db",
            username="sa",
            password="Password123!",
        )
        assert config.host == "localhost"
        assert config.port == 1433
        assert config.database == "test_db"
        assert config.username == "sa"
        assert config.password == "Password123!"

    def test_build_connection_string(self):
        """Test connection string building."""
        config = SQLServerConnectionConfig(
            host="localhost",
            port=1433,
            database="test_db",
            username="sa",
            password="Password123!",
            driver="ODBC Driver 17 for SQL Server",
        )
        conn_str = config.build_connection_string()
        assert "DRIVER={ODBC Driver 17 for SQL Server}" in conn_str
        assert "SERVER=localhost,1433" in conn_str
        assert "DATABASE=test_db" in conn_str
        assert "UID=sa" in conn_str
        assert "PWD=Password123!" in conn_str

    def test_build_connection_string_legacy_driver(self):
        """Test connection string with legacy SQL Server driver."""
        config = SQLServerConnectionConfig(
            host="localhost",
            port=1433,
            database="test_db",
            username="sa",
            password="Password123!",
            driver="SQL Server",
        )
        conn_str = config.build_connection_string()
        assert "DRIVER={SQL Server}" in conn_str
        assert "Encrypt=" not in conn_str

    def test_trusted_connection(self):
        """Test Windows Authentication configuration."""
        config = SQLServerConnectionConfig(
            host="localhost",
            database="test_db",
            trusted_connection=True,
        )
        conn_str = config.build_connection_string()
        assert "Trusted_Connection=yes" in conn_str

    def test_encrypt_options(self):
        """Test encryption options."""
        config = SQLServerConnectionConfig(
            host="localhost",
            port=1433,
            database="test_db",
            username="sa",
            password="Password123!",
            encrypt=True,
            trust_server_certificate=True,
        )
        conn_str = config.build_connection_string()
        assert "Encrypt=yes" in conn_str
        assert "TrustServerCertificate=yes" in conn_str

    def test_config_validation_no_auth(self):
        """Test that validation fails without authentication."""
        config = SQLServerConnectionConfig(
            host="localhost",
            database="test_db",
        )
        with pytest.raises(ValueError, match="trusted_connection|username and password"):
            config.validate_config()

    def test_repr_masks_password(self):
        """Test that password is masked in repr."""
        config = SQLServerConnectionConfig(
            host="localhost",
            database="test_db",
            username="sa",
            password="secret123",
        )
        repr_str = repr(config)
        assert "secret123" not in repr_str
        assert "***MASKED***" in repr_str

    @patch.dict(
        os.environ,
        {
            "SQLSERVER_HOST": "env-host",
            "SQLSERVER_PORT": "1434",
            "SQLSERVER_DATABASE": "env_db",
            "SQLSERVER_USERNAME": "env_user",
            "SQLSERVER_PASSWORD": "env_pass",
        },
    )
    def test_from_env(self):
        """Test creating config from environment variables."""
        config = SQLServerConnectionConfig(
            host=os.environ.get("SQLSERVER_HOST", "localhost"),
            port=int(os.environ.get("SQLSERVER_PORT", "1433")),
            database=os.environ.get("SQLSERVER_DATABASE", "test_db"),
            username=os.environ.get("SQLSERVER_USERNAME"),
            password=os.environ.get("SQLSERVER_PASSWORD"),
        )
        assert config.host == "env-host"
        assert config.port == 1434
        assert config.database == "env_db"
        assert config.username == "env_user"
        assert config.password == "env_pass"
