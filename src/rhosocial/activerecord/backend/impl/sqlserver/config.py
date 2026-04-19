# src/rhosocial/activerecord/backend/impl/sqlserver/config.py
"""
SQL Server connection configuration.

This module provides configuration classes for SQL Server database connections,
supporting both Windows Authentication and SQL Server Authentication.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class SQLServerConnectionConfig(BaseModel):
    """SQL Server connection configuration.
    
    Supports connection via ODBC driver with full configuration options
    for various authentication modes and connection settings.
    
    Attributes:
        host: Database server hostname or IP address
        port: Database server port (default: 1433)
        database: Database name
        username: Username for SQL Server Authentication
        password: Password for SQL Server Authentication
        trusted_connection: Use Windows Authentication
        driver: ODBC driver name
        encrypt: Encrypt connection (recommended for production)
        trust_server_certificate: Trust server certificate
        timeout: Connection timeout in seconds
        query_timeout: Query timeout in seconds (0 = no limit)
        autocommit: Auto-commit mode
        charset: Character encoding
        pool_size: Connection pool size (ODBC)
        pool_timeout: Pool timeout in seconds
        options: Additional ODBC options
    
    Example:
        # Windows Authentication
        config = SQLServerConnectionConfig(
            host="localhost",
            database="mydb",
            trusted_connection=True
        )
        
        # SQL Authentication
        config = SQLServerConnectionConfig(
            host="localhost",
            database="mydb",
            username="sa",
            password="password123"
        )
        
        # Get connection string
        conn_str = config.build_connection_string()
    """
    
    host: str = Field(default="localhost", description="Database server hostname")
    port: int = Field(default=1433, ge=1, le=65535, description="Database server port")
    database: str = Field(..., description="Database name")
    
    username: Optional[str] = Field(default=None, description="Username for SQL Authentication")
    password: Optional[str] = Field(default=None, description="Password for SQL Authentication")
    
    trusted_connection: bool = Field(default=False, description="Use Windows Authentication")
    
    driver: str = Field(
        default="ODBC Driver 17 for SQL Server",
        description="ODBC driver name"
    )
    
    encrypt: bool = Field(default=True, description="Encrypt connection")
    trust_server_certificate: bool = Field(
        default=False,
        description="Trust server certificate (use only for development)"
    )
    
    timeout: int = Field(default=30, ge=0, description="Connection timeout in seconds")
    query_timeout: int = Field(default=0, ge=0, description="Query timeout (0 = no limit)")
    
    autocommit: bool = Field(default=True, description="Auto-commit mode")
    
    charset: str = Field(default="UTF-8", description="Character encoding")
    
    pool_size: int = Field(default=5, ge=1, description="Connection pool size")
    pool_timeout: int = Field(default=30, ge=1, description="Pool timeout in seconds")
    
    options: Dict[str, Any] = Field(default_factory=dict, description="Additional ODBC options")
    
    model_config = {"extra": "allow"}
    
    @field_validator("driver")
    @classmethod
    def validate_driver(cls, v: str) -> str:
        """Validate ODBC driver name."""
        return v

    def build_connection_string(self) -> str:
        """Build ODBC connection string from configuration.
        
        Constructs an ODBC connection string suitable for use with pyodbc.
        
        Returns:
            ODBC connection string
        
        Example:
            >>> config = SQLServerConnectionConfig(
            ...     host="localhost",
            ...     database="mydb",
            ...     trusted_connection=True
            ... )
            >>> config.build_connection_string()
            "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=mydb;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
        """
        parts = []
        
        parts.append(f"DRIVER={{{self.driver}}}")
        
        if self.host.lower().startswith("(localdb)"):
            parts.append(f"SERVER={self.host}")
        else:
            parts.append(f"SERVER={self.host},{self.port}")
        
        parts.append(f"DATABASE={self.database}")
        
        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if self.username:
                parts.append(f"UID={self.username}")
            if self.password:
                parts.append(f"PWD={self.password}")
        
        legacy_drivers = ["SQL Server", "SQL Server Native Client 11.0"]
        if self.driver not in legacy_drivers:
            parts.append(f"Encrypt={'yes' if self.encrypt else 'no'}")
            parts.append(f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'}")

        parts.append(f"Connection Timeout={self.timeout}")
        
        if self.charset and self.charset.upper() != "UTF-8":
            parts.append(f"CharacterSet={self.charset}")
        
        for key, value in self.options.items():
            if value is not None:
                parts.append(f"{key}={value}")
        
        return ";".join(parts)
    
    def validate_config(self) -> None:
        """Validate configuration for common issues.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.trusted_connection:
            if not self.username or not self.password:
                raise ValueError(
                    "Either trusted_connection must be True, "
                    "or both username and password must be provided"
                )
        
        if self.encrypt and self.trust_server_certificate:
            import warnings
            warnings.warn(
                "trust_server_certificate=True with encrypt=True is not recommended "
                "for production environments. It disables certificate validation.",
                UserWarning,
                stacklevel=2
            )
    
    def __repr__(self) -> str:
        """Return safe string representation (password masked)."""
        safe_dict = self.model_dump()
        if safe_dict.get("password"):
            safe_dict["password"] = "***MASKED***"
        return f"SQLServerConnectionConfig({safe_dict})"
