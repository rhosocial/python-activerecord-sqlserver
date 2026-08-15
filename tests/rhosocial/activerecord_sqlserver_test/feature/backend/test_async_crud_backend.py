# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_async_crud_backend.py
"""
SQL Server async CRUD backend tests.

This module tests async CRUD operations for SQL Server backend.
"""
from datetime import datetime
import pytest
import pytest_asyncio
from decimal import Decimal


@pytest_asyncio.fixture
async def setup_test_table(async_sqlserver_backend_single):
    """Create a test table."""
    await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_async_crud_table")
    await async_sqlserver_backend_single.execute("""
        CREATE TABLE test_async_crud_table (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255),
            age INT,
            balance DECIMAL(10, 2),
            created_at DATETIME DEFAULT GETDATE()
        )
    """)
    yield
    await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_async_crud_table")


@pytest.mark.asyncio
async def test_async_insert_success(async_sqlserver_backend_single, setup_test_table):
    """Test successful async insertion."""
    sql = "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)"
    params = ("test", 20, Decimal("100.00"))
    result = await async_sqlserver_backend_single.execute(sql, params)
    assert result.affected_rows == 1


@pytest.mark.asyncio
async def test_async_insert_with_invalid_data(async_sqlserver_backend_single, setup_test_table):
    """Test async inserting invalid data."""
    with pytest.raises(Exception):
        sql = "INSERT INTO test_async_crud_table (invalid_column) VALUES (?)"
        params = ("value",)
        await async_sqlserver_backend_single.execute(sql, params)


@pytest.mark.asyncio
async def test_async_fetch_one(async_sqlserver_backend_single, setup_test_table):
    """Test async querying a single record."""
    sql = "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)"
    params = ("test", 20, Decimal("100.00"))
    await async_sqlserver_backend_single.execute(sql, params)
    
    row = await async_sqlserver_backend_single.fetch_one(
        "SELECT * FROM test_async_crud_table WHERE name = ?", ("test",)
    )
    assert row is not None
    assert row["name"] == "test"
    assert row["age"] == 20


@pytest.mark.asyncio
async def test_async_fetch_all(async_sqlserver_backend_single, setup_test_table):
    """Test async querying multiple records."""
    sql = "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)"
    params1 = ("test1", 20, Decimal("100.00"))
    params2 = ("test2", 30, Decimal("200.00"))
    await async_sqlserver_backend_single.execute(sql, params1)
    await async_sqlserver_backend_single.execute(sql, params2)
    
    rows = await async_sqlserver_backend_single.fetch_all(
        "SELECT * FROM test_async_crud_table ORDER BY age"
    )
    assert len(rows) == 2
    assert rows[0]["age"] == 20
    assert rows[1]["age"] == 30


@pytest.mark.asyncio
async def test_async_update(async_sqlserver_backend_single, setup_test_table):
    """Test async updating a record."""
    sql = "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)"
    params = ("test", 20, Decimal("100.00"))
    await async_sqlserver_backend_single.execute(sql, params)

    sql = "UPDATE test_async_crud_table SET age = ? WHERE name = ?"
    params = (21, "test")
    result = await async_sqlserver_backend_single.execute(sql, params)
    assert result.affected_rows == 1

    row = await async_sqlserver_backend_single.fetch_one(
        "SELECT * FROM test_async_crud_table WHERE name = ?", ("test",)
    )
    assert row["age"] == 21


@pytest.mark.asyncio
async def test_async_delete(async_sqlserver_backend_single, setup_test_table):
    """Test async deleting a record."""
    sql = "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)"
    params = ("test", 20, Decimal("100.00"))
    await async_sqlserver_backend_single.execute(sql, params)

    sql = "DELETE FROM test_async_crud_table WHERE name = ?"
    params = ("test",)
    result = await async_sqlserver_backend_single.execute(sql, params)
    assert result.affected_rows == 1

    row = await async_sqlserver_backend_single.fetch_one(
        "SELECT * FROM test_async_crud_table WHERE name = ?", ("test",)
    )
    assert row is None


@pytest.mark.asyncio
async def test_async_transaction_commit(async_sqlserver_backend_single, setup_test_table):
    """Test async transaction commit."""
    tx_manager = async_sqlserver_backend_single.transaction_manager

    await tx_manager.begin()

    await async_sqlserver_backend_single.execute(
        "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)",
        ("tx_test", 25, Decimal("500.00"))
    )

    await tx_manager.commit()

    rows = await async_sqlserver_backend_single.fetch_all(
        "SELECT name FROM test_async_crud_table"
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "tx_test"


@pytest.mark.asyncio
async def test_async_transaction_rollback(async_sqlserver_backend_single, setup_test_table):
    """Test async transaction rollback."""
    tx_manager = async_sqlserver_backend_single.transaction_manager

    await tx_manager.begin()

    await async_sqlserver_backend_single.execute(
        "INSERT INTO test_async_crud_table (name, age, balance) VALUES (?, ?, ?)",
        ("tx_test", 25, Decimal("500.00"))
    )

    await tx_manager.rollback()

    rows = await async_sqlserver_backend_single.fetch_all(
        "SELECT name FROM test_async_crud_table"
    )
    assert len(rows) == 0