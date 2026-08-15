# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_ddl_features.py
"""
SQL Server DDL features tests.

This module tests SQL Server-specific DDL features:
- SELECT INTO (alternative to CREATE TABLE LIKE)
- Temporary tables
- Schema operations
"""
import pytest
import pytest_asyncio
from decimal import Decimal


class TestSQLServerDDLFeatures:
    """Tests for SQL Server DDL features."""

    @pytest.fixture
    def source_table(self, sqlserver_backend_single):
        """Create a source table."""
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_source_table")
        sqlserver_backend_single.execute("""
            CREATE TABLE test_source_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                age INT,
                balance DECIMAL(10, 2)
            )
        """)

        sqlserver_backend_single.execute(
            "INSERT INTO test_source_table (name, age, balance) VALUES (?, ?, ?)",
            ("TestUser", 25, Decimal("100.00"))
        )

        yield "test_source_table"
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_source_table")

    def test_select_into_copy(self, sqlserver_backend_single, source_table):
        """Test SELECT INTO creates a copy of table structure."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_copy_table")

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
        result = sqlserver_backend_single.execute(
            "SELECT id, name, age, balance INTO test_copy_table FROM test_source_table WHERE 1=0",
            options=ddl_options
        )

        assert result.data is None

        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_copy_table")

    def test_select_into_with_data(self, sqlserver_backend_single, source_table):
        """Test SELECT INTO creates copy with data."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_copy_table")

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
        sqlserver_backend_single.execute(
            "SELECT * INTO test_copy_table FROM test_source_table",
            options=ddl_options
        )

        rows = sqlserver_backend_single.fetch_all("SELECT * FROM test_copy_table")
        assert len(rows) == 1

        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_copy_table")

    def test_temporary_table(self, sqlserver_backend_single, source_table):
        """Test local temporary table."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
        sqlserver_backend_single.execute(
            "SELECT * INTO #temp_local_table FROM test_source_table",
            options=ddl_options
        )

        rows = sqlserver_backend_single.fetch_all(
            "SELECT * FROM #temp_local_table"
        )
        assert len(rows) == 1

        sqlserver_backend_single.execute("DROP TABLE IF EXISTS #temp_local_table")

    def test_global_temporary_table(self, sqlserver_backend_single, source_table):
        """Test global temporary table."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
        sqlserver_backend_single.execute(
            "SELECT * INTO ##temp_global_table FROM test_source_table",
            options=ddl_options
        )

        rows = sqlserver_backend_single.fetch_all(
            "SELECT * FROM ##temp_global_table"
        )
        assert len(rows) == 1

        sqlserver_backend_single.execute("DROP TABLE IF EXISTS ##temp_global_table")


class TestAsyncDDLFeatures:
    """Tests for SQL Server async DDL features."""

    @pytest_asyncio.fixture
    async def async_source_table(self, async_sqlserver_backend_single):
        """Create a source table."""
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_source_table")
        await async_sqlserver_backend_single.execute("""
            CREATE TABLE test_source_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                age INT,
                balance DECIMAL(10, 2)
            )
        """)

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_source_table (name, age, balance) VALUES (?, ?, ?)",
            ("TestUser", 25, Decimal("100.00"))
        )

        yield "test_source_table"
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_source_table")

    @pytest.mark.asyncio
    async def test_async_select_into(self, async_sqlserver_backend_single, async_source_table):
        """Test async SELECT INTO."""
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_async_copy")

        await async_sqlserver_backend_single.execute(
            "SELECT * INTO test_async_copy FROM test_source_table"
        )

        rows = await async_sqlserver_backend_single.fetch_all(
            "SELECT * FROM test_async_copy"
        )
        assert len(rows) == 1

        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_async_copy")