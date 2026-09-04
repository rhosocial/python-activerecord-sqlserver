# tests/rhosocial/activerecord_sqlserver_test/feature/backend/backend/test_backend.py
"""
SQL Server backend tests using real database connection.

This module tests SQL Server backend functionality with real database.
Each test has sync and async versions for complete coverage.
"""
import pytest
import pytest_asyncio


class TestSQLServerBackend:
    """Synchronous tests for SQL Server backend."""

    def test_connection(self, sqlserver_backend_single):
        """Test basic connection to SQL Server."""
        # Backend is connected when fixture is created
        result = sqlserver_backend_single.execute("SELECT 1 AS value")
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["value"] == 1

    def test_execute_simple_query(self, sqlserver_backend_single):
        """Test executing a simple query."""
        result = sqlserver_backend_single.execute("SELECT @@VERSION AS version")
        assert result.data is not None
        assert len(result.data) == 1
        assert "version" in result.data[0]

    def test_execute_with_parameters(self, sqlserver_backend_single):
        """Test executing query with parameters."""
        result = sqlserver_backend_single.execute(
            "SELECT ? AS param1, ? AS param2",
            (1, "test"),
        )
        assert result.data is not None
        assert result.data[0]["param1"] == 1
        assert result.data[0]["param2"] == "test"

    def test_create_and_drop_table(self, sqlserver_backend_single):
        """Test creating and dropping a table."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

        sqlserver_backend_single.execute(
            "CREATE TABLE test_backend_table (id INT PRIMARY KEY, name NVARCHAR(100))",
            options=ddl_options,
        )

        result = sqlserver_backend_single.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
            ("test_backend_table",),
        )
        assert result.data is not None
        assert len(result.data) == 1

        sqlserver_backend_single.execute(
            "DROP TABLE test_backend_table",
            options=ddl_options,
        )

    def test_insert_and_select(self, sqlserver_backend_single):
        """Test inserting and selecting data."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

        sqlserver_backend_single.execute(
            "CREATE TABLE test_insert_table (id INT PRIMARY KEY, name NVARCHAR(100))",
            options=ddl_options,
        )

        try:
            sqlserver_backend_single.execute(
                "INSERT INTO test_insert_table (id, name) VALUES (?, ?)",
                (1, "Alice"),
            )

            result = sqlserver_backend_single.execute(
                "SELECT * FROM test_insert_table WHERE id = ?",
                (1,),
            )
            assert result.data is not None
            assert len(result.data) == 1
            assert result.data[0]["name"] == "Alice"
        finally:
            sqlserver_backend_single.execute(
                "DROP TABLE test_insert_table",
                options=ddl_options,
            )

    def test_transaction_commit(self, sqlserver_backend_single):
        """Test transaction commit."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

        sqlserver_backend_single.execute(
            "CREATE TABLE test_trans_table (id INT PRIMARY KEY, value INT)",
            options=ddl_options,
        )

        try:
            with sqlserver_backend_single.transaction():
                sqlserver_backend_single.execute(
                    "INSERT INTO test_trans_table (id, value) VALUES (?, ?)",
                    (1, 100),
                )

            result = sqlserver_backend_single.execute(
                "SELECT * FROM test_trans_table WHERE id = ?",
                (1,),
            )
            assert result.data is not None
            assert result.data[0]["value"] == 100
        finally:
            sqlserver_backend_single.execute(
                "DROP TABLE test_trans_table",
                options=ddl_options,
            )

    def test_transaction_rollback(self, sqlserver_backend_single):
        """Test transaction rollback."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

        sqlserver_backend_single.execute(
            "CREATE TABLE test_rollback_table (id INT PRIMARY KEY, value INT)",
            options=ddl_options,
        )

        try:
            try:
                with sqlserver_backend_single.transaction():
                    sqlserver_backend_single.execute(
                        "INSERT INTO test_rollback_table (id, value) VALUES (?, ?)",
                        (1, 100),
                    )
                    raise Exception("Intentional error for rollback test")
            except Exception:
                pass

            result = sqlserver_backend_single.execute(
                "SELECT COUNT(*) AS cnt FROM test_rollback_table",
            )
            assert result.data[0]["cnt"] == 0
        finally:
            sqlserver_backend_single.execute(
                "DROP TABLE test_rollback_table",
                options=ddl_options,
            )

    def test_dialect_property(self, sqlserver_backend_single):
        """Test that backend has correct dialect."""
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        assert isinstance(sqlserver_backend_single.dialect, SQLServerDialect)


class TestAsyncSQLServerBackend:
    """Asynchronous tests for SQL Server backend."""

    @pytest.mark.asyncio
    async def test_async_connection(self, async_sqlserver_backend_single):
        """Test basic async connection to SQL Server."""
        result = await async_sqlserver_backend_single.execute("SELECT 1 AS value")
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["value"] == 1

    @pytest.mark.asyncio
    async def test_async_execute_with_parameters(self, async_sqlserver_backend_single):
        """Test async executing query with parameters."""
        result = await async_sqlserver_backend_single.execute(
            "SELECT ? AS param1, ? AS param2",
            (1, "test"),
        )
        assert result.data is not None
        assert result.data[0]["param1"] == 1
        assert result.data[0]["param2"] == "test"

    @pytest.mark.asyncio
    async def test_async_transaction_commit(self, async_sqlserver_backend_single):
        """Test async transaction commit."""
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

        await async_sqlserver_backend_single.execute(
            "CREATE TABLE test_async_trans_table (id INT PRIMARY KEY, value INT)",
            options=ddl_options,
        )

        try:
            # Use transaction manager directly
            tx_manager = async_sqlserver_backend_single.transaction_manager
            await tx_manager.begin()
            await async_sqlserver_backend_single.execute(
                "INSERT INTO test_async_trans_table (id, value) VALUES (?, ?)",
                (1, 100),
            )
            await tx_manager.commit()

            result = await async_sqlserver_backend_single.execute(
                "SELECT * FROM test_async_trans_table WHERE id = ?",
                (1,),
            )
            assert result.data is not None
            assert result.data[0]["value"] == 100
        finally:
            await async_sqlserver_backend_single.execute(
                "DROP TABLE test_async_trans_table",
                options=ddl_options,
            )

    @pytest.mark.asyncio
    async def test_async_dialect_property(self, async_sqlserver_backend_single):
        """Test that async backend has correct dialect."""
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        assert isinstance(async_sqlserver_backend_single.dialect, SQLServerDialect)
